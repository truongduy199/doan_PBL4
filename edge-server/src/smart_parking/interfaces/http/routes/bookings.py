"""Booking Routes (/api/bookings/*) for 60-minute Slot Reservation & Cancellation."""
from __future__ import annotations

from typing import Any, Dict

from smart_parking.domain.exceptions import DomainException, SlotNotAvailableException
from smart_parking.interfaces.http._compat import APIRouter, Request, Response
from smart_parking.interfaces.http.dependencies import get_container, get_current_user

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("")
async def create_booking(request: Request, response: Response) -> Dict[str, Any]:
    """
    Create a 60-minute slot reservation for the authenticated USER's vehicle.
    Supports `X-Idempotency-Key` header or `idempotency_key` body field to prevent duplicate requests.
    """
    user_claims = get_current_user(request)
    container = get_container(request)
    body = await request.json()

    raw_vehicle_id = body.get("vehicle_id")
    raw_slot_id = body.get("slot_id")
    if raw_vehicle_id is None or not raw_slot_id:
        raise DomainException(
            "Vui lòng cung cấp đầy đủ vehicle_id và slot_id.",
            reason_code="MISSING_BOOKING_FIELDS",
            http_status=400,
        )

    idem_key = (
        request.headers.get("x-idempotency-key")
        or request.headers.get("X-Idempotency-Key")
        or body.get("idempotency_key")
    )

    # Run opportunistic expiry sweep before attempting booking
    container.booking_service.expire_overdue_bookings()

    try:
        result = container.booking_service.create_booking(
            user_id=int(user_claims["user_id"]),
            vehicle_id=int(raw_vehicle_id),
            slot_id=str(raw_slot_id),
            idempotency_key=str(idem_key) if idem_key else None,
        )
        response.status_code = 201
        return result
    except SlotNotAvailableException as exc:
        # Attach latest 4-slot view to 409 Conflict details so UI immediately refreshes
        latest_slots = container.slot_service.get_slots_view(
            viewer_user_id=int(user_claims["user_id"]),
            viewer_role=str(user_claims["role"]),
        )
        exc.details["latest_slots"] = latest_slots["slots"]
        raise


@router.get("/current")
async def get_current_booking(request: Request) -> Dict[str, Any]:
    """
    Return the current effective booking (`Reserved`, `Checkin_pending`, or active `Checked_in`)
    of the authenticated user along with `server_time` and `remaining_seconds`.
    """
    user_claims = get_current_user(request)
    container = get_container(request)
    container.booking_service.expire_overdue_bookings()
    return container.booking_service.get_current_booking(user_id=int(user_claims["user_id"]))


@router.get("/{booking_id}")
async def get_booking_by_id(booking_id: str, request: Request) -> Dict[str, Any]:
    """Return booking detail; only booking owner or ADMIN is permitted."""
    user_claims = get_current_user(request)
    container = get_container(request)
    return container.booking_service.get_booking_detail(
        booking_id=booking_id,
        requester_user_id=int(user_claims["user_id"]),
        requester_role=str(user_claims["role"]),
    )


@router.post("/{booking_id}/cancel")
async def cancel_booking(booking_id: str, request: Request) -> Dict[str, Any]:
    """Cancel a booking if owned by requester (or ADMIN) and still in `Reserved` state."""
    user_claims = get_current_user(request)
    container = get_container(request)
    return container.booking_service.cancel_booking(
        booking_id=booking_id,
        requester_user_id=int(user_claims["user_id"]),
        requester_role=str(user_claims["role"]),
    )
