"""Legacy /reviews alias route redirecting to /api/admin/reviews with Admin RBAC check."""
from __future__ import annotations

from typing import Any, Dict

from smart_parking.interfaces.http._compat import APIRouter, Request
from smart_parking.interfaces.http.dependencies import get_container, require_admin_user

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("")
async def list_reviews_legacy(request: Request) -> Dict[str, Any]:
    require_admin_user(request)
    container = get_container(request)
    return container.admin_query_service.list_reviews()
