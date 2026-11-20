"""HTTP Dependencies & Service Container for FastAPI Routes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from smart_parking.application.services.auth_service import AuthService
from smart_parking.application.services.booking_service import BookingService
from smart_parking.application.services.event_service import RealtimeEventBus
from smart_parking.application.services.gate_data_service import GateDataService
from smart_parking.application.services.retention_service import RetentionService
from smart_parking.application.services.session_service import AdminQueryService
from smart_parking.application.services.slot_service import SlotService
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.enums import UserRole
from smart_parking.domain.exceptions import AuthenticationException, AuthorizationException
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork
from smart_parking.infrastructure.security.embedding_cipher import EmbeddingCipher
from smart_parking.interfaces.http._compat import Request


@dataclass
class AppContainer:
    """Holds wired application services and database unit of work."""
    settings: Settings
    db: MySQLDatabase
    uow: UnitOfWork
    cipher: EmbeddingCipher
    event_bus: RealtimeEventBus
    auth_service: AuthService
    slot_service: SlotService
    booking_service: BookingService
    gate_data_service: GateDataService
    retention_service: RetentionService
    admin_query_service: AdminQueryService


def build_container(
    settings: Optional[Settings] = None,
    db: Optional[MySQLDatabase] = None,
) -> AppContainer:
    cfg = settings or get_settings()
    mysql_db = db or MySQLDatabase(cfg)
    uow = UnitOfWork(mysql_db)
    cipher = EmbeddingCipher(
        secret_key=cfg.embedding_secret_key,
        default_key_version=cfg.embedding_key_version,
    )
    event_bus = RealtimeEventBus()
    auth_service = AuthService(uow=uow, settings=cfg)
    slot_service = SlotService(uow=uow, settings=cfg)
    booking_service = BookingService(uow=uow, event_bus=event_bus, settings=cfg)
    gate_data_service = GateDataService(
        uow=uow,
        cipher=cipher,
        event_bus=event_bus,
        settings=cfg,
    )
    retention_service = RetentionService(uow=uow, event_bus=event_bus)
    admin_query_service = AdminQueryService(uow=uow)

    return AppContainer(
        settings=cfg,
        db=mysql_db,
        uow=uow,
        cipher=cipher,
        event_bus=event_bus,
        auth_service=auth_service,
        slot_service=slot_service,
        booking_service=booking_service,
        gate_data_service=gate_data_service,
        retention_service=retention_service,
        admin_query_service=admin_query_service,
    )


def get_container(request: Request) -> AppContainer:
    container = getattr(request.app.state, "container", None)
    if container is None:
        container = build_container()
        request.app.state.container = container
    return container


def extract_token_from_request(request: Request) -> str:
    """Extract JWT token from `Authorization: Bearer <token>` header or `access_token` cookie."""
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token.strip()

    raise AuthenticationException(
        "Yêu cầu đăng nhập (thiếu Bearer token hoặc cookie xác thực).",
        reason_code="MISSING_AUTH_TOKEN",
    )


def get_current_user(request: Request) -> Dict[str, Any]:
    """Authenticate request and return current active user claims (`user_id`, `username`, `role`)."""
    container = get_container(request)
    token = extract_token_from_request(request)
    return container.auth_service.verify_token(token)


def require_admin_user(request: Request) -> Dict[str, Any]:
    """Authenticate request and enforce `role == 'admin'` (raises 403 AuthorizationException for 'user')."""
    user = get_current_user(request)
    if user.get("role") != UserRole.ADMIN.value:
        raise AuthorizationException(
            "Chỉ tài khoản ADMIN mới được phép truy cập API quản trị.",
            reason_code="ADMIN_ROLE_REQUIRED",
        )
    return user
