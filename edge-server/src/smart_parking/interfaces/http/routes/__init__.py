"""HTTP Route Modules Package."""
from smart_parking.interfaces.http.routes import (
    admin,
    auth,
    bookings,
    device,
    health,
    realtime,
    reviews,
    slots,
)

__all__ = ["admin", "auth", "bookings", "device", "health", "realtime", "reviews", "slots"]
