import json

import pytest

from jring import cli
from jring.readiness import ReadinessCheck, ReadinessReport


def not_ready_report():
    return ReadinessReport(
        checks=(
            ReadinessCheck("python", True, "Python 3.14 is supported"),
            ReadinessCheck(
                "bleak", False, "Bleak is not installed", "pip install -e '.[ble]'"
            ),
        ),
        simulator_ready=True,
        hardware_ready=False,
        input_ready=False,
        next_step="jring status --simulate",
    )


def test_human_status_is_readable(capsys):
    assert cli.main(["status", "--simulate"]) == 0
    output = capsys.readouterr().out
    assert "Battery: 84%" in output
    assert "Model: JR-SIM" in output
    assert "Standard HID: not available" in output
    assert "writes disabled" in output
    assert not output.lstrip().startswith("{")


def test_json_status_is_stable_and_private(capsys):
    assert cli.main(["status", "--simulate", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["battery_percent"] == 84
    assert result["device_info"]["model"] == "JR-SIM"
    assert result["capabilities"]["hid"] is False
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


def test_doctor_explains_hardware_setup_without_failing(monkeypatch, capsys):
    monkeypatch.setattr(cli, "diagnose", not_ready_report)

    assert cli.main(["doctor"]) == 0
    output = capsys.readouterr().out
    assert "Simulator: ready" in output
    assert "Hardware: not ready" in output
    assert "Desktop input: not ready" in output
    assert "pip install" in output
    assert "Next: jring status --simulate" in output
    assert "address" not in output.lower()


def test_doctor_json_can_strictly_require_hardware(monkeypatch, capsys):
    monkeypatch.setattr(cli, "diagnose", not_ready_report)

    assert cli.main(["doctor", "--json", "--require-hardware"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["simulator_ready"] is True
    assert result["hardware_ready"] is False
    assert result["input_ready"] is False
    assert result["checks"][1]["remedy"] == "pip install -e '.[ble]'"


def test_doctor_can_strictly_require_desktop_input(monkeypatch, capsys):
    monkeypatch.setattr(cli, "diagnose", not_ready_report)

    assert cli.main(["doctor", "--require-input"]) == 1
    assert "Desktop input: not ready" in capsys.readouterr().out


def test_step_mapping_previews_without_emitting_input(capsys):
    assert cli.main(["input", "--simulate", "--map", "step=click:left"]) == 0
    output = capsys.readouterr().out
    assert "Preview: step -> left mouse click" in output
    assert "No input emitted" in output


def test_input_injection_requires_opt_in(monkeypatch, capsys):
    class Sink:
        def __init__(self):
            self.actions = []
            self.closed = False

        def emit(self, action):
            self.actions.append(action)

        def close(self):
            self.closed = True

    sink = Sink()
    monkeypatch.setattr(cli, "create_uinput_sink", lambda: sink)

    assert cli.main([
        "input", "--simulate", "--map", "step=key:space", "--allow-input"
    ]) == 0
    assert [action.description for action in sink.actions] == ["Space key"]
    assert sink.closed
    assert "Emitted: step -> Space key" in capsys.readouterr().out


def test_hardware_motion_input_fails_before_opening_a_sink(monkeypatch, capsys):
    opened = False

    def open_sink():
        nonlocal opened
        opened = True

    monkeypatch.setattr(cli, "create_uinput_sink", open_sink)
    result = cli.main([
        "input", "--address", "AA:BB:CC:DD:EE:FF", "--map", "step=key:space",
        "--allow-input",
    ])

    assert result == 1
    assert not opened
    assert "hardware motion-event protocol is not verified" in capsys.readouterr().err
