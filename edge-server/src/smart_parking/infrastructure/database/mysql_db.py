"""MySQL / InnoDB Connection Pool, UTC Time Utilities, and Lock Order Enforcer."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Protocol, Sequence, Tuple, TypeVar

from smart_parking.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

VN_TZ = timezone(timedelta(hours=7), name="Asia/Ho_Chi_Minh")
T = TypeVar("T")

# Mandatory row lock hierarchy (SELECT ... FOR UPDATE) to prevent deadlocks:
# 1. vehicles -> 2. parking_slots -> 3. bookings -> 4. sessions -> 5. gate_events
LOCK_ORDER_RANK: Dict[str, int] = {
    "vehicles": 1,
    "parking_slots": 2,
    "bookings": 3,
    "sessions": 4,
    "gate_events": 5,
}


def utc_now() -> datetime:
    """Return current UTC datetime truncated to millisecond precision (DATETIME(3))."""
    now = datetime.now(timezone.utc)
    ms = (now.microsecond // 1000) * 1000
    return now.replace(microsecond=ms)


def to_db_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert a datetime to naive UTC datetime with millisecond precision for MySQL DATETIME(3)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    ms = (dt.microsecond // 1000) * 1000
    return dt.replace(microsecond=ms)


def from_db_utc(val: Any) -> Optional[datetime]:
    """Convert MySQL DATETIME(3) value (datetime or ISO string) to timezone-aware UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        cleaned = val.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            parsed = datetime.strptime(cleaned[:23], "%Y-%m-%d %H:%M:%S.%f" if "." in cleaned else "%Y-%m-%d %H:%M:%S")
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TypeError(f"Không thể chuyển đổi giá trị thời gian từ DB: {val!r}")


def format_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime as UTC ISO-8601 string with millisecond precision (e.g. 2026-11-18T12:00:00.000Z)."""
    if dt is None:
        return None
    aware = from_db_utc(dt)
    if aware is None:
        return None
    return aware.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def format_vn_iso(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime in Vietnam timezone (Asia/Ho_Chi_Minh, +07:00)."""
    if dt is None:
        return None
    aware = from_db_utc(dt)
    if aware is None:
        return None
    vn_dt = aware.astimezone(VN_TZ)
    return vn_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+07:00"


class LockOrderViolationError(RuntimeError):
    """Raised when a transaction attempts to lock a table out of the canonical lock order."""


class LockOrderTracker:
    """Tracks SELECT ... FOR UPDATE table locks within a single transaction to prevent deadlocks."""

    def __init__(self) -> None:
        self._max_rank: int = 0
        self._locked_tables: list[str] = []

    def record_lock(self, table_name: str) -> None:
        rank = LOCK_ORDER_RANK.get(table_name)
        if rank is None:
            return
        if rank < self._max_rank:
            raise LockOrderViolationError(
                f"Vi phạm thứ tự khóa chống deadlock! Đã khóa {self._locked_tables} "
                f"(rank={self._max_rank}) nhưng lại yêu cầu khóa '{table_name}' (rank={rank}). "
                "Thứ tự bắt buộc: vehicles (1) -> parking_slots (2) -> bookings (3) -> sessions (4)."
            )
        self._max_rank = rank
        self._locked_tables.append(table_name)

    @property
    def locked_tables(self) -> Tuple[str, ...]:
        return tuple(self._locked_tables)


class DBCursorProtocol(Protocol):
    lastrowid: Optional[int]
    rowcount: int

    def execute(self, operation: str, params: Sequence[Any] = ()) -> Any: ...
    def fetchone(self) -> Optional[Dict[str, Any]]: ...
    def fetchall(self) -> list[Dict[str, Any]]: ...
    def close(self) -> None: ...


class MySQLDatabase:
    """MySQL / InnoDB Connection Pool Manager."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._pool: Any = None

    def _init_pool(self) -> None:
        if self._pool is not None:
            return
        from mysql.connector import pooling

        self._pool = pooling.MySQLConnectionPool(
            pool_name="smart_parking_pool",
            pool_size=self.settings.mysql_pool_size,
            pool_reset_session=True,
            host=self.settings.mysql_host,
            port=self.settings.mysql_port,
            user=self.settings.mysql_user,
            password=self.settings.mysql_password,
            database=self.settings.mysql_database,
            autocommit=False,
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci",
            use_pure=True,
        )

    def get_connection(self) -> Any:
        """Acquire a connection from the MySQL pool with UTC time_zone and READ COMMITTED isolation."""
        self._init_pool()
        conn = self._pool.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SET time_zone = '+00:00'")
            cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        finally:
            cursor.close()
        return conn

    @staticmethod
    def is_deadlock_error(exc: BaseException) -> bool:
        """Detect MySQL InnoDB Deadlock (1213) or Lock Wait Timeout (1205)."""
        errno = getattr(exc, "errno", None)
        if errno in (1205, 1213):
            return True
        msg = str(exc).lower()
        return "deadlock" in msg or "lock wait timeout" in msg
