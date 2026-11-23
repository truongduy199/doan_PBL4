"""Gate & Device Orchestration Service (Section V, VI, VII.1 & VIII.2).

Coordinates:
- Single recognition queue shared between Gate IN and Gate OUT (`T10`).
- Holding new Gate IN entry requests while a prior vehicle is still `Parking_pending` (Section V.1).
- Receiving fresh JPEG frames from the two ESP32-S3 OV5640 cameras via `POST /api/device/images`
  (validating `event_id`, `camera_id`, `frame_id`, `gate_id`, `roi`, image decoding, freshness, and deduplication).
- Calling `PlatePipeline` + `FacePipeline` + `FaceVerifier` outside DB transactions.
- Calling `GateDataService` short transactions and publishing MQTT barrier commands after commit.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import base64
import re
import logging
import threading
import time
import uuid
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

from smart_parking.ai.face.pipeline import FacePipeline, FacePipelineResult
from smart_parking.ai.face.verifier import FaceVerifier
from smart_parking.ai.plate.pipeline import PlatePipeline, PlateRecognitionOutcome
from smart_parking.application.services.gate_data_service import GateDataService
from smart_parking.application.services.slot_service import SlotService
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.enums import GateId, LivenessStatus
from smart_parking.domain.exceptions import (
    DomainException,
    ResourceNotFoundException,
    SlotNotAvailableException,
)
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, utc_now

logger = logging.getLogger(__name__)

# Standard MQTT topics per Section VIII.2
TOPIC_GATE_IN_DETECTED = "parking/gates/IN/detected"
TOPIC_GATE_OUT_DETECTED = "parking/gates/OUT/detected"
TOPIC_SLOTS_SNAPSHOT = "parking/slots/snapshot"
TOPIC_CAM_PLATE_CAPTURE = "parking/cameras/plate/capture"
TOPIC_CAM_FACE_CAPTURE = "parking/cameras/face/capture"
TOPIC_GATE_IN_COMMAND = "parking/gates/IN/command"
TOPIC_GATE_OUT_COMMAND = "parking/gates/OUT/command"


@dataclass
class GateTurnContext:
    event_id: str
    gate_id: str
    device_id: str
    boot_id: str
    sequence: int
    roi: str
    created_at: datetime
    plate_frames: List[np.ndarray] = field(default_factory=list)
    face_frames: List[np.ndarray] = field(default_factory=list)
    received_frame_keys: set[str] = field(default_factory=set)
    evaluated: bool = False
    last_decision: Optional[Dict[str, Any]] = None
    state: str = "QUEUED"
    capture_started_at: Optional[datetime] = None
    plate_outcome: Optional[PlateRecognitionOutcome] = None
    face_result: Optional[FacePipelineResult] = None
    requested_samples: int = 1
    capture_deadlines: Dict[str, datetime] = field(default_factory=dict)
    capture_round: int = 0
    retry_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class GateWorkflowService:
    """
    Central coordinator connecting ESP32-S3 HTTP/MQTT events, AI pipelines,
    and the MySQL transactional `GateDataService`.
    """

    def __init__(
        self,
        gate_data_service: GateDataService,
        slot_service: Optional[SlotService] = None,
        plate_pipeline: Optional[PlatePipeline] = None,
        face_pipeline: Optional[FacePipeline] = None,
        face_verifier: Optional[FaceVerifier] = None,
        mqtt_publish_fn: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.gate_data_service = gate_data_service
        self.slot_service = slot_service
        self.settings = settings or get_settings()
        self.plate_pipeline = plate_pipeline or PlatePipeline(lazy_init=True)
        self.face_pipeline = face_pipeline or FacePipeline()
        self.face_verifier = face_verifier or FaceVerifier(t_accept=self.settings.face_t_accept, t_reject=self.settings.face_t_reject)
        self._mqtt_publish_fn = mqtt_publish_fn

        self._lock = threading.RLock()
        self._inference_lock = threading.Lock()
        self._gate_inference_waiters = 0
        self._face_guidance = None
        self._guidance_frame_key = None
        self._guidance_last_started = None
        self._guidance_interval_seconds = .5
        self._turns: Dict[str, GateTurnContext] = {}
        self._queue: Deque[str] = deque()
        self._active_event_id: Optional[str] = None
        self._device_status: Dict[str, Dict[str, Any]] = {}
        self._command_acks = deque(maxlen=100)
        self.published_mqtt_messages = deque(maxlen=200)
        self._commands: Dict[str, Dict[str, Any]] = {}
        self.ai_status = "NOT_INITIALIZED"
        self._message_sequences: Dict[tuple, int] = {}
        self._device_boots: Dict[str, str] = {}
        self._retired_boots = deque(maxlen=100)
        self._last_display_update: Optional[datetime] = None
        self._camera_images: Dict[str, Dict[str, Any]] = {}
        self._preview_capture: Optional[Dict[str, Any]] = None
        self._camera_stream: Optional[Dict[str, Any]] = None

    def _send_camera_stream_control(self, action: str, session: Dict[str, Any]) -> None:
        for camera in ("plate", "face"):
            self._publish_mqtt(f"parking/cameras/{camera}/stream", {
                "action": action, "event_id": session["event_id"], "stream_id": session["stream_id"],
                "gate_id": session["gate_id"], "roi": session["roi"],
                "expires_at_ms": int(session["expires_at"].timestamp() * 1000)})

    def _stop_camera_stream(self) -> None:
        session = self._camera_stream
        self._camera_stream = None
        self._face_guidance = None
        self._guidance_frame_key = None
        if session:
            self._send_camera_stream_control("STOP", session)

    def _start_camera_stream(self, event_id: str, gate_id: str, now: datetime, *, preview: bool = False) -> Dict[str, Any]:
        self._stop_camera_stream()
        self._preview_capture = None
        session = {"event_id": event_id, "stream_id": uuid.uuid4().hex[:20], "gate_id": gate_id,
                   "roi": f"ROI_{gate_id}", "expires_at": now + timedelta(seconds=30),
                   "last_refresh": now, "preview": preview, "sequences": {"cam_plate": 0, "cam_face": 0},
                   "frames_received": {"cam_plate": 0, "cam_face": 0}}
        self._camera_stream = session
        self._send_camera_stream_control("START", session)
        return {"event_id": event_id, "stream_id": session["stream_id"], "status": "STREAM_REQUESTED",
                "expires_at": format_utc_iso(session["expires_at"])}

    def request_camera_stream(self, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
        now = now_utc or utc_now()
        with self._lock:
            self._expire_camera_images(now)
            if self._active_event_id or self._queue or self._camera_stream:
                raise DomainException("Camera đang phục vụ lượt xe hoặc đang phát hình.", reason_code="CAMERA_BUSY", http_status=409)
            return self._start_camera_stream("view-" + uuid.uuid4().hex[:20], "IN", now, preview=True)

    def stop_camera_stream(self) -> Dict[str, Any]:
        with self._lock:
            self._stop_camera_stream()
            return {"status": "STREAM_STOPPED"}

    def ingest_stream_image(self, image_bytes: bytes, event_id: str, camera_id: str, device_id: str,
                            frame_id: str, gate_id: str, roi: str, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
        """Validate live JPEGs for display only; never invoke AI or gate/database services."""
        now = now_utc or utc_now()
        with self._lock:
            self._expire_camera_images(now)
            session = self._camera_stream
            if not session or session["event_id"] != event_id:
                raise DomainException("Luồng hình không còn hoạt động.", reason_code="STREAM_EXPIRED", http_status=409)
            if camera_id not in ("cam_plate", "cam_face"):
                raise DomainException("Invalid stream camera.", reason_code="CAPTURE_METADATA_MISMATCH", http_status=409)
            role = "plate" if camera_id == "cam_plate" else "face"
            expected_device = self.settings.controller_device_id if role == "plate" else self.settings.face_camera_device_id
            match = re.fullmatch(r"live-" + re.escape(session["stream_id"]) + "-" + role + r"-([1-9][0-9]{0,9})", frame_id)
            if device_id != expected_device or gate_id != session["gate_id"] or roi != session["roi"] or not match:
                raise DomainException("Stream metadata mismatch.", reason_code="CAPTURE_METADATA_MISMATCH", http_status=409)
            sequence = int(match.group(1))
            if sequence <= session["sequences"][camera_id]:
                raise DomainException("Frame cũ hoặc trùng.", reason_code="STALE_STREAM_FRAME", http_status=409)
            if len(image_bytes) < 64 or len(image_bytes) > 5 * 1024 * 1024 or not image_bytes.startswith(b"\xff\xd8"):
                raise DomainException("Invalid stream JPEG.", reason_code="INVALID_JPEG_DATA")
            import cv2
            frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None or frame.size == 0:
                raise DomainException("Invalid stream JPEG.", reason_code="INVALID_JPEG_DATA")
            session["sequences"][camera_id] = sequence
            session["frames_received"][camera_id] += 1
            self._remember_camera_image(camera_id, image_bytes, frame, event_id, gate_id, now)
            self._camera_images[camera_id]["stream_id"] = session["stream_id"]
            self._camera_images[camera_id]["frame_sequence"] = sequence
            return {"accepted": True, "stream": True, "camera_id": camera_id, "sequence": sequence}

    def update_face_guidance(self, now_utc: Optional[datetime] = None) -> None:
        """Best-effort, bounded UI feedback; gate inference has priority."""
        now = now_utc or utc_now()
        with self._lock:
            session = self._camera_stream
            image = self._camera_images.get("cam_face")
            if (not session or now >= session["expires_at"] or not image
                    or image.get("stream_id") != session["stream_id"]
                    or (now - image["captured_at"]).total_seconds() > 3
                    or self._gate_inference_waiters):
                return
            if self._guidance_last_started and (now - self._guidance_last_started).total_seconds() < self._guidance_interval_seconds:
                return
            key = (session["stream_id"], image.get("frame_sequence"))
            if key == self._guidance_frame_key or not self._inference_lock.acquire(blocking=False):
                return
            self._guidance_last_started = now
            self._guidance_frame_key = key
            started = time.perf_counter()
            jpeg = image["jpeg"]
            captured_at = image["captured_at"]
            gate = session["gate_id"]
        try:
            import cv2
            frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            result = self.face_pipeline.stream_guidance(frame, roi=self.settings.gate_rois[("face", gate)])
            with self._lock:
                current = self._camera_stream
                if current and current["stream_id"] == key[0] and current["expires_at"] > (now_utc or utc_now()):
                    elapsed = time.perf_counter() - started
                    self._guidance_interval_seconds = max(.5, elapsed * 4)
                    self._face_guidance = {**result, "processing_ms": round(elapsed * 1000, 1),
                                           "stream_id": key[0], "captured_at": captured_at,
                                           "updated_at": now_utc or utc_now()}
        except Exception:
            logger.exception("Live face guidance failed")
        finally:
            self._inference_lock.release()

    def _expire_camera_images(self, now: datetime) -> None:
        for camera, image in list(self._camera_images.items()):
            if now >= image["expires_at"]:
                del self._camera_images[camera]
        if self._preview_capture and now >= self._preview_capture["expires_at"]:
            self._preview_capture = None
        if self._camera_stream and now >= self._camera_stream["expires_at"]:
            self._stop_camera_stream()

    def _remember_camera_image(self, camera: str, image: bytes, frame: np.ndarray,
                               event_id: str, gate_id: str, now: datetime) -> None:
        self._camera_images[camera] = {"jpeg": image, "event_id": event_id, "gate_id": gate_id,
            "captured_at": now, "expires_at": now + timedelta(seconds=30),
            "resolution": [int(frame.shape[1]), int(frame.shape[0])]}

    def validate_stream_upload(self, stream_id: str, event_id: str, camera_id: str,
                               device_id: str, gate_id: str, roi: str) -> None:
        with self._lock:
            self._expire_camera_images(utc_now())
            session = self._camera_stream
            expected = {"cam_plate": self.settings.controller_device_id, "cam_face": self.settings.face_camera_device_id}
            if (not session or stream_id != session["stream_id"] or event_id != session["event_id"]
                    or gate_id != session["gate_id"] or roi != session["roi"]
                    or device_id != expected.get(camera_id)):
                raise DomainException("MJPEG session mismatch or expired.", reason_code="STREAM_EXPIRED", http_status=409)

    def camera_jpeg(self, camera_id: str, stream_id: Optional[str] = None):
        """Return immutable JPEG bytes; never expose mutable session state."""
        with self._lock:
            self._expire_camera_images(utc_now())
            active = bool(self._camera_stream and self._camera_stream["stream_id"] == stream_id)
            image = self._camera_images.get(camera_id)
            if stream_id and (not active or not image or image.get("stream_id") != stream_id):
                return active, None, None
            return active, image.get("captured_at") if image else None, image.get("jpeg") if image else None

    def camera_snapshots(self, now_utc: Optional[datetime] = None, *, include_images: bool = True) -> Dict[str, Any]:
        now = now_utc or utc_now()
        with self._lock:
            self._expire_camera_images(now)
            cameras = []
            for camera in ("cam_plate", "cam_face"):
                image = self._camera_images.get(camera)
                item: Dict[str, Any] = {"camera_id": camera, "image_base64": None, "has_image": bool(image)}
                if image:
                    item.update({k: v for k, v in image.items() if k not in ("jpeg", "captured_at", "expires_at")})
                    item.update(image_base64=base64.b64encode(image["jpeg"]).decode("ascii") if include_images else None,
                                captured_at=format_utc_iso(image["captured_at"]), expires_at=format_utc_iso(image["expires_at"]))
                    turn = self._turns.get(image["event_id"])
                    if turn:
                        item.update(scan_state=turn.state, capture_round=turn.capture_round)
                        recognition: Dict[str, Any] = {}
                        if camera == "cam_plate" and turn.plate_outcome:
                            result = turn.plate_outcome
                            recognition = {"ok": result.ok, "reason_code": result.reason_code,
                                           "message": result.message, "plate_number": result.normalized_plate,
                                           "display_plate": result.display_plate, "raw_text": result.raw_text}
                        elif camera == "cam_face" and turn.face_result:
                            result = turn.face_result
                            recognition = {"ok": result.ok, "reason_code": result.reason_code,
                                           "message": result.message, "quality_score": result.quality_score,
                                           "liveness_status": result.liveness_status, "liveness_score": result.liveness_score,
                                           "valid_sample_count": result.valid_sample_count}
                            decision = turn.last_decision or {}
                            recognition["session_id"] = decision.get("session_id")
                            recognition["template_saved"] = bool(turn.gate_id == "IN" and decision.get("decision") == "Approved" and decision.get("session_id"))
                            recognition["similarity_score"] = decision.get("similarity_score")
                        if recognition:
                            item["recognition"] = recognition
                    if turn and turn.last_decision:
                        item["decision"] = turn.last_decision.get("decision")
                        item["reason_code"] = turn.last_decision.get("reason_code")
                current = self._turns.get((self._camera_stream or {}).get("event_id"))
                if current and current.state in ("RETRY_WAIT", "QUEUED", "CAPTURING", "DECIDING"):
                    item.update(scan_state=current.state, capture_round=current.capture_round,
                                decision="Scanning", reason_code=(current.last_decision or {}).get("reason_code"))
                if camera == "cam_face" and self._camera_stream:
                    turn = self._turns.get(self._camera_stream["event_id"])
                    guidance = self._face_guidance
                    if self._gate_inference_waiters or (turn and turn.state == "DECIDING"):
                        item["guidance"] = {"ok": False, "reason_code": "GATE_PROCESSING", "message": "Đang nhận diện lượt xe. Giữ nguyên vị trí."}
                    elif (guidance and guidance["stream_id"] == self._camera_stream["stream_id"]
                          and (now - guidance["captured_at"]).total_seconds() <= 3):
                        item["guidance"] = {**guidance, "captured_at": format_utc_iso(guidance["captured_at"]),
                                            "updated_at": format_utc_iso(guidance["updated_at"])}
                    else:
                        item["guidance"] = {"ok": False, "reason_code": "WAITING_FRAME", "message": "Đang chờ ảnh mới để hướng dẫn tư thế."}
                cameras.append(item)
            session = self._camera_stream
            return {"cameras": cameras, "server_time": format_utc_iso(now), "retention_seconds": 30,
                    "stream": {"active": bool(session), "event_id": session["event_id"] if session else None,
                               "stream_id": session["stream_id"] if session else None,
                               "expires_at": format_utc_iso(session["expires_at"]) if session else None,
                               "preview": session["preview"] if session else False,
                               "frames_received": dict(session["frames_received"]) if session else {}}}

    def request_camera_preview(self, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
        now = now_utc or utc_now()
        with self._lock:
            self._expire_camera_images(now)
            if self._active_event_id or self._queue or self._camera_stream:
                raise DomainException("Cổng đang xử lý xe; ưu tiên ảnh của lượt hiện tại.", reason_code="CAMERA_BUSY", http_status=409)
            if self._preview_capture and self._preview_capture["remaining"]:
                raise DomainException("Đang chờ ảnh chụp kiểm tra.", reason_code="CAMERA_BUSY", http_status=409)
            event = "preview-" + uuid.uuid4().hex[:20]
            self._preview_capture = {"event_id": event, "expires_at": now + timedelta(seconds=5),
                                     "remaining": {"cam_plate", "cam_face"}}
            for camera in ("plate", "face"):
                self._publish_mqtt(f"parking/cameras/{camera}/capture", {
                    "event_id": event, "gate_id": "IN", "roi": "ROI_IN",
                    "frame_id": f"req-{camera}-{event}", "expires_at_ms": int(now.timestamp() * 1000) + 5000})
            return {"event_id": event, "status": "CAPTURE_REQUESTED", "expires_at": format_utc_iso(now + timedelta(seconds=5))}

    def initialize_ai(self) -> None:
        """Load local assets only; startup must never silently download model weights."""
        from pathlib import Path
        from smart_parking.ai.face.insightface_adapter import InsightFaceAdapter
        root = Path(self.settings.face_model_root)
        if not root.is_absolute():
            root = Path(__file__).resolve().parents[4] / root
        if not list((root / "models" / self.settings.face_model_pack).glob("*.onnx")):
            self.ai_status = "FACE_MODEL_MISSING"
            return
        adapter = InsightFaceAdapter(model_root=root, model_pack=self.settings.face_model_pack,
                                     provider=self.settings.face_provider)
        if adapter.initialize():
            self.face_pipeline = FacePipeline(adapter=adapter)
            try:
                # Warm YOLO/OCR before accepting gate captures; READY covers both AIs.
                self.plate_pipeline._ensure_reader()
            except Exception:
                logger.exception("Local plate models could not be initialized")
                self.ai_status = "PLATE_MODEL_UNAVAILABLE"
                return
            self.ai_status = "READY" if (root / "addons" / "liveness.onnx").is_file() else "LIVENESS_MISSING"
        else:
            self.ai_status = "FACE_MODEL_UNAVAILABLE"

    def set_mqtt_publisher(self, publish_fn: Callable[[str, Dict[str, Any]], None]) -> None:
        self._mqtt_publish_fn = publish_fn

    def _publish_mqtt(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish non-retained JSON message to MQTT broker and record for diagnostics/tests."""
        self.published_mqtt_messages.append((topic, payload))
        if self._mqtt_publish_fn is not None:
            try:
                self._mqtt_publish_fn(topic, payload)
            except Exception as exc:
                logger.error("Failed to publish MQTT topic %s: %s", topic, exc)
                command = self._commands.get(str(payload.get("command_id")))
                if command is not None:
                    command["delivery_status"] = "PUBLISH_FAILED"
                    command["delivery_error"] = type(exc).__name__

    def _has_parking_pending_session(self) -> bool:
        """Section V.1: New Gate IN turns wait if a prior vehicle is still in `Parking_pending`."""
        def _check(tx) -> bool:
            tx.cursor.execute("SELECT COUNT(*) AS n FROM sessions WHERE status = 'Entry_pending' "
                              "OR (status = 'Active' AND parking_status IN "
                              "('Parking_pending', 'Parking_review_required', 'Parking_timeout'))")
            return int(tx.cursor.fetchone()["n"]) > 0

        try:
            return bool(self.gate_data_service.uow.run_transactional(_check))
        except Exception:
            logger.exception("Cannot verify parking state; holding new entry turns")
            return True

    def _count_available_slots(self, now_utc: Optional[datetime] = None) -> int:
        if self.slot_service is None:
            return 0
        try:
            summary = self.slot_service.list_slots_for_role(role="admin", now_utc=now_utc)
            return int(summary.get("available_count", 0))
        except Exception:
            return 0

    def handle_gate_detected(
        self,
        event_id: str,
        gate_id: str,
        device_id: str = "s3_plate_ctrl",
        boot_id: str = "boot-0",
        sequence: int = 1,
        event_type: str = "DETECTED",
        ir_stable_detected: bool = True,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Handle `parking/gates/IN/detected` or `parking/gates/OUT/detected` from S3 controller:
        - If `event_type == 'PASSAGE_CONFIRMED'`: commits physical passage in MySQL and advances queue.
        - If `event_type == 'VEHICLE_LEFT_BEFORE_DECISION'`: cancels pending turn.
        - If `event_type == 'DETECTED'`: enqueues turn in shared recognition queue (`T10`) and requests fresh capture.
        """
        now_dt = now_utc or utc_now()
        clean_gate = (gate_id or "").strip().upper()
        if clean_gate not in (GateId.IN.value, GateId.OUT.value):
            raise DomainException(f"Mã cổng '{gate_id}' không hợp lệ (chỉ nhận IN hoặc OUT).", reason_code="INVALID_GATE_ID")

        if not event_id or len(event_id) > 36 or device_id != self.settings.controller_device_id:
            raise DomainException("Invalid event/device identity.", reason_code="INVALID_DEVICE_EVENT")
        allowed_types = {"DETECTED", "PASSAGE_CONFIRMED", "VEHICLE_LEFT_BEFORE_DECISION",
                         "BACKEND_DECISION_TIMEOUT", "OBSTACLE_DURING_CLOSING"}
        if event_type not in allowed_types:
            raise DomainException("Unsupported device event.", reason_code="INVALID_EVENT_TYPE")
        with self._lock:
            if event_type == "DETECTED":
                self._preview_capture = None  # Real gate events take priority over manual previews.
            existing = self._turns.get(event_id)
            if existing and (existing.gate_id != clean_gate or existing.device_id != device_id or existing.boot_id != boot_id):
                raise DomainException("Event identity mismatch.", reason_code="EVENT_ID_MISMATCH", http_status=409)
            if event_type == "PASSAGE_CONFIRMED":
                persisted = None
                if existing is None:
                    persisted = self.gate_data_service.uow.run_transactional(lambda tx: tx.gate_events.get_by_id(event_id))
                recovered = persisted is not None and persisted.gate_id.value == clean_gate and persisted.device_id == device_id and persisted.decision.value == "Approved" and persisted.session_id
                if not recovered and (existing is None or existing.state not in ("APPROVED", "COMPLETED", "PASSAGE_UNCERTAIN")):
                    raise DomainException("No approved turn for passage.", reason_code="PASSAGE_NOT_APPROVED", http_status=409)
            elif event_type == "OBSTACLE_DURING_CLOSING":
                return {"event_id": event_id, "status": "OBSTACLE_REPORTED"}
            elif event_type == "BACKEND_DECISION_TIMEOUT":
                return {"event_id": event_id, "status": "DEVICE_TIMEOUT_REPORTED"}

        if event_type == "PASSAGE_CONFIRMED":
            if clean_gate == GateId.IN.value:
                res = self.gate_data_service.confirm_gate_in_passage(event_id=event_id, now_utc=now_dt)
            else:
                res = self.gate_data_service.confirm_gate_out_passage(event_id=event_id, now_utc=now_dt)
            self._finish_active_turn(event_id, now_utc=now_dt)
            with self._lock:
                if existing:
                    existing.state = "COMPLETED"
            return res

        if event_type == "VEHICLE_LEFT_BEFORE_DECISION" or not ir_stable_detected:
            with self._lock:
                if existing:
                    existing.state = "PASSAGE_UNCERTAIN" if existing.state == "APPROVED" else "CANCELLED"
                    existing.plate_frames.clear()
                    existing.face_frames.clear()
            self._finish_active_turn(event_id, now_utc=now_dt)
            return {
                "event_id": event_id,
                "gate_id": clean_gate,
                "status": "CANCELLED_BEFORE_DECISION",
            }

        with self._lock:
            # Idempotent retry for existing event_id (T13)
            if event_id in self._turns:
                turn = self._turns[event_id]
                if turn.last_decision is not None:
                    return turn.last_decision
                return {
                    "event_id": event_id,
                    "gate_id": clean_gate,
                    "status": "QUEUED_OR_CAPTURING",
                    "active_event_id": self._active_event_id,
                    "state": turn.state,
                }

            if len(self._queue) >= self.settings.max_pending_turns:
                raise DomainException("Recognition queue is full.", reason_code="GATE_QUEUE_FULL", http_status=503)
            if any(t.gate_id == clean_gate and t.state in ("QUEUED", "RETRY_WAIT", "CAPTURING", "DECIDING", "APPROVED", "REVIEW") for t in self._turns.values()):
                raise DomainException("Gate already has a live turn.", reason_code="GATE_BUSY", http_status=409)

            roi_name = f"ROI_{clean_gate}"
            turn = GateTurnContext(
                event_id=event_id,
                gate_id=clean_gate,
                device_id=device_id,
                boot_id=boot_id,
                sequence=sequence,
                roi=roi_name,
                created_at=now_dt,
            )
            self._turns[event_id] = turn
            self._queue.append(event_id)
            self._advance_queue_locked(now_dt)

            is_active = (self._active_event_id == event_id)
            return {
                "event_id": event_id,
                "gate_id": clean_gate,
                "roi": roi_name,
                "status": "CAPTURE_REQUESTED" if is_active else "QUEUED_WAITING_TURN",
                "active_event_id": self._active_event_id,
                "queue_length": len(self._queue),
            }

    def _advance_queue_locked(self, now_dt: datetime) -> None:
        if self._active_event_id is not None:
            return
        if not self._queue:
            return

        # Peek queue: if head is Gate IN while a session is Parking_pending, allow a Gate OUT turn first
        selected_event_id: Optional[str] = None
        parking_pending_exists = self._has_parking_pending_session()

        for candidate_id in list(self._queue):
            turn = self._turns.get(candidate_id)
            if turn is None:
                self._queue.remove(candidate_id)
                continue
            if turn.gate_id == GateId.IN.value and parking_pending_exists:
                continue
            selected_event_id = candidate_id
            self._queue.remove(candidate_id)
            break

        if selected_event_id is None:
            return

        self._active_event_id = selected_event_id
        active_turn = self._turns[selected_event_id]
        active_turn.state = "CAPTURING"
        active_turn.capture_started_at = now_dt
        self._request_camera_captures_for_turn(active_turn, now_dt)

    def _request_camera_captures_for_turn(self, turn: GateTurnContext, now_dt: datetime) -> None:
        turn.requested_samples = self.settings.capture_sample_count
        turn.capture_round += 1
        turn.received_frame_keys.clear()
        turn.capture_deadlines.clear()
        if not self._camera_stream or self._camera_stream["event_id"] != turn.event_id:
            self._start_camera_stream(turn.event_id, turn.gate_id, now_dt)
        # One outstanding upload per camera avoids overflowing the ESP capture queue.
        for camera in ("plate", "face"):
            self._send_capture_sample(turn, camera, 1, now_dt)

    def _send_capture_sample(self, turn: GateTurnContext, camera: str, sample: int, now: datetime) -> None:
        round_suffix = "" if turn.capture_round == 1 else f"-r{turn.capture_round}"
        base = f"req-{camera}-{turn.event_id}{round_suffix}"
        # ESP accepts individual capture leases below 15 seconds; the whole batch may take longer.
        deadline = min(turn.capture_started_at + timedelta(seconds=self.settings.capture_timeout_seconds),
                       now + timedelta(seconds=14))
        remaining_ms = int((deadline - now).total_seconds() * 1000)
        if remaining_ms <= 0:
            return
        frame_id = base + ("" if sample == 1 else f"-{sample}")
        turn.capture_deadlines[f"cam_{camera}:{frame_id}"] = deadline
        self._publish_mqtt(TOPIC_CAM_PLATE_CAPTURE if camera == "plate" else TOPIC_CAM_FACE_CAPTURE, {
            "event_id": turn.event_id, "gate_id": turn.gate_id, "roi": turn.roi,
            "request_id": base, "frame_id": frame_id,
            "ttl_ms": remaining_ms, "issued_at": format_utc_iso(now),
            "expires_at_ms": int(deadline.timestamp() * 1000),
        })

    def _finish_active_turn(self, event_id: str, now_utc: Optional[datetime] = None) -> None:
        now_dt = now_utc or utc_now()
        with self._lock:
            turn = self._turns.get(event_id)
            if (self._camera_stream and self._camera_stream["event_id"] == event_id
                    and (turn is None or turn.state != "REVIEW")):
                self._stop_camera_stream()
            if event_id in self._queue:
                self._queue.remove(event_id)
            if self._active_event_id == event_id:
                self._active_event_id = None
            self._advance_queue_locked(now_dt)

    def ingest_device_image(
        self,
        image_bytes: bytes,
        event_id: str,
        camera_id: str,
        device_id: str,
        frame_id: str,
        gate_id: str,
        roi: str,
        auto_evaluate_when_ready: bool = True,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Validate and decode JPEG uploaded via `POST /api/device/images` (Section VII.1 & VIII.2):
        - Verifies non-empty payload, size limit, and valid OpenCV JPEG decoding.
        - Verifies `event_id` matches an existing turn and `gate_id` / `roi` match the requested gate.
        - Deduplicates duplicate `(camera_id, frame_id)` uploads.
        - When both `cam_plate` and `cam_face` frames have arrived for the active turn, automatically
          runs the AI + GateDataService workflow.
        """
        now_dt = now_utc or utc_now()
        try:
            import cv2
        except ImportError as exc:
            raise DomainException("OpenCV is not installed.", reason_code="IMAGE_DECODER_UNAVAILABLE", http_status=503) from exc
        if not event_id or not camera_id:
            raise DomainException(
                "Thiếu header bắt buộc X-Event-Id hoặc X-Camera-Id khi gửi ảnh.",
                reason_code="MISSING_IMAGE_METADATA",
                http_status=400,
            )
        if not image_bytes or len(image_bytes) < 64:
            raise DomainException(
                "Dữ liệu ảnh JPEG rỗng hoặc quá nhỏ.",
                reason_code="EMPTY_IMAGE_PAYLOAD",
                http_status=400,
            )
        if not image_bytes.startswith(b"\xff\xd8"):
            raise DomainException("Expected a JPEG payload.", reason_code="INVALID_JPEG_DATA")
        if len(image_bytes) > 5 * 1024 * 1024:
            raise DomainException(
                "Kích thước ảnh JPEG vượt quá giới hạn 5MB.",
                reason_code="IMAGE_TOO_LARGE",
                http_status=413,
            )

        clean_cam = camera_id.strip().lower()
        if clean_cam not in ("cam_plate", "cam_face", "plate", "face"):
            raise DomainException(
                f"camera_id '{camera_id}' không hợp lệ (chỉ nhận cam_plate hoặc cam_face).",
                reason_code="INVALID_CAMERA_ID",
                http_status=400,
            )

        buf = np.frombuffer(image_bytes, dtype=np.uint8)
        frame_bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if frame_bgr is None or frame_bgr.size == 0:
            raise DomainException(
                "Không thể giải mã dữ liệu ảnh JPEG từ ESP32-S3.",
                reason_code="INVALID_JPEG_DATA",
                http_status=400,
            )

        with self._lock:
            clean_cam = "cam_plate" if clean_cam in ("plate", "cam_plate") else "cam_face"
            if event_id.startswith("preview-"):
                preview = self._preview_capture
                expected_device = self.settings.controller_device_id if clean_cam == "cam_plate" else self.settings.face_camera_device_id
                expected_frame = f"req-{'plate' if clean_cam == 'cam_plate' else 'face'}-{event_id}"
                if not preview or preview["event_id"] != event_id or now_dt >= preview["expires_at"]:
                    raise DomainException("Ảnh kiểm tra đã hết hạn hoặc bị lượt xe thay thế.", reason_code="CAPTURE_EXPIRED", http_status=409)
                if device_id != expected_device or frame_id != expected_frame or gate_id != "IN" or roi != "ROI_IN":
                    raise DomainException("Image does not match the requested capture.", reason_code="CAPTURE_METADATA_MISMATCH", http_status=409)
                self._remember_camera_image(clean_cam, image_bytes, frame_bgr, event_id, gate_id, now_dt)
                preview["remaining"].discard(clean_cam)
                return {"accepted": True, "preview": True, "camera_id": clean_cam,
                        "resolution": [int(frame_bgr.shape[1]), int(frame_bgr.shape[0])], "workflow_decision": None}
            turn = self._turns.get(event_id)
            if turn is None:
                raise DomainException(
                    f"Không tìm thấy lượt sự kiện cổng đang chờ cho event_id '{event_id}' (ảnh cũ hoặc sai lượt).",
                    reason_code="STALE_OR_UNKNOWN_EVENT_ID",
                    http_status=409,
                )

            clean_cam = "cam_plate" if clean_cam in ("plate", "cam_plate") else "cam_face"
            expected_device = self.settings.controller_device_id if clean_cam == "cam_plate" else self.settings.face_camera_device_id
            round_suffix = "" if turn.capture_round == 1 else f"-r{turn.capture_round}"
            expected_frame = f"req-{'plate' if clean_cam == 'cam_plate' else 'face'}-{event_id}{round_suffix}"
            expected_frames = {expected_frame + ("" if sample == 1 else f"-{sample}")
                               for sample in range(1, turn.requested_samples + 1)}
            if device_id != expected_device or frame_id not in expected_frames or gate_id != turn.gate_id or roi != turn.roi:
                raise DomainException("Image does not match the requested capture.", reason_code="CAPTURE_METADATA_MISMATCH", http_status=409)
            if f"{clean_cam}:{frame_id}" in turn.received_frame_keys and turn.state in ("CAPTURING", "DECIDING", "APPROVED", "REVIEW", "COMPLETED"):
                return {"accepted": True, "duplicate_frame": True, "event_id": event_id,
                        "workflow_decision": turn.last_decision}
            received_count = len(turn.plate_frames) if clean_cam == "cam_plate" else len(turn.face_frames)
            next_sample = received_count + 1
            next_frame = expected_frame + ("" if next_sample == 1 else f"-{next_sample}")
            if frame_id != next_frame:
                raise DomainException("Sample was not requested yet.", reason_code="CAPTURE_METADATA_MISMATCH", http_status=409)
            if now_dt >= turn.capture_deadlines.get(f"{clean_cam}:{frame_id}", now_dt):
                raise DomainException("Capture request expired.", reason_code="CAPTURE_EXPIRED", http_status=409)
            if turn.state != "CAPTURING" or self._active_event_id != event_id or turn.capture_started_at is None:
                raise DomainException("Capture is no longer active.", reason_code="STALE_OR_UNKNOWN_EVENT_ID", http_status=409)
            if (now_dt - turn.capture_started_at).total_seconds() > self.settings.capture_timeout_seconds:
                raise DomainException("Capture deadline elapsed.", reason_code="CAPTURE_EXPIRED", http_status=409)

            if gate_id and gate_id.strip().upper() != turn.gate_id:
                raise DomainException(
                    f"Ảnh gửi sai cổng (nhận '{gate_id}', kỳ vọng '{turn.gate_id}').",
                    reason_code="GATE_ROI_MISMATCH",
                    http_status=409,
                )

            if roi and roi.strip().upper() != turn.roi.upper():
                raise DomainException(
                    f"Ảnh gửi sai vùng ROI (nhận '{roi}', kỳ vọng '{turn.roi}').",
                    reason_code="GATE_ROI_MISMATCH",
                    http_status=409,
                )

            dedup_key = f"{clean_cam}:{frame_id or 'default'}"
            if dedup_key in turn.received_frame_keys:
                return {
                    "accepted": True,
                    "duplicate_frame": True,
                    "event_id": event_id,
                    "camera_id": clean_cam,
                    "frame_id": frame_id,
                    "plate_frames_count": len(turn.plate_frames),
                    "face_frames_count": len(turn.face_frames),
                    "workflow_decision": turn.last_decision,
                }

            turn.received_frame_keys.add(dedup_key)
            configured_roi = self.settings.gate_rois[("plate" if clean_cam == "cam_plate" else "face", turn.gate_id)]
            if configured_roi and (configured_roi[2] > frame_bgr.shape[1] or configured_roi[3] > frame_bgr.shape[0]):
                turn.received_frame_keys.discard(dedup_key)
                raise DomainException("ROI exceeds the camera frame.", reason_code="INVALID_CAMERA_ROI")
            self._remember_camera_image(clean_cam, image_bytes, frame_bgr, event_id, gate_id, now_dt)
            if "plate" in clean_cam:
                turn.plate_frames.append(frame_bgr)
            else:
                turn.face_frames.append(frame_bgr)

            received_count = len(turn.plate_frames) if clean_cam == "cam_plate" else len(turn.face_frames)
            if received_count < turn.requested_samples:
                self._send_capture_sample(turn, "plate" if clean_cam == "cam_plate" else "face", received_count + 1, now_dt)

            ready_to_evaluate = (
                auto_evaluate_when_ready
                and not turn.evaluated
                and len(turn.plate_frames) >= turn.requested_samples
                and len(turn.face_frames) >= turn.requested_samples
            )

        workflow_decision: Optional[Dict[str, Any]] = None
        if ready_to_evaluate:
            workflow_decision = self.evaluate_turn(event_id, now_utc=now_dt)

        return {
            "accepted": True,
            "duplicate_frame": False,
            "event_id": event_id,
            "gate_id": turn.gate_id,
            "camera_id": clean_cam,
            "device_id": device_id,
            "frame_id": frame_id,
            "resolution": [int(frame_bgr.shape[1]), int(frame_bgr.shape[0])],
            "plate_frames_count": len(turn.plate_frames),
            "face_frames_count": len(turn.face_frames),
            "workflow_decision": workflow_decision,
        }

    def evaluate_turn(self, event_id: str, **kwargs: Any) -> Dict[str, Any]:
        with self._lock:
            self._gate_inference_waiters += 1
        try:
            with self._inference_lock:
                try:
                    return self._evaluate_turn_impl(event_id, **kwargs)
                except Exception as exc:
                    with self._lock:
                        turn = self._turns.get(event_id)
                        if turn and turn.state == "DECIDING":
                            reason = exc.reason_code if isinstance(exc, DomainException) else "AI_WORKFLOW_ERROR"
                            logger.exception("Gate decision failed for %s", event_id)
                            return self._mark_review(turn, reason, kwargs.get("now_utc") or utc_now())
                    raise
        finally:
            with self._lock:
                self._gate_inference_waiters -= 1

    def _evaluate_turn_impl(
        self,
        event_id: str,
        *,
        plate_outcome_override: Optional[PlateRecognitionOutcome] = None,
        face_result_override: Optional[FacePipelineResult] = None,
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Execute AI inference + GateDataService transactional check for `event_id` outside DB locks,
        then publish MQTT command to S3 controller after commit.
        """
        now_dt = now_utc or utc_now()
        with self._lock:
            turn = self._turns.get(event_id)
            if turn is None:
                raise ResourceNotFoundException(
                    f"Không tìm thấy lượt cổng {event_id}.",
                    reason_code="TURN_NOT_FOUND",
                )
            if turn.evaluated and turn.last_decision is not None:
                return turn.last_decision
            if turn.state != "CAPTURING" or self._active_event_id != event_id:
                raise DomainException("Turn is not active.", reason_code="TURN_NOT_ACTIVE", http_status=409)
            if turn.capture_started_at is None or (now_dt - turn.capture_started_at).total_seconds() > self.settings.capture_timeout_seconds:
                raise DomainException("Capture deadline elapsed.", reason_code="CAPTURE_EXPIRED", http_status=409)
            turn.state = "DECIDING"
            plate_frames = list(turn.plate_frames)
            face_frames = list(turn.face_frames)
            gate_id = turn.gate_id
            device_id = turn.device_id

        # 1. Run Plate AI Pipeline (outside DB transaction)
        plate_out = plate_outcome_override or self.plate_pipeline.process_frames(plate_frames, roi=self.settings.gate_rois[("plate", gate_id)])
        # 2. Run Face AI Pipeline with mandatory Liveness (outside DB transaction)
        face_out = face_result_override or self.face_pipeline.process_frames(
            face_frames,
            require_liveness=True,
            min_valid_samples=min(2, turn.requested_samples),
            min_sample_similarity=self.settings.face_t_accept,
            roi=self.settings.gate_rois[("face", gate_id)],
        )

        with self._lock:
            if turn.state != "DECIDING":
                raise DomainException("Vehicle left during recognition.", reason_code="TURN_CANCELLED", http_status=409)
            turn.plate_outcome = plate_out
            turn.face_result = face_out

        with self._lock:
            if turn.state != "DECIDING":
                raise DomainException("Turn cancelled.", reason_code="TURN_CANCELLED", http_status=409)
            recoverable_plate = {"INVALID_PLATE_IMAGE", "NO_PLATE_DETECTED", "OCR_EMPTY_TEXT",
                                 "INVALID_PLATE_FORMAT", "PLATE_VOTING_CONFLICT", "PLATE_INSUFFICIENT_CONSENSUS"}
            recoverable_face = {"NO_FACE", "FACE_QUALITY_FAILED", "FACE_REVIEW_REQUIRED", "FACE_SAMPLES_INCONSISTENT"}
            retry_reason = (plate_out.reason_code if not plate_out.ok and plate_out.reason_code in recoverable_plate
                            else face_out.reason_code if plate_out.ok and not face_out.ok and face_out.reason_code in recoverable_face
                            else None)
            if retry_reason and self._vehicle_waiting(turn, now_dt):
                return self._schedule_retry(turn, retry_reason, now_dt)
            if gate_id == GateId.IN.value:
                decision = self._process_gate_in_decision(
                    event_id=event_id,
                    device_id=device_id,
                    plate_out=plate_out,
                    face_out=face_out,
                    now_dt=now_dt,
                )
            else:
                decision = self._process_gate_out_decision(
                    event_id=event_id,
                    device_id=device_id,
                    plate_out=plate_out,
                    face_out=face_out,
                    now_dt=now_dt,
                )
            turn.evaluated = True
            turn.last_decision = decision
            turn.state = "APPROVED" if decision.get("decision") == "Approved" else "REVIEW"
            if turn.state == "APPROVED":
                turn.approved_at = now_dt
            turn.plate_frames.clear()
            turn.face_frames.clear()
            if decision.get("decision") != "Approved":
                # If denied or review required, release active turn slot so other gate is not deadlocked
                if self._active_event_id == event_id:
                    self._active_event_id = None
                self._advance_queue_locked(now_dt)

        return decision

    def _vehicle_waiting(self, turn: GateTurnContext, now: datetime) -> bool:
        device = self._device_status.get(turn.device_id, {})
        seen = device.get("received_at")
        if not seen or not device.get("online") or device.get("boot_id") != turn.boot_id:
            return False
        age = (now - datetime.fromisoformat(seen.replace("Z", "+00:00"))).total_seconds()
        gate = turn.gate_id.lower()
        return (0 <= age < 20 and device.get(f"gate_{gate}_event_id") == turn.event_id
                and device.get(f"gate_{gate}_state") in ("Waiting_backend", "Review_required"))

    def _schedule_retry(self, turn: GateTurnContext, reason: str, now: datetime) -> Dict[str, Any]:
        # Keep one bounded batch in RAM; never persist an incomplete recognition as a session.
        turn.state = "RETRY_WAIT"
        turn.evaluated = False
        turn.retry_at = now + timedelta(seconds=2)
        turn.plate_frames.clear()
        turn.face_frames.clear()
        turn.last_decision = {"event_id": turn.event_id, "decision": "Scanning",
                              "reason_code": reason, "capture_round": turn.capture_round}
        if self._active_event_id == turn.event_id:
            self._active_event_id = None
        self._advance_queue_locked(now)
        return turn.last_decision

    def _mark_review(self, turn: GateTurnContext, reason: str, now_dt: datetime) -> Dict[str, Any]:
        """Do not release a DB slot/session when physical passage is uncertain."""
        turn.state = "REVIEW"
        turn.evaluated = True
        turn.plate_frames.clear()
        turn.face_frames.clear()
        try:
            decision = self.gate_data_service.flag_gate_review_required(
                event_id=turn.event_id, gate_id=turn.gate_id, device_id=turn.device_id,
                reason_code=reason, now_utc=now_dt)
        except Exception:
            logger.exception("Unable to persist gate review; keeping the gate closed")
            decision = {"event_id": turn.event_id, "decision": "Review_required",
                        "reason_code": "REVIEW_PERSISTENCE_FAILED"}
        turn.last_decision = decision
        self._emit_gate_command(turn.gate_id, turn.event_id, str(uuid.uuid4()), "REVIEW_REQUIRED",
                                reason_code=reason, now_dt=now_dt)
        self._finish_active_turn(turn.event_id, now_dt)
        return decision

    def maintain(self, now_utc: Optional[datetime] = None) -> None:
        now = now_utc or utc_now()
        if self._mqtt_publish_fn and (self._last_display_update is None or (now - self._last_display_update).total_seconds() >= 5):
            self._publish_mqtt("parking/display/status", {"available_slots": self._count_available_slots(now),
                                "expires_at_ms": int((now.timestamp() + 8) * 1000)})
            self._last_display_update = now
        with self._lock:
            session = self._camera_stream
            if session and not session["preview"]:
                if now >= session["expires_at"]:
                    self._stop_camera_stream()
                    session = None
            if session and not session["preview"]:
                turn = self._turns.get(session["event_id"])
                if turn is None or turn.state in ("CANCELLED", "COMPLETED", "PASSAGE_UNCERTAIN"):
                    self._stop_camera_stream()
                elif (now - session["last_refresh"]).total_seconds() >= 10:
                    device = self._device_status.get(self.settings.controller_device_id, {})
                    seen = device.get("received_at")
                    recent = seen and (now - datetime.fromisoformat(seen.replace("Z", "+00:00"))).total_seconds() < 20
                    if recent and device.get(f"gate_{session['gate_id'].lower()}_event_id") == session["event_id"]:
                        session["expires_at"] = now + timedelta(seconds=30)
                        session["last_refresh"] = now
                        self._send_camera_stream_control("START", session)
            for turn in list(self._turns.values()):
                age = (now - turn.created_at).total_seconds()
                capture_age = (now - (turn.capture_started_at or now)).total_seconds()
                if turn.state == "CAPTURING" and capture_age > self.settings.capture_timeout_seconds:
                    if self._vehicle_waiting(turn, now):
                        self._schedule_retry(turn, "CAPTURE_TIMEOUT", now)
                    else:
                        self._mark_review(turn, "CAPTURE_TIMEOUT", now)
                elif turn.state == "RETRY_WAIT" and now >= turn.retry_at:
                    if self._vehicle_waiting(turn, now):
                        turn.state = "QUEUED"
                        self._queue.append(turn.event_id)
                    else:
                        self._mark_review(turn, "CONTROLLER_PRESENCE_LOST", now)
                elif turn.state in ("QUEUED", "DECIDING") and age > self.settings.gate_turn_timeout_seconds and not (turn.capture_round and self._vehicle_waiting(turn, now)):
                    self._mark_review(turn, "GATE_TURN_TIMEOUT", now)
                elif turn.state == "APPROVED" and (now - (turn.approved_at or turn.created_at)).total_seconds() > self.settings.gate_turn_timeout_seconds:
                    turn.state = "PASSAGE_UNCERTAIN"
                    turn.plate_frames.clear()
                    turn.face_frames.clear()
                    self._finish_active_turn(turn.event_id, now)
                if age > 600 and turn.state in ("COMPLETED", "CANCELLED", "REVIEW", "PASSAGE_UNCERTAIN"):
                    turn.face_result = None
                    turn.plate_outcome = None
                    del self._turns[turn.event_id]
            self._expire_camera_images(now)
            self._advance_queue_locked(now)

    def diagnostics(self, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
        now = now_utc or utc_now()
        with self._lock:
            self._expire_camera_images(now)
            for command in self._commands.values():
                if command["delivery_status"] == "PENDING_ACK" and int(now.timestamp() * 1000) > command["expires_at_ms"]:
                    command["delivery_status"] = "ACK_TIMEOUT"
            devices = []
            for device_id in (self.settings.controller_device_id, self.settings.face_camera_device_id):
                info = self._device_status.get(device_id, {})
                seen = info.get("received_at")
                age = (now - datetime.fromisoformat(seen.replace("Z", "+00:00"))).total_seconds() if seen else None
                devices.append({**info, "device_id": device_id,
                                "online": bool(info.get("online")) and age is not None and age < 20,
                                "age_seconds": int(age) if age is not None else None})
            return {"ai_status": self.ai_status, "active_event_id": self._active_event_id,
                    "queue_length": len(self._queue), "devices": devices,
                    "turns": [{"event_id": t.event_id, "gate_id": t.gate_id, "state": t.state, "capture_round": t.capture_round,
                               "reason_code": (t.last_decision or {}).get("reason_code"),
                               "created_at": format_utc_iso(t.created_at)} for t in self._turns.values()],
                    "commands": list(self._commands.values())[-20:]}

    def submit_manual_review(self, event_id: str, admin_user_id: int, action: str, reason: str,
                             command_id: Optional[str] = None, now_utc: Optional[datetime] = None) -> Dict[str, Any]:
        now = now_utc or utc_now()
        action = action.strip().upper()
        if command_id and len(command_id) > 36:
            raise DomainException("command_id exceeds the database limit.", reason_code="INVALID_COMMAND_ID")
        if action not in ("APPROVE", "DENY") or not reason.strip():
            raise DomainException("Choose APPROVE/DENY and enter a reason.", reason_code="INVALID_REVIEW_INPUT")
        if event_id.startswith("PARK-"):
            return self.gate_data_service.record_manual_review_decision(event_id, admin_user_id, action, reason, now_utc=now)
        with self._inference_lock, self._lock:
            admin = self.gate_data_service.uow.run_transactional(lambda tx: tx.users.get_by_id(admin_user_id))
            if admin is None or admin.role.value != "admin" or admin.status.value != "Active":
                raise DomainException("Active admin required.", reason_code="ADMIN_REQUIRED", http_status=403)
            turn = self._turns.get(event_id)
            ev = self.gate_data_service.uow.run_transactional(lambda tx: tx.gate_events.get_by_id(event_id))
            if ev is None:
                raise ResourceNotFoundException("Review event not found.")
            if ev.reviewer_id is not None and ev.decision.value in ("Approved", "Denied"):
                raise DomainException("Review already decided.", reason_code="REVIEW_ALREADY_DECIDED", http_status=409)
            if ev.decision.value not in ("Pending", "Review_required"):
                raise DomainException("Event does not require review.", reason_code="REVIEW_NOT_REQUIRED", http_status=409)
            if action == "APPROVE":
                if turn is None or turn.state != "REVIEW" or (now - turn.created_at).total_seconds() > self.settings.gate_turn_timeout_seconds:
                    raise DomainException("A fresh gate turn is required.", reason_code="REVIEW_TURN_STALE", http_status=409)
                # Never open an entry without an allocated session and a usable session template.
                if not ev.session_id:
                    face, plate = turn.face_result, turn.plate_outcome
                    if turn.gate_id != "IN" or face is None or plate is None or not plate.ok or not face.ok or face.embedding is None or face.liveness_status != LivenessStatus.PASSED.value:
                        raise DomainException("Capture a valid plate and live face before approving entry.", reason_code="ENTRY_TEMPLATE_REQUIRED", http_status=409)
                    cmd_id = command_id or str(uuid.uuid4())
                    if ev.booking_id:
                        self.gate_data_service.confirm_booking_entry_permission(ev.booking_id, event_id, face.to_template_payload(), command_id=cmd_id, now_utc=now)
                    else:
                        self.gate_data_service.allocate_walkin_entry(plate.normalized_plate, event_id, face.to_template_payload(), command_id=cmd_id, device_id=turn.device_id, now_utc=now)
            result = self.gate_data_service.record_manual_review_decision(
                event_id, admin_user_id, action, reason, command_id=command_id, now_utc=now)
            if turn is not None:
                session = self.gate_data_service.uow.run_transactional(lambda tx: tx.sessions.get_by_id(result["session_id"])) if result.get("session_id") else None
                command = self._emit_gate_command(turn.gate_id, event_id, result.get("command_id") or str(uuid.uuid4()),
                                                  "OPEN" if action == "APPROVE" else "DENY", assigned_slot_id=session.assigned_slot_id if session else None, now_dt=now)
                turn.state = "APPROVED" if action == "APPROVE" else "CANCELLED"
                turn.last_decision = result
                result = {**result, "command_id": command["command_id"], "command_status": self._commands[command["command_id"]]["delivery_status"]}
            return result

    def _emit_gate_command(
        self,
        gate_id: str,
        event_id: str,
        command_id: str,
        action: str,
        assigned_slot_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        now_dt: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        topic = TOPIC_GATE_IN_COMMAND if gate_id == GateId.IN.value else TOPIC_GATE_OUT_COMMAND
        cmd_payload = {
            "command_id": command_id,
            "event_id": event_id,
            "gate_id": gate_id,
            "action": action,
            "assigned_slot_id": assigned_slot_id or "",
            "reason_code": reason_code or "",
            "expires_in_ms": self.settings.command_ttl_seconds * 1000,
            "expires_at_ms": int(((now_dt or utc_now()).timestamp() + self.settings.command_ttl_seconds) * 1000),
            "expires_at": format_utc_iso((now_dt or utc_now()) + timedelta(seconds=self.settings.command_ttl_seconds)),
            "available_slots": self._count_available_slots(now_utc=now_dt),
            "issued_at": format_utc_iso(now_dt or utc_now()),
        }
        self._commands[command_id] = {**cmd_payload, "delivery_status": "PENDING_ACK"}
        while len(self._commands) > 100:
            del self._commands[next(iter(self._commands))]
        self._publish_mqtt(topic, cmd_payload)
        return cmd_payload

    def _process_gate_in_decision(
        self,
        event_id: str,
        device_id: str,
        plate_out: PlateRecognitionOutcome,
        face_out: FacePipelineResult,
        now_dt: datetime,
    ) -> Dict[str, Any]:
        # Fail-closed if plate unreadable or ambiguous
        if not plate_out.ok or not plate_out.normalized_plate:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                reason_code=plate_out.reason_code or "PLATE_UNREADABLE",
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.IN.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=rev["reason_code"], now_dt=now_dt)
            return rev

        # Fail-closed if face quality or liveness failed (T20)
        if not face_out.ok or face_out.embedding is None or face_out.liveness_status != LivenessStatus.PASSED.value:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                reason_code=face_out.reason_code or "FACE_LIVENESS_OR_QUALITY_FAILED",
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.IN.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=rev["reason_code"], now_dt=now_dt)
            return rev

        # Check if vehicle has an active pre-booking (`Reserved`)
        checkin_info: Optional[Dict[str, Any]] = None
        try:
            checkin_info = self.gate_data_service.begin_booking_checkin(
                plate_number=plate_out.normalized_plate,
                event_id=event_id,
                device_id=device_id,
                now_utc=now_dt,
            )
        except ResourceNotFoundException as exc:
            if exc.reason_code not in ("VEHICLE_NOT_REGISTERED", "BOOKING_NOT_FOUND"):
                raise
            # No registered vehicle or no active booking -> treat as walk-in guest (Section V.4)
            checkin_info = None
        except DomainException as exc:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                reason_code=exc.reason_code,
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.IN.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=exc.reason_code, now_dt=now_dt)
            return rev

        # Case A: Pre-booked vehicle arrival (Section V.3 & IV.5)
        if checkin_info is not None:
            booking_id = checkin_info["booking_id"]
            cmd_id = str(uuid.uuid4())
            approved = self.gate_data_service.confirm_booking_entry_permission(
                booking_id=booking_id,
                event_id=event_id,
                session_face_template_data=face_out.to_template_payload(),
                command_id=cmd_id,
                ocr_confidence=plate_out.ocr_confidence,
                now_utc=now_dt,
            )
            self._emit_gate_command(
                GateId.IN.value,
                event_id,
                cmd_id,
                "OPEN",
                assigned_slot_id=approved["assigned_slot_id"],
                reason_code="BOOKING_ENTRY_APPROVED",
                now_dt=now_dt,
            )
            return {
                **approved,
                "decision": "Approved",
                "flow_type": "BOOKING",
            }

        # Case B: Walk-in guest vehicle arrival (Section V.4 & IV.6)
        try:
            cmd_id = str(uuid.uuid4())
            approved = self.gate_data_service.allocate_walkin_entry(
                plate_number=plate_out.normalized_plate,
                event_id=event_id,
                session_face_template_data=face_out.to_template_payload(),
                command_id=cmd_id,
                device_id=device_id,
                ocr_confidence=plate_out.ocr_confidence,
                now_utc=now_dt,
            )
            self._emit_gate_command(
                GateId.IN.value,
                event_id,
                cmd_id,
                "OPEN",
                assigned_slot_id=approved["assigned_slot_id"],
                reason_code="WALKIN_ENTRY_APPROVED",
                now_dt=now_dt,
            )
            return {
                **approved,
                "decision": "Approved",
                "flow_type": "WALKIN",
            }
        except SlotNotAvailableException as exc:
            denied = self.gate_data_service.deny_gate_event(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                reason_code=exc.reason_code,
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.IN.value, event_id, cmd_id, "DENY", reason_code=exc.reason_code, now_dt=now_dt)
            return denied
        except DomainException as exc:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.IN.value,
                device_id=device_id,
                reason_code=exc.reason_code,
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.IN.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=exc.reason_code, now_dt=now_dt)
            return rev

    def _process_gate_out_decision(
        self,
        event_id: str,
        device_id: str,
        plate_out: PlateRecognitionOutcome,
        face_out: FacePipelineResult,
        now_dt: datetime,
    ) -> Dict[str, Any]:
        if not plate_out.ok or not plate_out.normalized_plate:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.OUT.value,
                device_id=device_id,
                reason_code=plate_out.reason_code or "PLATE_UNREADABLE",
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.OUT.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=rev["reason_code"], now_dt=now_dt)
            return rev

        try:
            prep = self.gate_data_service.prepare_exit_verification(
                plate_number=plate_out.normalized_plate,
                event_id=event_id,
                device_id=device_id,
                now_utc=now_dt,
            )
        except DomainException as exc:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.OUT.value,
                device_id=device_id,
                reason_code=exc.reason_code,
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.OUT.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=exc.reason_code, now_dt=now_dt)
            return rev

        session_id = prep["session_id"]
        if not face_out.ok or face_out.embedding is None or face_out.liveness_status != LivenessStatus.PASSED.value:
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.OUT.value,
                device_id=device_id,
                reason_code=face_out.reason_code or "FACE_LIVENESS_OR_QUALITY_FAILED",
                session_id=session_id,
                booking_id=prep.get("booking_id"),
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.OUT.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=rev["reason_code"], now_dt=now_dt)
            return rev

        # Compare 1:1 strictly against session_face_templates (`entry_embedding`), NEVER user_face_templates (T08)
        verify_out = self.face_verifier.verify_with_metadata(
            reference_embedding=prep["entry_embedding"],
            candidate_embedding=face_out.embedding,
            ref_model_id=prep.get("model_id"),
            cand_model_id=face_out.model_id,
            ref_model_version=prep.get("model_version"),
            cand_model_version=face_out.model_version,
        )
        if verify_out.decision != "ACCEPT":
            rev = self.gate_data_service.flag_gate_review_required(
                event_id=event_id,
                gate_id=GateId.OUT.value,
                device_id=device_id,
                reason_code=verify_out.reason_code,
                session_id=session_id,
                booking_id=prep.get("booking_id"),
                liveness_status=face_out.liveness_status,
                liveness_score=face_out.liveness_score,
                now_utc=now_dt,
            )
            cmd_id = str(uuid.uuid4())
            self._emit_gate_command(GateId.OUT.value, event_id, cmd_id, "REVIEW_REQUIRED", reason_code=verify_out.reason_code, now_dt=now_dt)
            return {**rev, "similarity_score": verify_out.similarity}

        cmd_id = str(uuid.uuid4())
        approved = self.gate_data_service.approve_exit_permission(
            session_id=session_id,
            event_id=event_id,
            command_id=cmd_id,
            liveness_status=face_out.liveness_status,
            liveness_score=face_out.liveness_score,
            similarity_score=verify_out.similarity,
            now_utc=now_dt,
        )
        self._emit_gate_command(
            GateId.OUT.value,
            event_id,
            cmd_id,
            "OPEN",
            assigned_slot_id=approved["assigned_slot_id"],
            reason_code="EXIT_FACE_MATCH_APPROVED",
            now_dt=now_dt,
        )
        return {
            **approved,
            "decision": "Approved",
            "similarity_score": verify_out.similarity,
        }

    def handle_mqtt_message(
        self, topic: str, payload_dict: Dict[str, Any], now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if not isinstance(payload_dict, dict):
            raise DomainException("MQTT payload must be an object.", reason_code="INVALID_DEVICE_PAYLOAD")
        device = payload_dict.get("device_id")
        boot = payload_dict.get("boot_id")
        sequence = payload_dict.get("sequence")
        if device not in (self.settings.controller_device_id, self.settings.face_camera_device_id) or not isinstance(boot, str) or not boot or type(sequence) is not int or sequence < 1:
            raise DomainException("Invalid MQTT envelope.", reason_code="INVALID_DEVICE_PAYLOAD")
        if topic.startswith("parking/devices/") and topic.split("/")[2] != device:
            raise DomainException("Device topic mismatch.", reason_code="DEVICE_TOPIC_MISMATCH")
        if topic in (TOPIC_GATE_IN_DETECTED, TOPIC_GATE_OUT_DETECTED, TOPIC_SLOTS_SNAPSHOT) and device != self.settings.controller_device_id:
            raise DomainException("Only the controller can send gate/IR events.", reason_code="DEVICE_TOPIC_MISMATCH")
        if topic in (TOPIC_GATE_IN_DETECTED, TOPIC_GATE_OUT_DETECTED):
            expected_gate = "IN" if topic == TOPIC_GATE_IN_DETECTED else "OUT"
            if payload_dict.get("gate_id") != expected_gate:
                raise DomainException("Gate topic mismatch.", reason_code="DEVICE_TOPIC_MISMATCH")
            if "ir_stable_detected" in payload_dict and type(payload_dict["ir_stable_detected"]) is not bool:
                raise DomainException("IR state must be boolean.", reason_code="INVALID_DEVICE_PAYLOAD")
        with self._lock:
            if (device, boot) in self._retired_boots:
                raise DomainException("Device boot has been superseded.", reason_code="RETIRED_DEVICE_BOOT", http_status=409)
            old_boot = self._device_boots.get(device)
            if old_boot and old_boot != boot:
                self._retired_boots.append((device, old_boot))
                for turn in list(self._turns.values()):
                    if turn.device_id == device and turn.boot_id == old_boot and turn.state not in ("COMPLETED", "CANCELLED"):
                        turn.state = "PASSAGE_UNCERTAIN" if turn.state == "APPROVED" else "CANCELLED"
                        turn.plate_frames.clear()
                        turn.face_frames.clear()
                        self._finish_active_turn(turn.event_id, now_utc)
            self._device_boots[device] = boot
        key = (device, boot, topic, payload_dict.get("event_id"), payload_dict.get("event_type"))
        with self._lock:
            if sequence <= self._message_sequences.get(key, 0):
                return {"ignored": True, "reason_code": "DUPLICATE_OR_OLD_SEQUENCE"}
        if payload_dict.get("event_type") == "DETECTED" and payload_dict.get("occurred_at_ms") is not None:
            age_ms = int((now_utc or utc_now()).timestamp() * 1000) - int(payload_dict["occurred_at_ms"])
            if age_ms > 15000 or age_ms < -2000:
                raise DomainException("Old gate detection event.", reason_code="STALE_GATE_DETECTION", http_status=409)
        result = self._dispatch_mqtt_message(topic, payload_dict, now_utc)
        with self._lock:
            self._message_sequences[key] = sequence
            if len(self._message_sequences) > 200:
                del self._message_sequences[next(iter(self._message_sequences))]
        return result

    def _dispatch_mqtt_message(
        self,
        topic: str,
        payload_dict: Dict[str, Any],
        now_utc: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Dispatch an incoming MQTT message from either ESP32-S3 board."""
        now_dt = now_utc or utc_now()
        if topic in (TOPIC_GATE_IN_DETECTED, TOPIC_GATE_OUT_DETECTED):
            gate_id = str(payload_dict.get("gate_id") or ("IN" if "/IN/" in topic else "OUT"))
            return self.handle_gate_detected(
                event_id=str(payload_dict.get("event_id") or ""),
                gate_id=gate_id,
                device_id=str(payload_dict.get("device_id") or "s3_plate_ctrl"),
                boot_id=str(payload_dict.get("boot_id") or "boot-0"),
                sequence=int(payload_dict.get("sequence") or 1),
                event_type=str(payload_dict.get("event_type") or "DETECTED"),
                ir_stable_detected=bool(payload_dict.get("ir_stable_detected", True)),
                now_utc=now_dt,
            )

        if topic == TOPIC_SLOTS_SNAPSHOT:
            slots_map = payload_dict.get("slots") or {}
            if not slots_map and isinstance(payload_dict.get("sensors"), list):
                for s in payload_dict["sensors"]:
                    if isinstance(s, dict) and s.get("slot_id") and s.get("stable_state"):
                        slots_map[str(s["slot_id"])] = str(s["stable_state"])
            res = self.gate_data_service.update_ir_slot_snapshot(
                device_id=str(payload_dict.get("device_id") or "s3_plate_ctrl"),
                boot_id=str(payload_dict.get("boot_id") or "boot-0"),
                sequence=int(payload_dict.get("sequence") or 1),
                slots_payload=slots_map,
                received_at=now_dt,
            )
            # If a Parking_pending session just became Parked_confirmed, advance any waiting Gate IN turn
            if res.get("session_transitions"):
                with self._lock:
                    self._advance_queue_locked(now_dt)
            return res

        if topic.startswith("parking/devices/") and topic.endswith("/ack"):
            with self._lock:
                command = self._commands.get(str(payload_dict.get("command_id")))
                if command is None or payload_dict.get("event_id") != command["event_id"] or payload_dict.get("gate_id") != command["gate_id"] or payload_dict.get("device_id") != self.settings.controller_device_id:
                    raise DomainException("ACK does not match a sent command.", reason_code="ACK_COMMAND_MISMATCH")
                command["delivery_status"] = "ACK_ACCEPTED" if payload_dict.get("accepted") is True else "ACK_REJECTED"
                command["servo_command_issued"] = payload_dict.get("servo_command_issued") is True
                command["ack_reason"] = payload_dict.get("reason")
                self._command_acks.append({**payload_dict, "received_at": format_utc_iso(now_dt)})
            return {"ack_recorded": True, "command_id": payload_dict.get("command_id")}

        if topic.startswith("parking/devices/") and topic.endswith("/status"):
            dev_id = str(payload_dict.get("device_id") or topic.split("/")[2])
            with self._lock:
                self._device_status[dev_id] = {**payload_dict, "received_at": format_utc_iso(now_dt)}
            return {"status_recorded": True, "device_id": dev_id}

        return {"ignored": True, "topic": topic}
