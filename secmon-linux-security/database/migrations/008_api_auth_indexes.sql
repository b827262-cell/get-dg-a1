-- P2 API authentication/session state and read-path indexes.  Existing files are immutable.
CREATE TABLE IF NOT EXISTS api_sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_sessions_user_expiry
    ON api_sessions(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_attack_events_source_detected
    ON attack_events(source_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_attack_events_severity_detected
    ON attack_events(severity, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_attackers_score_last_seen
    ON attackers(threat_score DESC, last_seen DESC);
