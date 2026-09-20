"""Parking Slot Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import SlotStatus

@dataclass
class ParkingSlot:
    slot_id: str
    status: SlotStatus
    assigned_session_id: Optional[str]
    updated_at: datetime