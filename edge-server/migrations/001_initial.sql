-- 001_initial.sql
CREATE TABLE IF NOT EXISTS parking_slots (
    slot_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('FREE', 'ASSIGNED', 'OCCUPIED', 'WRONG_VEHICLE', 'FAULT')),
    assigned_session_id TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS parking_sessions (
    session_id TEXT PRIMARY KEY,
    plate_number TEXT NOT NULL,
    assigned_slot_id TEXT REFERENCES parking_slots(slot_id),
    actual_slot_id TEXT REFERENCES parking_slots(slot_id),
    status TEXT NOT NULL CHECK(status IN ('INIT', 'ENTRY_PENDING', 'ACTIVE', 'EXIT_PENDING', 'COMPLETED', 'REJECTED', 'REVIEW_REQUIRED')),
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_time TIMESTAMP,
    plate_image_path TEXT
);

CREATE TABLE IF NOT EXISTS gate_transactions (
    gate_transaction_id TEXT PRIMARY KEY,
    event_id TEXT UNIQUE NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('IN', 'OUT')),
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    session_id TEXT,
    type TEXT NOT NULL,
    reason_code TEXT,
    payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS manual_reviews (
    review_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    operator_id TEXT,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS device_status (
    device_name TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT
);