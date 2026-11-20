"""Auth, User Profile (/api/me), and Personal History (/api/me/history) Routes."""
from __future__ import annotations

from typing import Any, Dict

from smart_parking.interfaces.http._compat import APIRouter, Request, Response
from smart_parking.interfaces.http.dependencies import (
    extract_token_from_request,
    get_container,
    get_current_user,
)

router = APIRouter(prefix="/api", tags=["Auth & Profile"])


@router.post("/auth/login")
async def login(request: Request, response: Response) -> Dict[str, Any]:
    """Authenticate USER or ADMIN and return Bearer JWT + HTTP-only cookie."""
    body = await request.json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    container = get_container(request)
    result = container.auth_service.login(username=username, password=password)

    response.set_cookie(
        key="access_token",
        value=result["access_token"],
        httponly=True,
        samesite="lax",
        max_age=result["expires_in"],
        path="/",
    )
    return result


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> Dict[str, Any]:
    """Revoke current Bearer/cookie token server-side, clear session cookie, and confirm logout."""
    container = get_container(request)
    try:
        token = extract_token_from_request(request)
        container.auth_service.revoke_token(token)
    except Exception:
        pass
    response.delete_cookie(key="access_token", path="/")
    return {"status": "logged_out", "message": "Đã đăng xuất phiên hiện tại."}


@router.get("/me")
async def get_me(request: Request) -> Dict[str, Any]:
    """Return current authenticated user profile, registered vehicles, and face template link status."""
    user_claims = get_current_user(request)
    container = get_container(request)
    return container.auth_service.get_current_user_profile(int(user_claims["user_id"]))


@router.get("/me/history")
async def get_my_history(request: Request) -> Dict[str, Any]:
    """
    Return personal booking history and parking session history of the authenticated user.
    Strictly uses `user_id` from server auth token (never trusts client-supplied user_id).
    """
    user_claims = get_current_user(request)
    container = get_container(request)
    qp = request.query_params
    booking_status = qp.get("booking_status") or None
    session_status = qp.get("session_status") or None
    limit = int(qp.get("limit", 50))
    offset = int(qp.get("offset", 0))
    return container.booking_service.get_user_history(
        user_id=int(user_claims["user_id"]),
        booking_status=booking_status,
        session_status=session_status,
        limit=limit,
        offset=offset,
    )
