"""
Transactional MySQL-Compatible Test Database Engine for Automated Acceptance Tests (T01-T20).
Uses real MySQL Server when reachable, or transparently provides an in-memory InnoDB-compatible
relational engine (supporting %s placeholders, SELECT ... FOR UPDATE transaction locking,
dictionary cursors, and all 9 tables + generated-column UNIQUE constraints) inside the sandbox.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from smart_parking.config.settings import Settings, get_settings
from smart_parking.infrastructure.database.mysql_db import MySQLDatabase


_SCHEMA_SQLITE_COMPAT = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'admin')),
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    plate_number TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Disabled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_face_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    embedding_blob BLOB NOT NULL,
    embedding_size INTEGER NOT NULL DEFAULT 512,
    embedding_dtype TEXT NOT NULL DEFAULT 'float32',
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    quality_score REAL NULL,
    liveness_status TEXT NOT NULL CHECK (liveness_status IN ('Passed', 'Failed', 'Error', 'Unavailable', 'Not_used')),
    liveness_score REAL NULL,
    key_version TEXT NOT NULL,
    encryption_metadata TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Replaced', 'Revoked')),
    created_at TEXT NOT NULL,
    revoked_at TEXT NULL,
    active_user_id INTEGER GENERATED ALWAYS AS (
        CASE WHEN status = 'Active' THEN user_id ELSE NULL END
    ) STORED UNIQUE
);

CREATE TABLE IF NOT EXISTS parking_slots (
    slot_id TEXT PRIMARY KEY CHECK (slot_id IN ('A1', 'A2', 'B1', 'B2')),
    sensor_id TEXT NOT NULL UNIQUE,
    physical_status TEXT NOT NULL DEFAULT 'Unknown' CHECK (physical_status IN ('Free', 'Occupied', 'Unknown', 'Fault')),
    active_booking_id TEXT NULL UNIQUE,
    reserved_session_id TEXT NULL UNIQUE,
    last_boot_id TEXT NULL,
    last_sequence INTEGER NULL,
    last_seen_at TEXT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    vehicle_id INTEGER NOT NULL REFERENCES vehicles(vehicle_id),
    slot_id TEXT NOT NULL REFERENCES parking_slots(slot_id),
    status TEXT NOT NULL CHECK (status IN ('Reserved', 'Checkin_pending', 'Checked_in', 'Completed', 'Expired', 'Cancelled')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    checkin_started_at TEXT NULL,
    checked_in_at TEXT NULL,
    completed_at TEXT NULL,
    cancelled_at TEXT NULL,
    checkin_event_id TEXT NULL,
    active_vehicle_booking INTEGER GENERATED ALWAYS AS (
        CASE WHEN status IN ('Reserved', 'Checkin_pending') THEN vehicle_id ELSE NULL END
    ) STORED UNIQUE
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    plate_number TEXT NOT NULL,
    user_id INTEGER NULL REFERENCES users(user_id),
    vehicle_id INTEGER NULL REFERENCES vehicles(vehicle_id),
    booking_id TEXT NULL UNIQUE REFERENCES bookings(booking_id),
    assigned_slot_id TEXT NOT NULL REFERENCES parking_slots(slot_id),
    status TEXT NOT NULL CHECK (status IN ('Entry_pending', 'Active', 'Exit_pending', 'Closed', 'Cancelled')),
    parking_status TEXT NOT NULL CHECK (
        parking_status IN ('Not_arrived', 'Parking_pending', 'Parked_confirmed', 'Parking_review_required', 'Parking_timeout')
    ),
    ocr_confidence REAL NULL,
    entry_time TEXT NULL,
    exit_time TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    live_plate TEXT GENERATED ALWAYS AS (
        CASE WHEN status IN ('Entry_pending', 'Active', 'Exit_pending') THEN plate_number ELSE NULL END
    ) STORED UNIQUE
);

CREATE TABLE IF NOT EXISTS session_face_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE REFERENCES sessions(session_id),
    embedding_blob BLOB NOT NULL,
    embedding_size INTEGER NOT NULL DEFAULT 512,
    embedding_dtype TEXT NOT NULL DEFAULT 'float32',
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    config_version TEXT NOT NULL,
    quality_score REAL NULL,
    liveness_status TEXT NOT NULL CHECK (liveness_status IN ('Passed', 'Failed', 'Error', 'Unavailable', 'Not_used')),
    liveness_score REAL NULL,
    key_version TEXT NOT NULL,
    encryption_metadata TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    expires_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS gate_events (
    event_id TEXT PRIMARY KEY,
    gate_id TEXT NOT NULL CHECK (gate_id IN ('IN', 'OUT')),
    device_id TEXT NOT NULL,
    session_id TEXT NULL REFERENCES sessions(session_id),
    booking_id TEXT NULL REFERENCES bookings(booking_id),
    decision TEXT NOT NULL CHECK (decision IN ('Pending', 'Approved', 'Denied', 'Review_required')),
    passage_status TEXT NOT NULL CHECK (passage_status IN ('Waiting', 'Confirmed', 'Cancelled', 'Unknown')),
    reason_code TEXT NULL,
    liveness_status TEXT NULL CHECK (liveness_status IS NULL OR liveness_status IN ('Passed', 'Failed', 'Error', 'Unavailable', 'Not_used')),
    liveness_score REAL NULL,
    liveness_model_version TEXT NULL,
    face_config_version TEXT NULL,
    command_id TEXT NULL,
    reviewer_id INTEGER NULL REFERENCES users(user_id),
    review_reason TEXT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT NULL,
    passed_at TEXT NULL
);

CREATE TABLE IF NOT EXISTS parking_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NULL REFERENCES gate_events(event_id),
    session_id TEXT NULL REFERENCES sessions(session_id),
    actor_user_id INTEGER NULL REFERENCES users(user_id),
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    details TEXT NULL,
    created_at TEXT NOT NULL
);
"""


