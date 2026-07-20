"""Typed application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_production_storage_paths(
    environment: str,
    database_path: Path,
    cursor_path: Path,
) -> None:
    """Reject repository-local storage when the collector runs in production."""
    if environment != "production":
        return

    repository_root = Path(__file__).resolve().parents[1]
    for setting_name, path in (
        ("SECMON_DATABASE_PATH", database_path),
        ("SECMON_SSH_CURSOR_PATH", cursor_path),
    ):
        resolved_path = path.expanduser().resolve()
        if not path.is_absolute() or resolved_path.is_relative_to(repository_root):
            raise ValueError(
                f"{setting_name} must be an absolute path outside the repository in production"
            )


class Settings(BaseSettings):
    """Runtime settings; secrets are supplied by the environment, never committed."""

    # Runtime secrets are injected by the service manager; never load a repository .env.
    model_config = SettingsConfigDict(env_prefix="SECMON_", extra="ignore")

    app_name: str = "SecMon"
    environment: str = Field(default="development", pattern="^(development|test|production)$")
    database_path: Path = Path("./var/secmon.db")
    ssh_log_path: Path = Path("/var/log/auth.log")
    ssh_cursor_path: Path = Path("./var/ssh_cursor.position")
    collect_interval_seconds: float = Field(default=5.0, ge=0.5)
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    api_jwt_secret: SecretStr | None = None
    api_jwt_issuer: str = "secmon-api"
    api_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    api_cors_origins: tuple[str, ...] = ()
    api_docs_enabled: bool = False
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    trusted_proxy_cidrs: tuple[str, ...] = ()
    auto_block_enabled: bool = False
    nft_binary: str = Field(default="/usr/sbin/nft", pattern=r"^/usr/sbin/nft$")
    nft_timeout_seconds: float = Field(default=5.0, ge=0.1, le=30.0)
    telegram_enabled: bool = False
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    telegram_timeout_seconds: float = Field(default=5.0, ge=0.1)
    telegram_min_severity: int = Field(default=3, ge=1, le=5)
    telegram_cooldown_seconds: int = Field(default=60, ge=0)
    # ATD-A: zero-privilege network metrics collector.  Defaults to off so an
    # upgrade never changes runtime behaviour without an explicit operator opt-in.
    network_metrics_enabled: bool = False
    network_metrics_interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    network_metrics_retention_days: int = Field(default=7, ge=1, le=90)

    @model_validator(mode="after")
    def _validate_production_paths(self) -> Settings:
        validate_production_storage_paths(
            self.environment,
            self.database_path,
            self.ssh_cursor_path,
        )
        return self


def get_settings() -> Settings:
    """Build current settings so test/runtime environment changes are respected."""
    return Settings()
