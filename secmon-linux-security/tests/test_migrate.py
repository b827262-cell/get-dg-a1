import sqlite3
from pathlib import Path

from database.migrate import migrate


def test_initial_migration_creates_schema(tmp_path: Path) -> None:
    database = tmp_path / "secmon.db"
    migrate(database, Path("database/migrations"))
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "schema_migrations",
            "attack_events",
            "attackers",
            "audit_logs",
            "network_interfaces",
            "network_samples",
        } <= tables
        assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)


def test_migrate_repeat_run_is_idempotent(tmp_path: Path) -> None:
    """Applying migrations twice must not error, duplicate rows, or alter schema."""
    database = tmp_path / "secmon.db"
    migrations_dir = Path("database/migrations")

    migrate(database, migrations_dir)
    with sqlite3.connect(database) as connection:
        first_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        first_versions = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        }
        first_quick = connection.execute("PRAGMA quick_check").fetchone()

    # Second run: every migration is already applied, so it must be a no-op.
    migrate(database, migrations_dir)
    with sqlite3.connect(database) as connection:
        second_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        second_versions = {
            row[0] for row in connection.execute("SELECT version FROM schema_migrations")
        }
        second_quick = connection.execute("PRAGMA quick_check").fetchone()

    assert first_tables == second_tables
    assert first_versions == second_versions
    assert first_quick == ("ok",) == second_quick


def test_migrate_012_atd_schema_is_well_formed(tmp_path: Path) -> None:
    """The ATD-A migration must define the expected tables, FK, index, and integrity."""
    database = tmp_path / "secmon.db"
    migrate(database, Path("database/migrations"))
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        # Foreign key from network_samples.interface_id -> network_interfaces(id).
        fk_rows = connection.execute("PRAGMA foreign_key_list(network_samples)").fetchall()
        assert any(
            row[2] == "network_interfaces" and row[3] == "interface_id" and row[4] == "id"
            for row in fk_rows
        ), f"expected FK to network_interfaces not found in {fk_rows}"
        # ON DELETE CASCADE is encoded as the on_delete action (PRAGMA column index 6).
        assert any(row[6] == "CASCADE" for row in fk_rows), (
            f"expected ON DELETE CASCADE, got actions {[row[6] for row in fk_rows]}"
        )
        # Required indexes exist.
        index_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
        }
        assert {
            "idx_network_interfaces_name_ifindex",
            "idx_network_samples_time",
            "idx_network_samples_iface_time",
        } <= index_names
        # Integrity and FK checks pass on a fresh DB.
        assert connection.execute("PRAGMA quick_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        # The unique composite index enforces the (name, ifindex) identity.
        connection.execute(
            "INSERT INTO network_interfaces(name, ifindex) VALUES ('eth0', 2)"
        )
        connection.execute(
            "INSERT INTO network_interfaces(name, ifindex) VALUES ('eth0', 3)"
        )
        try:
            connection.execute(
                "INSERT INTO network_interfaces(name, ifindex) VALUES ('eth0', 2)"
            )
        except sqlite3.IntegrityError:
            pass
        else:  # pragma: no cover - the assertion above must fail
            raise AssertionError("duplicate (name, ifindex) was unexpectedly accepted")
