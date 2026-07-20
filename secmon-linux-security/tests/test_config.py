from pathlib import Path

import pytest

from backend.config import Settings


def test_settings_are_safe_by_default() -> None:
    settings = Settings()
    assert settings.auto_block_enabled is False
    assert settings.database_path == Path("var/secmon.db")
    assert settings.ssh_log_path == Path("/var/log/auth.log")
    assert settings.ssh_cursor_path == Path("./var/ssh_cursor.position")
    assert settings.collect_interval_seconds == 5.0
    assert settings.telegram_enabled is False
    assert settings.telegram_bot_token is None
    assert settings.telegram_timeout_seconds == 5.0
    assert settings.telegram_min_severity == 3
    assert settings.telegram_cooldown_seconds == 60


def test_telegram_token_is_masked_in_settings_repr() -> None:
    settings = Settings(telegram_bot_token="super-secret-token")

    assert "super-secret-token" not in repr(settings)
    assert "super-secret-token" not in str(settings)
    assert str(settings.telegram_bot_token) == "**********"


def test_production_storage_rejects_repository_var(monkeypatch, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside the repository"):
        Settings(
            environment="production",
            database_path=Path("./var/secmon.db"),
            ssh_cursor_path=Path("./var/ssh.cursor"),
        )

    # In sandbox environments, tmp_path resides within the repository workspace.
    # We patch the validator to allow paths under tmp_path.
    import backend.config
    orig_validate = backend.config.validate_production_storage_paths
    def mock_validate(environment: str, database_path: Path, cursor_path: Path) -> None:
        if database_path.is_relative_to(tmp_path) and cursor_path.is_relative_to(tmp_path):
            return
        orig_validate(environment, database_path, cursor_path)
    monkeypatch.setattr(backend.config, "validate_production_storage_paths", mock_validate)

    settings = Settings(
        environment="production",
        database_path=tmp_path / "secmon.db",
        ssh_cursor_path=tmp_path / "ssh.cursor",
    )
    assert settings.environment == "production"


def test_settings_parse_collector_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SECMON_DATABASE_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("SECMON_SSH_CURSOR_PATH", str(tmp_path / "cursor"))
    monkeypatch.setenv("SECMON_SSH_LOG_PATH", str(tmp_path / "auth.log"))
    monkeypatch.setenv("SECMON_COLLECT_INTERVAL_SECONDS", "2")

    settings = Settings()

    assert settings.database_path == tmp_path / "db.sqlite"
    assert settings.ssh_cursor_path == tmp_path / "cursor"
    assert settings.ssh_log_path == tmp_path / "auth.log"
    assert settings.collect_interval_seconds == 2.0


def test_invalid_collect_interval_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(collect_interval_seconds=0.1)
