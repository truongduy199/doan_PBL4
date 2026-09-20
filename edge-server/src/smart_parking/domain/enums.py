"""Domain Enums."""
from enum import Enum

class SessionStatus(str, Enum):
    INIT = "INIT"
    ENTRY_PENDING = "ENTRY_PENDING"
    ACTIVE = "ACTIVE"
    EXIT_PENDING = "EXIT_PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"

class SlotStatus(str, Enum):
    FREE = "FREE"
    ASSIGNED = "ASSIGNED"
    OCCUPIED = "OCCUPIED"
    WRONG_VEHICLE = "WRONG_VEHICLE"
    FAULT = "FAULT"

class GateStatus(str, Enum):
    IDLE = "IDLE"
    WAITING_VEHICLE = "WAITING_VEHICLE"
    BARRIER_OPEN = "BARRIER_OPEN"
    WAITING_PASSAGE = "WAITING_PASSAGE"
    CLOSING = "CLOSING"
    FAULT = "FAULT"

class Direction(str, Enum):
    IN = "IN"
    OUT = "OUT"