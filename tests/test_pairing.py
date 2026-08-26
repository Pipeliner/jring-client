from __future__ import annotations

from types import SimpleNamespace

import pytest

from jring import pairing
from jring import cli


ADDRESS = ":".join(("AA", "BB", "CC", "DD", "EE", "FF"))


def test_pairing_requires_explicit_consent_before_subprocess(monkeypatch):
    called = False

    def forbidden(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(pairing.subprocess, "run", forbidden)
    result = pairing.pair_device(ADDRESS, timeout=2, allow_pairing=False)
    assert result.status == "consent_required"
    assert called is False


def test_pairing_success_sanitizes_address_and_never_trusts(monkeypatch):
    seen = {}
    monkeypatch.setattr(pairing.shutil, "which", lambda _name: "/usr/bin/bluetoothctl")

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=f"Device {ADDRESS} Pairing successful", stderr="")

    monkeypatch.setattr(pairing.subprocess, "run", fake_run)
    result = pairing.pair_device(ADDRESS, timeout=2, allow_pairing=True)
    assert result.status == "paired"
    assert ADDRESS not in result.detail
    assert seen["command"] == ["bluetoothctl", "pair", ADDRESS]
    assert "trust" not in seen["command"]
    assert seen["kwargs"]["timeout"] == 2


def test_trust_requires_its_own_confirmation_and_is_a_second_operation(monkeypatch):
    calls = []
    monkeypatch.setattr(pairing.shutil, "which", lambda _name: "/usr/bin/bluetoothctl")

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="success", stderr="")

    monkeypatch.setattr(pairing.subprocess, "run", fake_run)
    result = pairing.pair_device(ADDRESS, timeout=2, allow_pairing=True, allow_trust=True)
    assert result.status == "trusted"
    assert calls == [["bluetoothctl", "pair", ADDRESS], ["bluetoothctl", "trust", ADDRESS]]

    denied = pairing.pair_device(ADDRESS, timeout=2, allow_pairing=True, allow_trust=False)
    assert denied.status == "paired"


def test_trust_device_is_standalone_and_never_pairs(monkeypatch):
    calls = []
    monkeypatch.setattr(pairing.shutil, "which", lambda _name: "/usr/bin/bluetoothctl")
    monkeypatch.setattr(pairing.subprocess, "run", lambda command, **kwargs: calls.append(command) or SimpleNamespace(returncode=0, stdout="trust succeeded", stderr=""))
    result = pairing.trust_device(ADDRESS, timeout=2, allow_trust=True)
    assert result.status == "trusted"
    assert calls == [["bluetoothctl", "trust", ADDRESS]]


def test_pairing_timeout_is_uncertain_and_not_retried(monkeypatch):
    monkeypatch.setattr(pairing.shutil, "which", lambda _name: "/usr/bin/bluetoothctl")
    def fake_run(*_args, **_kwargs):
        raise pairing.subprocess.TimeoutExpired(cmd="bluetoothctl", timeout=2)

    monkeypatch.setattr(pairing.subprocess, "run", fake_run)
    result = pairing.pair_device(ADDRESS, timeout=2, allow_pairing=True)
    assert result.status == "timed_out"
    assert "retry" not in result.detail.lower()


def test_cli_pair_requires_explicit_consent_before_selection(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_selected_address", lambda _args: (_ for _ in ()).throw(AssertionError("must gate first")))
    with pytest.raises(SystemExit):
        cli.main(["pair", "--address-file", "/tmp/address"])
    assert "--allow-pairing" in capsys.readouterr().err


def test_cli_trust_requires_explicit_consent_before_selection(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_selected_address", lambda _args: (_ for _ in ()).throw(AssertionError("must gate first")))
    with pytest.raises(SystemExit):
        cli.main(["trust", "--address-file", "/tmp/address"])
    assert "--allow-trust" in capsys.readouterr().err
