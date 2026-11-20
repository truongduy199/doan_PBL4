"""Slot Repository for `parking_slots` table (Lock Rank 2)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from smart_parking.config.constants import SLOT_IDS, SLOT_SENSOR_MAP
from smart_parking.domain.entities.parking_slot import ParkingSlot
from smart_parking.domain.enums import PhysicalSlotStatus
from smart_parking.infrastructure.database.mysql_db import (
    DBCursorProtocol,
    LockOrderTracker,
    from_db_utc,
    to_db_utc,
    utc_now,
)


def _row_to_slot(row: Dict[str, Any]) -> ParkingSlot:
    return ParkingSlot(
        slot_id=str(row["slot_id"]),
        sensor_id=str(row["sensor_id"]),
        physical_status=PhysicalSlotStatus(row["physical_status"]),
        active_booking_id=row.get("active_booking_id"),
        reserved_session_id=row.get("reserved_session_id"),
        last_boot_id=row.get("last_boot_id"),
        last_sequence=int(row["last_sequence"]) if row.get("last_sequence") is not None else None,
        last_seen_at=from_db_utc(row.get("last_seen_at")),
        updated_at=from_db_utc(row["updated_at"]) or utc_now(),
    )


class SlotRepository:
    """Data access layer for `parking_slots` table with mandatory lock rank 2 (`parking_slots`)."""

    def __init__(self, cursor: DBCursorProtocol, lock_tracker: LockOrderTracker) -> None:
        self._cursor = cursor
        self._locks = lock_tracker

    def get_all_slots(self) -> List[ParkingSlot]:
        self._cursor.execute(
            "SELECT slot_id, sensor_id, physical_status, active_booking_id, reserved_session_id, "
            "last_boot_id, last_sequence, last_seen_at, updated_at "
            "FROM parking_slots ORDER BY slot_id ASC"
        )
        return [_row_to_slot(r) for r in self._cursor.fetchall()]

    def get_by_id(self, slot_id: str) -> Optional[ParkingSlot]:
        self._cursor.execute(
            "SELECT slot_id, sensor_id, physical_status, active_booking_id, reserved_session_id, "
            "last_boot_id, last_sequence, last_seen_at, updated_at "
            "FROM parking_slots WHERE slot_id = %s",
            (slot_id.strip().upper(),),
        )
        row = self._cursor.fetchone()
        return _row_to_slot(row) if row else None

    def lock_by_id_for_update(self, slot_id: str) -> Optional[ParkingSlot]:
        """Rank 2 row lock: SELECT ... FROM parking_slots WHERE slot_id = %s FOR UPDATE."""
        self._locks.record_lock("parking_slots")
        self._cursor.execute(
            "SELECT slot_id, sensor_id, physical_status, active_booking_id, reserved_session_id, "
            "last_boot_id, last_sequence, last_seen_at, updated_at "
            "FROM parking_slots WHERE slot_id = %s FOR UPDATE",
            (slot_id.strip().upper(),),
        )
        row = self._cursor.fetchone()
        return _row_to_slot(row) if row else None

    def lock_all_slots_for_update(self) -> List[ParkingSlot]:
        """Rank 2 row lock on all 4 slots ordered by slot_id ASC."""
        self._locks.record_lock("parking_slots")
        self._cursor.execute(
            "SELECT slot_id, sensor_id, physical_status, active_booking_id, reserved_session_id, "
            "last_boot_id, last_sequence, last_seen_at, updated_at "
            "FROM parking_slots ORDER BY slot_id ASC FOR UPDATE"
        )
        return [_row_to_slot(r) for r in self._cursor.fetchall()]

    def seed_default_slots(
        self,
        initial_physical_status: str = "Unknown",
        last_seen_at: Optional[datetime] = None,
        now_utc: Optional[datetime] = None,
    ) -> List[ParkingSlot]:
        """Ensure the 4 fixed slots (A1, A2, B1, B2) exist in `parking_slots` idempotently."""
        now_dt = to_db_utc(now_utc or utc_now())
        seen_dt = to_db_utc(last_seen_at)
        for slot_id in SLOT_IDS:
            sensor_id = SLOT_SENSOR_MAP[slot_id]
            existing = self.get_by_id(slot_id)
            if existing is None:
                self._cursor.execute(
                    "INSERT INTO parking_slots ("
                    "slot_id, sensor_id, physical_status, active_booking_id, reserved_session_id, "
                    "last_boot_id, last_sequence, last_seen_at, updated_at"
                    ") VALUES (%s, %s, %s, NULL, NULL, NULL, NULL, %s, %s)",
                    (slot_id, sensor_id, initial_physical_status, seen_dt, now_dt),
                )
        return self.get_all_slots()

    def assign_booking(self, slot_id: str, booking_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE parking_slots SET active_booking_id = %s, updated_at = %s WHERE slot_id = %s",
            (booking_id, to_db_utc(now_utc), slot_id),
        )

    def release_booking_if_matches(self, slot_id: str, booking_id: str, now_utc: datetime) -> bool:
        """
        Clear active_booking_id = NULL ONLY if active_booking_id currently equals booking_id.
        Never touches reserved_session_id.
        """
        self._cursor.execute(
            "UPDATE parking_slots SET active_booking_id = NULL, updated_at = %s "
            "WHERE slot_id = %s AND active_booking_id = %s",
            (to_db_utc(now_utc), slot_id, booking_id),
        )
        return bool(self._cursor.rowcount > 0)

    def assign_session(self, slot_id: str, session_id: str, now_utc: datetime) -> None:
        self._cursor.execute(
            "UPDATE parking_slots SET reserved_session_id = %s, updated_at = %s WHERE slot_id = %s",
            (session_id, to_db_utc(now_utc), slot_id),
        )

    def release_session_if_matches(self, slot_id: str, session_id: str, now_utc: datetime) -> bool:
        self._cursor.execute(
            "UPDATE parking_slots SET reserved_session_id = NULL, updated_at = %s "
            "WHERE slot_id = %s AND reserved_session_id = %s",
            (to_db_utc(now_utc), slot_id, session_id),
        )
        return bool(self._cursor.rowcount > 0)

    def update_ir_sensor(
        self,
        slot_id: str,
        physical_status: str,
        boot_id: str,
        sequence: int,
        seen_at: datetime,
    ) -> None:
        seen_dt = to_db_utc(seen_at)
        self._cursor.execute(
            "UPDATE parking_slots "
            "SET physical_status = %s, last_boot_id = %s, last_sequence = %s, "
            "last_seen_at = %s, updated_at = %s "
            "WHERE slot_id = %s",
            (physical_status, boot_id, int(sequence), seen_dt, seen_dt, slot_id),
        )
