-- P4 detection operations: query indexes and immutable audit evidence.
CREATE INDEX IF NOT EXISTS idx_alerts_status_updated
    ON alerts(status, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_src_ip_updated
    ON alerts(src_ip, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_allowlist_enabled_value
    ON ip_allowlist(enabled, ip_or_cidr);

-- Audit evidence is append-only.  The application role only inserts rows;
-- SQLite enforces that accidental or compromised write paths cannot rewrite it.
CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
BEFORE UPDATE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit_logs are immutable');
END;

CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
BEFORE DELETE ON audit_logs
BEGIN
    SELECT RAISE(ABORT, 'audit_logs are immutable');
END;
