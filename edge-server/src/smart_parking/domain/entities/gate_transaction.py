"""Gate Event Entity (replaces legacy GateTransaction)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from smart_parking.domain.enums import Direction, GateDecision, GateId, LivenessStatus, PassageStatus


@dataclass
class GateEvent:
    event_id: str
    gate_id: GateId
    device_id: str
    decision: GateDecision
    passage_status: PassageStatus
    created_at: datetime
    session_id: Optional[str] = None
    booking_id: Optional[str] = None
    reason_code: Optional[str] = None
    liveness_status: Optional[LivenessStatus] = None
    liveness_score: Optional[float] = None
    liveness_model_version: Optional[str] = None
    face_config_version: Optional[str] = None
    command_id: Optional[str] = None
    reviewer_id: Optional[int] = None
    review_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    passed_at: Optional[datetime] = None


@dataclass
class GateTransaction:
    """Backwards-compatible alias entity."""
    gate_transaction_id: str
    event_id: str
    direction: Direction
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
