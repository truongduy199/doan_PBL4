"""Admin Query & Manual Review Routes (/api/admin/*) restricted strictly to role == 'admin'."""
from __future__ import annotations

from typing import Any, Dict
import asyncio
import time
from smart_parking.domain.exceptions import DomainException

from smart_parking.interfaces.http._compat import APIRouter, Request, Response, StreamingResponse
from smart_parking.interfaces.http.dependencies import get_container, require_admin_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/cameras")
async def get_admin_cameras(request: Request, response: Response) -> Dict[str, Any]:
    require_admin_user(request)
    response.headers["Cache-Control"] = "no-store, private"
    return get_container(request).gate_workflow_service.camera_snapshots(include_images=request.query_params.get("images") != "0")


@router.get("/cameras/{camera_id}/image")
async def get_camera_jpeg(camera_id: str, request: Request) -> Response:
    require_admin_user(request)
    _, _, jpeg = get_container(request).gate_workflow_service.camera_jpeg(camera_id)
    if jpeg is None:
        raise DomainException("Camera image expired.", reason_code="IMAGE_EXPIRED", http_status=404)
    return Response(content=jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store, private"})


@router.get("/cameras/{camera_id}/mjpeg")
async def view_camera_mjpeg(camera_id: str, request: Request) -> Any:
    require_admin_user(request)
    if camera_id not in ("cam_plate", "cam_face"):
        raise DomainException("Unknown camera.", reason_code="INVALID_CAMERA_ID", http_status=404)
    stream_id = request.query_params.get("stream_id", "")
    service = get_container(request).gate_workflow_service
    if not stream_id or not service.camera_jpeg(camera_id, stream_id)[0]:
        raise DomainException("Stream expired.", reason_code="STREAM_EXPIRED", http_status=409)

    async def frames():
        previous, auth_checked = None, 0.0
        while not await request.is_disconnected():
            if time.monotonic() - auth_checked >= 1:
                try:
                    require_admin_user(request)
                except DomainException:
                    break
                auth_checked = time.monotonic()
            active, stamp, jpeg = service.camera_jpeg(camera_id, stream_id)
            if not active:
                break
            if jpeg is not None and stamp != previous:
                previous = stamp
                yield (b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode()
                       + b"\r\n\r\n" + jpeg + b"\r\n")
            await asyncio.sleep(.02)
        yield b"--frame--\r\n"

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store, private", "X-Accel-Buffering": "no"})


@router.post("/cameras/capture")
async def capture_admin_cameras(request: Request) -> Dict[str, Any]:
    require_admin_user(request)
    bridge = getattr(request.app.state, "mqtt_bridge", None)
    if not bridge or not bridge.status().get("connected"):
        raise DomainException("MQTT chưa kết nối; chưa thể yêu cầu chụp.", reason_code="MQTT_DISCONNECTED", http_status=503)
    return get_container(request).gate_workflow_service.request_camera_preview()


@router.post("/cameras/stream")
async def control_admin_camera_stream(request: Request) -> Dict[str, Any]:
    require_admin_user(request)
    body = await request.json()
    service = get_container(request).gate_workflow_service
    if body.get("action") == "STOP":
        return service.stop_camera_stream()
    if body.get("action") != "START":
        raise DomainException("Chọn START hoặc STOP.", reason_code="INVALID_STREAM_ACTION")
    bridge = getattr(request.app.state, "mqtt_bridge", None)
    if not bridge or not bridge.status().get("connected"):
        raise DomainException("MQTT chưa kết nối.", reason_code="MQTT_DISCONNECTED", http_status=503)
    return service.request_camera_stream()


@router.get("/sessions")
async def list_admin_sessions(request: Request) -> Dict[str, Any]:
    """Return active and historical parking sessions combined with booking expiry countdown."""
    require_admin_user(request)
    container = get_container(request)
    qp = request.query_params
    status_filter = qp.get("status") or None
    limit = int(qp.get("limit", 100))
    offset = int(qp.get("offset", 0))
    return container.admin_query_service.list_sessions(
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/bookings")
async def list_admin_bookings(request: Request) -> Dict[str, Any]:
    """Return all current and historical bookings across all users."""
    require_admin_user(request)
    container = get_container(request)
    container.booking_service.expire_overdue_bookings()
    qp = request.query_params
    status_filter = qp.get("status") or None
    limit = int(qp.get("limit", 100))
    offset = int(qp.get("offset", 0))
    return container.admin_query_service.list_bookings(
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/reviews")
async def list_admin_reviews(request: Request) -> Dict[str, Any]:
    """Return gate events and parking sessions requiring manual review."""
    require_admin_user(request)
    container = get_container(request)
    qp = request.query_params
    include_resolved = str(qp.get("include_resolved", "false")).lower() in ("1", "true", "yes")
    return container.admin_query_service.list_reviews(include_resolved=include_resolved)


@router.post("/reviews/{event_id}/decision")
async def submit_admin_review_decision(event_id: str, request: Request) -> Dict[str, Any]:
    """Record ADMIN manual review decision ('APPROVE' or 'DENY') with mandatory audit log."""
    admin_claims = require_admin_user(request)
    container = get_container(request)
    body = await request.json()
    action = str(body.get("action") or "")
    reason = str(body.get("reason") or "")
    command_id = body.get("command_id")
    return container.gate_workflow_service.submit_manual_review(
        event_id=event_id,
        admin_user_id=int(admin_claims["user_id"]),
        action=action,
        reason=reason,
        command_id=str(command_id) if command_id else None,
    )


@router.get("/devices")
async def get_admin_devices(request: Request) -> Dict[str, Any]:
    """Return IR sensor freshness (`last_seen_at`, `last_boot_id`, `last_sequence`) for all 4 slots."""
    require_admin_user(request)
    container = get_container(request)
    return {**container.slot_service.get_admin_devices_health(),
            "gateway": container.gate_workflow_service.diagnostics(),
            "mqtt": getattr(request.app.state, "mqtt_bridge", None).status()
                    if getattr(request.app.state, "mqtt_bridge", None) else {"connected": False, "enabled": False}}


@router.get("/logs")
async def list_admin_logs(request: Request) -> Dict[str, Any]:
    """Return recent sanitized audit logs from `parking_logs` for Admin Dashboard."""
    require_admin_user(request)
    container = get_container(request)
    qp = request.query_params
    limit = int(qp.get("limit", 50))
    session_id = qp.get("session_id") or None
    return container.admin_query_service.list_audit_logs(limit=limit, session_id=session_id)
