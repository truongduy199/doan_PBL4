"""Unit of Work Pattern with Short Transactions, Lock Order Tracking, and Deadlock Retries."""
from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, TypeVar

from smart_parking.infrastructure.database.booking_repository import BookingRepository
from smart_parking.infrastructure.database.event_repository import (
    GateEventRepository,
    ParkingLogRepository,
)
from smart_parking.infrastructure.database.mysql_db import (
    LockOrderTracker,
    MySQLDatabase,
)
from smart_parking.infrastructure.database.review_repository import ReviewRepository
from smart_parking.infrastructure.database.session_repository import SessionRepository
from smart_parking.infrastructure.database.slot_repository import SlotRepository
from smart_parking.infrastructure.database.user_repository import (
    FaceTemplateRepository,
    UserRepository,
    VehicleRepository,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")


class TransactionContext:
    """Holds all repositories bound to a single active DB transaction cursor and lock tracker."""

    def __init__(self, cursor: Any, lock_tracker: LockOrderTracker) -> None:
        self.cursor = cursor
        self.lock_tracker = lock_tracker
        self.users = UserRepository(cursor, lock_tracker)
        self.vehicles = VehicleRepository(cursor, lock_tracker)
        self.face_templates = FaceTemplateRepository(cursor, lock_tracker)
        self.slots = SlotRepository(cursor, lock_tracker)
        self.bookings = BookingRepository(cursor, lock_tracker)
        self.sessions = SessionRepository(cursor, lock_tracker)
        self.gate_events = GateEventRepository(cursor, lock_tracker)
        self.parking_logs = ParkingLogRepository(cursor, lock_tracker)
        self.reviews = ReviewRepository(cursor, lock_tracker)


class UnitOfWork:
    """
    Manages short MySQL/InnoDB transactions with:
    - Mandatory lock ordering (`vehicles -> parking_slots -> bookings -> sessions -> gate_events`)
    - Bounded retry on InnoDB deadlock (1213) / lock wait timeout (1205)
    """

    def __init__(self, db: MySQLDatabase, max_deadlock_retries: Optional[int] = None) -> None:
        self.db = db
        self.max_deadlock_retries = (
            max_deadlock_retries
            if max_deadlock_retries is not None
            else getattr(db.settings, "mysql_deadlock_retries", 3)
        )

    @contextmanager
    def transaction(self, readonly: bool = False) -> Iterator[TransactionContext]:
        """Open a short transaction context and commit on exit (or rollback on exception)."""
        conn = self.db.get_connection()
        cursor = conn.cursor(dictionary=True)
        lock_tracker = LockOrderTracker()
        tx = TransactionContext(cursor=cursor, lock_tracker=lock_tracker)
        try:
            yield tx
            if readonly:
                conn.rollback()
            else:
                conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def run_transactional(
        self,
        operation: Callable[[TransactionContext], T],
        readonly: bool = False,
    ) -> T:
        """
        Execute `operation(tx)` inside a short MySQL transaction.
        Automatically rolls back and retries up to `max_deadlock_retries` times on InnoDB deadlock.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                with self.transaction(readonly=readonly) as tx:
                    return operation(tx)
            except BaseException as exc:
                if self.db.is_deadlock_error(exc) and attempt <= self.max_deadlock_retries:
                    backoff_sec = 0.03 * attempt
                    logger.warning(
                        "MySQL deadlock/lock timeout detected (attempt %d/%d). Retrying in %.2fs...",
                        attempt,
                        self.max_deadlock_retries,
                        backoff_sec,
                    )
                    time.sleep(backoff_sec)
                    continue
                raise
