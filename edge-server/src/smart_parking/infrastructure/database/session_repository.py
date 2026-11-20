"""Session Repository for `sessions` table (Lock Rank 4)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from smart_parking.ai.plate.normalizer import PlateNormalizer
from smart_parking.domain.entities.parking_session import ParkingSession
from smart_parking.domain.enums import ParkingStatus, SessionStatus
from smart_parking.infrastructure.database.mysql_db import (
    DBCursorProtocol,
    LockOrderTracker,
    from_db_utc,
    to_db_utc,
    utc_now,
)


def _row_to_session(row: Dict[str, Any]) -> ParkingSession:
    return ParkingSession(
        session_id=str(row["session_id"]),
        plate_number=str(row["plate_number"]),
        user_id=int(row["user_id"]) if row.get("user_id") is not None else None,
        vehicle_id=int(row["vehicle_id"]) if row.get("vehicle_id") is not None else None,
        booking_id=row.get("booking_id"),
        assigned_slot_id=str(row["assigned_slot_id"]),
        status=SessionStatus(row["status"]),
        parking_status=ParkingStatus(row["parking_status"]),
        ocr_confidence=float(row["ocr_confidence"]) if row.get("ocr_confidence") is not None else None,
        entry_time=from_db_utc(row.get("entry_time")),
        exit_time=from_db_utc(row.get("exit_time")),
        created_at=from_db_utc(row["created_at"]) or utc_now(),
        updated_at=from_db_utc(row["updated_at"]) or utc_now(),
    )


class SessionRepository:
    """Data access layer for `sessions` table with mandatory lock rank 4 (`sessions`)."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def create(
        self,
        session_id: str,
        plate_number: str,
        assigned_slot_id: str,
        status: str = "Entry_pending",
        parking_status: str = "Not_arrived",
        user_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        booking_id: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
        entry_time: Optional[datetime] = None,
        now_utc: Optional[datetime] = None,
    ) -> ParkingSession:
        norm_plate = PlateNormalizer.normalize(plate_number)
        now_dt = to_db_utc(now_utc or utc_now())
        entry_dt = to_db_utc(entry_time)
        self._cursor.execute(
            "INSERT INTO sessions ("
            "session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s)",
            (
                session_id,
                norm_plate,
                user_id,
                vehicle_id,
                booking_id,
                assigned_slot_id,
                status,
                parking_status,
                ocr_confidence,
                entry_dt,
                now_dt,
                now_dt,
            ),
        )
        created = self.get_by_id(session_id)
        assert created is not None
        return created

    def get_by_id(self, session_id: str) -> Optional[ParkingSession]:
        self._cursor.execute(
            "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
            "FROM sessions WHERE session_id = %s",
            (session_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_session(row) if row else None

    def lock_by_id_for_update(self, session_id: str) -> Optional[ParkingSession]:
        """Rank 4 row lock: SELECT ... FROM sessions WHERE session_id = %s FOR UPDATE."""
        self._locks.record_lock("sessions")
        self._cursor.execute(
            "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
            "FROM sessions WHERE session_id = %s FOR UPDATE",
            (session_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_session(row) if row else None

    def find_live_by_plate(self, plate_number: str) -> Optional[ParkingSession]:
        """Find a session in ('Entry_pending', 'Active', 'Exit_pending') for plate_number."""
        norm_plate = PlateNormalizer.normalize(plate_number)
        self._cursor.execute(
            "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
            "FROM sessions "
            "WHERE plate_number = %s AND status IN ('Entry_pending', 'Active', 'Exit_pending') "
            "ORDER BY created_at DESC LIMIT 1",
            (norm_plate,),
        )
        row = self._cursor.fetchone()
        return _row_to_session(row) if row else None

    def lock_live_by_plate_for_update(self, plate_number: str) -> Optional[ParkingSession]:
        """Rank 4 row lock on any live session ('Entry_pending', 'Active', 'Exit_pending') for plate."""
        norm_plate = PlateNormalizer.normalize(plate_number)
        self._locks.record_lock("sessions")
        self._cursor.execute(
            "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
            "FROM sessions "
            "WHERE plate_number = %s AND status IN ('Entry_pending', 'Active', 'Exit_pending') "
            "ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
            (norm_plate,),
        )
        row = self._cursor.fetchone()
        return _row_to_session(row) if row else None

    def find_by_booking_id(self, booking_id: str) -> Optional[ParkingSession]:
        self._cursor.execute(
            "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
            "FROM sessions WHERE booking_id = %s",
            (booking_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_session(row) if row else None

    def lock_active_parking_pending_sessions(self) -> List[ParkingSession]:
        """Rank 4 row lock on all Active sessions currently waiting for parking confirmation."""
        self._locks.record_lock("sessions")
        self._cursor.execute(
            "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
            "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
            "FROM sessions "
            "WHERE status = 'Active' AND parking_status = 'Parking_pending' "
            "ORDER BY created_at ASC FOR UPDATE"
        )
        return [_row_to_session(r) for r in self._cursor.fetchall()]

    def mark_entry_confirmed(self, session_id: str, now_utc: datetime) -> None:
        now_dt = to_db_utc(now_utc)
        self._cursor.execute(
            "UPDATE sessions "
            "SET status = 'Active', parking_status = 'Parking_pending', entry_time = %s, updated_at = %s "
            "WHERE session_id = %s",
            (now_dt, now_dt, session_id),
        )

    def update_parking_status(self, session_id: str, parking_status: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE sessions SET parking_status = %s, updated_at = %s WHERE session_id = %s",
            (parking_status, to_db_utc(now_utc), session_id),
        )

    def mark_exit_pending(self, session_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE sessions SET status = 'Exit_pending', updated_at = %s WHERE session_id = %s",
            (to_db_utc(now_utc), session_id),
        )

    def revert_exit_pending_to_active(self, session_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE sessions SET status = 'Active', updated_at = %s "
            "WHERE session_id = %s AND status = 'Exit_pending'",
            (to_db_utc(now_utc), session_id),
        )

    def mark_closed(self, session_id: str, now_utc: datetime) -> None:
        now_dt = to_db_utc(now_utc)
        self._cursor.execute(
            "UPDATE sessions SET status = 'Closed', exit_time = %s, updated_at = %s WHERE session_id = %s",
            (now_dt, now_dt, session_id),
        )

    def mark_cancelled(self, session_id: str, now_utc: datetime) -> None:
        now_dt = to_db_utc(now_utc)
        self._cursor.execute(
            "UPDATE sessions SET status = 'Cancelled', updated_at = %s WHERE session_id = %s",
            (now_dt, session_id),
        )

    def list_by_user(
        self,
        user_id: int,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ParkingSession]:
        if status_filter:
            self._cursor.execute(
                "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
                "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
                "FROM sessions WHERE user_id = %s AND status = %s "
                "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (int(user_id), status_filter, int(limit), int(offset)),
            )
        else:
            self._cursor.execute(
                "SELECT session_id, plate_number, user_id, vehicle_id, booking_id, assigned_slot_id, "
                "status, parking_status, ocr_confidence, entry_time, exit_time, created_at, updated_at "
                "FROM sessions WHERE user_id = %s "
                "ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (int(user_id), int(limit), int(offset)),
            )
        return [_row_to_session(r) for r in self._cursor.fetchall()]

    def list_all_admin(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if status_filter:
            self._cursor.execute(
                "SELECT s.*, b.status AS booking_status, b.expires_at AS booking_expires_at, "
                "u.username, u.display_name "
                "FROM sessions s "
                "LEFT JOIN bookings b ON b.booking_id = s.booking_id "
                "LEFT JOIN users u ON u.user_id = s.user_id "
                "WHERE s.status = %s "
                "ORDER BY s.created_at DESC LIMIT %s OFFSET %s",
                (status_filter, int(limit), int(offset)),
            )
        else:
            self._cursor.execute(
                "SELECT s.*, b.status AS booking_status, b.expires_at AS booking_expires_at, "
                "u.username, u.display_name "
                "FROM sessions s "
                "LEFT JOIN bookings b ON b.booking_id = s.booking_id "
                "LEFT JOIN users u ON u.user_id = s.user_id "
                "ORDER BY s.created_at DESC LIMIT %s OFFSET %s",
                (int(limit), int(offset)),
            )
        return list(self._cursor.fetchall())
