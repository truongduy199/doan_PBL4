"""MJPEG framing, session binding and admin-only delivery."""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "src", ROOT / "tests"):
    sys.path.insert(0, str(folder))
from smart_parking.interfaces.http.mjpeg import MjpegParser
from smart_parking.domain.exceptions import DomainException


def part(frame_id, jpeg):
    return (f"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\nX-Frame-Id: {frame_id}\r\n\r\n".encode()
            + jpeg + b"\r\n")


def test_multipart_parser_handles_every_byte_boundary():
    jpeg = b"\xff\xd8" + b"x" * 80
    wire = part("one", jpeg) + part("two", jpeg) + b"--frame--\r\n"
    parser, frames = MjpegParser(), []
    for byte in wire:
        frames.extend(parser.feed(bytes([byte])))
    parser.finish()
    assert frames == [("one", jpeg), ("two", jpeg)]


@pytest.mark.parametrize("wire", [b"x" * 2050, part("x", b"a" * 64).replace(b"64", b"999999999"),
                                 part("x", b"a" * 64)[:-1]])
def test_multipart_parser_rejects_oversized_and_truncated_bodies(wire):
    parser = MjpegParser()
    with pytest.raises(DomainException):
        parser.feed(wire)
        parser.finish()


def test_mjpeg_http_upload_and_admin_delivery():
    from test_gate_runtime import GateRuntimeTests
    runtime = GateRuntimeTests()
    runtime.setUp()
    try:
        session = runtime.wf.request_camera_stream()
        _, encoded = cv2.imencode(".jpg", np.full((120, 160, 3), 127, dtype=np.uint8))
        jpeg = encoded.tobytes()
        body = b"".join(part(f"live-{session['stream_id']}-plate-{i}", jpeg) for i in (1, 2)) + b"--frame--\r\n"
        headers = {"Content-Type": "multipart/x-mixed-replace; boundary=frame", "X-Device-Key": runtime.settings.device_api_key,
                   "X-Event-Id": session["event_id"], "X-Stream-Id": session["stream_id"], "X-Camera-Id": "cam_plate",
                   "X-Device-Id": runtime.settings.controller_device_id, "X-Gate-Id": "IN", "X-ROI": "ROI_IN"}
        runtime.wf.evaluate_turn = Mock(side_effect=AssertionError("MJPEG must never run AI"))
        assert runtime.client.post("/api/device/mjpeg", content=body, headers={**headers, "X-Device-Key": "wrong"}).status_code == 401
        assert runtime.client.post("/api/device/mjpeg", content=body, headers={**headers, "X-Stream-Id": "old"}).status_code == 409
        response = runtime.client.post("/api/device/mjpeg", content=body, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["accepted_frames"] == 2
        assert runtime.wf.camera_snapshots()["stream"]["frames_received"]["cam_plate"] == 2
        runtime.wf.evaluate_turn.assert_not_called()

        url = f"/api/admin/cameras/cam_plate/mjpeg?stream_id={session['stream_id']}"
        assert runtime.client.get(url).status_code == 401
        assert runtime.client.get("/api/admin/cameras/cam_plate/image").status_code == 401
        runtime.client.post("/api/auth/login", json={"username": runtime.settings.demo_user_username, "password": runtime.settings.demo_user_password})
        assert runtime.client.get(url).status_code == 403
        assert runtime.client.get("/api/admin/cameras/cam_plate/image").status_code == 403
        runtime.client.post("/api/auth/login", json={"username": runtime.settings.demo_admin_username, "password": runtime.settings.demo_admin_password})
        metadata = runtime.client.get("/api/admin/cameras?images=0").json()["cameras"][0]
        assert metadata["has_image"] and metadata["image_base64"] is None
        assert runtime.client.get("/api/admin/cameras/cam_plate/image").content == jpeg
        with patch.object(runtime.wf, "camera_jpeg", side_effect=[(True, None, None), (True, 1, jpeg), (False, None, None)]):
            response = runtime.client.get(url)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
        assert "no-store" in response.headers["cache-control"]
        assert jpeg in response.content and response.content.endswith(b"--frame--\r\n")
        runtime.wf.stop_camera_stream()
        assert runtime.client.get(url).status_code == 409
        assert runtime.client.post("/api/device/mjpeg", content=body, headers=headers).status_code == 409
    finally:
        runtime.tearDown()
