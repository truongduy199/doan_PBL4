"""Authentication & RBAC Service for USER and ADMIN accounts."""
from __future__ import annotations

from typing import Any, Dict, Optional

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.config.settings import Settings, get_settings
from smart_parking.domain.enums import AccountStatus
from smart_parking.domain.exceptions import AuthenticationException, AuthorizationException
from smart_parking.infrastructure.database.mysql_db import format_utc_iso, format_vn_iso, utc_now
from smart_parking.infrastructure.database.unit_of_work import UnitOfWork
from smart_parking.infrastructure.security.auth_security import (
    create_access_token,
    decode_access_token,
    verify_password,
)


class AuthService:
    """Handles login, token verification, RBAC checks, and user profile lookups."""

    def __init__(self, uow: UnitOfWork, settings: Optional[Settings] = None) -> None:
        self.uow = uow
        self.settings = settings or get_settings()

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate username/password against MySQL `users` table and issue JWT token."""
        if not username or not password:
            raise AuthenticationException("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu.")

        def _tx(tx) -> Dict[str, Any]:
            user = tx.users.get_by_username(username.strip())
            if user is None or not verify_password(password, user.password_hash):
                raise AuthenticationException("Tên đăng nhập hoặc mật khẩu không chính xác.")
            if user.status != AccountStatus.ACTIVE:
                raise AuthorizationException(
                    "Tài khoản đã bị vô hiệu hóa.",
                    reason_code="ACCOUNT_DISABLED",
                )
            vehicles = tx.vehicles.list_by_user(user.user_id)
            face_tpl = tx.face_templates.get_active_user_template(user.user_id)
            return self._build_user_profile_dto(user, vehicles, face_tpl)

        profile = self.uow.run_transactional(_tx, readonly=True)
        token = create_access_token(
            user_id=profile["user_id"],
            username=profile["username"],
            role=profile["role"],
            secret_key=self.settings.jwt_secret_key,
            expire_hours=self.settings.jwt_expire_hours,
            algorithm=self.settings.jwt_algorithm,
        )
        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.jwt_expire_hours * 3600,
            "user": profile,
            "server_time": format_utc_iso(utc_now()),
        }

    def get_current_user_profile(self, user_id: int) -> Dict[str, Any]:
        """Fetch current user info, registered vehicles, and face template link status (no BLOB)."""
        def _tx(tx) -> Dict[str, Any]:
            user = tx.users.get_by_id(user_id)
            if user is None:
                raise AuthenticationException("Không tìm thấy tài khoản người dùng.")
            if user.status != AccountStatus.ACTIVE:
                raise AuthorizationException("Tài khoản đã bị khóa.", reason_code="ACCOUNT_DISABLED")
            vehicles = tx.vehicles.list_by_user(user.user_id)
            face_tpl = tx.face_templates.get_active_user_template(user.user_id)
            return self._build_user_profile_dto(user, vehicles, face_tpl)

        profile = self.uow.run_transactional(_tx, readonly=True)
        profile["server_time"] = format_utc_iso(utc_now())
        return profile

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Decode JWT token and verify the user still exists and is Active in MySQL."""
        try:
            payload = decode_access_token(
                token=token,
                secret_key=self.settings.jwt_secret_key,
                algorithm=self.settings.jwt_algorithm,
            )
        except ValueError as exc:
            raise AuthenticationException(str(exc), reason_code="INVALID_TOKEN") from exc

        user_id = int(payload["user_id"])

        def _tx(tx) -> Dict[str, Any]:
            user = tx.users.get_by_id(user_id)
            if user is None:
                raise AuthenticationException("Tài khoản không tồn tại.", reason_code="USER_NOT_FOUND")
            if user.status != AccountStatus.ACTIVE:
                raise AuthorizationException("Tài khoản đã bị vô hiệu hóa.", reason_code="ACCOUNT_DISABLED")
            return {
                "user_id": user.user_id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role.value,
                "status": user.status.value,
            }

        return self.uow.run_transactional(_tx, readonly=True)

    @staticmethod
    def _build_user_profile_dto(user, vehicles, face_tpl) -> Dict[str, Any]:
        vehicle_list = [
            {
                "vehicle_id": v.vehicle_id,
                "plate_number": v.plate_number,
                "plate_display": PlateNormalizer.format_display(v.plate_number),
                "status": v.status.value,
            }
            for v in vehicles
            if v.status == AccountStatus.ACTIVE
        ]
        face_info: Dict[str, Any] = {
            "has_active_template": face_tpl is not None,
            "template_id": face_tpl.template_id if face_tpl else None,
            "model_id": face_tpl.model_id if face_tpl else None,
            "model_version": face_tpl.model_version if face_tpl else None,
            "liveness_status": face_tpl.liveness_status.value if face_tpl else None,
            "status": face_tpl.status.value if face_tpl else None,
            "updated_at": format_utc_iso(face_tpl.created_at) if face_tpl else None,
            "updated_at_vn": format_vn_iso(face_tpl.created_at) if face_tpl else None,
        }
        return {
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": user.role.value,
            "status": user.status.value,
            "vehicles": vehicle_list,
            "face_template": face_info,
        }
