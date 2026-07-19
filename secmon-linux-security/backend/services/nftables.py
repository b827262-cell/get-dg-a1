"""Fail-closed, isolated nftables boundary for SecMon manual blocks."""

from __future__ import annotations

import ipaddress
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

TABLE_FAMILY, TABLE_NAME = "inet", "secmon"
SET_V4, SET_V6, CHAIN = "blocked_ipv4", "blocked_ipv6", "input"


class FirewallError(RuntimeError):
    """The requested firewall state could not be safely confirmed."""


@dataclass(frozen=True)
class FirewallStatus:
    available: bool
    table_present: bool
    ipv4_set_present: bool
    ipv6_set_present: bool


Runner = Callable[..., subprocess.CompletedProcess[str]]


class NftablesService:
    """Only operate on the dedicated ``inet secmon`` table and its fixed sets."""

    def __init__(
        self, binary: str = "/usr/sbin/nft", timeout_seconds: float = 5.0,
        runner: Runner = subprocess.run,
    ) -> None:
        self.binary, self.timeout_seconds, self._runner = binary, timeout_seconds, runner

    @staticmethod
    def parse_ip(value: str) -> tuple[str, Literal["ipv4", "ipv6"]]:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise FirewallError("invalid IP address") from exc
        if address.is_loopback or address.is_unspecified or address.is_multicast:
            raise FirewallError("unsafe IP address")
        return str(address), "ipv4" if address.version == 4 else "ipv6"

    @staticmethod
    def _set_for(family: Literal["ipv4", "ipv6"]) -> str:
        return SET_V4 if family == "ipv4" else SET_V6

    def _run(self, argv: Sequence[str], *, allow_nonzero: bool = False) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(
                [self.binary, *argv], capture_output=True, text=True,
                timeout=self.timeout_seconds, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FirewallError("nftables command did not complete") from exc
        if result.returncode and not allow_nonzero:
            raise FirewallError("nftables command failed")
        return result

    def _exists(self, argv: Sequence[str]) -> bool:
        return self._run(argv, allow_nonzero=True).returncode == 0

    def _ensure_layout(self) -> None:
        if not self._exists(("list", "table", TABLE_FAMILY, TABLE_NAME)):
            self._run(("add", "table", TABLE_FAMILY, TABLE_NAME))
        for name, address_type in ((SET_V4, "ipv4_addr"), (SET_V6, "ipv6_addr")):
            if not self._exists(("list", "set", TABLE_FAMILY, TABLE_NAME, name)):
                self._run(("add", "set", TABLE_FAMILY, TABLE_NAME, name, "{", "type", address_type, ";", "}"))
        if not self._exists(("list", "chain", TABLE_FAMILY, TABLE_NAME, CHAIN)):
            self._run(("add", "chain", TABLE_FAMILY, TABLE_NAME, CHAIN, "{", "type", "filter", "hook", "input", "priority", "0", ";", "policy", "accept", ";", "}"))
            self._run(("add", "rule", TABLE_FAMILY, TABLE_NAME, CHAIN, "ip", "saddr", "@" + SET_V4, "drop"))
            self._run(("add", "rule", TABLE_FAMILY, TABLE_NAME, CHAIN, "ip6", "saddr", "@" + SET_V6, "drop"))

    def status(self) -> FirewallStatus:
        try:
            available = self._exists(("--version",))
            table = available and self._exists(("list", "table", TABLE_FAMILY, TABLE_NAME))
            return FirewallStatus(
                available, table,
                table and self._exists(("list", "set", TABLE_FAMILY, TABLE_NAME, SET_V4)),
                table and self._exists(("list", "set", TABLE_FAMILY, TABLE_NAME, SET_V6)),
            )
        except FirewallError:
            return FirewallStatus(False, False, False, False)

    def preview(self, value: str, operation: Literal["block", "unblock"] = "block") -> dict[str, object]:
        ip, family = self.parse_ip(value)
        verb = "add" if operation == "block" else "delete"
        address_set = self._set_for(family)
        self._run(("--check", verb, "element", TABLE_FAMILY, TABLE_NAME, address_set, "{", ip, "}"))
        return {"ip": ip, "family": family, "operation": operation, "table": f"{TABLE_FAMILY} {TABLE_NAME}", "set": address_set}

    def block(self, value: str) -> str:
        ip, family = self.parse_ip(value)
        self._ensure_layout()
        self._run(("-exist", "add", "element", TABLE_FAMILY, TABLE_NAME, self._set_for(family), "{", ip, "}"))
        return ip

    def unblock(self, value: str) -> str:
        ip, family = self.parse_ip(value)
        if self._exists(("list", "set", TABLE_FAMILY, TABLE_NAME, self._set_for(family))):
            self._run(("-exist", "delete", "element", TABLE_FAMILY, TABLE_NAME, self._set_for(family), "{", ip, "}"))
        return ip
