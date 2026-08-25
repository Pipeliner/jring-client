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
    assert (
        "Codec traceability: 85/85 request rows; 86/86 callback rows; "
        "0 family bindings unresolved."
    ) in output
    assert (
        "Request packet routes: 79 main; 6 raw; 1 stateful shared; 1 dynamic; "
        "1 descriptor; 1 DFU; 23 without a fixed packet."
    ) in output
    assert (
        "Reviewed builder parity: 37 byte-exact families on accepted Python "
        "domains; 31 main queue; 6 raw queue; 2 front-inserted."
    ) in output
    assert (
        "Request/callback correlation: 85/85 deterministic request rows; "
        "0 unspecified; 20 wholly unclosed; 58 carry explicit caveats."
    ) in output
    assert (
        "Terminal rules: 36 single matched response; 29 none proven; "
        "17 per-frame only; 2 local quiet unknown; 1 metadata/marker or local "
        "quiet unknown."
    ) in output
    assert (
        "Owned app interface use: 51/112 request targets across 152 direct "
        "invokes; 103/105 callbacks have a direct invoke (181 sites: "
        "125 main, 6 raw, 50 outside dispatchers)."
    ) in output
    assert (
        "Binder parity: 217 transactions; 217 synchronous; 0 Parcel-order "
        "mismatches."
    ) in output
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
    assert result["summary"]["request_codec_locators"] == 85
    assert result["summary"]["callback_codec_locators"] == 86
    assert result["summary"]["unresolved_codec_family_bindings"] == 0
    assert result["summary"]["request_main_layouts"] == 79
    assert result["summary"]["request_raw_layouts"] == 6
    assert result["summary"]["request_no_fixed_packets"] == 23
    assert result["summary"]["request_builder_families"] == 37
    assert result["summary"]["request_builder_main_queue"] == 31
    assert result["summary"]["request_builder_raw_queue"] == 6
    assert result["summary"]["request_builder_front_inserted"] == 2
    assert result["summary"]["request_correlation_rows"] == 85
    assert result["summary"]["request_correlation_unspecified"] == 0
    assert result["summary"]["request_correlation_explicitly_unresolved"] == 20
    assert result["summary"]["request_correlation_rows_with_caveats"] == 58
    assert result["summary"]["request_correlation_terminal_rules"] == [
        {"rule": "local_quiet_unknown", "count": 2},
        {
            "rule": "metadata_or_explicit_marker_else_local_quiet_unknown",
            "count": 1,
        },
        {"rule": "none_proven", "count": 29},
        {"rule": "per_frame_only", "count": 17},
        {"rule": "single_matched_response", "count": 36},
    ]
    assert result["summary"]["app_direct_request_targets"] == 51
    assert result["summary"]["app_direct_request_invokes"] == 152
    assert result["summary"]["directly_invoked_callbacks"] == 103
    assert result["summary"]["direct_callback_invokes"] == 181
    assert result["summary"]["main_response_callback_targets"] == 85
    assert result["summary"]["main_response_callback_invokes"] == 125
    assert result["summary"]["raw_response_callback_targets"] == 5
    assert result["summary"]["raw_response_callback_invokes"] == 6
    assert result["summary"]["outside_dispatcher_callback_targets"] == 17
    assert result["summary"]["outside_dispatcher_callback_invokes"] == 50
    assert result["summary"]["binder_transactions"] == 217
    assert result["summary"]["binder_synchronous_transactions"] == 217
    assert result["summary"]["binder_parcel_order_mismatches"] == 0
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
    codec_registry = result["supplemental"]["codec_registry"]
    request_routing = result["supplemental"]["request_routing"]
    request_builders = result["supplemental"]["request_builder_evidence"]
    request_correlations = result["supplemental"]["request_callback_correlations"]
    app_use = result["supplemental"]["app_use_evidence"]
    binder = result["supplemental"]["binder_evidence"]
    assert len(binder["request"]["rows"]) == 112
    assert len(request_builders["families"]) == 37
    assert request_builders["byte_exact_family_count"] == 37
    assert request_builders["runnable"] is False
    assert request_builders["python_callable"] is False
    assert request_builders["hardware_eligible"] is False
    assert request_builders["hardware_verified"] is False
    assert len(request_correlations["rows"]) == 85
    assert request_correlations["unspecified_count"] == 0
    assert request_correlations["explicitly_unresolved_count"] == 20
    assert request_correlations["rows_with_unresolved_reasons_count"] == 58
    assert request_correlations["terminal_rule_counts"] == [
        {"rule": "local_quiet_unknown", "count": 2},
        {
            "rule": "metadata_or_explicit_marker_else_local_quiet_unknown",
            "count": 1,
        },
        {"rule": "none_proven", "count": 29},
        {"rule": "per_frame_only", "count": 17},
        {"rule": "single_matched_response", "count": 36},
    ]
    assert request_correlations["runnable"] is False
    assert request_correlations["hardware_eligible"] is False
    assert len(binder["callback"]["rows"]) == 105
    assert binder["request"]["one_way_transaction_count"] == 0
    assert binder["callback"]["one_way_transaction_count"] == 0
    assert binder["trailing_data_rejection_observed"] is False
    assert binder["hardware_eligible"] is False
    assert len(app_use["requests"]) == 112
    assert len(app_use["callbacks"]) == 105
    assert app_use["direct_request_target_count"] == 51
    assert app_use["direct_request_invoke_count"] == 152
    assert app_use["directly_invoked_callback_count"] == 103
    assert app_use["direct_callback_invoke_count"] == 181
    assert app_use["main_response_callback_target_count"] == 85
    assert app_use["main_response_callback_invoke_count"] == 125
    assert app_use["raw_response_callback_target_count"] == 5
    assert app_use["raw_response_callback_invoke_count"] == 6
    assert app_use["outside_dispatcher_callback_target_count"] == 17
    assert app_use["outside_dispatcher_callback_invoke_count"] == 50
    assert app_use["cross_namespace_name_collisions"] == ["setAutoHeartMode"]
    assert app_use["dynamic_request_interface_invokes_observed"] is False
    assert app_use["hardware_eligible"] is False
    assert len(request_routing["requests"]) == 112
    assert request_routing["standalone_deterministic_offline_count"] == 85
    assert request_routing["owner_authorized"] is False
    assert len(codec_registry["requests"]) == 85
    assert len(codec_registry["callbacks"]) == 86
    assert all(row["hardware_eligible"] is False for row in codec_registry["requests"])
    assert dispatcher["switch_instruction_count"] == 0
    assert len(dispatcher["callback_routes"]) == 85
    assert dispatcher["hardware_eligible"] is False
    assert len(callback_surfaces) == 16
    assert sum(row["direct_invoke_observed"] for row in callback_surfaces) == 14
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

    assert output.startswith(
        "LIVE RING INPUT UNAVAILABLE — no ring contacted\n"
        "JRing is not a live HID driver. Linux uinput is simulator-only today and "
        "a future translation sink for verified events.\n"
    )
    assert "Standard HID metadata" in output
    assert "Media play/pause" in output
    assert "Call answer" in output
    assert "location access blocked" in output
    assert "device write request blocked" in output
    assert "Cumulative step counter" in output
    assert "Classic profile attachment" in output
    assert "Classic RFCOMM socket lifecycle reference" in output
    assert "Host volume-state request" in output
    assert "General-use static codecs" in output
    assert "Main-channel ChatGPT action" in output
    assert "Offline speech-recognition mode" in output
    assert "Wi-Fi SSID inventory" in output
    assert "Device dial metadata" in output
    assert "privacy: network_identifier" in output
    assert "runnable: no; hardware eligible: no" in output
    assert "available now: no; input eligible: no; hardware verified: no" in output
    assert output.index("Static device actions") < output.index("Sensor-derived candidates")
    assert output.index("Sensor-derived candidates") < output.index("Standards metadata")
    assert output.index("Standards metadata") < output.index("Classic Bluetooth evidence")
    assert output.index("Classic Bluetooth evidence") < output.index("Host integration")
    assert output.index("Host integration") < output.index("General-use static codecs")
    assert output.index("General-use static codecs") < output.index("Raw non-health framing")
    first_candidate = output.index("input candidate: yes")
    assert output.rfind("available now: no; input eligible: no", 0, first_candidate) != -1
    assert "meaning: source-classified label; hardware meaning: unverified" in output


