-- P4 closure: event case handling and durable, safe alert operations.
CREATE TABLE IF NOT EXISTS event_dispositions (
    event_id INTEGER PRIMARY KEY REFERENCES attack_events(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','investigating','resolved','false_positive','ignored')),
    handling_note TEXT,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0,1)),
    minimum_severity INTEGER NOT NULL CHECK (minimum_severity BETWEEN 1 AND 5),
    event_threshold INTEGER NOT NULL DEFAULT 1 CHECK (event_threshold >= 1),
    window_minutes INTEGER NOT NULL DEFAULT 5 CHECK (window_minutes BETWEEN 1 AND 1440),
    quiet_start TEXT,
    quiet_end TEXT,
    suppression_minutes INTEGER NOT NULL DEFAULT 15 CHECK (suppression_minutes BETWEEN 0 AND 10080),
    channels_json TEXT NOT NULL DEFAULT '["simulation"]',
    recipients_json TEXT NOT NULL DEFAULT '[]',
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alert_deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER REFERENCES alert_rules(id) ON DELETE SET NULL,
    alert_id INTEGER REFERENCES alerts(id) ON DELETE SET NULL,
    channel TEXT NOT NULL CHECK (channel IN ('email','telegram','webhook','simulation')),
    destination TEXT,
    status TEXT NOT NULL CHECK (status IN ('simulated','sent','failed','suppressed')),
    error_code TEXT,
    dedup_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_event_dispositions_status ON event_dispositions(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled);
CREATE INDEX IF NOT EXISTS idx_alert_deliveries_dedup ON alert_deliveries(dedup_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_blocks_expiry ON blocked_ips(active, expires_at);
