"""System Event Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

@dataclass
class SystemEvent:
    event_id: str
    type: str
    created_at: datetime
    session_id: Optional[str] = None
    reason_code: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None