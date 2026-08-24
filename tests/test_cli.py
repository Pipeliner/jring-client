import json

import pytest

from jring import cli


def test_human_status_is_readable(capsys):
    assert cli.main(["status", "--simulate"]) == 0
    output = capsys.readouterr().out
    assert "Battery: 84%" in output
    assert "Model: JR-SIM" in output
    assert "writes disabled" in output
    assert not output.lstrip().startswith("{")


def test_json_status_is_stable_and_private(capsys):
    assert cli.main(["status", "--simulate", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["battery_percent"] == 84
    assert result["device_info"]["model"] == "JR-SIM"
    assert "address" not in json.dumps(result).lower()


def test_global_option_placement_remains_compatible(capsys):
    assert cli.main(["--simulate", "status"]) == 0
    assert "Battery: 84%" in capsys.readouterr().out


def test_expected_error_is_actionable_without_traceback(monkeypatch, capsys):
    async def fail(_args):
        raise RuntimeError("hardware support requires: pip install '.[ble]'")

    monkeypatch.setattr(cli, "_run", fail)
    assert cli.main(["status", "--simulate"]) == 1
    error = capsys.readouterr().err
    assert error.startswith("jring: error:")
    assert "pip install" in error
    assert "Traceback" not in error


def test_time_sync_requires_explicit_confirmation(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["time-sync", "--simulate"])
    assert raised.value.code == 2
    assert "--allow-write/--yes" in capsys.readouterr().err
