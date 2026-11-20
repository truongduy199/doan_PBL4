"""Parking Session Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import ParkingStatus, SessionStatus


@dataclass
class ParkingSession:
    session_id: str
    plate_number: str
    assigned_slot_id: str
    status: SessionStatus
    parking_status: ParkingStatus = ParkingStatus.NOT_ARRIVED
    user_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    booking_id: Optional[str] = None
    ocr_confidence: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    actual_slot_id: Optional[str] = None
    plate_image_path: Optional[str] = None
