"""Canonical Domain Enums aligned with the MySQL/InnoDB specification (18/11/2026)."""
from enum import Enum


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class AccountStatus(str, Enum):
    ACTIVE = "Active"
    DISABLED = "Disabled"


class FaceTemplateStatus(str, Enum):
    ACTIVE = "Active"
    REPLACED = "Replaced"
    REVOKED = "Revoked"


class LivenessStatus(str, Enum):
    PASSED = "Passed"
    FAILED = "Failed"
    ERROR = "Error"
    UNAVAILABLE = "Unavailable"
    NOT_USED = "Not_used"


class BookingStatus(str, Enum):
    RESERVED = "Reserved"
    CHECKIN_PENDING = "Checkin_pending"
    CHECKED_IN = "Checked_in"
    COMPLETED = "Completed"
    EXPIRED = "Expired"
    CANCELLED = "Cancelled"


class SessionStatus(str, Enum):
    ENTRY_PENDING = "Entry_pending"
    ACTIVE = "Active"
    EXIT_PENDING = "Exit_pending"
    CLOSED = "Closed"
    CANCELLED = "Cancelled"


class ParkingStatus(str, Enum):
    NOT_ARRIVED = "Not_arrived"
    PARKING_PENDING = "Parking_pending"
    PARKED_CONFIRMED = "Parked_confirmed"
    PARKING_REVIEW_REQUIRED = "Parking_review_required"
    PARKING_TIMEOUT = "Parking_timeout"


class PhysicalSlotStatus(str, Enum):
    FREE = "Free"
    OCCUPIED = "Occupied"
    UNKNOWN = "Unknown"
    FAULT = "Fault"


class DisplaySlotStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ASSIGNED_PENDING = "ASSIGNED_PENDING"
    OCCUPIED = "OCCUPIED"
    UNKNOWN_OR_FAULT = "UNKNOWN_OR_FAULT"


# Legacy alias for backwards compatibility
SlotStatus = PhysicalSlotStatus


class GateId(str, Enum):
    IN = "IN"
    OUT = "OUT"


Direction = GateId


class GateDecision(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    DENIED = "Denied"
    REVIEW_REQUIRED = "Review_required"


class PassageStatus(str, Enum):
    WAITING = "Waiting"
    CONFIRMED = "Confirmed"
    CANCELLED = "Cancelled"
    UNKNOWN = "Unknown"


class GateStatus(str, Enum):
    IDLE = "IDLE"
    WAITING_VEHICLE = "WAITING_VEHICLE"
    BARRIER_OPEN = "BARRIER_OPEN"
    WAITING_PASSAGE = "WAITING_PASSAGE"
    CLOSING = "CLOSING"
    FAULT = "FAULT"


class LogEventType(str, Enum):
    GATE_IN = "GATE_IN"
    GATE_OUT = "GATE_OUT"
    SLOT_UPDATE = "SLOT_UPDATE"
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_EXPIRED = "BOOKING_EXPIRED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    RETENTION_PURGE = "RETENTION_PURGE"
    FACE_TEMPLATE_UPDATED = "FACE_TEMPLATE_UPDATED"
    ERROR = "ERROR"
