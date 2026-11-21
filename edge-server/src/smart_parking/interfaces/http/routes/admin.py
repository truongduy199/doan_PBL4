"""Admin Query & Manual Review Routes (/api/admin/*) restricted strictly to role == 'admin'."""
from __future__ import annotations

from typing import Any, Dict

from smart_parking.interfaces.http._compat import APIRouter, Request
from smart_parking.interfaces.http.dependencies import get_container, require_admin_user

router = APIRouter(prefix="/api/admin", tags=["Admin"])


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
