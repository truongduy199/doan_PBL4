"""Repositories for users, vehicles, user_face_templates, and session_face_templates."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.domain.entities.face_template import SessionFaceTemplate, UserFaceTemplate
from smart_parking.domain.entities.user import User, Vehicle
from smart_parking.domain.enums import AccountStatus, FaceTemplateStatus, LivenessStatus, UserRole
from smart_parking.infrastructure.database.mysql_db import (
    DBCursorProtocol,
    LockOrderTracker,
    from_db_utc,
    to_db_utc,
    utc_now,
)


def _row_to_user(row: Dict[str, Any]) -> User:
    return User(
        user_id=int(row["user_id"]),
        username=str(row["username"]),
        password_hash=str(row["password_hash"]),
        display_name=row.get("display_name"),
        role=UserRole(row["role"]),
        status=AccountStatus(row["status"]),
        created_at=from_db_utc(row["created_at"]) or utc_now(),
        updated_at=from_db_utc(row["updated_at"]) or utc_now(),
    )


def _row_to_vehicle(row: Dict[str, Any]) -> Vehicle:
    return Vehicle(
        vehicle_id=int(row["vehicle_id"]),
        user_id=int(row["user_id"]),
        plate_number=str(row["plate_number"]),
        status=AccountStatus(row["status"]),
        created_at=from_db_utc(row["created_at"]) or utc_now(),
        updated_at=from_db_utc(row["updated_at"]) or utc_now(),
    )


def _parse_json_field(val: Any) -> Dict[str, Any]:
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, (bytes, bytearray)):
        val = val.decode("utf-8")
    if isinstance(val, str):
        return json.loads(val)
    return dict(val)


def _row_to_user_face_template(row: Dict[str, Any]) -> UserFaceTemplate:
    return UserFaceTemplate(
        template_id=int(row["template_id"]),
        user_id=int(row["user_id"]),
        embedding_blob=bytes(row["embedding_blob"]),
        embedding_size=int(row["embedding_size"]),
        embedding_dtype=str(row["embedding_dtype"]),
        model_id=str(row["model_id"]),
        model_version=str(row["model_version"]),
        config_version=str(row["config_version"]),
        quality_score=float(row["quality_score"]) if row.get("quality_score") is not None else None,
        liveness_status=LivenessStatus(row["liveness_status"]),
        liveness_score=float(row["liveness_score"]) if row.get("liveness_score") is not None else None,
        key_version=str(row["key_version"]),
        encryption_metadata=_parse_json_field(row["encryption_metadata"]),
        status=FaceTemplateStatus(row["status"]),
        created_at=from_db_utc(row["created_at"]) or utc_now(),
        revoked_at=from_db_utc(row.get("revoked_at")),
    )


def _row_to_session_face_template(row: Dict[str, Any]) -> SessionFaceTemplate:
    return SessionFaceTemplate(
        template_id=int(row["template_id"]),
        session_id=str(row["session_id"]),
        embedding_blob=bytes(row["embedding_blob"]),
        embedding_size=int(row["embedding_size"]),
        embedding_dtype=str(row["embedding_dtype"]),
        model_id=str(row["model_id"]),
        model_version=str(row["model_version"]),
        config_version=str(row["config_version"]),
        quality_score=float(row["quality_score"]) if row.get("quality_score") is not None else None,
        liveness_status=LivenessStatus(row["liveness_status"]),
        liveness_score=float(row["liveness_score"]) if row.get("liveness_score") is not None else None,
        key_version=str(row["key_version"]),
        encryption_metadata=_parse_json_field(row["encryption_metadata"]),
        captured_at=from_db_utc(row["captured_at"]) or utc_now(),
        expires_at=from_db_utc(row.get("expires_at")),
    )


class UserRepository:
    """Data access layer for `users` table using parameterized %s queries."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def get_by_id(self, user_id: int) -> Optional[User]:
        self._cursor.execute(
            "SELECT user_id, username, password_hash, display_name, role, status, created_at, updated_at "
            "FROM users WHERE user_id = %s",
            (int(user_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_user(row) if row else None

    def get_by_username(self, username: str) -> Optional[User]:
        self._cursor.execute(
            "SELECT user_id, username, password_hash, display_name, role, status, created_at, updated_at "
            "FROM users WHERE username = %s",
            (username.strip(),),
        )
        row = self._cursor.fetchone()
        return _row_to_user(row) if row else None

    def create_or_update(
        self,
        username: str,
        password_hash: str,
        role: str,
        display_name: Optional[str] = None,
        status: str = "Active",
        now_utc: Optional[datetime] = None,
    ) -> User:
        now_dt = to_db_utc(now_utc or utc_now())
        existing = self.get_by_username(username)
        if existing is not None:
            self._cursor.execute(
                "UPDATE users SET password_hash = %s, display_name = %s, role = %s, status = %s, updated_at = %s "
                "WHERE user_id = %s",
                (password_hash, display_name, role, status, now_dt, existing.user_id),
            )
            updated = self.get_by_id(existing.user_id)
            assert updated is not None
            return updated

        self._cursor.execute(
            "INSERT INTO users (username, password_hash, display_name, role, status, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (username.strip(), password_hash, display_name, role, status, now_dt, now_dt),
        )
        created = self.get_by_username(username)
        assert created is not None
        return created


class VehicleRepository:
    """Data access layer for `vehicles` table with mandatory lock rank 1 (`vehicles`)."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def get_by_id(self, vehicle_id: int) -> Optional[Vehicle]:
        self._cursor.execute(
            "SELECT vehicle_id, user_id, plate_number, status, created_at, updated_at "
            "FROM vehicles WHERE vehicle_id = %s",
            (int(vehicle_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_vehicle(row) if row else None

    def lock_by_id_for_update(self, vehicle_id: int) -> Optional[Vehicle]:
        """Rank 1 row lock: SELECT ... FROM vehicles WHERE vehicle_id = %s FOR UPDATE."""
        self._locks.record_lock("vehicles")
        self._cursor.execute(
            "SELECT vehicle_id, user_id, plate_number, status, created_at, updated_at "
            "FROM vehicles WHERE vehicle_id = %s FOR UPDATE",
            (int(vehicle_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_vehicle(row) if row else None

    def get_by_plate(self, plate_number: str) -> Optional[Vehicle]:
        norm_plate = PlateNormalizer.normalize(plate_number)
        self._cursor.execute(
            "SELECT vehicle_id, user_id, plate_number, status, created_at, updated_at "
            "FROM vehicles WHERE plate_number = %s",
            (norm_plate,),
        )
        row = self._cursor.fetchone()
        return _row_to_vehicle(row) if row else None

    def lock_by_plate_for_update(self, plate_number: str) -> Optional[Vehicle]:
        """Rank 1 row lock by normalized license plate."""
        norm_plate = PlateNormalizer.normalize(plate_number)
        self._locks.record_lock("vehicles")
        self._cursor.execute(
            "SELECT vehicle_id, user_id, plate_number, status, created_at, updated_at "
            "FROM vehicles WHERE plate_number = %s FOR UPDATE",
            (norm_plate,),
        )
        row = self._cursor.fetchone()
        return _row_to_vehicle(row) if row else None

    def list_by_user(self, user_id: int) -> List[Vehicle]:
        self._cursor.execute(
            "SELECT vehicle_id, user_id, plate_number, status, created_at, updated_at "
            "FROM vehicles WHERE user_id = %s ORDER BY vehicle_id ASC",
            (int(user_id),),
        )
        return [_row_to_vehicle(r) for r in self._cursor.fetchall()]

    def create_or_update(
        self,
        user_id: int,
        plate_number: str,
        status: str = "Active",
        now_utc: Optional[datetime] = None,
    ) -> Vehicle:
        norm_plate = PlateNormalizer.normalize(plate_number)
        now_dt = to_db_utc(now_utc or utc_now())
        existing = self.get_by_plate(norm_plate)
        if existing is not None:
            self._cursor.execute(
                "UPDATE vehicles SET user_id = %s, status = %s, updated_at = %s WHERE vehicle_id = %s",
                (int(user_id), status, now_dt, existing.vehicle_id),
            )
            updated = self.get_by_id(existing.vehicle_id)
            assert updated is not None
            return updated

        self._cursor.execute(
            "INSERT INTO vehicles (user_id, plate_number, status, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (int(user_id), norm_plate, status, now_dt, now_dt),
        )
        created = self.get_by_plate(norm_plate)
        assert created is not None
        return created


class FaceTemplateRepository:
    """Data access layer for `user_face_templates` and `session_face_templates`."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def get_active_user_template(self, user_id: int) -> Optional[UserFaceTemplate]:
        self._cursor.execute(
            "SELECT template_id, user_id, embedding_blob, embedding_size, embedding_dtype, "
            "model_id, model_version, config_version, quality_score, liveness_status, liveness_score, "
            "key_version, encryption_metadata, status, created_at, revoked_at "
            "FROM user_face_templates WHERE user_id = %s AND status = 'Active'",
            (int(user_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_user_face_template(row) if row else None

    def upsert_active_user_template(
        self,
        user_id: int,
        embedding_blob: bytes,
        key_version: str,
        encryption_metadata: Dict[str, Any],
        model_id: str,
        model_version: str,
        config_version: str,
        liveness_status: str = "Not_used",
        liveness_score: Optional[float] = None,
        quality_score: Optional[float] = None,
        embedding_size: int = 512,
        embedding_dtype: str = "float32",
        now_utc: Optional[datetime] = None,
    ) -> UserFaceTemplate:
        """
        Replace any existing Active template for user_id (setting status='Replaced', revoked_at=now)
        and insert the new Active template atomically within the current transaction.
        Enforces truthfulness of liveness_status ('Not_used' -> liveness_score MUST be None).
        """
        if liveness_status == LivenessStatus.NOT_USED.value:
            liveness_score = None

        now_dt = to_db_utc(now_utc or utc_now())
        # Mark any current Active template as Replaced
        self._cursor.execute(
            "UPDATE user_face_templates SET status = 'Replaced', revoked_at = %s "
            "WHERE user_id = %s AND status = 'Active'",
            (now_dt, int(user_id)),
        )

        meta_json = json.dumps(encryption_metadata)
        self._cursor.execute(
            "INSERT INTO user_face_templates ("
            "user_id, embedding_blob, embedding_size, embedding_dtype, "
            "model_id, model_version, config_version, quality_score, "
            "liveness_status, liveness_score, key_version, encryption_metadata, "
            "status, created_at, revoked_at"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Active', %s, NULL)",
            (
                int(user_id),
                embedding_blob,
                int(embedding_size),
                embedding_dtype,
                model_id,
                model_version,
                config_version,
                quality_score,
                liveness_status,
                liveness_score,
                key_version,
                meta_json,
                now_dt,
            ),
        )
        created = self.get_active_user_template(user_id)
        assert created is not None
        return created

    def revoke_active_user_template(self, user_id: int, now_utc: Optional[datetime] = None) -> int:
        now_dt = to_db_utc(now_utc or utc_now())
        self._cursor.execute(
            "UPDATE user_face_templates SET status = 'Revoked', revoked_at = %s "
            "WHERE user_id = %s AND status = 'Active'",
            (now_dt, int(user_id)),
        )
        return int(self._cursor.rowcount)

    def create_session_template(
        self,
        session_id: str,
        embedding_blob: bytes,
        key_version: str,
        encryption_metadata: Dict[str, Any],
        model_id: str,
        model_version: str,
        config_version: str,
        liveness_status: str,
        liveness_score: Optional[float] = None,
        quality_score: Optional[float] = None,
        embedding_size: int = 512,
        embedding_dtype: str = "float32",
        captured_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
    ) -> SessionFaceTemplate:
        if liveness_status == LivenessStatus.NOT_USED.value:
            liveness_score = None
        cap_dt = to_db_utc(captured_at or utc_now())
        exp_dt = to_db_utc(expires_at)
        meta_json = json.dumps(encryption_metadata)
        self._cursor.execute(
            "INSERT INTO session_face_templates ("
            "session_id, embedding_blob, embedding_size, embedding_dtype, "
            "model_id, model_version, config_version, quality_score, "
            "liveness_status, liveness_score, key_version, encryption_metadata, "
            "captured_at, expires_at"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session_id,
                embedding_blob,
                int(embedding_size),
                embedding_dtype,
                model_id,
                model_version,
                config_version,
                quality_score,
                liveness_status,
                liveness_score,
                key_version,
                meta_json,
                cap_dt,
                exp_dt,
            ),
        )
        created = self.get_session_template(session_id)
        assert created is not None
        return created

    def get_session_template(self, session_id: str) -> Optional[SessionFaceTemplate]:
        self._cursor.execute(
            "SELECT template_id, session_id, embedding_blob, embedding_size, embedding_dtype, "
            "model_id, model_version, config_version, quality_score, liveness_status, liveness_score, "
            "key_version, encryption_metadata, captured_at, expires_at "
            "FROM session_face_templates WHERE session_id = %s",
            (session_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_session_face_template(row) if row else None

    def set_session_template_expiry(self, session_id: str, expires_at: datetime) -> None:
        self._cursor.execute(
            "UPDATE session_face_templates SET expires_at = %s WHERE session_id = %s",
            (to_db_utc(expires_at), session_id),
        )

    def purge_expired_session_templates(self, now_utc: datetime) -> int:
        """
        Delete session_face_templates ONLY for sessions that are already 'Closed' or 'Cancelled'
        and whose expires_at <= now_utc. Never touches live sessions or user_face_templates.
        """
        now_dt = to_db_utc(now_utc)
        self._cursor.execute(
            "SELECT sft.template_id "
            "FROM session_face_templates sft "
            "INNER JOIN sessions s ON s.session_id = sft.session_id "
            "WHERE s.status IN ('Closed', 'Cancelled') "
            "AND sft.expires_at IS NOT NULL "
            "AND sft.expires_at <= %s",
            (now_dt,),
        )
        rows = self._cursor.fetchall()
        if not rows:
            return 0
        template_ids = [int(r["template_id"]) for r in rows]
        placeholders = ", ".join(["%s"] * len(template_ids))
        self._cursor.execute(
            f"DELETE FROM session_face_templates WHERE template_id IN ({placeholders})",
            tuple(template_ids),
        )
        return len(template_ids)
