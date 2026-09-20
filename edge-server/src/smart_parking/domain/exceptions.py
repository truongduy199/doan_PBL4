"""Domain Exceptions."""
class DomainException(Exception):
    """Base domain exception."""

class SlotNotAvailableException(DomainException):
    """Bãi đỗ đã hết ô trống."""

class SessionNotFoundException(DomainException):
    """Không tìm thấy phiên đỗ xe."""

class GateOperationException(DomainException):
    """Lỗi vận hành cổng."""