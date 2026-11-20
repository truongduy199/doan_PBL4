"""Background Workers for Booking Expiry (60m TTL) and Session Face Template Retention."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from smart_parking.application.services.booking_service import BookingService
from smart_parking.application.services.retention_service import RetentionService

logger = logging.getLogger(__name__)


class BookingExpiryAndRetentionWorker:
    """Periodically expires overdue Reserved bookings and purges expired session face templates."""

    def __init__(
        self,
        booking_service: BookingService,
        retention_service: RetentionService,
        interval_seconds: int = 5,
    ) -> None:
        self.booking_service = booking_service
        self.retention_service = retention_service
        self.interval_seconds = max(1, int(interval_seconds))
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def run_once(self) -> dict:
        """Execute a single sweep of booking expiry and template retention."""
        expired = self.booking_service.expire_overdue_bookings()
        purged = self.retention_service.purge_expired_session_templates()
        return {
            "expired_bookings_count": len(expired),
            "purged_templates_count": purged.get("purged_count", 0),
        }

    async def _loop(self) -> None:
        while self._running:
            try:
                self.run_once()
            except Exception as exc:
                logger.warning("Background expiry/retention tick error: %s", exc)
            await asyncio.sleep(self.interval_seconds)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
