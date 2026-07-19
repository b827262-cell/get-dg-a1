from __future__ import annotations

import subprocess

import pytest

from backend.services.nftables import FirewallError, NftablesService


def completed(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, 0, stdout='{"nftables": []}', stderr="")


def test_preview_uses_fixed_argv_and_validates_both_ip_versions() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def runner(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((argv, kwargs))
        return completed(argv, **kwargs)

    service = NftablesService(binary="nft", runner=runner)
    assert service.preview("192.0.2.8")["family"] == "ipv4"
    assert service.preview("2001:db8::8")["family"] == "ipv6"
    assert all(call[0][0] == "nft" and call[1]["timeout"] == 5.0 for call in calls)
    assert all("shell" not in call[1] for call in calls)


@pytest.mark.parametrize("value", ["not-an-ip", "127.0.0.1", "::1", "1.2.3.4;flush ruleset"])
def test_unsafe_input_never_reaches_runner(value: str) -> None:
    service = NftablesService(runner=completed)
    with pytest.raises(FirewallError):
        service.preview(value)


def test_timeout_and_nonzero_exit_are_safe_errors() -> None:
    def timeout(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(argv, 5)

    def failed(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, stdout="secret", stderr="failure")

    assert NftablesService(runner=timeout).status().available is False
    assert NftablesService(runner=failed).status().available is False
