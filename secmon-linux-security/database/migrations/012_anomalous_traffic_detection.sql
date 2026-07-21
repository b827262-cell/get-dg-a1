-- ATD-A: zero-privilege network observability schema.  Existing files are immutable.
-- Stores cumulative kernel counters (raw values); rates are derived by the API
-- via per-interface differencing.  No payload, no per-flow capture in this phase.
CREATE TABLE IF NOT EXISTS network_interfaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ifindex INTEGER,
    mac_address TEXT,
    is_loopback INTEGER NOT NULL DEFAULT 0 CHECK (is_loopback IN (0, 1)),
    is_virtual INTEGER NOT NULL DEFAULT 0 CHECK (is_virtual IN (0, 1)),
    is_up INTEGER NOT NULL DEFAULT 0 CHECK (is_up IN (0, 1)),
    mtu INTEGER,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- A name may be reused with a different ifindex across reboots or renaming;
-- the composite key tolerates that without treating name alone as immutable.
CREATE UNIQUE INDEX IF NOT EXISTS idx_network_interfaces_name_ifindex
    ON network_interfaces(name, ifindex);

CREATE TABLE IF NOT EXISTS network_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interface_id INTEGER NOT NULL REFERENCES network_interfaces(id) ON DELETE CASCADE,
    sampled_at TEXT NOT NULL,
    sensor_host TEXT NOT NULL,
    rx_bytes INTEGER,
    tx_bytes INTEGER,
    rx_packets INTEGER,
    tx_packets INTEGER,
    rx_errors INTEGER,
    tx_errors INTEGER,
    rx_drops INTEGER,
    tx_drops INTEGER,
    active_tcp INTEGER,
    active_udp INTEGER,
    source TEXT NOT NULL DEFAULT 'proc',
    collector_version TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_network_samples_time ON network_samples(sampled_at);
CREATE INDEX IF NOT EXISTS idx_network_samples_iface_time
    ON network_samples(interface_id, sampled_at);
