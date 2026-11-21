"""Integration tests for Nam's AI pipelines (Plate + Face + Liveness) and Duy's HTTP/MQTT Gate Workflow."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import cv2
import numpy as np
import pytest

EDGE_SERVER_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = EDGE_SERVER_DIR / "src"
TESTS_DIR = EDGE_SERVER_DIR / "tests"
for p in (SRC_DIR, TESTS_DIR, EDGE_SERVER_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fakes.fake_mysql_db import SandboxMySQLTestDatabase
from scripts.seed_demo_data import seed_demo_data, make_deterministic_l2_vector
from smart_parking.ai.face.pipeline import FacePipeline, FacePipelineResult
from smart_parking.ai.face.template import FaceTemplateNormalizer
from smart_parking.ai.face.verifier import FaceVerifier
from smart_parking.ai.plate.pipeline import PlatePipeline, PlateRecognitionOutcome
from smart_parking.application.services.gate_workflow_service import (
    TOPIC_CAM_FACE_CAPTURE,
    TOPIC_CAM_PLATE_CAPTURE,
    TOPIC_GATE_IN_COMMAND,
    TOPIC_GATE_IN_DETECTED,
    TOPIC_GATE_OUT_COMMAND,
    TOPIC_GATE_OUT_DETECTED,
    TOPIC_SLOTS_SNAPSHOT,
)
from smart_parking.config.constants import (
    DEFAULT_FACE_CONFIG_VERSION,
    DEFAULT_FACE_MODEL_ID,
    DEFAULT_FACE_MODEL_VERSION,
)
from smart_parking.config.settings import Settings
from smart_parking.domain.enums import LivenessStatus
from smart_parking.interfaces.http.app import LocalTestClient, create_app
from smart_parking.interfaces.http.dependencies import build_container


def _make_jpeg_bytes(width: int = 320, height: int = 240) -> bytes:
    img = np.full((height, width, 3), 180, dtype=np.uint8)
    cv2.rectangle(img, (40, 40), (200, 160), (40, 120, 220), -1)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def _unit_vec(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512).astype(np.float32)
    return FaceTemplateNormalizer.l2_normalize(v)


def test_face_pipeline_enforces_liveness_and_single_face() -> None:
    vec = _unit_vec(101)
    live_face = SimpleNamespace(
        bbox=np.array([100, 60, 220, 200], dtype=np.float32),
        kps=np.array([[135, 110], [185, 110], [160, 138], [140, 168], [180, 168]], dtype=np.float32),
        normed_embedding=vec,
        det_score=0.95,
        liveness=SimpleNamespace(status="ok", is_live=True, live_score=0.94),
    )
    spoof_face = SimpleNamespace(
        bbox=np.array([100, 60, 220, 200], dtype=np.float32),
        kps=np.array([[135, 110], [185, 110], [160, 138], [140, 168], [180, 168]], dtype=np.float32),
        normed_embedding=vec,
        det_score=0.95,
        liveness=SimpleNamespace(status="ok", is_live=False, live_score=0.18),
    )

    frame = np.full((260, 320, 3), 128, dtype=np.uint8)

    # 1. Valid live face passes
    adapter_ok = SimpleNamespace(app=SimpleNamespace(get=lambda _f: [live_face]))
    pipe_ok = FacePipeline(adapter=adapter_ok, min_face_size=50, liveness_threshold=0.80)
    res_ok = pipe_ok.process_frame(frame, require_liveness=True)
    assert res_ok.ok is True
    assert res_ok.liveness_status == LivenessStatus.PASSED.value
    assert res_ok.liveness_score == 0.94
    assert res_ok.embedding is not None and res_ok.embedding.shape == (512,)

    # 2. Spoof face fails closed (T20)
    adapter_spoof = SimpleNamespace(app=SimpleNamespace(get=lambda _f: [spoof_face]))
    pipe_spoof = FacePipeline(adapter=adapter_spoof, min_face_size=50, liveness_threshold=0.80)
    res_spoof = pipe_spoof.process_frame(frame, require_liveness=True)
    assert res_spoof.ok is False
    assert res_spoof.reason_code == "LIVENESS_FAILED"
    assert res_spoof.liveness_status == LivenessStatus.FAILED.value
    assert res_spoof.embedding is None

    # 3. Controlled offline import records Not_used / score None (T20)
    res_offline = pipe_spoof.process_frame(frame, require_liveness=False)
    assert res_offline.ok is True
    assert res_offline.liveness_status == LivenessStatus.NOT_USED.value
    assert res_offline.liveness_score is None


def test_plate_pipeline_uses_nam_ocr_and_rejects_multiple_plates() -> None:
    fake_single_reader = SimpleNamespace(
        predict=lambda _img: [
            SimpleNamespace(
                bbox=(40, 50, 200, 110),
                confidence=0.92,
                ocr=SimpleNamespace(raw_text="43A-123.45", text="43A12345", char_count=8),
            )
        ]
    )
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    pipe = PlatePipeline(reader=fake_single_reader)
    out = pipe.process_frame(frame)
    assert out.ok is True
    assert out.normalized_plate == "43A12345"
    assert out.display_plate == "43A-123.45"

    # Multiple plates in ROI -> rejected for manual review (Section II.5)
    fake_multi_reader = SimpleNamespace(
        predict=lambda _img: [
            SimpleNamespace(bbox=(10, 10, 80, 40), confidence=0.9, ocr=SimpleNamespace(raw_text="43A12345", text="43A12345", char_count=8)),
            SimpleNamespace(bbox=(100, 10, 180, 40), confidence=0.88, ocr=SimpleNamespace(raw_text="92A99999", text="92A99999", char_count=8)),
        ]
    )
    pipe_multi = PlatePipeline(reader=fake_multi_reader)
    out_multi = pipe_multi.process_frame(frame)
    assert out_multi.ok is False
    assert out_multi.reason_code == "MULTIPLE_PLATES_IN_ROI"


def test_http_device_image_upload_and_mqtt_gate_workflow_end_to_end() -> None:
    settings = Settings(slot_stale_seconds=300, device_api_key="integration-test-key")
    fake_db = SandboxMySQLTestDatabase(settings)
    container = build_container(settings=settings, db=fake_db)
    seed_demo_data(uow=container.uow, cipher=container.cipher, settings=settings, with_test_fixtures=True, init_slots_free=True)

    driver_vec = make_deterministic_l2_vector(20261118)

    # Inject deterministic PlatePipeline and FacePipeline mocks into GateWorkflowService
    wf = container.gate_workflow_service
    wf.plate_pipeline = SimpleNamespace(
        process_frames=lambda _frames, **_kw: PlateRecognitionOutcome(
            ok=True,
            reason_code="OK",
            message="OK",
            raw_text="43A12345",
            normalized_plate="43A12345",
            display_plate="43A-123.45",
            detector_confidence=0.95,
            ocr_confidence=0.95,
            bbox=(20, 30, 180, 90),
            detector_version="yolo-v1",
            ocr_version="ocr-v1",
            latency_ms=12.5,
        )
    )
    wf.face_pipeline = SimpleNamespace(
        process_frames=lambda _frames, **_kw: FacePipelineResult(
            ok=True,
            reason_code="OK",
            message="OK",
            embedding=driver_vec,
            quality_score=0.93,
            liveness_status=LivenessStatus.PASSED.value,
            liveness_score=0.96,
            model_id=DEFAULT_FACE_MODEL_ID,
            model_version=DEFAULT_FACE_MODEL_VERSION,
            config_version=DEFAULT_FACE_CONFIG_VERSION,
            valid_sample_count=1,
        )
    )

    app = create_app(container=container, enable_background_worker=False)
    client = LocalTestClient(app)

    # 1. User books slot B1
    login_resp = client.post("/api/auth/login", json={"username": "viet_user", "password": settings.demo_user_password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    book_resp = client.post(
        "/api/bookings",
        json={"slot_id": "B1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert book_resp.status_code == 201

    # 2. S3 controller sends MQTT Gate IN detected
    trig = wf.handle_mqtt_message(
        TOPIC_GATE_IN_DETECTED,
        {
            "event_id": "ev-in-001",
            "gate_id": "IN",
            "device_id": "s3_plate_ctrl",
            "boot_id": "b001",
            "sequence": 10,
            "event_type": "DETECTED",
            "ir_stable_detected": True,
        },
    )
    assert trig["status"] == "CAPTURE_REQUESTED"
    published_topics = [t for t, _ in wf.published_mqtt_messages]
    assert TOPIC_CAM_PLATE_CAPTURE in published_topics
    assert TOPIC_CAM_FACE_CAPTURE in published_topics

    # 3. S3 Plate Camera & S3 Face Camera upload JPEGs via POST /api/device/images
    jpeg_bytes = _make_jpeg_bytes()
    r_plate = client.post(
        "/api/device/images",
        content=jpeg_bytes,
        headers={
            "Content-Type": "image/jpeg",
            "X-Event-Id": "ev-in-001",
            "X-Camera-Id": "cam_plate",
            "X-Device-Id": "s3_plate_ctrl",
            "X-Frame-Id": "req-plate-ev-in-001",
            "X-Device-Key": "integration-test-key",
            "X-Gate-Id": "IN",
            "X-ROI": "ROI_IN",
        },
    )
    assert r_plate.status_code == 200
    assert r_plate.json()["accepted"] is True
    assert r_plate.json()["workflow_decision"] is None  # Still waiting for face image

    r_face = client.post(
        "/api/device/images",
        content=jpeg_bytes,
        headers={
            "Content-Type": "image/jpeg",
            "X-Event-Id": "ev-in-001",
            "X-Camera-Id": "cam_face",
            "X-Device-Id": "s3_face_cam",
            "X-Frame-Id": "req-face-ev-in-001",
            "X-Device-Key": "integration-test-key",
            "X-Gate-Id": "IN",
            "X-ROI": "ROI_IN",
        },
    )
    assert r_face.status_code == 200
    decision = r_face.json()["workflow_decision"]
    assert decision is not None
    assert decision["decision"] == "Approved"
    assert decision["assigned_slot_id"] == "B1"
    assert decision["flow_type"] == "BOOKING"

    # Verify MQTT OPEN command was emitted on parking/gates/IN/command
    in_cmds = [p for t, p in wf.published_mqtt_messages if t == TOPIC_GATE_IN_COMMAND]
    assert len(in_cmds) == 1
    assert in_cmds[0]["action"] == "OPEN"
    assert in_cmds[0]["assigned_slot_id"] == "B1"

    # 4. S3 controller confirms physical passage after 3s continuous IR clear
    pass_in = wf.handle_mqtt_message(
        TOPIC_GATE_IN_DETECTED,
        {
            "event_id": "ev-in-001",
            "gate_id": "IN",
            "device_id": "s3_plate_ctrl",
            "boot_id": "b001",
            "sequence": 11,
            "event_type": "PASSAGE_CONFIRMED",
        },
    )
    assert pass_in["session_status"] == "Active"
    assert pass_in["parking_status"] == "Parking_pending"

    # 5. S3 controller sends 4-slot IR snapshot with B1 Occupied -> Parked_confirmed
    snap = wf.handle_mqtt_message(
        TOPIC_SLOTS_SNAPSHOT,
        {
            "device_id": "s3_plate_ctrl",
            "boot_id": "b001",
            "sequence": 12,
            "slots": {"A1": "Free", "A2": "Free", "B1": "Occupied", "B2": "Free"},
        },
    )
    assert snap["accepted"] is True
    assert snap["session_transitions"][0]["new_parking_status"] == "Parked_confirmed"

    # 6. Vehicle drives to Gate OUT -> trigger + upload images -> exit approved -> passage confirmed
    trig_out = wf.handle_mqtt_message(
        TOPIC_GATE_OUT_DETECTED,
        {
            "event_id": "ev-out-001",
            "gate_id": "OUT",
            "device_id": "s3_plate_ctrl",
            "boot_id": "b001",
            "sequence": 13,
            "event_type": "DETECTED",
            "ir_stable_detected": True,
        },
    )
    assert trig_out["status"] == "CAPTURE_REQUESTED"

    client.post(
        "/api/device/images",
        content=jpeg_bytes,
        headers={
            "Content-Type": "image/jpeg",
            "X-Event-Id": "ev-out-001",
            "X-Camera-Id": "cam_plate",
            "X-Device-Id": "s3_plate_ctrl",
            "X-Frame-Id": "req-plate-ev-out-001",
            "X-Device-Key": "integration-test-key",
            "X-Gate-Id": "OUT",
            "X-ROI": "ROI_OUT",
        },
    )
    r_out_face = client.post(
        "/api/device/images",
        content=jpeg_bytes,
        headers={
            "Content-Type": "image/jpeg",
            "X-Event-Id": "ev-out-001",
            "X-Camera-Id": "cam_face",
            "X-Device-Id": "s3_face_cam",
            "X-Frame-Id": "req-face-ev-out-001",
            "X-Device-Key": "integration-test-key",
            "X-Gate-Id": "OUT",
            "X-ROI": "ROI_OUT",
        },
    )
    assert r_out_face.status_code == 200
    assert r_out_face.json()["workflow_decision"]["decision"] == "Approved"

    out_cmds = [p for t, p in wf.published_mqtt_messages if t == TOPIC_GATE_OUT_COMMAND]
    assert len(out_cmds) == 1
    assert out_cmds[0]["action"] == "OPEN"

    pass_out = wf.handle_mqtt_message(
        TOPIC_GATE_OUT_DETECTED,
        {
            "event_id": "ev-out-001",
            "gate_id": "OUT",
            "device_id": "s3_plate_ctrl",
            "boot_id": "b001",
            "sequence": 14,
            "event_type": "PASSAGE_CONFIRMED",
        },
    )
    assert pass_out["session_status"] == "Closed"
