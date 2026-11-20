"""Booking Domain Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import BookingStatus


@dataclass
class Booking:
    booking_id: str
    user_id: int
    vehicle_id: int
    slot_id: str
    status: BookingStatus
    created_at: datetime
    expires_at: datetime
    checkin_started_at: Optional[datetime] = None
    checked_in_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    checkin_event_id: Optional[str] = None
    plate_number: Optional[str] = None
