"""Hardware-free orchestration regression tests; real repositories + isolated test DB.

AI outcomes are injected. These tests do not measure recognition accuracy or GPIO timing.
Run: python -m unittest discover -s edge-server/tests -p test_gate_runtime.py -v
"""
from pathlib import Path
import sys
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "src", ROOT / "tests", ROOT):
    sys.path.insert(0, str(directory))

from fakes.fake_mysql_db import SandboxMySQLTestDatabase
from scripts.seed_demo_data import seed_demo_data, make_deterministic_l2_vector
from smart_parking.ai.face.pipeline import FacePipelineResult
from smart_parking.ai.plate.pipeline import PlateRecognitionOutcome, _LP_MODULE_DIR
from smart_parking.config.constants import DEFAULT_FACE_MODEL_ID, DEFAULT_FACE_MODEL_VERSION, DEFAULT_FACE_CONFIG_VERSION
from smart_parking.config.settings import Settings
from smart_parking.domain.exceptions import DomainException
from smart_parking.infrastructure.database.mysql_db import utc_now
from smart_parking.interfaces.http.dependencies import build_container
from smart_parking.interfaces.http.app import LocalTestClient, create_app
from smart_parking.application.services.gate_workflow_service import TOPIC_GATE_IN_COMMAND
from smart_parking.infrastructure.mqtt.mqtt_bridge import MqttGateBridge


class GateRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.now = utc_now()
        self.settings = Settings(device_api_key="test-device-key", slot_stale_seconds=300,
                                 capture_sample_count=1, capture_timeout_seconds=5)
        self.db = SandboxMySQLTestDatabase(self.settings)
        self.c = build_container(settings=self.settings, db=self.db)
        self.seed = seed_demo_data(uow=self.c.uow, cipher=self.c.cipher, settings=self.settings,
                                   with_test_fixtures=True, init_slots_free=True, now_utc=self.now)
        self.wf = self.c.gate_workflow_service
        self.client = LocalTestClient(create_app(container=self.c, enable_background_worker=False))
        self.face = FacePipelineResult(True, "OK", "OK", make_deterministic_l2_vector(27), .95,
                                      "Passed", .95, DEFAULT_FACE_MODEL_ID, DEFAULT_FACE_MODEL_VERSION,
                                      DEFAULT_FACE_CONFIG_VERSION)
        self.plate = PlateRecognitionOutcome(True, "OK", "OK", "43A88888", "43A88888", "43A-888.88",
                                            .95, .95, (1, 1, 100, 50), "test", "test", 1.0)

    def tearDown(self):
        self.db._raw_conn.close()

    def detect(self, event="ev-in", gate="IN", at=None):
        return self.wf.handle_gate_detected(event, gate, boot_id="test-boot", now_utc=at or self.now)

    def decide(self, event="ev-in", face=None, plate=None):
        return self.wf.evaluate_turn(event, plate_outcome_override=plate or self.plate,
                                     face_result_override=face or self.face, now_utc=self.now)

    def test_walkin_entry_parking_exit_and_no_duplicate_open(self):
        self.detect()
        entered = self.decide()
        self.assertEqual(entered["decision"], "Approved")
        self.decide()
        self.assertEqual(sum(t == TOPIC_GATE_IN_COMMAND for t, _ in self.wf.published_mqtt_messages), 1)
        passed = self.wf.handle_gate_detected("ev-in", "IN", boot_id="test-boot", event_type="PASSAGE_CONFIRMED", now_utc=self.now)
        self.assertEqual(passed["session_status"], "Active")
        self.detect("ev-next")
        self.assertEqual(self.wf._turns["ev-next"].state, "QUEUED")
        slots = {s: "Free" for s in ("A1", "A2", "B1", "B2")}
        slots[entered["assigned_slot_id"]] = "Occupied"
        self.wf.handle_mqtt_message("parking/slots/snapshot", {"device_id": "s3_plate_ctrl", "boot_id": "test-boot",
                                    "sequence": 30, "slots": slots}, self.now)
        self.assertEqual(self.wf._turns["ev-next"].state, "CAPTURING")
        self.wf.handle_gate_detected("ev-next", "IN", boot_id="test-boot", event_type="VEHICLE_LEFT_BEFORE_DECISION", now_utc=self.now)
        self.detect("ev-out", "OUT")
        exited = self.decide("ev-out")
        self.assertEqual(exited["decision"], "Approved")
        closed = self.wf.handle_gate_detected("ev-out", "OUT", boot_id="test-boot", event_type="PASSAGE_CONFIRMED", now_utc=self.now)
        self.assertEqual(closed["session_status"], "Closed")

    def test_capture_timeout_releases_recognition_queue(self):
        self.detect()
        self.detect("ev-out", "OUT")
        self.wf.maintain(self.now + timedelta(seconds=6))
        self.assertEqual(self.wf._turns["ev-in"].state, "REVIEW")
        self.assertEqual(self.wf._active_event_id, "ev-out")
        self.assertFalse(any(p.get("action") == "OPEN" for _, p in self.wf.published_mqtt_messages))

    def test_database_error_holds_new_entries(self):
        with patch.object(self.wf.gate_data_service.uow, "run_transactional", side_effect=RuntimeError("offline")):
            self.assertEqual(self.detect()["status"], "QUEUED_WAITING_TURN")

    def test_passage_without_permission_and_wrong_gate_rejected(self):
        self.detect()
        with self.assertRaises(DomainException):
            self.wf.handle_gate_detected("ev-in", "IN", boot_id="test-boot", event_type="PASSAGE_CONFIRMED", now_utc=self.now)
        with self.assertRaises(DomainException):
            self.detect("ev-in", "OUT")

    def test_cancelled_turn_cannot_be_evaluated(self):
        self.detect()
        self.wf.handle_gate_detected("ev-in", "IN", boot_id="test-boot", event_type="VEHICLE_LEFT_BEFORE_DECISION", now_utc=self.now)
        with self.assertRaises(DomainException):
            self.decide()

    def test_liveness_failure_requires_review_without_session(self):
        self.detect()
        bad = FacePipelineResult(False, "LIVENESS_FAILED", "failed", None, None, "Failed", .1,
                                 DEFAULT_FACE_MODEL_ID, DEFAULT_FACE_MODEL_VERSION, DEFAULT_FACE_CONFIG_VERSION)
        self.assertEqual(self.decide(face=bad)["decision"], "Review_required")
        admin = self.c.auth_service.login("admin", self.settings.demo_admin_password)["user"]["user_id"]
        with self.assertRaises(DomainException) as cm:
            self.wf.submit_manual_review("ev-in", admin, "APPROVE", "test", now_utc=self.now)
        self.assertEqual(cm.exception.reason_code, "ENTRY_TEMPLATE_REQUIRED")

    def test_http_device_auth_and_admin_rbac(self):
        self.assertEqual(self.client.post("/api/device/images", content=b"bad").status_code, 401)
        self.assertEqual(self.client.get("/api/device/time", headers={"X-Device-Key": "test-device-key"}).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/devices").status_code, 401)

    def test_mqtt_payload_validation_dedup_and_ack_matching(self):
        payload = {"device_id": "s3_plate_ctrl", "boot_id": "test-boot", "sequence": 1,
                   "event_id": "ev-in", "gate_id": "IN", "ir_stable_detected": True}
        self.wf.handle_mqtt_message("parking/gates/IN/detected", payload, self.now)
        self.assertTrue(self.wf.handle_mqtt_message("parking/gates/IN/detected", payload, self.now)["ignored"])
        with self.assertRaises(DomainException):
            self.wf.handle_mqtt_message("parking/gates/OUT/detected", payload, self.now)
        self.decide()
        command = next(p for t, p in self.wf.published_mqtt_messages if t == TOPIC_GATE_IN_COMMAND)
        ack = {**payload, "sequence": 2, "command_id": command["command_id"], "accepted": True, "servo_command_issued": True}
        self.wf.handle_mqtt_message("parking/devices/s3_plate_ctrl/ack", ack, self.now)
        self.assertEqual(self.wf._turns["ev-in"].state, "APPROVED")
        self.assertEqual(self.wf._commands[command["command_id"]]["delivery_status"], "ACK_ACCEPTED")

    def test_disconnect_is_reported_and_does_not_replay_open(self):
        bridge = MqttGateBridge(self.wf)
        self.detect()
        self.decide()
        self.assertIn("PUBLISH_FAILED", [c["delivery_status"] for c in self.wf._commands.values()])
        self.assertFalse(bridge.status()["connected"])

    def test_local_plate_module_path_and_roi_validation(self):
        self.assertTrue(_LP_MODULE_DIR.is_dir())
        with self.assertRaises(ValueError):
            Settings(plate_roi_in="0,0,-1,10")

    def test_backend_restart_recovers_passage_without_reopening(self):
        self.detect()
        self.decide()
        self.wf._turns.clear()
        self.wf._active_event_id = None
        passed = self.wf.handle_gate_detected("ev-in", "IN", boot_id="test-boot", event_type="PASSAGE_CONFIRMED", now_utc=self.now)
        self.assertEqual(passed["session_status"], "Active")
        self.assertEqual(sum(t == TOPIC_GATE_IN_COMMAND for t, _ in self.wf.published_mqtt_messages), 1)

    def test_capture_pair_metadata_dedup_and_expiry(self):
        # Decoder double isolates protocol rules; this does not test real JPEG decoding.
        decoder = SimpleNamespace(imdecode=lambda *_: np.zeros((240, 320, 3), dtype=np.uint8), IMREAD_COLOR=1)
        self.wf.plate_pipeline = SimpleNamespace(process_frames=lambda *_a, **_k: self.plate)
        self.wf.face_pipeline = SimpleNamespace(process_frames=lambda *_a, **_k: self.face)
        self.detect()
        def upload(camera, frame=None, gate="IN", at=None):
            return self.wf.ingest_device_image(b"\xff\xd8" + b"x" * 98, "ev-in", f"cam_{camera}",
                    "s3_plate_ctrl" if camera == "plate" else "s3_face_cam",
                    frame or f"req-{camera}-ev-in", gate, "ROI_IN", now_utc=at or self.now)
        with patch.dict(sys.modules, {"cv2": decoder}):
            with self.assertRaises(DomainException): upload("plate", frame="old-frame")
            with self.assertRaises(DomainException): upload("plate", gate="OUT")
            with self.assertRaises(DomainException): upload("plate", at=self.now + timedelta(seconds=6))
            self.assertIsNone(upload("plate")["workflow_decision"])
            self.assertEqual(upload("face")["workflow_decision"]["decision"], "Approved")
            self.assertTrue(upload("face")["duplicate_frame"])
        self.assertEqual(sum(t == TOPIC_GATE_IN_COMMAND for t, _ in self.wf.published_mqtt_messages), 1)

    def test_manual_booking_review_creates_session_before_command(self):
        user = self.seed["demo_user"]
        booking = self.c.booking_service.create_booking(user_id=user["user_id"], vehicle_id=user["vehicle_id"], slot_id="B1", now_utc=self.now)
        self.detect()
        plate = PlateRecognitionOutcome(True, "OK", "OK", "43A12345", "43A12345", "43A-123.45", .95, .95,
                                         (1, 1, 100, 50), "test", "test", 1.0)
        self.assertEqual(self.decide(plate=plate)["decision"], "Review_required")
        admin = self.c.auth_service.login("admin", self.settings.demo_admin_password)["user"]["user_id"]
        approved = self.wf.submit_manual_review("ev-in", admin, "APPROVE", "Physically verified driver", now_utc=self.now)
        self.assertIsNotNone(approved["session_id"])
        cmd = [p for t, p in self.wf.published_mqtt_messages if t == TOPIC_GATE_IN_COMMAND and p["action"] == "OPEN"][-1]
        self.assertEqual(cmd["assigned_slot_id"], "B1")
        self.assertEqual(self.wf._turns["ev-in"].state, "APPROVED")
        with self.assertRaises(DomainException):
            self.wf.submit_manual_review("ev-in", admin, "APPROVE", "Duplicate click", now_utc=self.now)

    def test_unacknowledged_command_expires_without_retry(self):
        self.detect()
        self.decide()
        count = len(self.wf.published_mqtt_messages)
        status = self.wf.diagnostics(self.now + timedelta(seconds=9))
        self.assertEqual(status["commands"][-1]["delivery_status"], "ACK_TIMEOUT")
        self.assertEqual(len(self.wf.published_mqtt_messages), count)

    def test_missing_face_model_does_not_download_or_accept(self):
        self.settings.face_model_root = "definitely-not-present"
        self.wf.initialize_ai()
        self.assertEqual(self.wf.ai_status, "FACE_MODEL_MISSING")
        self.assertIsNone(self.wf.face_pipeline.adapter)

    def test_vehicle_leaves_while_ai_is_running(self):
        self.detect()
        def plate_ai(*_a, **_kw):
            self.wf.handle_gate_detected("ev-in", "IN", boot_id="test-boot", event_type="VEHICLE_LEFT_BEFORE_DECISION", now_utc=self.now)
            return self.plate
        self.wf.plate_pipeline = SimpleNamespace(process_frames=plate_ai)
        self.wf.face_pipeline = SimpleNamespace(process_frames=lambda *_a, **_k: self.face)
        with self.assertRaises(DomainException):
            self.wf.evaluate_turn("ev-in", now_utc=self.now)
        self.assertFalse(any(p.get("action") == "OPEN" for _, p in self.wf.published_mqtt_messages))

    def test_retired_boot_snapshot_cannot_replace_current_state(self):
        topic = "parking/slots/snapshot"
        payload = {"device_id": "s3_plate_ctrl", "boot_id": "boot-a", "sequence": 1,
                   "slots": {s: "Free" for s in ("A1", "A2", "B1", "B2")}}
        self.wf.handle_mqtt_message(topic, payload, self.now)
        self.wf.handle_mqtt_message(topic, {**payload, "boot_id": "boot-b"}, self.now)
        with self.assertRaises(DomainException) as cm:
            self.wf.handle_mqtt_message(topic, {**payload, "sequence": 99}, self.now)
        self.assertEqual(cm.exception.reason_code, "RETIRED_DEVICE_BOOT")

    def test_event_identifier_respects_database_char36(self):
        self.assertEqual(self.detect("e" * 36)["status"], "CAPTURE_REQUESTED")
        with self.assertRaises(DomainException) as cm:
            self.detect("e" * 37, "OUT")
        self.assertEqual(cm.exception.reason_code, "INVALID_DEVICE_EVENT")


if __name__ == "__main__":
    unittest.main()
