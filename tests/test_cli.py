import json
import os

import pytest

from jring import cli
from jring.discovery import DiscoveryObservation, build_selection_candidates
from jring.protocol import ProtocolError
from jring.readiness import ReadinessCheck, ReadinessReport
from jring.transport import FakeTransport
from jring.uuids import FIRMWARE


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
    assert "Standard HID service: not advertised" in output
    assert "writes disabled" in output
    assert not output.lstrip().startswith("{")


def test_json_status_is_stable_and_private(capsys):
    assert cli.main(["status", "--simulate", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["operation"] == "status"
    assert result["source"] == "simulator"
    assert result["ok"] is True
    assert result["battery_percent"] == 84
    assert result["device_info"]["model"] == "JR-SIM"
    assert result["capabilities"]["hid_service_advertised"] is False
    assert "address" not in json.dumps(result).lower()


@pytest.mark.parametrize(
    "argv, operation, source",
    [
        (["doctor", "--json"], "doctor", "local"),
        (["input", "--simulate", "--map", "step=key:space", "--json"],
         "input", "simulator"),
        (["time-sync", "--simulate", "--yes", "--json"],
         "time_sync", "simulator"),
    ],
)
def test_every_json_success_has_the_common_envelope(argv, operation, source, capsys):
    assert cli.main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["operation"] == operation
    assert result["source"] == source
    assert result["ok"] is True


def test_discovery_json_success_has_the_common_envelope(monkeypatch, capsys):
    async def no_devices(**_kwargs):
        return []

    monkeypatch.setattr(cli, "discover", no_devices)
    assert cli.main(["discover", "--active-scan", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {
        "devices": [],
        "ok": True,
        "operation": "discover",
        "schema_version": 1,
        "source": "hardware",
    }


def test_global_option_placement_remains_compatible(capsys):
    assert cli.main(["--simulate", "status"]) == 0
    assert "Battery: 84%" in capsys.readouterr().out


def test_expected_error_is_actionable_without_traceback(monkeypatch, capsys):
    async def fail(_args):
        raise RuntimeError("hardware support requires: pip install '.[ble]'")

    monkeypatch.setattr(cli, "_run", fail)
    assert cli.main(["status", "--simulate"]) == 70
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
    assert "BLE prerequisites: incomplete" in output
    assert "Desktop-input prerequisites: incomplete" in output
    assert "pip install" in output
    assert "Next: jring status --simulate" in output
    assert "address" not in output.lower()


def test_doctor_json_can_strictly_require_hardware(monkeypatch, capsys):
    monkeypatch.setattr(cli, "diagnose", not_ready_report)

    assert cli.main(["doctor", "--json", "--require-hardware"]) == 3
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["operation"] == "doctor"
    assert result["source"] == "local"
    assert result["ok"] is False
    assert result["error"]["code"] == "unavailable"
    assert result["simulator_ready"] is True
    assert result["hardware_ready"] is False
    assert result["input_ready"] is False
    assert result["checks"][1]["remedy"] == "pip install -e '.[ble]'"


def test_doctor_can_strictly_require_desktop_input(monkeypatch, capsys):
    monkeypatch.setattr(cli, "diagnose", not_ready_report)

    assert cli.main(["doctor", "--require-input"]) == 3
    assert "Desktop-input prerequisites: incomplete" in capsys.readouterr().out


def test_step_mapping_previews_without_emitting_input(capsys):
    assert cli.main(["input", "--simulate", "--map", "step=click:left"]) == 0
    output = capsys.readouterr().out
    assert "Preview: step -> primary (left) mouse click" in output
    assert "No input emitted" in output


def test_input_actions_are_screen_reader_ordered(capsys):
    assert cli.main(["input-actions"]) == 0
    output = capsys.readouterr().out
    assert output.index("Available simulated events") < output.index("Keyboard actions")
    assert output.index("Keyboard actions") < output.index("Mouse actions")
    assert "primary (left)" in output
    assert "secondary (right)" in output
    assert "No hardware gesture or motion event is verified yet." in output
    assert "\x1b" not in output


def test_input_actions_json_uses_common_envelope(capsys):
    assert cli.main(["input-actions", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["operation"] == "input_actions"
    assert result["source"] == "local"
    assert result["ok"] is True
    assert result["hardware_events"] == []
    assert [item["name"] for item in result["actions"][-3:]] == [
        "primary", "secondary", "middle",
    ]


def test_protocol_coverage_human_summary_is_offline_and_honest(capsys):
    assert cli.main(["protocol-coverage"]) == 0
    output = capsys.readouterr().out

    assert "OFFLINE PROTOCOL COVERAGE — no ring contacted" in output
    assert "Requests: 112" in output
    assert "Callbacks: 105" in output
    assert "Live vendor operations: 0" in output
    assert "Hardware-verified vendor operations: 0" in output


def test_protocol_coverage_json_accounts_for_every_entry(capsys):
    assert cli.main(["protocol-coverage", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["operation"] == "protocol_coverage"
    assert result["source"] == "local"
    assert result["ok"] is True
    assert result["summary"]["request_total"] == 112
    assert result["summary"]["callback_total"] == 105
    assert result["summary"]["live_vendor_operations"] == 0
    assert len(result["requests"]) == 112
    assert len(result["callbacks"]) == 105
    assert "frame" not in json.dumps(result).lower()


def test_protocol_coverage_never_constructs_a_transport(monkeypatch, capsys):
    def forbidden_transport(*_args, **_kwargs):
        raise AssertionError("transport must not be constructed")

    monkeypatch.setattr(cli, "BleakTransport", forbidden_transport)

    assert cli.main(["protocol-coverage"]) == 0
    assert "no ring contacted" in capsys.readouterr().out


def test_unsupported_mapping_fails_before_opening_a_sink(monkeypatch, capsys):
    opened = False

    def open_sink(_actions):
        nonlocal opened
        opened = True

    monkeypatch.setattr(cli, "create_uinput_sink", open_sink)

    assert cli.main([
        "input", "--simulate", "--map", "step=key:KEY_F13", "--allow-input",
    ]) == 2
    assert not opened
    assert "unsupported input action" in capsys.readouterr().err


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
    selected = []

    def create_sink(actions):
        selected.extend(actions)
        return sink

    monkeypatch.setattr(cli, "create_uinput_sink", create_sink)

    assert cli.main([
        "input", "--simulate", "--map", "step=key:space", "--allow-input"
    ]) == 0
    assert [action.description for action in sink.actions] == ["Space key"]
    assert selected == sink.actions
    assert sink.closed
    assert "Emitted: step -> Space key" in capsys.readouterr().out


def test_hardware_motion_input_fails_before_opening_a_sink(monkeypatch, capsys):
    opened = False

    def open_sink():
        nonlocal opened
        opened = True

    monkeypatch.setattr(cli, "create_uinput_sink", open_sink)
    with pytest.raises(SystemExit) as raised:
        cli.main([
            "input", "--address", "AA:BB:CC:DD:EE:FF", "--map", "step=key:space",
            "--allow-input",
        ])

    assert raised.value.code == 2
    assert not opened
    assert "use --simulate" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv, option",
    [
        (["--simulate", "doctor"], "--simulate"),
        (["--timeout", "1", "doctor"], "--timeout"),
        (["--timeout", "1", "input", "--simulate", "--map", "step=key:space"], "--timeout"),
        (["--simulate", "input-actions"], "--simulate"),
        (["--simulate", "protocol-coverage"], "--simulate"),
    ],
)
def test_non_applicable_global_options_are_rejected(argv, option, capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(argv)
    assert raised.value.code == 2
    assert option in capsys.readouterr().err


def test_discovery_requires_explicit_active_scan(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["discover"])
    assert raised.value.code == 2
    assert "--active-scan" in capsys.readouterr().err


def test_simulated_discovery_never_scans(monkeypatch, capsys):
    touched_radio = False

    async def scan(**_kwargs):
        nonlocal touched_radio
        touched_radio = True

    monkeypatch.setattr(cli, "discover", scan)
    with pytest.raises(SystemExit) as raised:
        cli.main(["discover", "--simulate"])
    assert raised.value.code == 2
    assert not touched_radio
    assert "does not support simulation" in capsys.readouterr().err


def synthetic_selection_candidates():
    return build_selection_candidates(
        (
            DiscoveryObservation("11:22:33:44:55:66", "other", ("180a",), -70),
            DiscoveryObservation("AA:BB:CC:DD:EE:FF", "JRing", ("1812",), -42),
        ),
        salt=b"synthetic-guided-selection",
    )


def enable_interactive_terminal(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)


def test_guided_status_selects_only_after_confirmation(monkeypatch, capsys):
    enable_interactive_terminal(monkeypatch)
    candidates = synthetic_selection_candidates()
    selected = candidates[1]
    connected = []

    async def scan(**_kwargs):
        return candidates

    def transport(address):
        connected.append(address)
        return FakeTransport.standard_ring()

    responses = iter(["2", "y"])
    monkeypatch.setattr(cli, "discover_for_selection", scan)
    monkeypatch.setattr(cli, "BleakTransport", transport)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli.main(["status", "--select", "--active-scan"]) == 0
    output = capsys.readouterr().out
    assert connected == [selected.connection_address()]
    assert output.index("ACTIVE SCAN") < output.index("CONNECTION NOT STARTED")
    assert selected.alias in output
    assert "AA:BB" not in output
    assert "11:22" not in output


@pytest.mark.parametrize("confirmation", ["", "n", "no"])
def test_guided_selection_never_autoconnects(monkeypatch, capsys, confirmation):
    enable_interactive_terminal(monkeypatch)
    candidates = synthetic_selection_candidates()[:1]
    connected = False

    async def scan(**_kwargs):
        return candidates

    def transport(_address):
        nonlocal connected
        connected = True

    responses = iter(["1", confirmation])
    monkeypatch.setattr(cli, "discover_for_selection", scan)
    monkeypatch.setattr(cli, "BleakTransport", transport)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli.main(["status", "--select", "--active-scan"]) == 0
    assert not connected
    assert "Cancelled; no connection made." in capsys.readouterr().out


@pytest.mark.parametrize("candidates,response,exit_code", [([], None, 3), (None, "3", 2)])
def test_guided_selection_zero_or_invalid_results_do_not_connect(
    monkeypatch, capsys, candidates, response, exit_code
):
    enable_interactive_terminal(monkeypatch)
    found = synthetic_selection_candidates() if candidates is None else candidates
    connected = False

    async def scan(**_kwargs):
        return found

    def transport(_address):
        nonlocal connected
        connected = True

    monkeypatch.setattr(cli, "discover_for_selection", scan)
    monkeypatch.setattr(cli, "BleakTransport", transport)
    if response is not None:
        monkeypatch.setattr("builtins.input", lambda _prompt: response)

    assert cli.main(["status", "--select", "--active-scan"]) == exit_code
    assert not connected
    output = capsys.readouterr()
    assert "AA:BB" not in output.out + output.err


@pytest.mark.parametrize(
    "argv,message",
    [
        (["status", "--select"], "--active-scan"),
        (["status", "--active-scan"], "--select"),
        (["status", "--select", "--active-scan", "--simulate"], "mutually exclusive"),
    ],
)
def test_guided_selection_requires_unambiguous_human_consent(argv, message, capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(argv)
    assert raised.value.code == 2
    assert message in capsys.readouterr().err


def test_guided_selection_rejects_json_with_a_private_envelope(capsys):
    assert cli.main(["status", "--select", "--active-scan", "--json"]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["error"]["code"] == "usage"
    assert "human-only" in result["error"]["message"]
    assert "AA:BB" not in captured.out
    assert captured.err == ""


def test_guided_selection_rejects_noninteractive_input_before_scan(monkeypatch, capsys):
    scanned = False

    async def scan(**_kwargs):
        nonlocal scanned
        scanned = True

    monkeypatch.setattr(cli, "discover_for_selection", scan)

    with pytest.raises(SystemExit) as raised:
        cli.main(["status", "--select", "--active-scan"])
    assert raised.value.code == 2
    assert not scanned
    assert "interactive terminal" in capsys.readouterr().err


def test_source_modes_are_exclusive(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["status", "--simulate", "--address", "AA:BB:CC:DD:EE:FF"])
    assert raised.value.code == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_simulated_status_has_provenance(capsys):
    assert cli.main(["status", "--simulate", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["schema_version"] == 1
    assert result["source"] == "simulator"


def test_cli_exposes_partial_status_states(capsys):
    assert cli.main(["status", "--simulate", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["battery_state"] == "available"
    assert result["device_info_states"] == {
        "firmware": "available",
        "hardware": "unavailable",
        "manufacturer": "available",
        "model": "available",
        "software": "unavailable",
    }
    assert result["capabilities"]["inventory_state"] == "available"

    assert cli.main(["status", "--simulate"]) == 0
    output = capsys.readouterr().out
    assert "Model: JR-SIM (available)" in output
    assert "Hardware: unavailable" in output


def test_malformed_device_information_never_echoes_raw_value(monkeypatch, capsys):
    transport = FakeTransport.standard_ring()
    transport.values[FIRMWARE] = b"\xffprivate-raw-value"
    monkeypatch.setattr(cli.FakeTransport, "standard_ring", lambda: transport)

    assert cli.main(["status", "--simulate", "--json"]) == 0
    serialized = capsys.readouterr().out
    result = json.loads(serialized)
    assert result["device_info"]["firmware"] is None
    assert result["device_info_states"]["firmware"] == "malformed"
    assert "private-raw-value" not in serialized


@pytest.mark.parametrize("timeout", ["0", "-1", "nan", "inf", "31"])
def test_timeout_must_be_finite_and_bounded(timeout, capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["status", "--simulate", "--timeout", timeout])
    assert raised.value.code == 2
    assert "timeout" in capsys.readouterr().err.lower()


def test_cli_errors_redact_identifiers(monkeypatch, capsys):
    async def fail(_args):
        raise RuntimeError(
            "device AA:BB:CC:DD:EE:FF at /org/bluez/hci0/dev_AA_BB failed "
            "payload deadbeefcafebabe"
        )

    monkeypatch.setattr(cli, "_run", fail)
    assert cli.main(["status", "--simulate"]) == 70
    error = capsys.readouterr().err
    assert "AA:BB" not in error
    assert "/org/bluez" not in error
    assert "deadbeef" not in error
    assert "Traceback" not in error


def test_address_file_must_be_private(tmp_path, capsys):
    address_file = tmp_path / "ring-address"
    address_file.write_text("AA:BB:CC:DD:EE:FF\n")
    os.chmod(address_file, 0o644)

    assert cli.main(["status", "--address-file", str(address_file)]) == 6
    assert "mode 0600" in capsys.readouterr().err


def test_ignored_json_option_is_rejected(capsys):
    assert cli.main(["history", "--simulate", "--json", "--output", "x.jsonl"]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["error"]["code"] == "usage"
    assert "--json is not supported" in result["error"]["message"]
    assert captured.err == ""


@pytest.mark.parametrize(
    "error, exit_code, code, retryable",
    [
        (ValueError("bad mapping"), 2, "usage", False),
        (ModuleNotFoundError("optional dependency missing"), 3, "unavailable", True),
        (TimeoutError("operation expired"), 4, "timeout", True),
        (ProtocolError("malformed value"), 5, "protocol_incompatible", False),
        (PermissionError("access denied"), 6, "permission_denied", False),
        (RuntimeError("unexpected failure"), 70, "internal", False),
    ],
)
def test_json_failures_have_stable_envelopes_and_exit_codes(
    monkeypatch, capsys, error, exit_code, code, retryable
):
    async def fail(_args):
        raise error

    monkeypatch.setattr(cli, "_run", fail)
    assert cli.main(["status", "--simulate", "--json"]) == exit_code
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    expected_message = "unexpected client failure" if code == "internal" else str(error)
    assert result == {
        "error": {
            "code": code,
            "message": expected_message,
            "retryable": retryable,
        },
        "ok": False,
        "operation": "status",
        "schema_version": 1,
        "source": "simulator",
    }
    assert captured.err == ""


def test_json_usage_error_has_no_stderr(capsys):
    assert cli.main(["status", "--simulate", "--json", "--timeout", "nan"]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["operation"] == "status"
    assert result["source"] == "simulator"
    assert result["ok"] is False
    assert result["error"]["code"] == "usage"
    assert "timeout" in result["error"]["message"].lower()
    assert captured.err == ""


def test_json_error_redaction(monkeypatch, capsys):
    async def fail(_args):
        raise ProtocolError(
            "device AA:BB:CC:DD:EE:FF at /org/bluez/hci0/dev_AA_BB failed "
            "payload deadbeefcafebabe"
        )

    monkeypatch.setattr(cli, "_run", fail)
    assert cli.main(["status", "--simulate", "--json"]) == 5
    captured = capsys.readouterr()
    serialized = captured.out
    result = json.loads(serialized)
    assert result["error"]["code"] == "protocol_incompatible"
    assert "[redacted device]" in result["error"]["message"]
    assert "AA:BB" not in serialized
    assert "/org/bluez" not in serialized
    assert "deadbeef" not in serialized
    assert "Traceback" not in serialized
    assert captured.err == ""


def test_json_interruption_is_structured(monkeypatch, capsys):
    async def interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run", interrupt)
    assert cli.main(["status", "--simulate", "--json"]) == 130
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["error"]["code"] == "interrupted"
    assert result["error"]["retryable"] is True
    assert captured.err == ""
