"""Camera previews must expire, stay admin-only, and never grant gate permission."""
from pathlib import Path
import sys
from datetime import timedelta
from unittest.mock import Mock

import cv2
import numpy as np
import pytest

EDGE = Path(__file__).resolve().parents[1]
for folder in (EDGE / "src", EDGE / "tests", EDGE):
    sys.path.insert(0, str(folder))

from smart_parking.application.services.gate_workflow_service import GateWorkflowService
from smart_parking.config.settings import Settings
from smart_parking.domain.exceptions import DomainException
from smart_parking.infrastructure.database.mysql_db import utc_now


@pytest.fixture
def preview():
    now = utc_now()
    service = GateWorkflowService(None, settings=Settings(device_api_key="test"))
    result = service.request_camera_preview(now)
    ok, image = cv2.imencode(".jpg", np.full((120, 160, 3), 127, dtype=np.uint8))
    assert ok
    return service, now, result["event_id"], image.tobytes()


def upload(service, now, event, jpeg, camera="plate", **overrides):
    args = dict(image_bytes=jpeg, event_id=event, camera_id="cam_" + camera,
                device_id="s3_plate_ctrl" if camera == "plate" else "s3_face_cam",
                frame_id=f"req-{camera}-{event}", gate_id="IN", roi="ROI_IN", now_utc=now)
    args.update(overrides)
    return service.ingest_device_image(**args)


def test_real_jpegs_preview_never_evaluates_or_emits_gate_commands(preview):
    service, now, event, jpeg = preview
    service.evaluate_turn = Mock(side_effect=AssertionError("Preview must not run gate AI"))
    assert upload(service, now, event, jpeg)["preview"]
    assert upload(service, now, event, jpeg, "face")["preview"]
    assert len(service._camera_images) == 2
    assert service._turns == {} and service._commands == {}
    assert all(topic.endswith("/capture") for topic, _ in service.published_mqtt_messages)
    service.evaluate_turn.assert_not_called()


def test_preview_rejects_wrong_device_and_expired_requests(preview):
    service, now, event, jpeg = preview
    with pytest.raises(DomainException) as error:
        upload(service, now, event, jpeg, device_id="s3_face_cam")
    assert error.value.reason_code == "CAPTURE_METADATA_MISMATCH"
    with pytest.raises(DomainException) as error:
        upload(service, now + timedelta(seconds=6), event, jpeg)
    assert error.value.reason_code == "CAPTURE_EXPIRED"
    assert not service._camera_images


def test_image_bytes_are_removed_at_retention_deadline(preview):
    service, now, event, jpeg = preview
    upload(service, now, event, jpeg)
    assert service.camera_snapshots(now)["cameras"][0]["image_base64"]
    result = service.camera_snapshots(now + timedelta(seconds=30))
    assert all(item["image_base64"] is None for item in result["cameras"])
    assert not service._camera_images


def test_preview_does_not_interrupt_an_active_gate_turn(preview):
    service, now, _, _ = preview
    service._active_event_id = "actual-car"
    with pytest.raises(DomainException) as error:
        service.request_camera_preview(now)
    assert error.value.reason_code == "CAMERA_BUSY"
    assert service._active_event_id == "actual-car"


def test_admin_api_does_not_expose_images_to_user_or_anonymous():
    from test_gate_runtime import GateRuntimeTests
    runtime = GateRuntimeTests()
    runtime.setUp()
    try:
        assert runtime.client.get("/api/admin/cameras").status_code == 401
        assert runtime.client.post("/api/admin/cameras/capture").status_code == 401
        assert runtime.client.post("/api/admin/cameras/stream", json={"action": "START"}).status_code == 401
        login = runtime.client.post("/api/auth/login", json={"username": runtime.settings.demo_user_username,
                                                           "password": runtime.settings.demo_user_password})
        user = {"Authorization": "Bearer " + login.json()["access_token"]}
        assert runtime.client.get("/api/admin/cameras", headers=user).status_code == 403
        assert runtime.client.post("/api/admin/cameras/capture", headers=user).status_code == 403
        assert runtime.client.post("/api/admin/cameras/stream", json={"action": "STOP"}, headers=user).status_code == 403
        admin = runtime.client.post("/api/auth/login", json={"username": runtime.settings.demo_admin_username,
                                                            "password": runtime.settings.demo_admin_password})
        response = runtime.client.get("/api/admin/cameras", headers={"Authorization": "Bearer " + admin.json()["access_token"]})
        assert response.status_code == 200
        assert "no-store" in response.headers["cache-control"]
    finally:
        runtime.tearDown()


