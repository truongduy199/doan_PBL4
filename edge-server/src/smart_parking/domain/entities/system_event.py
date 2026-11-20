"""Parking Log Entity (Audit & Event Log)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ParkingLog:
    log_id: Optional[int]
    event_type: str
    reason_code: str
    created_at: datetime
    event_id: Optional[str] = None
    session_id: Optional[str] = None
    actor_user_id: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


# Legacy alias
SystemEvent = ParkingLog
