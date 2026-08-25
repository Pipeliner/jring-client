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
    assert "Simulator profile: basic" in output
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
    assert result["simulator_profile"] == "basic"
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


@pytest.mark.parametrize(
    "argv",
    (
        ["--simulate", "--simulate-profile", "hid", "status", "--json"],
        ["status", "--simulate", "--simulate-profile", "hid", "--json"],
    ),
)
def test_simulator_profile_preserves_global_and_task_first_forms(argv, capsys):
    assert cli.main(argv) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source"] == "simulator"
    assert result["simulator_profile"] == "hid"
    assert result["capabilities"]["hid_service_advertised"] is True


def test_simulator_profile_requires_simulation(capsys):
    assert cli.main([
        "status", "--simulate-profile", "hid", "--json",
    ]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "usage"
    assert "requires --simulate" in result["error"]["message"]


@pytest.mark.parametrize("profile", ("basic", "hid"))
def test_simulator_profiles_never_construct_hardware_transport(
    profile, monkeypatch, capsys
):
    def forbidden_transport(*_args, **_kwargs):
        raise AssertionError("simulator profile must not construct hardware transport")

    monkeypatch.setattr(cli, "BleakTransport", forbidden_transport)
    assert cli.main([
        "status", "--simulate", "--simulate-profile", profile,
    ]) == 0
    assert f"Simulator profile: {profile}" in capsys.readouterr().out


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
    assert "[ok] python:" in output
    assert "[fix] bleak:" in output
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
    assert "Simulator profile: basic" in output
    assert "Preview: step -> primary (left) mouse click" in output
    assert "No input emitted" in output


def test_input_actions_are_screen_reader_ordered(capsys):
    assert cli.main(["input-actions"]) == 0
    output = capsys.readouterr().out
    assert output.index("Simulator profiles") < output.index("Available simulated events")
    assert "basic: standard ring metadata; standard HID not advertised" in output
    assert "hid: basic metadata plus standard HID advertisement metadata" in output
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
    assert [profile["name"] for profile in result["simulator_profiles"]] == [
        "basic", "hid",
    ]
    assert result["simulator_profiles"][1]["standard_hid_advertised"] is True
    assert [item["name"] for item in result["actions"][-3:]] == [
        "primary", "secondary", "middle",
    ]


def test_input_profile_is_explicit_in_human_and_json_output(capsys):
    assert cli.main([
        "input", "--simulate", "--simulate-profile", "hid",
        "--map", "step=key:space",
    ]) == 0
    output = capsys.readouterr().out
    assert "Simulator profile: hid" in output
    assert "No input emitted" in output

    assert cli.main([
        "input", "--simulate", "--simulate-profile", "hid",
        "--map", "step=key:space", "--json",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["source"] == "simulator"
    assert result["simulator_profile"] == "hid"
    assert result["emitted"] is False


def test_simulator_profiles_are_discoverable_in_help(capsys):
    with pytest.raises(SystemExit) as raised:
        cli.main(["capabilities", "--help"])
    assert raised.value.code == 0
    output = capsys.readouterr().out
    assert "--simulate-profile {basic,hid}" in output
    assert "never reads or emits HID reports" in " ".join(output.split())


def test_protocol_coverage_human_summary_is_offline_and_honest(capsys):
    assert cli.main(["protocol-coverage"]) == 0
    output = capsys.readouterr().out

    assert "OFFLINE PROTOCOL COVERAGE — no ring contacted" in output
    assert "Static source recovery completeness: not established." in output
    assert "Decompiler run: 6,705 classes processed; 89 run-reported failures." in output
    assert "Structured output: 88 failed-method stubs across 52 files." in output
    assert "Emitted error or incorrect-code markers: 87." in output
    assert "JRing application scope: 0 hard-failure files among 268 outputs scanned." in output
    assert "Embedded BLE SDK scope: 0 hard-failure files among 47 outputs scanned." in output
    assert "Warning-bearing files remain: 23 application; 21 embedded SDK." in output
    assert "Fallback-mode decompiler pass: completed" in output
    assert "Complete semantic source review: not performed." in output
    assert "Complete smali/instruction review: not performed." in output
    assert "Complete DEX coverage: not claimed." in output
    assert "Owned-scope warning audit: semantic correctness not established." in output
    assert (
        "Bluetooth-related warning-bearing files: 11 application; 21 embedded SDK; "
        "5 dependency files excluded."
    ) in output
    assert "Owned warning occurrences: 29 application; 62 embedded SDK." in output
    assert "Same-tool surface corroborations: 2; comparison divergences: 1." in output
    assert "Instruction-reviewed facts contradicted: 0." in output
    assert "Instruction reviews inconclusive: 0." in output
    assert "Bounded instruction facts confirmed: 8." in output
    assert (
        "Dispatcher structure: 85 targets; 125 syntactic invokes (124 reachable); "
        "104 distinct opcodes."
    ) in output
    assert "Target instruction reviews not performed: 0." in output
    assert "Artifact-surface completeness: not established." in output
    assert "AIDL interface parity: 112 requests; 105 callbacks; 0 missing rows." in output
    assert "Exclusive owned method classification: 903 methods across 125 classes." in output
    assert "Dynamic receiver gaps: 3 registered actions without cases" in output
    assert "Native declarations unresolved: 7; native Bluetooth absence not established." in output
    assert "Native JNI roots: 3 image/wallpaper entries reviewed" in output
    assert "Owned reflection: 11 calls resolved to constant Android helper targets" in output
    assert "Standalone dial static activation: no edge in reviewed Binder/resource paths" in output
    assert "Dial-transfer dynamic activation: inconclusive." in output
    assert output.index("Dynamic receiver gaps:") < output.index("AIDL interface parity:")
    assert "missing failure" not in output.lower()
    assert "success rate" not in output.lower()
    assert "Requests: 112" in output
    assert "Callbacks: 105" in output
    assert "Offline request codecs: 85" in output
    assert "Offline response codecs: 86" in output
    assert "Offline local projections: 3" in output
    assert "Offline callback behavior evidence: 14" in output
    assert "Offline callback declaration evidence: 2" in output
    assert "Unclassified callbacks: 0" in output
    assert "Supplemental session transitions (not interface entries): 33" in output
    assert "Adversarial session races: 22" in output
    assert "Source-labeled binding reactions: 6" in output
    assert "Offline control models: 1" in output
    assert "Offline behavior evidence: 26" in output
    assert "Unclassified requests: 0" in output
    assert "Live vendor operations: 0" in output
    assert "Hardware-eligible vendor operations: 0" in output
    assert "Hardware-verified vendor operations: 0" in output
    assert "Static coverage never authorizes Bluetooth writes or subscriptions." in output
    assert "Supplemental session evidence is static and non-runnable." in output
    assert output.rstrip().endswith(
        "Hardware status remains: 0 hardware-verified vendor operations."
    )


def test_protocol_coverage_json_accounts_for_every_entry(capsys):
    assert cli.main(["protocol-coverage", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["operation"] == "protocol_coverage"
    assert result["source"] == "local"
    assert result["ok"] is True
    assert result["summary"]["request_total"] == 112
    assert result["summary"]["callback_total"] == 105
    assert result["summary"]["offline_request_codecs"] == 85
    assert result["summary"]["offline_response_codecs"] == 86
    assert result["summary"]["offline_local_projections"] == 3
    assert result["summary"]["offline_callback_behavior_evidence"] == 14
    assert result["summary"]["offline_callback_declaration_evidence"] == 2
    assert result["summary"]["unclassified_callbacks"] == 0
    assert result["summary"]["supplemental_session_transitions"] == 33
    assert result["summary"]["supplemental_session_races"] == 22
    assert result["summary"]["supplemental_binding_reactions"] == 6
    assert result["summary"]["decompiler_processed_classes"] == 6_705
    assert result["summary"]["decompiler_run_reported_failures"] == 89
    assert result["summary"]["decompiler_failed_method_stubs"] == 88
    assert result["summary"]["decompiler_hard_failure_files"] == 52
    assert result["summary"]["decompiler_error_or_incorrect_markers"] == 87
    assert result["summary"]["owned_warning_audit_files"] == 32
    assert result["summary"]["owned_warning_audit_occurrences"] == 91
    assert result["summary"]["same_tool_surface_corroborations"] == 2
    assert result["summary"]["warning_comparison_divergences"] == 1
    assert result["summary"]["instruction_bounded_facts_confirmed"] == 8
    assert result["summary"]["instruction_bounded_facts_contradicted"] == 0
    assert result["summary"]["instruction_reviews_inconclusive"] == 0
    assert result["summary"]["dispatcher_unique_callback_targets"] == 85
    assert result["summary"]["dispatcher_reachable_callback_invokes"] == 124
    assert result["summary"]["dispatcher_distinct_opcodes"] == 104
    assert result["summary"]["offline_control_models"] == 1
    assert result["summary"]["offline_behavior_evidence"] == 26
    assert result["summary"]["unclassified_requests"] == 0
    assert result["summary"]["live_vendor_operations"] == 0
    assert result["summary"]["hardware_eligible_vendor_operations"] == 0
    assert result["summary"]["hardware_verified_vendor_operations"] == 0
    assert len(result["requests"]) == 112
    assert len(result["callbacks"]) == 105
    session = result["supplemental"]["session_sequence"]
    assert session["interface_entries"] is False
    assert session["runnable"] is False
    assert session["hardware_eligible"] is False
    assert session["hardware_verified"] is False
    assert session["owner_authorized"] is False
    assert len(session["transitions"]) == 33
    assert len(session["races"]) == 22
    assert len(session["binding_reactions"]) == 6
    decompilation = result["supplemental"]["decompilation_coverage"]
    assert decompilation["interface_entries"] is False
    assert decompilation["source_recovery_completeness"] == "not_established"
    assert decompilation["count_reconciliation"] == "different_observables"
    assert decompilation["run_to_marker_mapping_established"] is False
    assert decompilation["primary_pass"]["run_reported_failure_count"] == 89
    assert decompilation["primary_pass"]["failed_method_stub_count"] == 88
    assert decompilation["fallback_pass"]["run_reported_failure_count"] is None
    assert decompilation["fallback_pass"]["run_failure_count_available"] is False
    assert decompilation["semantic_correctness_established"] is False
    assert decompilation["complete_semantic_source_review_completed"] is False
    assert decompilation["complete_smali_review_completed"] is False
    assert decompilation["complete_dex_instruction_review_completed"] is False
    assert decompilation["complete_dex_coverage"] is False
    assert decompilation["hardware_authority"] is False
    assert decompilation["hardware_verified"] is False
    assert "missing_error_count" not in json.dumps(decompilation)
    assert "success_rate" not in json.dumps(decompilation)
    warning_audit = result["supplemental"]["warning_audit"]
    assert warning_audit["interface_entries"] is False
    assert warning_audit["source_recovery_completeness"] == "not_established"
    assert warning_audit["semantic_correctness_established"] is False
    assert warning_audit["instruction_review_complete"] is False
    assert warning_audit["all_bounded_facts_resolved"] is True
    assert warning_audit["exhaustive_bluetooth_dependency_audit"] is False
    assert warning_audit["hardware_eligible"] is False
    assert warning_audit["hardware_verified"] is False
    assert len(warning_audit["scopes"]) == 3
    assert len(warning_audit["comparisons"]) == 8
    artifact = result["supplemental"]["artifact_surface"]
    callback_surfaces = result["supplemental"]["callback_behavior_surfaces"]
    dispatcher = result["supplemental"]["dispatcher_evidence"]
    assert dispatcher["switch_instruction_count"] == 0
    assert len(dispatcher["callback_routes"]) == 85
    assert dispatcher["hardware_eligible"] is False
    assert len(callback_surfaces) == 16
    assert sum(row["direct_dispatch_observed"] for row in callback_surfaces) == 14
    assert all(row["runnable"] is False for row in callback_surfaces)
    assert all(row["hardware_eligible"] is False for row in callback_surfaces)
    assert artifact["interface_entries"] is False
    assert artifact["source_recovery_completeness"] == "not_established"
    assert artifact["complete_artifact_coverage"] is False
    assert artifact["reflection_or_dynamic_activation_exhaustively_disproved"] is False
    assert artifact["hardware_eligible"] is False
    assert artifact["hardware_verified"] is False
    assert artifact["interface_parity"]["missing_public_row_count"] == 0
    assert artifact["exclusive_classified_method_count"] == 903
    assert artifact["dynamic_activation_surface"]["review_state"] == "inconclusive"
    assert result["summary"]["artifact_missing_interface_rows"] == 0
    assert result["summary"]["artifact_unresolved_native_declarations"] == 7
    assert result["summary"]["artifact_rooted_jni_entries_reviewed"] == 3
    assert result["summary"]["artifact_owned_reflective_invokes"] == 11
    assert result["summary"]["artifact_standalone_dial_external_references"] == 0
    assert result["summary"]["artifact_relevant_binder_outbound_invokes"] == 0
    def keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield key
                yield from keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from keys(nested)

    assert all("frame" not in key.lower() for key in keys(result))


def test_protocol_coverage_never_constructs_a_transport(monkeypatch, capsys):
    def forbidden_transport(*_args, **_kwargs):
        raise AssertionError("transport must not be constructed")

    monkeypatch.setattr(cli, "BleakTransport", forbidden_transport)

    assert cli.main(["protocol-coverage"]) == 0
    assert "no ring contacted" in capsys.readouterr().out


def test_non_health_capabilities_are_local_task_first_and_screen_reader_ordered(
    monkeypatch, capsys
):
    def forbidden_transport(*_args, **_kwargs):
        raise AssertionError("local non-health inventory must not construct a transport")

    monkeypatch.setattr(cli, "BleakTransport", forbidden_transport)
    assert cli.main(["non-health-capabilities"]) == 0
    output = capsys.readouterr().out

    assert output.startswith("LIVE RING INPUT UNAVAILABLE — no ring contacted\n")
    assert "Standard HID metadata" in output
    assert "Media play/pause" in output
    assert "Call answer" in output
    assert "location access blocked" in output
    assert "device write request blocked" in output
    assert "Cumulative step counter" in output
    assert "hardware verified: no; live available: no; input eligible: no" in output
    assert output.index("Standard HID metadata") < output.index("Static device actions")
    assert output.index("Static device actions") < output.index("Sensor-derived candidates")


def test_non_health_capabilities_json_has_stable_local_taxonomy(capsys):
    assert cli.main(["non-health-capabilities", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["operation"] == "non_health_capabilities"
    assert result["source"] == "local"
    assert result["ok"] is True
    assert result["live_ring_input"] == "unavailable"
    assert len(result["capabilities"]) == 18
    assert sum(
        item["group"] == "device_actions" for item in result["capabilities"]
    ) == 13
    assert all("evidence" in item for item in result["capabilities"])
    assert all(item["input_eligible"] is False for item in result["capabilities"])
    serialized = json.dumps(result).lower()
    assert "payload_bytes" not in serialized
    assert '"frame"' not in serialized


def test_non_health_capabilities_rejects_unrelated_runtime_selectors(capsys):
    assert cli.main([
        "--simulate", "non-health-capabilities", "--json",
    ]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "usage"


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
