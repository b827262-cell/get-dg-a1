-- P4 firewall operation audit metadata.  Existing audit rows remain valid.
ALTER TABLE audit_logs ADD COLUMN details_json TEXT;
ALTER TABLE audit_logs ADD COLUMN actor_role TEXT;
ALTER TABLE audit_logs ADD COLUMN result TEXT;
ALTER TABLE audit_logs ADD COLUMN details TEXT;
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_blocked_ips_active_src ON blocked_ips(active, src_ip);
