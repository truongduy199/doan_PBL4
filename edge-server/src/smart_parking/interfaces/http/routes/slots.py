"""4-Slot Status Route (/api/slots) with Role-Based Privacy Masking."""
from __future__ import annotations

from typing import Any, Dict

from smart_parking.interfaces.http._compat import APIRouter, Request
from smart_parking.interfaces.http.dependencies import get_container, get_current_user

router = APIRouter(prefix="/api", tags=["Slots"])


@router.get("/slots")
async def list_slots(request: Request) -> Dict[str, Any]:
    """
    Return status of the 4 fixed slots (A1, A2, B1, B2) with `server_time`.
    Masks booking/session owner details when called by USER; reveals full details for ADMIN.
    """
    user_claims = get_current_user(request)
    container = get_container(request)
    # Run opportunistic overdue booking expiry check before returning slot snapshot
    container.booking_service.expire_overdue_bookings()
    return container.slot_service.get_slots_view(
        viewer_user_id=int(user_claims["user_id"]),
        viewer_role=str(user_claims["role"]),
    )
