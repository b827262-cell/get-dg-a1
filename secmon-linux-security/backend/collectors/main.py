"""Production loop for the SecMon SSH collector."""

from __future__ import annotations

import logging
import signal
import time
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import TypeVar, cast

from backend.collectors.network_metrics import NetworkMetricsCollector
from backend.collectors.ssh_collector import SSHCollector
from backend.config import Settings, get_settings, validate_production_storage_paths
from backend.notifiers import TelegramNotifier

logger = logging.getLogger(__name__)
_STOP_EVENT = Event()
_MIN_SLEEP_SECONDS = 0.5
T = TypeVar("T")


def _configure_logging(level_name: str) -> None:
    if logging.getLogger().handlers:
        logging.getLogger().setLevel(level_name)
        return
    logging.basicConfig(
        level=level_name,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _setting_value(settings: object, name: str, default: T) -> T:
    if isinstance(settings, Settings):
        return cast(T, getattr(settings, name))
    return cast(T, vars(settings).get(name, default))


def _install_signal_handlers() -> None:
    def _handle_signal(signum: int, _frame: object) -> None:
        logger.info("Received signal %s, stopping collector loop", signum)
        _STOP_EVENT.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


def _build_notifier(settings: Settings) -> TelegramNotifier | None:
    if not bool(_setting_value(settings, "telegram_enabled", False)):
        return None
    bot_token = _setting_value(settings, "telegram_bot_token", None)
    chat_id = _setting_value(settings, "telegram_chat_id", None)
    if bot_token is None or chat_id is None:
        raise ValueError("Telegram is enabled but bot token or chat id is missing")
    notifier = TelegramNotifier(
        bot_token,
        str(chat_id),
        timeout_seconds=float(_setting_value(settings, "telegram_timeout_seconds", 5.0)),
    )
    notifier.cooldown_seconds = int(_setting_value(settings, "telegram_cooldown_seconds", 60))
    return notifier


def run_collector_loop() -> int:
    try:
        settings = get_settings()
        _configure_logging(str(_setting_value(settings, "log_level", "INFO")))
        _STOP_EVENT.clear()
        _install_signal_handlers()

        database_path = Path(
            _setting_value(settings, "database_path", "/var/lib/secmon/secmon.db")
        )
        cursor_path = Path(
            _setting_value(settings, "ssh_cursor_path", "/var/lib/secmon/ssh.cursor")
        )
        validate_production_storage_paths(
            str(_setting_value(settings, "environment", "development")),
            database_path,
            cursor_path,
        )
        notifier = _build_notifier(settings)
        collector = SSHCollector(
            notifier=notifier,
            cursor_path=cursor_path,
            database_path=database_path,
        )
    except Exception:
        logger.exception("Failed to initialize the SSH collector")
        return 1

    poll_interval = max(
        float(_setting_value(settings, "collect_interval_seconds", 5.0)),
        _MIN_SLEEP_SECONDS,
    )
    log_path = Path(_setting_value(settings, "ssh_log_path", "/var/log/auth.log"))

    # ATD-A: an optional, separately-cadenced zero-privilege network metrics
    # collector.  Disabled by default; when enabled it shares this loop and the
    # existing secmon-collector.service unit (no new privileges, no new unit).
    network_enabled = bool(_setting_value(settings, "network_metrics_enabled", False))
    network_collector: NetworkMetricsCollector | None = None
    network_interval = poll_interval
    if network_enabled:
        try:
            network_collector = NetworkMetricsCollector(database_path, settings=settings)
            network_interval = max(
                float(_setting_value(settings, "network_metrics_interval_seconds", 5.0)),
                _MIN_SLEEP_SECONDS,
            )
        except Exception:
            logger.exception("Failed to initialize the network metrics collector")
            network_collector = None
    next_network_at = time.monotonic() if network_collector is not None else float("inf")

    logger.info(
        "Starting SecMon SSH collector loop (log_path=%s, db=%s, cursor=%s, interval=%.1fs, "
        "network_metrics=%s)",
        log_path,
        collector.database_path,
        collector.cursor_position_file,
        poll_interval,
        "enabled" if network_collector is not None else "disabled",
    )

    while not _STOP_EVENT.is_set():
        round_start = time.monotonic()
        started_at = datetime.now().isoformat(timespec="seconds")
        new_events = 0
        new_attackers = 0
        try:
            new_events, new_attackers = collector.collect_from_file(str(log_path))
        except Exception as exc:
            logger.warning("Recoverable collection error: %s", exc, exc_info=True)

        network_samples = 0
        network_interfaces = 0
        if network_collector is not None and round_start >= next_network_at:
            try:
                network_samples, network_interfaces = network_collector.collect_once()
            except Exception as exc:
                logger.warning("Recoverable network metrics error: %s", exc, exc_info=True)
            next_network_at = time.monotonic() + network_interval

        duration = time.monotonic() - round_start
        next_poll = max(poll_interval - duration, _MIN_SLEEP_SECONDS)
        logger.info(
            "SSH collection round start=%s new_events=%d new_attackers=%d "
            "net_samples=%d net_interfaces=%d duration=%.3fs next_poll=%.3fs",
            started_at,
            new_events,
            new_attackers,
            network_samples,
            network_interfaces,
            duration,
            next_poll,
        )

        if _STOP_EVENT.wait(next_poll):
            break

    logger.info("SecMon SSH collector loop stopped")
    return 0


def main() -> int:
    return run_collector_loop()


if __name__ == "__main__":
    raise SystemExit(main())