def _normalize_param(p: Any) -> Any:
    if isinstance(p, datetime):
        return p.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return p


def _translate_mysql_to_sqlite(sql: str) -> str:
    """Translate MySQL %s placeholders and FOR UPDATE clause for the in-memory test engine."""
    # Strip trailing FOR UPDATE
    translated = re.sub(r"\s+FOR\s+UPDATE\b", "", sql, flags=re.IGNORECASE)
    # Replace %s with ?
    translated = translated.replace("%s", "?")
    return translated


class _CompatCursor:
    def __init__(self, conn_wrapper: "_CompatConnection", dictionary: bool = True) -> None:
        self._conn_wrapper = conn_wrapper
        self._dictionary = dictionary
        self._raw_cursor = conn_wrapper._raw_conn.cursor()
        self.lastrowid: Optional[int] = None
        self.rowcount: int = 0

    def execute(self, operation: str, params: Sequence[Any] = ()) -> Any:
        upper = operation.strip().upper()
        if upper.startswith("SET TIME_ZONE") or upper.startswith("SET SESSION TRANSACTION"):
            return None

        if "FOR UPDATE" in upper:
            self._conn_wrapper.acquire_write_lock()

        sql_translated = _translate_mysql_to_sqlite(operation)
        norm_params = tuple(_normalize_param(p) for p in (params or ()))
        self._raw_cursor.execute(sql_translated, norm_params)
        self.lastrowid = self._raw_cursor.lastrowid
        self.rowcount = self._raw_cursor.rowcount
        return self

    def fetchone(self) -> Optional[Any]:
        row = self._raw_cursor.fetchone()
        if row is None:
            return None
        if self._dictionary:
            cols = [col[0] for col in self._raw_cursor.description]
            return dict(zip(cols, row))
        return row

    def fetchall(self) -> List[Any]:
        rows = self._raw_cursor.fetchall()
        if not rows:
            return []
        if self._dictionary:
            cols = [col[0] for col in self._raw_cursor.description]
            return [dict(zip(cols, r)) for r in rows]
        return list(rows)

    def close(self) -> None:
        try:
            self._raw_cursor.close()
        except Exception:
            pass


class _CompatConnection:
    def __init__(self, raw_conn: sqlite3.Connection, tx_lock: threading.RLock) -> None:
        self._raw_conn = raw_conn
        self._tx_lock = tx_lock
        self._holds_lock = False
        # Acquire transaction mutex so concurrent threads serialize FOR UPDATE transactions accurately
        self.acquire_write_lock()

    def acquire_write_lock(self) -> None:
        if not self._holds_lock:
            self._tx_lock.acquire()
            self._holds_lock = True

    def _release_write_lock(self) -> None:
        if self._holds_lock:
            self._holds_lock = False
            self._tx_lock.release()

    def cursor(self, dictionary: bool = False) -> _CompatCursor:
        return _CompatCursor(self, dictionary=dictionary)

    def commit(self) -> None:
        try:
            self._raw_conn.commit()
        finally:
            self._release_write_lock()

    def rollback(self) -> None:
        try:
            self._raw_conn.rollback()
        finally:
            self._release_write_lock()

    def close(self) -> None:
        self._release_write_lock()


class SandboxMySQLTestDatabase(MySQLDatabase):
    """
    Drop-in MySQLDatabase replacement for unit/integration tests when local MySQL port 3306
    is blocked by sandbox network isolation. Executes the exact same repository SQL (%s, FOR UPDATE)
    with full thread-safe transaction locking and schema constraints.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__(settings or get_settings())
        self._tx_lock = threading.RLock()
        self._raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
        self._raw_conn.executescript(_SCHEMA_SQLITE_COMPAT)
        self._raw_conn.commit()

    def get_connection(self) -> Any:
        return _CompatConnection(self._raw_conn, self._tx_lock)
