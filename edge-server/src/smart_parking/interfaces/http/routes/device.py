"""Device HTTP Endpoints (`POST /api/device/images` & MQTT bridge endpoints) per Section VII.1 & VIII.2."""
from __future__ import annotations

import base64
import hmac
import asyncio
import json
from typing import Any, Dict

from smart_parking.domain.exceptions import DomainException
from smart_parking.interfaces.http._compat import APIRouter, Request, HAS_FASTAPI
from smart_parking.interfaces.http.dependencies import get_container
from smart_parking.infrastructure.database.mysql_db import utc_now, format_utc_iso

router = APIRouter(prefix="/api/device", tags=["Device IoT"])


@router.post("/mjpeg")
async def upload_device_mjpeg(request: Request) -> Dict[str, Any]:
    from smart_parking.interfaces.http.mjpeg import MjpegParser
    from starlette.requests import ClientDisconnect
    authenticate_device(request)
    if _get_header(request.headers, "content-type") != "multipart/x-mixed-replace; boundary=frame":
        raise DomainException("Expected MJPEG multipart body.", reason_code="INVALID_MJPEG", http_status=415)
    service = get_container(request).gate_workflow_service
    metadata = {key: _get_header(request.headers, header) for key, header in (
        ("event_id", "x-event-id"), ("camera_id", "x-camera-id"), ("device_id", "x-device-id"),
        ("gate_id", "x-gate-id"), ("roi", "x-roi"))}
    stream_id = _get_header(request.headers, "x-stream-id")
    service.validate_stream_upload(stream_id, **metadata)
    parser, accepted = MjpegParser(), 0
    chunks = request.stream().__aiter__()
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(chunks.__anext__(), timeout=5)
            except StopAsyncIteration:
                break
            service.validate_stream_upload(stream_id, **metadata)
            # Bound parser memory even if ASGI groups many network chunks together.
            for offset in range(0, len(chunk), 16384):
                for frame_id, jpeg in parser.feed(chunk[offset:offset + 16384]):
                    await asyncio.to_thread(service.ingest_stream_image, image_bytes=jpeg, frame_id=frame_id, **metadata)
                    accepted += 1
        parser.finish()
    except ClientDisconnect:
        return {"accepted_frames": accepted, "disconnected": True}
    except asyncio.TimeoutError as exc:
        raise DomainException("MJPEG upload idle timeout.", reason_code="STREAM_IDLE", http_status=408) from exc
    return {"accepted_frames": accepted}


def authenticate_device(request: Request) -> None:
    key = get_container(request).settings.device_api_key
    received = _get_header(request.headers, "x-device-key")
    if not key or not hmac.compare_digest(received, key):
        raise DomainException("Invalid device key.", reason_code="DEVICE_AUTH_REQUIRED", http_status=401)


@router.get("/time")
def device_time(request: Request) -> Dict[str, Any]:
    authenticate_device(request)
    now = utc_now()
    return {"server_time": format_utc_iso(now), "epoch_ms": int(now.timestamp() * 1000)}


def _get_header(headers: Dict[str, str], name: str, default: str = "") -> str:
    for key in (name, name.lower(), name.upper()):
        if key in headers and headers[key] is not None:
            return str(headers[key]).strip()
    lower_target = name.lower()
    for k, v in headers.items():
        if k.lower() == lower_target and v is not None:
            return str(v).strip()
    return default


@router.post("/images")
@router.post("/stream")
async def upload_device_image(request: Request) -> Dict[str, Any]:
    """
    Receive fresh JPEG image from ESP32-S3 OV5640 (`cam_plate` or `cam_face`) per Section VII.1 & VIII.2.
    Supports:
    - Raw `image/jpeg` binary body with metadata in HTTP headers (`X-Event-Id`, `X-Camera-Id`, `X-Device-Id`,
      `X-Frame-Id`, `X-Gate-Id`, `X-ROI`) or query params.
    - JSON payload with `image_base64` + metadata fields for easy testing.
    """
    container = get_container(request)
    authenticate_device(request)
    headers = request.headers or {}
    qp = request.query_params or {}

    content_type = _get_header(headers, "content-type", "").lower()
    image_bytes: bytes = b""
    raw_body = bytearray()
    if hasattr(request, "stream"):
        async for chunk in request.stream():
            raw_body.extend(chunk)
            if len(raw_body) > 7 * 1024 * 1024:
                raise DomainException("Image request is too large.", reason_code="IMAGE_TOO_LARGE", http_status=413)
    else:
        raw_body.extend(await request.body())
    if len(raw_body) > 7 * 1024 * 1024:
        raise DomainException("Image request is too large.", reason_code="IMAGE_TOO_LARGE", http_status=413)

    event_id = _get_header(headers, "x-event-id") or qp.get("event_id", "")
    camera_id = _get_header(headers, "x-camera-id") or qp.get("camera_id", "")
    device_id = _get_header(headers, "x-device-id") or qp.get("device_id", "s3_camera")
    frame_id = _get_header(headers, "x-frame-id") or qp.get("frame_id", "frame-1")
    gate_id = _get_header(headers, "x-gate-id") or qp.get("gate_id", "")
    roi = _get_header(headers, "x-roi") or qp.get("roi", "")

    if "application/json" in content_type:
        try:
            body = json.loads(raw_body)
            if not isinstance(body, dict):
                raise ValueError("JSON body must be an object")
        except (ValueError, UnicodeError) as exc:
            raise DomainException("Invalid JSON image request.", reason_code="INVALID_IMAGE_JSON") from exc
        event_id = str(body.get("event_id") or event_id)
        camera_id = str(body.get("camera_id") or camera_id)
        device_id = str(body.get("device_id") or device_id)
        frame_id = str(body.get("frame_id") or frame_id)
        gate_id = str(body.get("gate_id") or gate_id)
        roi = str(body.get("roi") or roi)
        b64_data = body.get("image_base64") or ""
        if b64_data:
            try:
                image_bytes = base64.b64decode(b64_data, validate=True)
            except Exception as exc:
                raise DomainException(
                    f"Không giải mã được chuỗi base64 ảnh: {exc}",
                    reason_code="INVALID_BASE64_IMAGE",
                    http_status=400,
                ) from exc
    else:
        image_bytes = bytes(raw_body)

    kwargs = dict(
        image_bytes=image_bytes,
        event_id=event_id,
        camera_id=camera_id,
        device_id=device_id,
        frame_id=frame_id,
        gate_id=gate_id,
        roi=roi,
    )
    ingest = (container.gate_workflow_service.ingest_stream_image if str(request.url).split("?")[0].endswith("/stream")
              else container.gate_workflow_service.ingest_device_image)
    if HAS_FASTAPI:
        return await asyncio.to_thread(ingest, **kwargs)
    return ingest(**kwargs)
