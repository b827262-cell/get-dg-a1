-- ATD-B event persistence.  Interface counters cannot attribute an IP.
CREATE TABLE IF NOT EXISTS traffic_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_id INTEGER NOT NULL REFERENCES network_interfaces(id) ON DELETE CASCADE,
    ifindex INTEGER,
    interface_name TEXT NOT NULL,
    detector_type TEXT NOT NULL CHECK (detector_type = 'interface_counter'),
    severity TEXT NOT NULL CHECK (severity IN ('low','medium','high','critical')),
    state TEXT NOT NULL CHECK (state IN ('NORMAL','WATCH','ALERT','RECOVERING','RESOLVED')),
    observed_rate REAL,
    baseline REAL,
    threshold REAL,
    deviation_ratio REAL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1 CHECK (count > 0),
    resolved_at TEXT,
    evidence TEXT NOT NULL DEFAULT '{}',
    source_ip TEXT,
    destination_ip TEXT,
    port INTEGER,
    protocol TEXT,
    event_key TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_traffic_alerts_last_seen ON traffic_alerts(last_seen, id);
CREATE INDEX IF NOT EXISTS idx_traffic_alerts_state ON traffic_alerts(state, last_seen);
