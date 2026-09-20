"""Parking Session Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import SessionStatus

@dataclass
class ParkingSession:
    session_id: str
    plate_number: str
    assigned_slot_id: Optional[str]
    actual_slot_id: Optional[str]
    status: SessionStatus
    entry_time: datetime
    exit_time: Optional[datetime] = None
    plate_image_path: Optional[str] = None