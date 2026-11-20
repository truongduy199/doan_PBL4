"""Repositories for `gate_events` (Lock Rank 5) and `parking_logs` (Audit Log)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from smart_parking.domain.entities.gate_transaction import GateEvent
from smart_parking.domain.entities.system_event import ParkingLog
from smart_parking.domain.enums import GateDecision, GateId, LivenessStatus, PassageStatus
from smart_parking.infrastructure.database.mysql_db import (
    DBCursorProtocol,
    LockOrderTracker,
    from_db_utc,
    to_db_utc,
    utc_now,
)

_FORBIDDEN_LOG_KEYS = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "embedding_secret_key",
    "jwt_secret_key",
    "embedding",
    "embedding_blob",
    "vector",
    "vector_np",
    "face_vector",
}


def sanitize_log_details(details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively strip passwords, encryption keys, and face embedding vectors from audit details."""
    if details is None:
        return None
    cleaned: Dict[str, Any] = {}
    for k, v in details.items():
        if str(k).lower() in _FORBIDDEN_LOG_KEYS:
            continue
        if isinstance(v, dict):
            cleaned[k] = sanitize_log_details(v)
        elif isinstance(v, (bytes, bytearray, memoryview)):
            continue
        else:
            cleaned[k] = v
    return cleaned


def _row_to_gate_event(row: Dict[str, Any]) -> GateEvent:
    return GateEvent(
        event_id=str(row["event_id"]),
        gate_id=GateId(row["gate_id"]),
        device_id=str(row["device_id"]),
        session_id=row.get("session_id"),
        booking_id=row.get("booking_id"),
        decision=GateDecision(row["decision"]),
        passage_status=PassageStatus(row["passage_status"]),
        reason_code=row.get("reason_code"),
        liveness_status=LivenessStatus(row["liveness_status"]) if row.get("liveness_status") else None,
        liveness_score=float(row["liveness_score"]) if row.get("liveness_score") is not None else None,
        liveness_model_version=row.get("liveness_model_version"),
        face_config_version=row.get("face_config_version"),
        command_id=row.get("command_id"),
        reviewer_id=int(row["reviewer_id"]) if row.get("reviewer_id") is not None else None,
        review_reason=row.get("review_reason"),
        created_at=from_db_utc(row["created_at"]) or utc_now(),
        decided_at=from_db_utc(row.get("decided_at")),
        passed_at=from_db_utc(row.get("passed_at")),
    )


def _row_to_parking_log(row: Dict[str, Any]) -> ParkingLog:
    raw_details = row.get("details")
    parsed_details: Optional[Dict[str, Any]] = None
    if raw_details is not None:
        if isinstance(raw_details, dict):
            parsed_details = raw_details
        elif isinstance(raw_details, (bytes, bytearray)):
            parsed_details = json.loads(raw_details.decode("utf-8"))
        elif isinstance(raw_details, str) and raw_details.strip():
            parsed_details = json.loads(raw_details)
    return ParkingLog(
        log_id=int(row["log_id"]),
        event_id=row.get("event_id"),
        session_id=row.get("session_id"),
        actor_user_id=int(row["actor_user_id"]) if row.get("actor_user_id") is not None else None,
        event_type=str(row["event_type"]),
        reason_code=str(row["reason_code"]),
        details=parsed_details,
        created_at=from_db_utc(row["created_at"]) or utc_now(),
    )