def test_guided_selection_labels_name_match_as_client_heuristic(monkeypatch, capsys):
    candidates = synthetic_selection_candidates()
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    assert cli._choose_candidate(candidates) is None
    output = capsys.readouterr().out
    assert "possible JRing (client name heuristic)" in output


def test_discovery_labels_name_match_as_client_heuristic(capsys):
    cli._print_discovery(
        [synthetic_selection_candidates()[0].public_summary()]
    )

    output = capsys.readouterr().out
    assert "possible JRing (client name heuristic)" in output


def test_non_health_capabilities_json_has_stable_local_taxonomy(capsys):
    assert cli.main(["non-health-capabilities", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["operation"] == "non_health_capabilities"
    assert result["source"] == "local"
    assert result["ok"] is True
    assert result["live_ring_input"] == "unavailable"
    assert len(result["capabilities"]) == 38
    assert sum(
        item["group"] == "device_actions" for item in result["capabilities"]
    ) == 13
    assert all("evidence" in item for item in result["capabilities"])
    expected_keys = {
        "name", "label", "group", "description", "evidence", "maturity",
        "meaning", "input_candidate", "privacy_classes", "request_operations",
        "callback_operations", "runnable", "hardware_eligible",
        "hardware_verified", "live_available", "input_eligible",
    }
    assert all(set(item) == expected_keys for item in result["capabilities"])
    assert all(item["evidence"] and item["maturity"] for item in result["capabilities"])
    assert sum(
        item["group"] == "general_use" for item in result["capabilities"]
    ) == 15
    assert all(item["privacy_classes"] for item in result["capabilities"])
    assert all(item["runnable"] is False for item in result["capabilities"])
    assert all(item["hardware_eligible"] is False for item in result["capabilities"])
    assert all(item["input_eligible"] is False for item in result["capabilities"])
    serialized = json.dumps(result).lower()
    assert "payload_bytes" not in serialized
    assert '"frame"' not in serialized


@pytest.mark.parametrize(
    "argv",
    [
        ["non-health-capabilities"],
        ["non-health-capabilities", "--json"],
        ["input-actions"],
        ["input-actions", "--json"],
    ],
)
def test_local_inventory_commands_construct_no_transport_scan_or_input_sink(
    monkeypatch, capsys, argv
):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("local inventory must not construct an external capability")

    monkeypatch.setattr(cli, "BleakTransport", forbidden)
    monkeypatch.setattr(cli, "JRingClient", forbidden)
    monkeypatch.setattr(cli.FakeTransport, "for_simulator_profile", forbidden)
    monkeypatch.setattr(cli, "discover", forbidden)
    monkeypatch.setattr(cli, "discover_for_selection", forbidden)
    monkeypatch.setattr(cli, "create_uinput_sink", forbidden)

    assert cli.main(argv) == 0
    assert capsys.readouterr().out


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


def test_guided_capabilities_selects_ephemerally_and_reads_metadata_only(
    monkeypatch, capsys
):
    enable_interactive_terminal(monkeypatch)
    candidates = synthetic_selection_candidates()
    selected = candidates[1]
    transport = FakeTransport.standard_hid_ring()
    connected = []

    async def forbidden_value(*_args, **_kwargs):
        raise AssertionError("capability inventory must not read, write, or subscribe")

    def forbidden_sink(*_args, **_kwargs):
        raise AssertionError("capability inventory must not open uinput")

    transport.read = forbidden_value
    transport.write = forbidden_value
    transport.write_with_response = forbidden_value
    transport.subscribe = forbidden_value

    async def scan(**_kwargs):
        return candidates

    def make_transport(address):
        connected.append(address)
        return transport

    responses = iter(["2", "y"])
    monkeypatch.setattr(cli, "discover_for_selection", scan)
    monkeypatch.setattr(cli, "BleakTransport", make_transport)
    monkeypatch.setattr(cli, "create_uinput_sink", forbidden_sink)
    monkeypatch.setattr(
        cli.Path,
        "write_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("guided selection must not persist a result")
        ),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli.main(["capabilities", "--select", "--active-scan"]) == 0
    output = capsys.readouterr().out
    assert connected == [selected.connection_address()]
    assert "for capabilities" in output
    assert output.index("ACTIVE SCAN") < output.index("CONNECTION NOT STARTED")
    assert selected.alias in output
    assert "AA:BB" not in output
    assert "11:22" not in output


@pytest.mark.parametrize("confirmation", ["", "n", "no"])
def test_guided_capabilities_default_no_never_constructs_transport(
    monkeypatch, capsys, confirmation
):
    enable_interactive_terminal(monkeypatch)
    candidates = synthetic_selection_candidates()[:1]
    constructed = False

    async def scan(**_kwargs):
        return candidates

    def forbidden_transport(_address):
        nonlocal constructed
        constructed = True
        raise AssertionError("default-no selection must not construct a transport")

    responses = iter(["1", confirmation])
    monkeypatch.setattr(cli, "discover_for_selection", scan)
    monkeypatch.setattr(cli, "BleakTransport", forbidden_transport)
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    assert cli.main(["capabilities", "--select", "--active-scan"]) == 0
    assert constructed is False
    assert "Cancelled; no connection made." in capsys.readouterr().out


def test_guided_capabilities_eof_at_confirmation_is_default_no(monkeypatch, capsys):
    enable_interactive_terminal(monkeypatch)
    candidates = synthetic_selection_candidates()[:1]
    calls = iter(["1"])

    async def scan(**_kwargs):
        return candidates

    def answer(_prompt):
        try:
            return next(calls)
        except StopIteration as exc:
            raise EOFError from exc

    monkeypatch.setattr(cli, "discover_for_selection", scan)
    monkeypatch.setattr(
        cli,
        "BleakTransport",
        lambda _address: (_ for _ in ()).throw(
            AssertionError("EOF confirmation must not construct a transport")
        ),
    )
    monkeypatch.setattr("builtins.input", answer)

    assert cli.main(["capabilities", "--select", "--active-scan"]) == 0
    assert "Cancelled; no connection made." in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv,message",
    [
        (["capabilities", "--select"], "--active-scan"),
        (["capabilities", "--active-scan"], "--select"),
    ],
)
def test_guided_capabilities_requires_explicit_human_scan_consent(
    argv, message, capsys
):
    with pytest.raises(SystemExit) as raised:
        cli.main(argv)
    assert raised.value.code == 2
    captured = capsys.readouterr()
    assert message in captured.err


def test_guided_capabilities_json_fails_with_private_usage_envelope(capsys):
    assert cli.main([
        "capabilities", "--select", "--active-scan", "--json",
    ]) == 2
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["error"]["code"] == "usage"
    assert "human-only" in result["error"]["message"]
    assert "AA:BB" not in captured.out
    assert captured.err == ""


def test_guided_capabilities_noninteractive_rejects_before_scan(monkeypatch, capsys):
    scanned = False

    async def scan(**_kwargs):
        nonlocal scanned
        scanned = True

    monkeypatch.setattr(cli, "discover_for_selection", scan)

    with pytest.raises(SystemExit) as raised:
        cli.main(["capabilities", "--select", "--active-scan"])
    assert raised.value.code == 2
    assert scanned is False
    assert "interactive terminal" in capsys.readouterr().err


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
