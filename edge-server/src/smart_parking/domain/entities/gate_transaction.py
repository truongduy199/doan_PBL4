"""Gate Transaction Entity."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import Direction

@dataclass
class GateTransaction:
    gate_transaction_id: str
    event_id: str
    direction: Direction
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None