"""Parking Slot Entity with physical status vs usage right separation."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Tuple
from smart_parking.domain.enums import DisplaySlotStatus, PhysicalSlotStatus


@dataclass
class ParkingSlot:
    slot_id: str
    sensor_id: str
    physical_status: PhysicalSlotStatus
    updated_at: datetime
    active_booking_id: Optional[str] = None
    reserved_session_id: Optional[str] = None
    last_boot_id: Optional[str] = None
    last_sequence: Optional[int] = None
    last_seen_at: Optional[datetime] = None

    def is_sensor_fresh(self, now_utc: datetime, stale_seconds: int = 30) -> bool:
        """Check if last_seen_at is present and within the configured freshness threshold."""
        if self.last_seen_at is None:
            return False
        return (now_utc - self.last_seen_at) <= timedelta(seconds=stale_seconds)

    def is_available(self, now_utc: datetime, stale_seconds: int = 30) -> bool:
        """
        Canonical availability formula:
        available(slot) = (physical_status == 'Free')
                          AND (last_seen_at is fresh within stale_seconds)
                          AND (active_booking_id IS NULL)
                          AND (reserved_session_id IS NULL)
        """
        status_val = (
            self.physical_status.value
            if isinstance(self.physical_status, PhysicalSlotStatus)
            else str(self.physical_status)
        )
        return (
            status_val == PhysicalSlotStatus.FREE.value
            and self.is_sensor_fresh(now_utc, stale_seconds)
            and self.active_booking_id is None
            and self.reserved_session_id is None
        )

    def compute_display_status(self, now_utc: datetime, stale_seconds: int = 30) -> Tuple[DisplaySlotStatus, str]:
        """Compute composite UI display status and Vietnamese label."""
        status_val = (
            self.physical_status.value
            if isinstance(self.physical_status, PhysicalSlotStatus)
            else str(self.physical_status)
        )
        fresh = self.is_sensor_fresh(now_utc, stale_seconds)

        # If physical sensor is Fault/Unknown or stale while no active reservation/occupation override:
        # Wait: even if physical is Free, if it's stale and not reserved/assigned, it is UNKNOWN_OR_FAULT!
        if status_val in (PhysicalSlotStatus.UNKNOWN.value, PhysicalSlotStatus.FAULT.value) or not fresh:
            # Note: If a slot currently has an active booking or reserved session, Wait:
            # What if a slot has active_booking_id? It is RESERVED.
            # What if physical_status is Unknown/Fault or stale and no active booking/session? UNKNOWN_OR_FAULT.
            if self.active_booking_id is not None and self.reserved_session_id is None:
                return DisplaySlotStatus.RESERVED, "Đã đặt trước"
            if self.reserved_session_id is not None and status_val != PhysicalSlotStatus.OCCUPIED.value:
                return DisplaySlotStatus.ASSIGNED_PENDING, "Đang cấp / Chờ xe đỗ"
            return DisplaySlotStatus.UNKNOWN_OR_FAULT, "Chưa đủ dữ liệu / Lỗi cảm biến"

        if status_val == PhysicalSlotStatus.OCCUPIED.value:
            return DisplaySlotStatus.OCCUPIED, "Đang có xe"

        if self.reserved_session_id is not None:
            return DisplaySlotStatus.ASSIGNED_PENDING, "Đang cấp / Chờ xe đỗ"

        if self.active_booking_id is not None:
            return DisplaySlotStatus.RESERVED, "Đã đặt trước"

        return DisplaySlotStatus.AVAILABLE, "Có thể đặt / Nhận xe"
