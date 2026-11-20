"""Domain Exceptions for Smart Parking PBL4."""
from typing import Optional


class DomainException(Exception):
    """Base domain exception with structured reason_code and HTTP status mapping."""

    def __init__(
        self,
        message: str,
        reason_code: str = "DOMAIN_ERROR",
        http_status: int = 400,
        details: Optional[dict] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        self.http_status = http_status
        self.details = details or {}


class AuthenticationException(DomainException):
    """Sai thông tin đăng nhập hoặc token không hợp lệ."""

    def __init__(self, message: str = "Thông tin đăng nhập không hợp lệ.", reason_code: str = "AUTH_FAILED"):
        super().__init__(message, reason_code=reason_code, http_status=401)


class AuthorizationException(DomainException):
    """Không đủ quyền truy cập tài nguyên (RBAC 403)."""

    def __init__(self, message: str = "Bạn không có quyền thực hiện thao tác này.", reason_code: str = "FORBIDDEN"):
        super().__init__(message, reason_code=reason_code, http_status=403)


class ResourceNotFoundException(DomainException):
    """Không tìm thấy bản ghi yêu cầu (404)."""

    def __init__(self, message: str = "Không tìm thấy dữ liệu yêu cầu.", reason_code: str = "NOT_FOUND"):
        super().__init__(message, reason_code=reason_code, http_status=404)


class SlotNotAvailableException(DomainException):
    """Ô đỗ không khả dụng (đã có người đặt, đang có xe, hoặc dữ liệu cảm biến quá hạn/lỗi)."""

    def __init__(
        self,
        message: str = "Ô đỗ hiện không khả dụng để đặt hoặc cấp phát.",
        reason_code: str = "SLOT_NOT_AVAILABLE",
        details: Optional[dict] = None,
    ):
        super().__init__(message, reason_code=reason_code, http_status=409, details=details)


class BookingConflictException(DomainException):
    """Xung đột đặt chỗ (xe đã có booking/session hoạt động hoặc không thể hủy)."""

    def __init__(
        self,
        message: str = "Xung đột trạng thái đặt chỗ.",
        reason_code: str = "BOOKING_CONFLICT",
        details: Optional[dict] = None,
    ):
        super().__init__(message, reason_code=reason_code, http_status=409, details=details)


class SessionNotFoundException(ResourceNotFoundException):
    """Không tìm thấy phiên đỗ xe."""

    def __init__(self, message: str = "Không tìm thấy phiên đỗ xe."):
        super().__init__(message, reason_code="SESSION_NOT_FOUND")


class GateOperationException(DomainException):
    """Lỗi vận hành cổng vào/ra."""

    def __init__(
        self,
        message: str = "Lỗi vận hành cổng.",
        reason_code: str = "GATE_OPERATION_ERROR",
        http_status: int = 409,
    ):
        super().__init__(message, reason_code=reason_code, http_status=http_status)