def stream_upload(service, now, session, jpeg, number, camera="plate", **overrides):
    args = dict(image_bytes=jpeg, event_id=session["event_id"], camera_id="cam_" + camera,
                device_id="s3_plate_ctrl" if camera == "plate" else "s3_face_cam",
                frame_id=f"live-{session['stream_id']}-{camera}-{number}", gate_id="IN", roi="ROI_IN", now_utc=now)
    args.update(overrides)
    return service.ingest_stream_image(**args)


def test_stream_accepts_successive_frames_without_ai_or_gate_commands(preview):
    service, now, _, jpeg = preview
    session = service.request_camera_stream(now)
    service.evaluate_turn = Mock(side_effect=AssertionError("Stream must not run gate AI"))
    for n in (1, 2, 3):
        stream_upload(service, now + timedelta(milliseconds=500 * n), session, jpeg, n)
        stream_upload(service, now + timedelta(milliseconds=500 * n), session, jpeg, n, "face")
    assert service.camera_snapshots(now + timedelta(seconds=2))["stream"]["frames_received"] == {"cam_plate": 3, "cam_face": 3}
    assert not service._turns and not service._commands
    assert all(not topic.endswith("/command") for topic, _ in service.published_mqtt_messages)
    service.evaluate_turn.assert_not_called()


def test_stream_rejects_wrong_identity_old_frames_and_wrong_session(preview):
    service, now, _, jpeg = preview
    session = service.request_camera_stream(now)
    stream_upload(service, now, session, jpeg, 2)
    with pytest.raises(DomainException) as error:
        stream_upload(service, now, session, jpeg, 1)
    assert error.value.reason_code == "STALE_STREAM_FRAME"
    for overrides in ({"device_id": "s3_face_cam"}, {"frame_id": "live-another-session-plate-3"},
                      {"gate_id": "OUT"}, {"roi": "ROI_OUT"}):
        with pytest.raises(DomainException):
            stream_upload(service, now, session, jpeg, 3, **overrides)
    assert service._camera_stream["frames_received"]["cam_plate"] == 1


def test_stop_and_timeout_reject_late_stream_frames(preview):
    service, now, _, jpeg = preview
    session = service.request_camera_stream(now)
    service.stop_camera_stream()
    with pytest.raises(DomainException) as error:
        stream_upload(service, now, session, jpeg, 1)
    assert error.value.reason_code == "STREAM_EXPIRED"
    session = service.request_camera_stream(now)
    with pytest.raises(DomainException) as error:
        stream_upload(service, now + timedelta(seconds=31), session, jpeg, 1)
    assert error.value.reason_code == "STREAM_EXPIRED"
    assert service._camera_stream is None


def test_real_ir_event_starts_stream_and_vehicle_departure_stops_it():
    from test_gate_runtime import GateRuntimeTests
    runtime = GateRuntimeTests(); runtime.setUp()
    try:
        runtime.detect("real-ir-event")
        assert runtime.wf._camera_stream["event_id"] == "real-ir-event"
        assert not runtime.wf._camera_stream["preview"]
        runtime.wf.handle_gate_detected("real-ir-event", "IN", boot_id="test-boot",
                                       event_type="VEHICLE_LEFT_BEFORE_DECISION", now_utc=runtime.now)
        assert runtime.wf._camera_stream is None
        stops = [payload for topic, payload in runtime.wf.published_mqtt_messages
                 if topic.endswith("/stream") and payload["action"] == "STOP"]
        assert len(stops) == 2
    finally:
        runtime.tearDown()


