#!/usr/bin/env python3
"""Exercise the SecMon nftables adapter inside an already-isolated kernel."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from backend.services.nftables import NftablesService

NFT = os.environ.get("NFT_BINARY", "/usr/sbin/nft")
IPV4 = "10.244.44.2"
IPV6 = "fd44:244::2"
TARGET4 = "10.244.44.1"
TARGET6 = "fd44:244::1"
IP = "/usr/bin/ip"
PING = "/usr/bin/ping"


def table() -> str:
    result = subprocess.run(
        [NFT, "list", "table", "inet", "secmon"],
        capture_output=True, check=True, text=True, timeout=5,
    )
    return result.stdout


def assert_not_present(value: str) -> None:
    if value in table():
        raise AssertionError(f"element remained after rollback/unblock: {value}")


def command(argv: list[str], *, expect: int = 0) -> None:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=5, check=False)
    if result.returncode != expect:
        raise AssertionError(f"unexpected exit {result.returncode} for {argv!r}: {result.stderr}")


def configure_packet_probe() -> None:
    for binary in (IP, PING):
        if not Path(binary).is_file():
            raise AssertionError(f"missing packet-test binary: {binary}")
    command([IP, "link", "set", "lo", "up"])
    command([IP, "link", "add", "p4dummy", "type", "dummy"])
    command([IP, "addr", "add", f"{TARGET4}/24", "dev", "p4dummy"])
    command([IP, "addr", "add", f"{IPV4}/24", "dev", "p4dummy"])
    command([IP, "-6", "addr", "add", f"{TARGET6}/64", "dev", "p4dummy"])
    command([IP, "-6", "addr", "add", f"{IPV6}/64", "dev", "p4dummy"])
    command([IP, "link", "set", "p4dummy", "up"])


def ping_baseline() -> None:
    command([PING, "-c", "1", "-W", "1", "-I", IPV4, TARGET4])
    command([PING, "-6", "-c", "1", "-W", "1", "-I", IPV6, TARGET6])


def ping_blocked() -> None:
    command([PING, "-c", "1", "-W", "1", "-I", IPV4, TARGET4], expect=1)
    command([PING, "-6", "-c", "1", "-W", "1", "-I", IPV6, TARGET6], expect=1)


def main() -> None:
    configure_packet_probe()
    ping_baseline()
    service = NftablesService(binary=NFT)
    assert not service.status().table_present, "fresh isolation unexpectedly contains inet secmon"

    # Full ruleset validation must work before any table/set exists.
    assert service.preview(IPV4)["family"] == "ipv4"
    assert service.preview(IPV6)["family"] == "ipv6"

    # Model an application transaction failure after a firewall write.
    service.block(IPV4)
    service.unblock(IPV4)
    assert_not_present(IPV4)

    service.block(IPV4)
    service.block(IPV6)
    ping_blocked()
    rules = table()
    for required in (
        "set blocked_ipv4", "set blocked_ipv6", "chain input",
        "ip saddr @blocked_ipv4 drop", "ip6 saddr @blocked_ipv6 drop", IPV4, IPV6,
    ):
        assert required in rules, f"missing expected SecMon rule material: {required}"

    # A new adapter instance represents process restart: state is kernel-derived.
    restarted = NftablesService(binary=NFT)
    state = restarted.status()
    assert state.available and state.table_present and state.ipv4_set_present and state.ipv6_set_present
    restarted.block(IPV4)  # idempotence survives process restart.
    restarted.unblock(IPV4)
    restarted.unblock(IPV6)
    assert_not_present(IPV4)
    assert_not_present(IPV6)
    ping_baseline()
    print("P4_REAL_KERNEL_RUNTIME_PASS")


if __name__ == "__main__":
    main()
