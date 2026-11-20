"""HTTP Route Modules Package."""
from smart_parking.interfaces.http.routes import (
    admin,
    auth,
    bookings,
    health,
    realtime,
    reviews,
    slots,
)

__all__ = ["admin", "auth", "bookings", "health", "realtime", "reviews", "slots"]