def test_stream_renewal_needs_matching_recent_controller_heartbeat(preview):
    from smart_parking.application.services.gate_workflow_service import GateTurnContext
    from smart_parking.infrastructure.database.mysql_db import format_utc_iso
    service, now, _, _ = preview
    service._turns["gate-event"] = GateTurnContext("gate-event", "IN", "s3_plate_ctrl", "boot", 1, "ROI_IN", now, state="REVIEW")
    service._active_event_id = "gate-event"
    service._start_camera_stream("gate-event", "IN", now)
    service.maintain(now + timedelta(seconds=11))
    assert service._camera_stream["expires_at"] == now + timedelta(seconds=30)
    service._device_status["s3_plate_ctrl"] = {"received_at": format_utc_iso(now + timedelta(seconds=12)), "gate_in_event_id": "gate-event"}
    service.maintain(now + timedelta(seconds=12))
    assert service._camera_stream["expires_at"] == now + timedelta(seconds=42)


def test_camera_ai_summary_omits_embeddings_and_only_reports_committed_entry(preview):
    import json
    from types import SimpleNamespace
    from smart_parking.application.services.gate_workflow_service import GateTurnContext
    from smart_parking.ai.face.pipeline import FacePipelineResult
    service, now, event, jpeg = preview
    upload(service, now, event, jpeg)
    upload(service, now, event, jpeg, "face")
    turn = GateTurnContext(event, "IN", "s3_plate_ctrl", "boot", 1, "ROI_IN", now)
    service._turns[event] = turn
    vector = np.zeros(512, np.float32)
    vector[0] = 1
    turn.plate_outcome = SimpleNamespace(ok=True, reason_code="OK", message="Valid", normalized_plate="37AF67769",
                                        display_plate="37AF-677.69", raw_text="37AF67769")
    turn.face_result = FacePipelineResult(True, "OK", "Valid face", vector, .9, "Passed", .99, valid_sample_count=1)
    turn.last_decision = {"decision": "Review_required", "session_id": "existing-session"}
    cameras = service.camera_snapshots(now, include_images=False)["cameras"]
    assert cameras[0]["recognition"]["plate_number"] == "37AF67769"
    assert cameras[1]["recognition"]["liveness_status"] == "Passed"
    assert not cameras[1]["recognition"]["template_saved"]
    assert "embedding" not in json.dumps(cameras)
    turn.last_decision = {"decision": "Approved", "session_id": "entry-session"}
    assert service.camera_snapshots(now)["cameras"][1]["recognition"]["template_saved"]
    turn.gate_id = "OUT"
    assert not service.camera_snapshots(now)["cameras"][1]["recognition"]["template_saved"]


@pytest.mark.parametrize("plate_available", [True, False])
def test_ai_readiness_requires_warm_plate_models(preview, tmp_path, plate_available):
    from unittest.mock import patch
    service, _, _, _ = preview
    service.settings.face_model_root = str(tmp_path)
    pack = tmp_path / "models" / service.settings.face_model_pack
    pack.mkdir(parents=True)
    (pack / "local-test.onnx").touch()
    (tmp_path / "addons").mkdir()
    (tmp_path / "addons" / "liveness.onnx").touch()
    service.plate_pipeline = Mock()
    if not plate_available:
        service.plate_pipeline._ensure_reader.side_effect = RuntimeError("Missing local weights")
    with patch("smart_parking.ai.face.insightface_adapter.InsightFaceAdapter") as adapter:
        adapter.return_value.initialize.return_value = True
        service.initialize_ai()
    service.plate_pipeline._ensure_reader.assert_called_once()
    assert service.ai_status == ("READY" if plate_available else "PLATE_MODEL_UNAVAILABLE")


