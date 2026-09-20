-- 002_face_templates.sql
CREATE TABLE IF NOT EXISTS face_templates (
    session_id TEXT PRIMARY KEY REFERENCES parking_sessions(session_id) ON DELETE CASCADE,
    embedding BLOB NOT NULL,
    dimension INTEGER NOT NULL DEFAULT 512,
    model_id TEXT NOT NULL,
    config_version TEXT NOT NULL,
    quality_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);