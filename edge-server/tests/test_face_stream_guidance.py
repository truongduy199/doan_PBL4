"""Live hints are advisory, bounded and independent of gate decisions."""
import sys
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_parking.ai.face.pipeline import FacePipeline
from smart_parking.application.services.gate_workflow_service import GateWorkflowService
from smart_parking.config.settings import Settings
from smart_parking.infrastructure.database.mysql_db import utc_now


def test_detector_only_reports_pose_and_multiple_faces_without_identity():
    app = SimpleNamespace(det_model=SimpleNamespace(detect=Mock()), get=Mock(side_effect=AssertionError("No identity extraction")))
    pipeline = FacePipeline(adapter=SimpleNamespace(app=app))
    image = np.full((480, 640, 3), 128, np.uint8)
    app.det_model.detect.return_value = (np.empty((0, 5)), None)
    assert pipeline.stream_guidance(image)["reason_code"] == "NO_FACE"
    app.det_model.detect.return_value = (np.ones((2, 5)), None)
    assert pipeline.stream_guidance(image)["reason_code"] == "MULTIPLE_FACES"
    app.det_model.detect.return_value = (np.array([[200, 100, 400, 350, .99]]), np.array([[[240, 170], [350, 170], [310, 235], [265, 295], [340, 295]]]))
    image[:, ::2] = 90
    assert pipeline.stream_guidance(image)["reason_code"] == "POSE_READY"
    app.det_model.detect.return_value[1][0, 2] = [385, 235]
    assert pipeline.stream_guidance(image)["reason_code"] == "FACE_QUALITY_FAILED"
    app.get.assert_not_called()


def make_stream():
    now = utc_now()
    wf = GateWorkflowService(None, settings=Settings())
    wf.face_pipeline = SimpleNamespace(stream_guidance=Mock(return_value={"ok": True, "reason_code": "POSE_READY", "message": "ready"}))
    wf._start_camera_stream("view-test", "IN", now, preview=True)
    _, jpg = cv2.imencode(".jpg", np.full((120, 160, 3), 127, np.uint8))
    stream = wf._camera_stream["stream_id"]
    def upload(seq, at):
        wf.ingest_stream_image(jpg.tobytes(), "view-test", "cam_face", wf.settings.face_camera_device_id,
                               f"live-{stream}-face-{seq}", "IN", "ROI_IN", now_utc=at)
    return wf, now, upload


def test_latest_frame_throttle_gate_priority_and_no_database_or_commands():
    wf, now, upload = make_stream()
    upload(1, now)
    upload(2, now)
    before = list(wf.published_mqtt_messages)
    wf._gate_inference_waiters = 1
    wf.update_face_guidance(now)
    wf.face_pipeline.stream_guidance.assert_not_called()
    wf._gate_inference_waiters = 0
    wf._inference_lock.acquire()
    wf.update_face_guidance(now)
    wf._inference_lock.release()
    wf.face_pipeline.stream_guidance.assert_not_called()
    wf.update_face_guidance(now)
    assert wf._guidance_frame_key[1] == 2
    wf.update_face_guidance(now + timedelta(seconds=1))
    assert wf.face_pipeline.stream_guidance.call_count == 1
    upload(3, now + timedelta(seconds=.1))
    wf.update_face_guidance(now + timedelta(seconds=.1))
    assert wf.face_pipeline.stream_guidance.call_count == 1
    wf.update_face_guidance(now + timedelta(seconds=.6))
    assert wf.face_pipeline.stream_guidance.call_count == 2
    assert wf.camera_snapshots(now + timedelta(seconds=.7))["cameras"][1]["guidance"]["reason_code"] == "POSE_READY"
    assert wf.camera_snapshots(now + timedelta(seconds=4))["cameras"][1]["guidance"]["reason_code"] == "WAITING_FRAME"
    assert list(wf.published_mqtt_messages) == before
    assert not wf._turns and not wf._commands
    wf._stop_camera_stream()
    assert wf._face_guidance is None
    assert "guidance" not in wf.camera_snapshots(now + timedelta(seconds=4))["cameras"][1]


def test_stopped_or_changed_stream_discards_inflight_result():
    wf, now, upload = make_stream()
    upload(1, now)
    def stop(*args, **kwargs):
        wf._stop_camera_stream()
        return {"ok": True, "reason_code": "POSE_READY", "message": "old"}
    wf.face_pipeline.stream_guidance.side_effect = stop
    wf.update_face_guidance(now)
    assert wf._face_guidance is None
    assert wf._inference_lock.acquire(blocking=False)
    wf._inference_lock.release()


def test_slow_detection_reduces_hint_frequency():
    from unittest.mock import patch
    wf, now, upload = make_stream()
    upload(1, now)
    with patch("smart_parking.application.services.gate_workflow_service.time.perf_counter", side_effect=[10, 10.4]):
        wf.update_face_guidance(now)
    assert abs(wf._guidance_interval_seconds - 1.6) < .001
    upload(2, now + timedelta(seconds=.7))
    wf.update_face_guidance(now + timedelta(seconds=.7))
    assert wf.face_pipeline.stream_guidance.call_count == 1