class GateEventRepository:
    """Data access layer for `gate_events` table (Lock Rank 5)."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def get_by_id(self, event_id: str) -> Optional[GateEvent]:
        self._cursor.execute(
            "SELECT event_id, gate_id, device_id, session_id, booking_id, decision, passage_status, "
            "reason_code, liveness_status, liveness_score, liveness_model_version, face_config_version, "
            "command_id, reviewer_id, review_reason, created_at, decided_at, passed_at "
            "FROM gate_events WHERE event_id = %s",
            (event_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_gate_event(row) if row else None

    def lock_by_id_for_update(self, event_id: str) -> Optional[GateEvent]:
        """Rank 5 row lock: SELECT ... FROM gate_events WHERE event_id = %s FOR UPDATE."""
        self._locks.record_lock("gate_events")
        self._cursor.execute(
            "SELECT event_id, gate_id, device_id, session_id, booking_id, decision, passage_status, "
            "reason_code, liveness_status, liveness_score, liveness_model_version, face_config_version, "
            "command_id, reviewer_id, review_reason, created_at, decided_at, passed_at "
            "FROM gate_events WHERE event_id = %s FOR UPDATE",
            (event_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_gate_event(row) if row else None

    def create_if_not_exists(
        self,
        event_id: str,
        gate_id: str,
        device_id: str,
        decision: str = "Pending",
        passage_status: str = "Waiting",
        session_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        liveness_status: Optional[str] = None,
        liveness_score: Optional[float] = None,
        liveness_model_version: Optional[str] = None,
        face_config_version: Optional[str] = None,
        command_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
        decided_at: Optional[datetime] = None,
    ) -> Tuple[GateEvent, bool]:
        """
        Idempotently create a gate_event by event_id.
        Returns (gate_event, is_newly_created).
        """
        existing = self.get_by_id(event_id)
        if existing is not None:
            return existing, False

        if liveness_status == LivenessStatus.NOT_USED.value:
            liveness_score = None

        c_dt = to_db_utc(created_at or utc_now())
        d_dt = to_db_utc(decided_at)
        self._cursor.execute(
            "INSERT INTO gate_events ("
            "event_id, gate_id, device_id, session_id, booking_id, decision, passage_status, "
            "reason_code, liveness_status, liveness_score, liveness_model_version, face_config_version, "
            "command_id, reviewer_id, review_reason, created_at, decided_at, passed_at"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL, %s, %s, NULL)",
            (
                event_id,
                gate_id,
                device_id,
                session_id,
                booking_id,
                decision,
                passage_status,
                reason_code,
                liveness_status,
                liveness_score,
                liveness_model_version,
                face_config_version,
                command_id,
                c_dt,
                d_dt,
            ),
        )
        created = self.get_by_id(event_id)
        assert created is not None
        return created, True

    def update_decision(
        self,
        event_id: str,
        decision: str,
        reason_code: Optional[str] = None,
        session_id: Optional[str] = None,
        booking_id: Optional[str] = None,
        command_id: Optional[str] = None,
        liveness_status: Optional[str] = None,
        liveness_score: Optional[float] = None,
        liveness_model_version: Optional[str] = None,
        face_config_version: Optional[str] = None,
        decided_at: Optional[datetime] = None,
    ) -> GateEvent:
        if liveness_status == LivenessStatus.NOT_USED.value:
            liveness_score = None
        d_dt = to_db_utc(decided_at or utc_now())
        self._cursor.execute(
            "UPDATE gate_events "
            "SET decision = %s, reason_code = COALESCE(%s, reason_code), "
            "session_id = COALESCE(%s, session_id), booking_id = COALESCE(%s, booking_id), "
            "command_id = COALESCE(%s, command_id), "
            "liveness_status = COALESCE(%s, liveness_status), "
            "liveness_score = %s, "
            "liveness_model_version = COALESCE(%s, liveness_model_version), "
            "face_config_version = COALESCE(%s, face_config_version), "
            "decided_at = %s "
            "WHERE event_id = %s",
            (
                decision,
                reason_code,
                session_id,
                booking_id,
                command_id,
                liveness_status,
                liveness_score,
                liveness_model_version,
                face_config_version,
                d_dt,
                event_id,
            ),
        )
        updated = self.get_by_id(event_id)
        assert updated is not None
        return updated

    def confirm_passage(self, event_id: str, passed_at: datetime) -> GateEvent:
        self._cursor.execute(
            "UPDATE gate_events SET passage_status = 'Confirmed', passed_at = %s WHERE event_id = %s",
            (to_db_utc(passed_at), event_id),
        )
        updated = self.get_by_id(event_id)
        assert updated is not None
        return updated

    def record_manual_review(
        self,
        event_id: str,
        decision: str,
        reviewer_id: int,
        review_reason: str,
        reason_code: str,
        command_id: Optional[str],
        decided_at: datetime,
    ) -> GateEvent:
        self._cursor.execute(
            "UPDATE gate_events "
            "SET decision = %s, reviewer_id = %s, review_reason = %s, reason_code = %s, "
            "command_id = COALESCE(%s, command_id), decided_at = %s "
            "WHERE event_id = %s",
            (
                decision,
                int(reviewer_id),
                review_reason,
                reason_code,
                command_id,
                to_db_utc(decided_at),
                event_id,
            ),
        )
        updated = self.get_by_id(event_id)
        assert updated is not None
        return updated


class ParkingLogRepository:
    """Data access layer for `parking_logs` table with automatic sensitive field sanitization."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def append(
        self,
        event_type: str,
        reason_code: str,
        event_id: Optional[str] = None,
        session_id: Optional[str] = None,
        actor_user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        created_at: Optional[datetime] = None,
    ) -> None:
        clean_details = sanitize_log_details(details)
        details_json = json.dumps(clean_details) if clean_details is not None else None
        now_dt = to_db_utc(created_at or utc_now())
        self._cursor.execute(
            "INSERT INTO parking_logs ("
            "event_id, session_id, actor_user_id, event_type, reason_code, details, created_at"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                event_id,
                session_id,
                actor_user_id,
                event_type,
                reason_code,
                details_json,
                now_dt,
            ),
        )

    def list_recent(self, limit: int = 50, session_id: Optional[str] = None) -> List[ParkingLog]:
        if session_id:
            self._cursor.execute(
                "SELECT log_id, event_id, session_id, actor_user_id, event_type, reason_code, details, created_at "
                "FROM parking_logs WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
                (session_id, int(limit)),
            )
        else:
            self._cursor.execute(
                "SELECT log_id, event_id, session_id, actor_user_id, event_type, reason_code, details, created_at "
                "FROM parking_logs ORDER BY created_at DESC LIMIT %s",
                (int(limit),),
            )
        return [_row_to_parking_log(r) for r in self._cursor.fetchall()]


# Legacy alias
EventRepository = GateEventRepository