def test_burst_capture_waits_for_three_unique_frames_from_both_cameras():
    from test_gate_runtime import GateRuntimeTests
    runtime = GateRuntimeTests()
    runtime.setUp()
    try:
        runtime.settings.capture_sample_count = 3
        runtime.detect("burst-event")
        commands = [(topic, body) for topic, body in runtime.wf.published_mqtt_messages if topic.endswith("/capture")]
        assert len(commands) == 2
        runtime.wf.evaluate_turn = Mock(return_value={"decision": "Review_required"})
        _, encoded = cv2.imencode(".jpg", np.full((120, 160, 3), 127, np.uint8))
        for index in range(6):
            commands = [(topic, body) for topic, body in runtime.wf.published_mqtt_messages if topic.endswith("/capture")]
            topic, body = commands[index]
            camera = "cam_plate" if "/plate/" in topic else "cam_face"
            args = dict(image_bytes=encoded.tobytes(), event_id="burst-event", camera_id=camera,
                        device_id="s3_plate_ctrl" if camera == "cam_plate" else "s3_face_cam",
                        frame_id=body["frame_id"], gate_id="IN", roi="ROI_IN", now_utc=runtime.now)
            runtime.wf.ingest_device_image(**args)
            if index == 0:
                assert runtime.wf.ingest_device_image(**args)["duplicate_frame"]
            if index < 5:
                runtime.wf.evaluate_turn.assert_not_called()
        runtime.wf.evaluate_turn.assert_called_once()
        assert len(runtime.wf._turns["burst-event"].plate_frames) == 3
        assert len(runtime.wf._turns["burst-event"].face_frames) == 3
        with pytest.raises(DomainException):
            runtime.wf.ingest_device_image(**{**args, "frame_id": "req-face-burst-event-4"})
    finally:
        runtime.tearDown()


def test_three_frame_vote_requires_two_matching_reads():
    from dataclasses import replace
    from smart_parking.ai.plate.pipeline import PlatePipeline, PlateRecognitionOutcome
    good = PlateRecognitionOutcome(True, "OK", "OK", "37AF67769", "37AF67769", "37AF-677.69",
                                   .9, .9, (1, 1, 100, 50), "test", "test", 1)
    wrong = replace(good, normalized_plate="37AF67729", raw_text="37AF67729")
    invalid = replace(good, ok=False, reason_code="NO_PLATE_DETECTED", normalized_plate="")
    pipeline = PlatePipeline(reader=Mock())
    frames = [np.zeros((10, 10, 3), np.uint8)] * 3
    pipeline.process_frame = Mock(side_effect=[good, wrong, good])
    assert pipeline.process_frames(frames).normalized_plate == "37AF67769"
    pipeline.process_frame = Mock(side_effect=[good, invalid, invalid])
    assert pipeline.process_frames(frames).reason_code == "PLATE_INSUFFICIENT_CONSENSUS"


def test_face_burst_does_not_combine_different_people():
    from dataclasses import replace
    from smart_parking.ai.face.pipeline import FacePipeline, FacePipelineResult
    a, b = np.zeros(512, np.float32), np.zeros(512, np.float32)
    a[0], b[1] = 1, 1
    good = FacePipelineResult(True, "OK", "OK", a, .9, "Passed", .99)
    pipeline = FacePipeline()
    frames = [np.zeros((10, 10, 3), np.uint8)] * 3
    pipeline.process_frame = Mock(side_effect=[good, good, replace(good, embedding=b)])
    assert pipeline.process_frames(frames, min_valid_samples=2).reason_code == "FACE_SAMPLES_INCONSISTENT"
    pipeline.process_frame = Mock(side_effect=[good, good, good])
    result = pipeline.process_frames(frames, min_valid_samples=2)
    assert result.ok and result.valid_sample_count == 3
