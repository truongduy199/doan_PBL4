-- 001_mysql_tables.sql
-- MySQL / InnoDB Schema for PBL4 Smart Parking IoT System (Chốt ngày 18/11/2026)
-- All timestamps are stored in UTC as DATETIME(3).

-- 1. users
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(150) NULL,
    role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    created_at DATETIME(3) NOT NULL,
    updated_at DATETIME(3) NOT NULL,
    UNIQUE KEY uq_users_username (username),
    CONSTRAINT chk_users_role CHECK (role IN ('user', 'admin')),
    CONSTRAINT chk_users_status CHECK (status IN ('Active', 'Disabled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. vehicles
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    plate_number VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    created_at DATETIME(3) NOT NULL,
    updated_at DATETIME(3) NOT NULL,
    UNIQUE KEY uq_vehicles_plate_number (plate_number),
    KEY idx_vehicles_user_id (user_id),
    CONSTRAINT fk_vehicles_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT chk_vehicles_status CHECK (status IN ('Active', 'Disabled'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. user_face_templates
CREATE TABLE IF NOT EXISTS user_face_templates (
    template_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    embedding_blob BLOB NOT NULL,
    embedding_size SMALLINT UNSIGNED NOT NULL DEFAULT 512,
    embedding_dtype VARCHAR(20) NOT NULL DEFAULT 'float32',
    model_id VARCHAR(100) NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    config_version VARCHAR(50) NOT NULL,
    quality_score FLOAT NULL,
    liveness_status VARCHAR(30) NOT NULL,
    liveness_score FLOAT NULL,
    key_version VARCHAR(50) NOT NULL,
    encryption_metadata JSON NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    created_at DATETIME(3) NOT NULL,
    revoked_at DATETIME(3) NULL,
    active_user_id BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN status = 'Active' THEN user_id ELSE NULL END
    ) STORED,
    UNIQUE KEY uq_user_face_templates_active_user (active_user_id),
    KEY idx_user_face_templates_user_status (user_id, status),
    CONSTRAINT fk_user_face_templates_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT chk_user_face_liveness CHECK (
        liveness_status IN ('Passed', 'Failed', 'Error', 'Unavailable', 'Not_used')
    ),
    CONSTRAINT chk_user_face_status CHECK (
        status IN ('Active', 'Replaced', 'Revoked')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. parking_slots (Circular FKs active_booking_id and reserved_session_id added in 002)
CREATE TABLE IF NOT EXISTS parking_slots (
    slot_id VARCHAR(10) PRIMARY KEY,
    sensor_id VARCHAR(50) NOT NULL,
    physical_status VARCHAR(20) NOT NULL DEFAULT 'Unknown',
    active_booking_id CHAR(36) NULL,
    reserved_session_id CHAR(36) NULL,
    last_boot_id VARCHAR(64) NULL,
    last_sequence BIGINT UNSIGNED NULL,
    last_seen_at DATETIME(3) NULL,
    updated_at DATETIME(3) NOT NULL,
    UNIQUE KEY uq_parking_slots_sensor_id (sensor_id),
    UNIQUE KEY uq_parking_slots_active_booking (active_booking_id),
    UNIQUE KEY uq_parking_slots_reserved_session (reserved_session_id),
    CONSTRAINT chk_parking_slots_id CHECK (slot_id IN ('A1', 'A2', 'B1', 'B2')),
    CONSTRAINT chk_parking_slots_physical_status CHECK (
        physical_status IN ('Free', 'Occupied', 'Unknown', 'Fault')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. bookings (Circular FK checkin_event_id added in 002; NO UNIQUE on slot_id to preserve history)
CREATE TABLE IF NOT EXISTS bookings (
    booking_id CHAR(36) PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    vehicle_id BIGINT UNSIGNED NOT NULL,
    slot_id VARCHAR(10) NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at DATETIME(3) NOT NULL,
    expires_at DATETIME(3) NOT NULL,
    checkin_started_at DATETIME(3) NULL,
    checked_in_at DATETIME(3) NULL,
    completed_at DATETIME(3) NULL,
    cancelled_at DATETIME(3) NULL,
    checkin_event_id CHAR(36) NULL,
    active_vehicle_booking BIGINT UNSIGNED GENERATED ALWAYS AS (
        CASE WHEN status IN ('Reserved', 'Checkin_pending') THEN vehicle_id ELSE NULL END
    ) STORED,
    UNIQUE KEY uq_bookings_active_vehicle (active_vehicle_booking),
    KEY idx_bookings_status_expires (status, expires_at),
    KEY idx_bookings_vehicle_status (vehicle_id, status),
    KEY idx_bookings_user_created (user_id, created_at),
    KEY idx_bookings_slot_id (slot_id),
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_bookings_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    CONSTRAINT fk_bookings_slot FOREIGN KEY (slot_id) REFERENCES parking_slots(slot_id),
    CONSTRAINT chk_bookings_status CHECK (
        status IN ('Reserved', 'Checkin_pending', 'Checked_in', 'Completed', 'Expired', 'Cancelled')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. sessions
CREATE TABLE IF NOT EXISTS sessions (
    session_id CHAR(36) PRIMARY KEY,
    plate_number VARCHAR(20) NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    vehicle_id BIGINT UNSIGNED NULL,
    booking_id CHAR(36) NULL,
    assigned_slot_id VARCHAR(10) NOT NULL,
    status VARCHAR(30) NOT NULL,
    parking_status VARCHAR(40) NOT NULL,
    ocr_confidence FLOAT NULL,
    entry_time DATETIME(3) NULL,
    exit_time DATETIME(3) NULL,
    created_at DATETIME(3) NOT NULL,
    updated_at DATETIME(3) NOT NULL,
    live_plate VARCHAR(20) GENERATED ALWAYS AS (
        CASE WHEN status IN ('Entry_pending', 'Active', 'Exit_pending') THEN plate_number ELSE NULL END
    ) STORED,
    UNIQUE KEY uq_sessions_booking_id (booking_id),
    UNIQUE KEY uq_sessions_live_plate (live_plate),
    KEY idx_sessions_plate_status (plate_number, status),
    KEY idx_sessions_user_id (user_id),
    KEY idx_sessions_assigned_slot (assigned_slot_id),
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT fk_sessions_vehicle FOREIGN KEY (vehicle_id) REFERENCES vehicles(vehicle_id),
    CONSTRAINT fk_sessions_booking FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
    CONSTRAINT fk_sessions_assigned_slot FOREIGN KEY (assigned_slot_id) REFERENCES parking_slots(slot_id),
    CONSTRAINT chk_sessions_status CHECK (
        status IN ('Entry_pending', 'Active', 'Exit_pending', 'Closed', 'Cancelled')
    ),
    CONSTRAINT chk_sessions_parking_status CHECK (
        parking_status IN (
            'Not_arrived',
            'Parking_pending',
            'Parked_confirmed',
            'Parking_review_required',
            'Parking_timeout'
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. session_face_templates
CREATE TABLE IF NOT EXISTS session_face_templates (
    template_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id CHAR(36) NOT NULL,
    embedding_blob BLOB NOT NULL,
    embedding_size SMALLINT UNSIGNED NOT NULL DEFAULT 512,
    embedding_dtype VARCHAR(20) NOT NULL DEFAULT 'float32',
    model_id VARCHAR(100) NOT NULL,
    model_version VARCHAR(100) NOT NULL,
    config_version VARCHAR(50) NOT NULL,
    quality_score FLOAT NULL,
    liveness_status VARCHAR(30) NOT NULL,
    liveness_score FLOAT NULL,
    key_version VARCHAR(50) NOT NULL,
    encryption_metadata JSON NOT NULL,
    captured_at DATETIME(3) NOT NULL,
    expires_at DATETIME(3) NULL,
    UNIQUE KEY uq_session_face_templates_session (session_id),
    KEY idx_session_face_templates_expires (expires_at),
    CONSTRAINT fk_session_face_templates_session FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    CONSTRAINT chk_session_face_liveness CHECK (
        liveness_status IN ('Passed', 'Failed', 'Error', 'Unavailable', 'Not_used')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. gate_events
CREATE TABLE IF NOT EXISTS gate_events (
    event_id CHAR(36) PRIMARY KEY,
    gate_id VARCHAR(10) NOT NULL,
    device_id VARCHAR(50) NOT NULL,
    session_id CHAR(36) NULL,
    booking_id CHAR(36) NULL,
    decision VARCHAR(30) NOT NULL,
    passage_status VARCHAR(30) NOT NULL,
    reason_code VARCHAR(60) NULL,
    liveness_status VARCHAR(30) NULL,
    liveness_score FLOAT NULL,
    liveness_model_version VARCHAR(100) NULL,
    face_config_version VARCHAR(50) NULL,
    command_id CHAR(36) NULL,
    reviewer_id BIGINT UNSIGNED NULL,
    review_reason TEXT NULL,
    created_at DATETIME(3) NOT NULL,
    decided_at DATETIME(3) NULL,
    passed_at DATETIME(3) NULL,
    KEY idx_gate_events_session_created (session_id, created_at),
    KEY idx_gate_events_booking_id (booking_id),
    KEY idx_gate_events_decision (decision),
    CONSTRAINT fk_gate_events_session FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    CONSTRAINT fk_gate_events_booking FOREIGN KEY (booking_id) REFERENCES bookings(booking_id),
    CONSTRAINT fk_gate_events_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(user_id),
    CONSTRAINT chk_gate_events_gate_id CHECK (gate_id IN ('IN', 'OUT')),
    CONSTRAINT chk_gate_events_decision CHECK (
        decision IN ('Pending', 'Approved', 'Denied', 'Review_required')
    ),
    CONSTRAINT chk_gate_events_passage_status CHECK (
        passage_status IN ('Waiting', 'Confirmed', 'Cancelled', 'Unknown')
    ),
    CONSTRAINT chk_gate_events_liveness CHECK (
        liveness_status IS NULL OR liveness_status IN ('Passed', 'Failed', 'Error', 'Unavailable', 'Not_used')
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. parking_logs
CREATE TABLE IF NOT EXISTS parking_logs (
    log_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    event_id CHAR(36) NULL,
    session_id CHAR(36) NULL,
    actor_user_id BIGINT UNSIGNED NULL,
    event_type VARCHAR(50) NOT NULL,
    reason_code VARCHAR(60) NOT NULL,
    details JSON NULL,
    created_at DATETIME(3) NOT NULL,
    KEY idx_parking_logs_session_created (session_id, created_at),
    KEY idx_parking_logs_event_id (event_id),
    KEY idx_parking_logs_event_type_created (event_type, created_at),
    CONSTRAINT fk_parking_logs_event FOREIGN KEY (event_id) REFERENCES gate_events(event_id),
    CONSTRAINT fk_parking_logs_session FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    CONSTRAINT fk_parking_logs_actor FOREIGN KEY (actor_user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
