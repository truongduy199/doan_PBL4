"""Booking Repository for `bookings` table (Lock Rank 3)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from smart_parking.domain.entities.booking import Booking
from smart_parking.domain.enums import BookingStatus
from smart_parking.infrastructure.database.mysql_db import (
    DBCursorProtocol,
    LockOrderTracker,
    from_db_utc,
    to_db_utc,
    utc_now,
)


def _row_to_booking(row: Dict[str, Any]) -> Booking:
    return Booking(
        booking_id=str(row["booking_id"]),
        user_id=int(row["user_id"]),
        vehicle_id=int(row["vehicle_id"]),
        slot_id=str(row["slot_id"]),
        status=BookingStatus(row["status"]),
        created_at=from_db_utc(row["created_at"]) or utc_now(),
        expires_at=from_db_utc(row["expires_at"]) or utc_now(),
        checkin_started_at=from_db_utc(row.get("checkin_started_at")),
        checked_in_at=from_db_utc(row.get("checked_in_at")),
        completed_at=from_db_utc(row.get("completed_at")),
        cancelled_at=from_db_utc(row.get("cancelled_at")),
        checkin_event_id=row.get("checkin_event_id"),
        plate_number=row.get("plate_number"),
    )


class BookingRepository:
    """Data access layer for `bookings` table with mandatory lock rank 3 (`bookings`)."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def create(
        self,
        booking_id: str,
        user_id: int,
        vehicle_id: int,
        slot_id: str,
        status: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> Booking:
        c_dt = to_db_utc(created_at)
        e_dt = to_db_utc(expires_at)
        self._cursor.execute(
            "INSERT INTO bookings ("
            "booking_id, user_id, vehicle_id, slot_id, status, created_at, expires_at, "
            "checkin_started_at, checked_in_at, completed_at, cancelled_at, checkin_event_id"
            ") VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, NULL)",
            (booking_id, int(user_id), int(vehicle_id), slot_id, status, c_dt, e_dt),
        )
        created = self.get_by_id(booking_id)
        assert created is not None
        return created

    def get_by_id(self, booking_id: str) -> Optional[Booking]:
        self._cursor.execute(
            "SELECT b.booking_id, b.user_id, b.vehicle_id, b.slot_id, b.status, "
            "b.created_at, b.expires_at, b.checkin_started_at, b.checked_in_at, "
            "b.completed_at, b.cancelled_at, b.checkin_event_id, v.plate_number "
            "FROM bookings b "
            "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
            "WHERE b.booking_id = %s",
            (booking_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_booking(row) if row else None

    def lock_by_id_for_update(self, booking_id: str) -> Optional[Booking]:
        """Rank 3 row lock: SELECT ... FROM bookings WHERE booking_id = %s FOR UPDATE."""
        self._locks.record_lock("bookings")
        self._cursor.execute(
            "SELECT booking_id, user_id, vehicle_id, slot_id, status, "
            "created_at, expires_at, checkin_started_at, checked_in_at, "
            "completed_at, cancelled_at, checkin_event_id "
            "FROM bookings WHERE booking_id = %s FOR UPDATE",
            (booking_id,),
        )
        row = self._cursor.fetchone()
        return _row_to_booking(row) if row else None

    def find_active_by_vehicle(self, vehicle_id: int) -> Optional[Booking]:
        """Find a booking for vehicle_id currently in ('Reserved', 'Checkin_pending')."""
        self._cursor.execute(
            "SELECT b.booking_id, b.user_id, b.vehicle_id, b.slot_id, b.status, "
            "b.created_at, b.expires_at, b.checkin_started_at, b.checked_in_at, "
            "b.completed_at, b.cancelled_at, b.checkin_event_id, v.plate_number "
            "FROM bookings b "
            "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
            "WHERE b.vehicle_id = %s AND b.status IN ('Reserved', 'Checkin_pending') "
            "ORDER BY b.created_at DESC LIMIT 1",
            (int(vehicle_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_booking(row) if row else None

    def lock_reserved_by_vehicle_for_update(self, vehicle_id: int) -> Optional[Booking]:
        """Rank 3 row lock on a 'Reserved' or 'Checkin_pending' booking for vehicle_id."""
        self._locks.record_lock("bookings")
        self._cursor.execute(
            "SELECT booking_id, user_id, vehicle_id, slot_id, status, "
            "created_at, expires_at, checkin_started_at, checked_in_at, "
            "completed_at, cancelled_at, checkin_event_id "
            "FROM bookings "
            "WHERE vehicle_id = %s AND status IN ('Reserved', 'Checkin_pending') "
            "ORDER BY created_at DESC LIMIT 1 FOR UPDATE",
            (int(vehicle_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_booking(row) if row else None

    def find_current_for_user(self, user_id: int) -> Optional[Booking]:
        """
        Return the user's current active booking:
        either ('Reserved', 'Checkin_pending') OR 'Checked_in' attached to an unclosed session.
        """
        self._cursor.execute(
            "SELECT b.booking_id, b.user_id, b.vehicle_id, b.slot_id, b.status, "
            "b.created_at, b.expires_at, b.checkin_started_at, b.checked_in_at, "
            "b.completed_at, b.cancelled_at, b.checkin_event_id, v.plate_number "
            "FROM bookings b "
            "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
            "LEFT JOIN sessions s ON s.booking_id = b.booking_id "
            "WHERE b.user_id = %s AND ("
            "  b.status IN ('Reserved', 'Checkin_pending') "
            "  OR (b.status = 'Checked_in' AND s.status IN ('Entry_pending', 'Active', 'Exit_pending'))"
            ") "
            "ORDER BY b.created_at DESC LIMIT 1",
            (int(user_id),),
        )
        row = self._cursor.fetchone()
        return _row_to_booking(row) if row else None

    def find_overdue_reserved_candidates(self, now_utc: datetime) -> List[Dict[str, Any]]:
        """Query candidate overdue bookings (status = 'Reserved' AND expires_at <= now_utc) outside lock."""
        self._cursor.execute(
            "SELECT booking_id, user_id, vehicle_id, slot_id "
            "FROM bookings "
            "WHERE status = 'Reserved' AND expires_at <= %s "
            "ORDER BY expires_at ASC",
            (to_db_utc(now_utc),),
        )
        return list(self._cursor.fetchall())

    def mark_checkin_pending(
        self,
        booking_id: str,
        event_id: str,
        now_utc: datetime,
    ) -> None:
        self._cursor.execute(
            "UPDATE bookings "
            "SET status = 'Checkin_pending', checkin_started_at = %s, checkin_event_id = %s "
            "WHERE booking_id = %s",
            (to_db_utc(now_utc), event_id, booking_id),
        )

    def revert_checkin_pending_to_reserved(self, booking_id: str) -> None:
        self._cursor.execute(
            "UPDATE bookings "
            "SET status = 'Reserved', checkin_started_at = NULL, checkin_event_id = NULL "
            "WHERE booking_id = %s AND status = 'Checkin_pending'",
            (booking_id,),
        )

    def mark_checked_in(self, booking_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE bookings SET status = 'Checked_in', checked_in_at = %s WHERE booking_id = %s",
            (to_db_utc(now_utc), booking_id),
        )

    def mark_completed(self, booking_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE bookings SET status = 'Completed', completed_at = %s WHERE booking_id = %s",
            (to_db_utc(now_utc), booking_id),
        )

    def mark_cancelled(self, booking_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE bookings SET status = 'Cancelled', cancelled_at = %s WHERE booking_id = %s",
            (to_db_utc(now_utc), booking_id),
        )

    def mark_expired(self, booking_id: str) -> None:
        self._cursor.execute(
            "UPDATE bookings SET status = 'Expired' WHERE booking_id = %s AND status = 'Reserved'",
            (booking_id,),
        )

    def list_by_user(
        self,
        user_id: int,
        status_filter: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Booking]:
        if status_filter:
            self._cursor.execute(
                "SELECT b.booking_id, b.user_id, b.vehicle_id, b.slot_id, b.status, "
                "b.created_at, b.expires_at, b.checkin_started_at, b.checked_in_at, "
                "b.completed_at, b.cancelled_at, b.checkin_event_id, v.plate_number "
                "FROM bookings b "
                "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
                "WHERE b.user_id = %s AND b.status = %s "
                "ORDER BY b.created_at DESC LIMIT %s OFFSET %s",
                (int(user_id), status_filter, int(limit), int(offset)),
            )
        else:
            self._cursor.execute(
                "SELECT b.booking_id, b.user_id, b.vehicle_id, b.slot_id, b.status, "
                "b.created_at, b.expires_at, b.checkin_started_at, b.checked_in_at, "
                "b.completed_at, b.cancelled_at, b.checkin_event_id, v.plate_number "
                "FROM bookings b "
                "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
                "WHERE b.user_id = %s "
                "ORDER BY b.created_at DESC LIMIT %s OFFSET %s",
                (int(user_id), int(limit), int(offset)),
            )
        return [_row_to_booking(r) for r in self._cursor.fetchall()]

    def list_all_admin(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if status_filter:
            self._cursor.execute(
                "SELECT b.*, v.plate_number, u.username, u.display_name "
                "FROM bookings b "
                "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
                "LEFT JOIN users u ON u.user_id = b.user_id "
                "WHERE b.status = %s "
                "ORDER BY b.created_at DESC LIMIT %s OFFSET %s",
                (status_filter, int(limit), int(offset)),
            )
        else:
            self._cursor.execute(
                "SELECT b.*, v.plate_number, u.username, u.display_name "
                "FROM bookings b "
                "LEFT JOIN vehicles v ON v.vehicle_id = b.vehicle_id "
                "LEFT JOIN users u ON u.user_id = b.user_id "
                "ORDER BY b.created_at DESC LIMIT %s OFFSET %s",
                (int(limit), int(offset)),
            )
        return list(self._cursor.fetchall())
