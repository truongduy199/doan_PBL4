"""Gate Event DTO."""
from pydantic import BaseModel
from typing import Dict, Any

class GateEventDTO(BaseModel):
    version: int
    message_id: str
    type: str
    gate_transaction_id: str
    timestamp_ms: int
    payload: Dict[str, Any]