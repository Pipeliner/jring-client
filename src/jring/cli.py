from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
import importlib.resources
import json
import math
import os
import re
import stat
import sys
from urllib.parse import quote, urlencode
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import IntEnum
from io import StringIO
from pathlib import Path
from typing import Any

from . import __version__
from .bleak_transport import BleakTransport
from .client import JRingClient
from .discovery import SelectionCandidate, discover, discover_for_selection, select_exact
from .errors import UnavailableError
from .input import (
    InputMapper,
    create_uinput_sink,
    input_action_inventory,
    parse_binding,
)
from .non_health import static_non_health_capabilities
from .pairing import pair_device
from .owner_hardware_evidence import (
    OwnerEvidenceError,
    OwnerEvidenceStatus,
    OwnerHardwareEvidenceRunner,
    load_private_owner_evidence,
    prepare_owner_evidence_run,
    prepare_owner_evidence_selection,
    prepare_owner_negative_control,
    render_approved_compatibility_row,
    validate_owner_evidence_prerequisites,
    write_owner_evidence_review,
    write_reviewed_compatibility_row,
)
from .private_observation import (
    ObservationError,
    ObservationStatus,
    PrivateObservationRunner,
    load_private_observation,
    prepare_observation_plan,
)
from .protocol import HeartRate, ProtocolError
from .readiness import ReadinessReport, diagnose
from .transport import SIMULATOR_PROFILES, FakeTransport
from .uuids import HEART_RATE_MEASUREMENT
from .vendor_app_use_evidence import recovered_vendor_app_use_evidence
from .bluetooth_parity_manifest import bluetooth_parity_manifest_payload
from .clean_room_gap_registry import clean_room_gap_payload
from .vendor_artifact_evidence import recovered_artifact_surface_evidence
from .vendor_binder_evidence import recovered_vendor_binder_evidence
from .vendor_callback_surfaces import recovered_callback_behavior_surfaces
from .vendor_codec_registry import (
    CALLBACK_CODEC_LOCATORS,
    REQUEST_CODEC_LOCATORS,
    CodecBindingKind,
)
from .vendor_coverage import (
    OFFLINE_REQUEST_CODEC_STATES,
    VendorPythonState,
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)
from .vendor_decompilation_evidence import recovered_decompilation_coverage
from .vendor_dispatcher_evidence import recovered_dispatcher_evidence
from .vendor_input_preview import synthetic_vendor_step_preview
from .vendor_request_builder_evidence import recovered_request_builder_evidence
from .vendor_request_callback_correlation import (
    recovered_request_callback_correlations,
)
from .vendor_request_routing import recovered_request_routing_evidence
from .vendor_operation_registry import (
    recovered_vendor_operation_registry,
    vendor_operation_registry_payload,
)
from .vendor_runtime_eligibility import (
    FakeSingletonEligibilityState,
    recovered_vendor_fake_singleton_eligibility,
)
from .vendor_session_evidence import recovered_session_evidence
from .vendor_warning_evidence import (
    ComparisonState,
    recovered_warning_audit,
)


class ExitCode(IntEnum):
    OK = 0
    USAGE = 2
    UNAVAILABLE = 3
    TIMEOUT = 4
    PROTOCOL_INCOMPATIBLE = 5
    PERMISSION_DENIED = 6
    INTERNAL = 70
    INTERRUPTED = 130


@dataclass(frozen=True)
class ErrorContract:
    code: str
    exit_code: ExitCode
    retryable: bool


class _OwnerEvidenceInterrupted(RuntimeError):
    def __init__(self, payload: dict[str, object]):
        self.payload = dict(payload)
        super().__init__(
            "owner evidence interrupted; a write may have been dispatched; inspect "
            "the requested private record before any manual rerun"
        )


_USAGE = ErrorContract("usage", ExitCode.USAGE, False)
_UNAVAILABLE = ErrorContract("unavailable", ExitCode.UNAVAILABLE, True)
_TIMEOUT = ErrorContract("timeout", ExitCode.TIMEOUT, True)
_PROTOCOL = ErrorContract(
    "protocol_incompatible", ExitCode.PROTOCOL_INCOMPATIBLE, False
)
_PERMISSION = ErrorContract("permission_denied", ExitCode.PERMISSION_DENIED, False)
_INTERNAL = ErrorContract("internal", ExitCode.INTERNAL, False)
_INTERRUPTED = ErrorContract("interrupted", ExitCode.INTERRUPTED, True)


def _json_envelope(
    *,
    operation: str,
    source: str,
    ok: bool,
    payload: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = dict(payload or {})
    result.update({
        "schema_version": 1,
        "operation": operation,
        "source": source,
        "ok": ok,
    })
    if error is not None:
        result["error"] = error
    return result


def _print_json_success(operation: str, source: str, payload: dict[str, Any]) -> None:
    print(json.dumps(_json_envelope(
        operation=operation,
        source=source,
        ok=True,
        payload=payload,
    ), indent=2, sort_keys=True))


def _print_status(result: dict[str, Any]) -> None:
    info = result["device_info"]
    info_states = result["device_info_states"]
    capabilities = result["capabilities"]
    if result["source"] == "simulator":
        print("SIMULATION — no ring contacted")
        print(f"Simulator profile: {result['simulator_profile']}")
    else:
        print("HARDWARE — explicitly selected ring")
    battery_state = result["battery_state"]
    battery = (
        f"{result['battery_percent']}% (available)" if result["battery_available"]
        else _absent_value(battery_state)
    )
    print(f"Battery: {battery}")
    for label, name in (
        ("Model", "model"),
        ("Manufacturer", "manufacturer"),
        ("Firmware", "firmware"),
        ("Hardware", "hardware"),
        ("Software", "software"),
    ):
        state = info_states[name]
        value = f"{info[name]} (available)" if state == "available" else _absent_value(state)
        print(f"{label}: {value}")
    inventory_state = capabilities["inventory_state"]
    if inventory_state == "available":
        heart_rate = (
            "advertised (not tested)" if capabilities["heart_rate_service_advertised"]
            else "not advertised"
        )
        hid = (
            "advertised (usability unknown)" if capabilities["hid_service_advertised"]
            else "not advertised"
        )
    else:
        heart_rate = f"unknown ({inventory_state})"
        hid = f"unknown ({inventory_state})"
    print(f"Heart-rate service: {heart_rate}")
    print(f"Standard HID service: {hid}")
    vendor_count = len(capabilities["vendor_services_seen"])
    vendor = (
        f"{vendor_count} detected" if inventory_state == "available"
        else f"unknown ({inventory_state})"
    )
    print(f"Vendor services: {vendor}; writes disabled")


def _absent_value(state: str) -> str:
    return {
        "unavailable": "unavailable",
        "malformed": "unavailable (malformed value)",
        "timed_out": "unavailable (timed out)",
        "not_advertised": "not advertised",
    }.get(state, f"unavailable ({state})")


def _heart_rate_payload(
    sample: HeartRate,
    *,
    source: str,
    simulator_profile: str | None,
) -> dict[str, object]:
    contact_state = (
        "unknown"
        if sample.contact_detected is None
        else "detected" if sample.contact_detected else "not_detected"
    )
    payload: dict[str, object] = {
        "synthetic": source == "simulator",
        "measurement": {
            "bpm": sample.bpm,
            "contact_state": contact_state,
        },
        "observation_scope": (
            "synthetic" if source == "simulator" else "this_connection_only"
        ),
        "firmware_support": "not_established",
        "medical_use": "not_for_medical_use",
        "persistence": "not_saved",
        "notification_control": (
            "not_used" if source == "simulator" else "standard_cccd"
        ),
        "notification_cleanup": (
            "not_applicable" if source == "simulator" else "complete"
        ),
        "vendor_command_sent": False,
    }
    if source == "simulator":
        payload["simulator_profile"] = simulator_profile
    return payload


def _print_heart_rate(payload: dict[str, object], source: str) -> None:
    if source == "simulator":
        print("SIMULATION — no ring contacted")
        print(f"Simulator profile: {payload['simulator_profile']}")
        print("Synthetic standard heart-rate sample")
    else:
        print("HARDWARE — explicitly selected ring")
        print("STANDARD HEART-RATE NOTIFICATION — observed on this connection")
    print("Health measurement: displayed only; not saved")
    measurement = payload["measurement"]
    print(f"Heart rate: {measurement['bpm']} bpm")
    print(f"Contact: {measurement['contact_state'].replace('_', ' ')}")
    print("Meaning: fitness information only; not medical advice")
    if source == "simulator":
        print("Notification control: not used; no Bluetooth operation occurred")
    else:
        print(
            "Notification control: standard CCCD only; "
            "no vendor characteristic command was sent"
        )
        print("Compatibility: model and firmware support not established")
        print("Notification cleanup: complete")


def _print_discovery(results: list[dict[str, object]]) -> None:
    if not results:
        print("No nearby Bluetooth devices found.")
        print("Keep the ring close, wake it, and try again.")
        return
    print(f"Found {len(results)} nearby Bluetooth device(s):")
    for item in results:
        likelihood = (
            "possible JRing (client name heuristic)"
            if item["likely_jring"]
            else "unidentified (client name heuristic)"
        )
        rssi = item["rssi"] if item["rssi"] is not None else "unknown"
        print(f"- {item['alias']}: {likelihood}, signal {rssi} dBm")
    print("Addresses stay hidden during discovery. Use BlueZ to identify your ring,")
    print("then store its exact address in a mode-0600 file and use --address-file.")
    print("Or run jring status --select --active-scan for same-process guided selection.")


def _choose_candidate(
    candidates: list[SelectionCandidate], *, purpose: str = "status"
) -> str | None:
    if not candidates:
        raise UnavailableError("no nearby Bluetooth devices found; no connection attempted")
    print(f"Found {len(candidates)} nearby Bluetooth device(s):")
    for index, candidate in enumerate(candidates, start=1):
        likelihood = (
            "possible JRing (client name heuristic)"
            if candidate.likely_jring
            else "unidentified (client name heuristic)"
        )
        print(
            f"{index}. {candidate.alias}: {likelihood}, "
            f"signal {_signal_strength(candidate.rssi)}"
        )
    try:
        answer = input("Choose a device number, or q to cancel: ").strip()
    except EOFError:
        answer = "q"
    if answer.lower() in {"q", "quit", "cancel"}:
        print("Cancelled; no connection made.")
        return None
    if not answer.isdecimal() or not 1 <= int(answer) <= len(candidates):
        raise ValueError("selection must be exactly one listed device number")
    selected = candidates[int(answer) - 1]
    print(f"CONNECTION NOT STARTED — selected {selected.alias}.")
    try:
        confirmation = input(
            f"Connect to this device for {purpose}? [y/N]: "
        ).strip().lower()
    except EOFError:
        confirmation = ""
    if confirmation not in {"y", "yes"}:
        print("Cancelled; no connection made.")
        return None
    print(f"CONNECTION AUTHORIZED — connecting to {selected.alias} for {purpose}.")
    return selected.connection_address()


def _signal_strength(rssi: int | None) -> str:
    if rssi is None:
        return "unknown"
    if rssi >= -55:
        return "strong"
    if rssi >= -70:
        return "moderate"
    return "weak"


def _print_readiness(report: ReadinessReport) -> None:
    print("JRing setup check")
    print(f"Simulator: {'ready' if report.simulator_ready else 'not ready'}")
    print(f"BLE prerequisites: {'installed' if report.hardware_ready else 'incomplete'}")
    adapter = (
        "operational" if report.adapter_operational is True
        else "incomplete" if report.adapter_operational is False
        else "not inspected"
    )
    print(f"Bluetooth adapter: {adapter}")
    print(f"Ring compatibility: {report.ring_compatibility.replace('_', ' ')}")
    print(f"Desktop-input prerequisites: {'installed' if report.input_ready else 'incomplete'}")
    for check in report.checks:
        print(f"[{'ok' if check.ok else 'fix'}] {check.name}: {check.detail}")
        if check.remedy:
            print(f"      Remedy: {check.remedy}")
    print(f"Next: {report.next_step}")


def _print_terminal_home() -> None:
    """Print the fixed, side-effect-free first screen for a bare human invocation."""

    print("JRING — SAFE START")
    print("No ring selected. No Bluetooth, scan, network, or desktop-input action occurred.")
    print()
    print("Start safely")
    print("  jring status --simulate")
    print("  Preview the local simulated status workflow.")
    print()
    print("Check this computer (optional)")
    print("  jring doctor")
    print("  Passively inspect local prerequisites without selecting or contacting a ring.")
    print()
    print("Shell integration (optional, offline)")
    print("  jring completion bash")
    print("  Print the packaged Bash completion script; it does not install or activate it.")
    print()
    print("Explore recovered evidence (offline)")
    print("  jring non-health-capabilities")
    print("  jring protocol-coverage")
    print()
    print("Use hardware only when ready")
    print("  Run jring doctor, then use --address-file (preferred) with a supported command.")
    print("  For private protocol investigation: capabilities → observe → review-observation.")
    print("  This stores bounded unknown notifications locally; it does not decode or enable behavior.")
    print()
    print("Unavailable today: live vendor Bluetooth operations, hardware-verified vendor behavior,")
    print("and host input from ring events.")
    print()
    print("More commands: jring --help")


def _tui_command(argv: list[str]) -> str:
    output = StringIO()
    with redirect_stdout(output):
        main(argv)
    return output.getvalue()


def _run_tui_pair_prompt() -> None:
    default_path = "~/.config/jring/address"
    try:
        entered = input(f"Address file [{default_path}]: ").strip()
        path = entered or default_path
        if input("Type PAIR to authorize one BlueZ pairing operation: ").strip() != "PAIR":
            print("Pairing cancelled; nothing was run.")
            return
        argv = ["pair", "--address-file", os.path.expanduser(path), "--allow-pairing"]
        if input("Also trust this device after pairing? [y/N]: ").strip().lower() in {"y", "yes"}:
            argv.append("--allow-trust")
        print(_tui_command(argv))
    except (EOFError, KeyboardInterrupt):
        print("Pairing cancelled; nothing was run.")


def _run_plain_tui() -> int:
    print("JRING — SAFE TUI")
    print("No ring selected. No Bluetooth, scan, network, or desktop-input action occurred.")
    print()
    print("s) Simulated status")
    print("c) Simulated capabilities (including HID metadata)")
    print("d) Check this computer (doctor)")
    print("i) Explore input actions")
    print("p) Pair (and optionally trust) one selected device")
    print("h) Show command-line quickstart")
    print("r) Refresh the selected view")
    print("q) Quit")
    last_view = ["s"]
    while True:
        try:
            choice = input("\nChoose an option [s/c/d/i/p/h/q]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return ExitCode.OK
        if choice == "q":
            print("Goodbye. No ring was contacted.")
            return ExitCode.OK
        if choice in {"s", "c", "d", "i", "p", "h"}:
            last_view[0] = choice
        if choice in {"s", "r"}:
            print(_tui_command(["status", "--simulate"]))
        elif choice == "c":
            print(_tui_command(["capabilities", "--simulate", "--simulate-profile", "hid"]))
        elif choice == "d":
            print(_tui_command(["doctor"]))
        elif choice == "i":
            print(_tui_command(["input-actions"]))
        elif choice == "p":
            _run_tui_pair_prompt()
        elif choice == "h":
            _print_terminal_home()
        else:
            if choice != "r":
                print("Choose s, c, d, i, p, h, r, or q. Nothing was run.")


def _run_curses_tui() -> int:
    import curses
    import time

    views = {
        "s": ("SIMULATED STATUS", ["status", "--simulate"]),
        "c": ("SIMULATED CAPABILITIES", ["capabilities", "--simulate", "--simulate-profile", "hid"]),
        "d": ("LOCAL READINESS", ["doctor"]),
        "i": ("INPUT ACTIONS", ["input-actions"]),
    }
    state = {"view": "s", "text": ""}

    def refresh_view() -> None:
        state["text"] = _tui_command(views[state["view"]][1])

    def draw(stdscr: Any) -> None:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.keypad(True)
        refresh_view()
        last_refresh = time.monotonic()
        while True:
            if time.monotonic() - last_refresh >= 2:
                refresh_view()
                last_refresh = time.monotonic()
            height, width = stdscr.getmaxyx()
            stdscr.erase()
            title = " JRING — SAFE TUI (simulator) "
            stdscr.addnstr(0, 0, title, max(0, width - 1), curses.A_REVERSE)
            stdscr.addnstr(1, 0, "No ring selected • no scan • no connection • no input", max(0, width - 1))
            stdscr.addnstr(3, 0, "[s] status  [c] capabilities  [d] doctor  [i] inputs  [p] pair  [r] refresh  [q] quit", max(0, width - 1))
            stdscr.addnstr(4, 0, f"View: {views[state['view']][0]}  (refreshes every 2s)", max(0, width - 1), curses.A_BOLD)
            for row, line in enumerate(state["text"].splitlines(), start=6):
                if row >= height - 1:
                    break
                stdscr.addnstr(row, 0, line, max(0, width - 1))
            stdscr.refresh()
            key = stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return
            if key in (ord("s"), ord("S"), ord("c"), ord("C"), ord("d"), ord("D"), ord("i"), ord("I")):
                state["view"] = chr(key).lower()
                refresh_view()
                last_refresh = time.monotonic()
            elif key in (ord("r"), ord("R")):
                refresh_view()
                last_refresh = time.monotonic()
            elif key in (ord("p"), ord("P")):
                curses.nocbreak()
                curses.echo()
                curses.endwin()
                _run_tui_pair_prompt()
                curses.def_prog_mode()
                curses.reset_prog_mode()
                stdscr.nodelay(True)
                stdscr.keypad(True)
                refresh_view()
                last_refresh = time.monotonic()
            time.sleep(0.05)

    try:
        curses.wrapper(draw)
    except (curses.error, OSError):
        return _run_plain_tui()
    print("Goodbye. No ring was contacted.")
    return ExitCode.OK


def _run_tui() -> int:
    """Run a refreshable simulator-first TUI with a plain-terminal fallback."""

    if sys.stdin.isatty() and sys.stdout.isatty() and not os.environ.get("JRING_TUI_PLAIN"):
        return _run_curses_tui()
    return _run_plain_tui()


def tui_main() -> int:
    """Console-script entry point for ``jring-tui``."""

    return int(_run_tui())


def _print_completion(shell: str) -> None:
    if shell != "bash":
        raise ValueError("unsupported completion shell")
    resource = importlib.resources.files("jring").joinpath(
        "resources", "completions", "jring.bash"
    )
    sys.stdout.write(resource.read_text(encoding="utf-8"))


def _print_input_actions(inventory: dict[str, list[dict[str, object]]]) -> None:
    print("Simulator profiles")
    for profile in inventory["simulator_profiles"]:
        print(f"- {profile['name']}: {profile['description']}")
    print("Available simulated events")
    for event in inventory["events"]:
        print(f"- {event['name']} (simulator only)")
    print("Keyboard actions")
    for action in inventory["actions"]:
        if action["kind"] == "key":
            print(f"- {action['name']}: {action['description']}")
    print("Mouse actions")
    for action in inventory["actions"]:
        if action["kind"] == "click":
            labels = ", ".join(action["labels"])
            print(f"- {labels}: {action['description']}")
    print("No hardware gesture or motion event is verified yet.")


def _source_semantics_recovery_is_complete(
    *, recovery_states: tuple[str, ...], completion_flags: tuple[bool, ...]
) -> bool:
    """Accept only explicit complete states; unknown future states fail closed."""

    return bool(recovery_states) and bool(completion_flags) and all(
        state == "complete" for state in recovery_states
    ) and all(completion_flags)


def _build_bluetooth_capability_parity(
    *,
    request_declared: int,
    request_implemented: int,
    request_accounted: int,
    request_ledger_rows: int,
    callback_declared: int,
    callback_implemented: int,
    callback_accounted: int,
    callback_ledger_rows: int,
    missing_rows: int,
    extra_rows: int,
    overloaded_declarations: int,
    unclassified_request_rows: int,
    unclassified_callback_rows: int,
    unledgered_interface_targets: int,
    source_semantics_recovery_complete: bool,
    request_callback_relationships_closed: bool,
    capability_denominator_established: bool,
    in_scope_vendor_operation_count: int | None,
    live_vendor_operations: int,
    hardware_verified_vendor_operations: int,
) -> dict[str, object]:
    """Build a strict aggregate verdict without inventing a capability denominator."""

    aidl_complete = (
        request_declared
        == request_implemented
        == request_accounted
        == request_ledger_rows
        and callback_declared
        == callback_implemented
        == callback_accounted
        == callback_ledger_rows
        and missing_rows == 0
        and extra_rows == 0
        and overloaded_declarations == 0
        and unclassified_request_rows == 0
        and unclassified_callback_rows == 0
        and unledgered_interface_targets == 0
    )
    source_semantics_complete = (
        source_semantics_recovery_complete
        and request_callback_relationships_closed
    )
    denominator_is_usable = (
        capability_denominator_established
        and in_scope_vendor_operation_count is not None
        and in_scope_vendor_operation_count > 0
    )
    all_in_scope_vendor_operations_live = (
        denominator_is_usable
        and live_vendor_operations == in_scope_vendor_operation_count
    )
    live_complete = (
        source_semantics_complete
        and denominator_is_usable
        and all_in_scope_vendor_operations_live
    )
    all_in_scope_vendor_operations_hardware_verified = (
        denominator_is_usable
        and hardware_verified_vendor_operations == in_scope_vendor_operation_count
    )
    hardware_complete = (
        live_complete and all_in_scope_vendor_operations_hardware_verified
    )
    dimensions = {
        "known_aidl_declaration_accounting": {
            "complete": aidl_complete,
            "status": "complete" if aidl_complete else "incomplete",
            "scope": "recovered_aidl_declarations",
            "request_declared": request_declared,
            "request_accounted": request_accounted,
            "callback_declared": callback_declared,
            "callback_accounted": callback_accounted,
            "missing_rows": missing_rows,
            "extra_rows": extra_rows,
        },
        "source_semantics": {
            "complete": source_semantics_complete,
            "status": "complete" if source_semantics_complete else "not_established",
            "request_callback_relationships_closed": (
                request_callback_relationships_closed
            ),
        },
        "live_vendor_availability": {
            "complete": live_complete,
            "status": (
                "complete"
                if live_complete
                else "unavailable" if live_vendor_operations == 0 else "not_established"
            ),
            "capability_denominator_established": capability_denominator_established,
            "in_scope_vendor_operation_count": in_scope_vendor_operation_count,
            "all_in_scope_vendor_operations_live": (
                all_in_scope_vendor_operations_live
            ),
            "live_vendor_operations": live_vendor_operations,
        },
        "hardware_verification": {
            "complete": hardware_complete,
            "status": (
                "complete"
                if hardware_complete
                else "not_verified"
                if hardware_verified_vendor_operations == 0
                else "not_established"
            ),
            "all_in_scope_vendor_operations_hardware_verified": (
                all_in_scope_vendor_operations_hardware_verified
            ),
            "hardware_verified_vendor_operations": (
                hardware_verified_vendor_operations
            ),
        },
    }
    blocking_dimensions = [
        name for name, dimension in dimensions.items()
        if not dimension["complete"]
    ]
    return {
        "complete": not blocking_dimensions,
        "verdict": "complete" if not blocking_dimensions else "not_established",
        "completion_rule": "all_dimensions_complete",
        "blocking_dimensions": blocking_dimensions,
        "dimensions": dimensions,
    }


def _protocol_coverage_payload() -> dict[str, object]:
    requests = static_vendor_operation_coverage()
    callbacks = static_vendor_callback_coverage()
    session = recovered_session_evidence()
    decompilation = recovered_decompilation_coverage()
    warning_audit = recovered_warning_audit()
    artifact = recovered_artifact_surface_evidence()
    callback_surfaces = recovered_callback_behavior_surfaces()
    dispatcher = recovered_dispatcher_evidence()
    request_builders = recovered_request_builder_evidence()
    request_correlations = recovered_request_callback_correlations()
    fake_singleton_eligibility = recovered_vendor_fake_singleton_eligibility()
    request_routing = recovered_request_routing_evidence()
    app_use = recovered_vendor_app_use_evidence()
    binder = recovered_vendor_binder_evidence()
    operation_registry = recovered_vendor_operation_registry()
    warning_scopes = {item.scope.value: item for item in warning_audit.scopes}
    live_vendor_operations = operation_registry.live_eligible_count
    hardware_verified_vendor_operations = operation_registry.hardware_verified_count
    interface = artifact.interface_parity
    source_semantics_recovery_complete = _source_semantics_recovery_is_complete(
        recovery_states=(
            decompilation.source_recovery_completeness.value,
            warning_audit.source_recovery_completeness,
            artifact.source_recovery_completeness,
        ),
        completion_flags=(
            decompilation.complete_semantic_source_review_completed,
            decompilation.complete_smali_review_completed,
            decompilation.complete_dex_instruction_review_completed,
            decompilation.complete_dex_coverage,
            decompilation.semantic_correctness_established,
            warning_audit.semantic_correctness_established,
            warning_audit.instruction_review_complete,
            warning_audit.exhaustive_bluetooth_dependency_audit,
            artifact.complete_artifact_coverage,
            artifact.reflection_or_dynamic_activation_exhaustively_disproved,
            artifact.semantic_correctness_established,
        ),
    )
    parity = _build_bluetooth_capability_parity(
        request_declared=interface.request_declaration_count,
        request_implemented=interface.request_implementation_count,
        request_accounted=interface.public_request_row_count,
        request_ledger_rows=len(requests),
        callback_declared=interface.callback_declaration_count,
        callback_implemented=interface.callback_implementation_count,
        callback_accounted=interface.public_callback_row_count,
        callback_ledger_rows=len(callbacks),
        missing_rows=interface.missing_public_row_count,
        extra_rows=interface.extra_public_row_count,
        overloaded_declarations=interface.overloaded_declaration_count,
        unclassified_request_rows=sum(
            entry.python_state is VendorPythonState.NOT_REPRODUCED
            for entry in requests
        ),
        unclassified_callback_rows=sum(
            entry.python_state is VendorPythonState.NOT_REPRODUCED
            for entry in callbacks
        ),
        unledgered_interface_targets=artifact.interface_links.unledgered_target_count,
        source_semantics_recovery_complete=source_semantics_recovery_complete,
        request_callback_relationships_closed=(
            len(request_correlations.rows) == len(REQUEST_CODEC_LOCATORS)
            and request_correlations.unspecified_count == 0
            and request_correlations.explicitly_unresolved_count == 0
            and request_correlations.rows_with_unresolved_reasons_count == 0
        ),
        capability_denominator_established=True,
        in_scope_vendor_operation_count=operation_registry.ring_facing_count,
        live_vendor_operations=live_vendor_operations,
        hardware_verified_vendor_operations=hardware_verified_vendor_operations,
    )
    return {
        "user_guidance": {
            "scope": "offline_evidence_and_simulator_only",
            "safe_now": [
                {
                    "command": "jring doctor",
                    "purpose": (
                        "check local prerequisites without selecting or contacting a ring"
                    ),
                },
                {
                    "command": "jring status --simulate",
                    "purpose": "preview the safe simulator workflow",
                },
                {
                    "command": "jring non-health-capabilities",
                    "purpose": "inspect static non-health candidates and their boundaries",
                },
            ],
            "unavailable": [
                "live vendor Bluetooth operations",
                "hardware-verified vendor behavior",
                "host input from ring events",
            ],
            "next_safe_action": "jring doctor",
        },
        "bluetooth_capability_parity": parity,
        "clean_room_bluetooth_parity_manifest": bluetooth_parity_manifest_payload(),
        "clean_room_analysis_gaps": clean_room_gap_payload(),
        "operation_registry": vendor_operation_registry_payload(),
        "summary": {
            "request_total": len(requests),
            "callback_total": len(callbacks),
            "offline_request_codecs": sum(
                entry.python_state in OFFLINE_REQUEST_CODEC_STATES for entry in requests
            ),
            "offline_control_models": sum(
                entry.python_state is VendorPythonState.OFFLINE_CONTROL_MODEL
                for entry in requests
            ),
            "offline_behavior_evidence": sum(
                entry.python_state is VendorPythonState.OFFLINE_BEHAVIOR_EVIDENCE
                for entry in requests
            ),
            "unclassified_requests": sum(
                entry.python_state is VendorPythonState.NOT_REPRODUCED
                for entry in requests
            ),
            "offline_response_codecs": sum(
                entry.python_state is VendorPythonState.OFFLINE_RESPONSE_CODEC
                for entry in callbacks
            ),
            "offline_local_projections": sum(
                entry.python_state is VendorPythonState.OFFLINE_LOCAL_PROJECTION
                for entry in callbacks
            ),
            "offline_callback_behavior_evidence": sum(
                entry.python_state is VendorPythonState.OFFLINE_BEHAVIOR_EVIDENCE
                for entry in callbacks
            ),
            "offline_callback_declaration_evidence": sum(
                entry.python_state is VendorPythonState.OFFLINE_DECLARATION_EVIDENCE
                for entry in callbacks
            ),
            "unclassified_callbacks": sum(
                entry.python_state is VendorPythonState.NOT_REPRODUCED
                for entry in callbacks
            ),
            "request_codec_locators": len(REQUEST_CODEC_LOCATORS),
            "callback_codec_locators": len(CALLBACK_CODEC_LOCATORS),
            "unresolved_codec_family_bindings": sum(
                locator.kind is CodecBindingKind.FAMILY_BINDING_UNRESOLVED
                for locator in (
                    *REQUEST_CODEC_LOCATORS.values(),
                    *CALLBACK_CODEC_LOCATORS.values(),
                )
            ),
            "request_main_layouts": request_routing.main_layout_count,
            "request_raw_layouts": request_routing.raw_layout_count,
            "request_no_fixed_packets": request_routing.no_fixed_packet_count,
            "request_builder_families": request_builders.byte_exact_family_count,
            "request_builder_main_queue": sum(
                row.endpoint_role == "main" for row in request_builders.families
            ),
            "request_builder_raw_queue": sum(
                row.endpoint_role == "raw" for row in request_builders.families
            ),
            "request_builder_front_inserted": sum(
                row.enqueue_position == "front" for row in request_builders.families
            ),
            "request_correlation_rows": len(request_correlations.rows),
            "request_correlation_unspecified": request_correlations.unspecified_count,
            "request_correlation_explicitly_unresolved": (
                request_correlations.explicitly_unresolved_count
            ),
            "request_correlation_rows_with_caveats": (
                request_correlations.rows_with_unresolved_reasons_count
            ),
            "request_correlation_terminal_rules": [
                {"rule": rule, "count": count}
                for rule, count in request_correlations.terminal_rule_counts
            ],
            "request_fake_singleton_matched_terminal": dict(
                fake_singleton_eligibility.state_counts
            )[FakeSingletonEligibilityState.SINGLETON_MATCHED_TERMINAL],
            "request_fake_singleton_typed_nonterminal_projection": dict(
                fake_singleton_eligibility.state_counts
            )[FakeSingletonEligibilityState.TYPED_NONTERMINAL_PROJECTION],
            "request_fake_singleton_ambiguous_or_batched_projection": dict(
                fake_singleton_eligibility.state_counts
            )[FakeSingletonEligibilityState.AMBIGUOUS_OR_BATCHED_PER_FRAME],
            "request_fake_singleton_no_proven_terminal": dict(
                fake_singleton_eligibility.state_counts
            )[FakeSingletonEligibilityState.NO_PROVEN_TERMINAL],
            "request_fake_singleton_local_or_marker_bounded_stream": dict(
                fake_singleton_eligibility.state_counts
            )[FakeSingletonEligibilityState.LOCAL_OR_MARKER_BOUNDED_STREAM],
            "request_fake_singleton_eligibility_scope": (
                fake_singleton_eligibility.eligibility_scope
            ),
            "request_fake_singleton_live_eligible": (
                fake_singleton_eligibility.live_eligible
            ),
            "request_fake_singleton_owner_authorized": (
                fake_singleton_eligibility.owner_authorized
            ),
            "request_fake_singleton_hardware_eligible": (
                fake_singleton_eligibility.hardware_eligible
            ),
            "request_fake_singleton_hardware_verified": (
                fake_singleton_eligibility.hardware_verified
            ),
            "app_direct_request_targets": app_use.direct_request_target_count,
            "app_direct_request_invokes": app_use.direct_request_invoke_count,
            "directly_invoked_callbacks": (
                app_use.directly_invoked_callback_count
            ),
            "direct_callback_invokes": app_use.direct_callback_invoke_count,
            "main_response_callback_targets": (
                app_use.main_response_callback_target_count
            ),
            "main_response_callback_invokes": (
                app_use.main_response_callback_invoke_count
            ),
            "raw_response_callback_targets": (
                app_use.raw_response_callback_target_count
            ),
            "raw_response_callback_invokes": (
                app_use.raw_response_callback_invoke_count
            ),
            "outside_dispatcher_callback_targets": (
                app_use.outside_dispatcher_callback_target_count
            ),
            "outside_dispatcher_callback_invokes": (
                app_use.outside_dispatcher_callback_invoke_count
            ),
            "binder_transactions": binder.total_transaction_count,
            "binder_synchronous_transactions": (
                binder.request.synchronous_transaction_count
                + binder.callback.synchronous_transaction_count
            ),
            "binder_parcel_order_mismatches": (
                binder.request.parcel_order_mismatch_count
                + binder.callback.parcel_order_mismatch_count
            ),
            "live_vendor_operations": live_vendor_operations,
            "hardware_eligible_vendor_operations": sum(
                entry.hardware_eligible for entry in requests
            ),
            "hardware_verified_vendor_operations": (
                hardware_verified_vendor_operations
            ),
            "supplemental_session_transitions": len(session.transitions),
            "supplemental_session_races": len(session.races),
            "supplemental_binding_reactions": len(session.binding_reactions),
            "decompiler_processed_classes": (
                decompilation.primary_pass.processed_class_count
            ),
            "decompiler_run_reported_failures": (
                decompilation.primary_pass.run_reported_failure_count
            ),
            "decompiler_failed_method_stubs": (
                decompilation.primary_pass.failed_method_stub_count
            ),
            "decompiler_hard_failure_files": (
                decompilation.primary_pass.hard_failure_file_count
            ),
            "decompiler_error_or_incorrect_markers": (
                decompilation.primary_pass.error_or_incorrect_marker_count
            ),
            "owned_warning_audit_files": (
                warning_scopes["application"].selected_file_count
                + warning_scopes["embedded_sdk"].selected_file_count
            ),
            "owned_warning_audit_occurrences": (
                warning_scopes["application"].warning_occurrence_count
                + warning_scopes["embedded_sdk"].warning_occurrence_count
            ),
            "same_tool_surface_corroborations": sum(
                item.comparison_state
                is ComparisonState.SAME_TOOL_SURFACE_CORROBORATION
                for item in warning_audit.comparisons
            ),
            "warning_comparison_divergences": sum(
                item.comparison_state is ComparisonState.COMPARISON_DIVERGENCE
                for item in warning_audit.comparisons
            ),
            "instruction_bounded_facts_confirmed": (
                warning_audit.bounded_fact_confirmed_count
            ),
            "instruction_bounded_facts_contradicted": (
                warning_audit.bounded_fact_contradicted_count
            ),
            "instruction_reviews_inconclusive": (
                warning_audit.inconclusive_review_count
            ),
            "instruction_reviews_not_performed": (
                warning_audit.instruction_review_not_performed_count
            ),
            "dispatcher_unique_callback_targets": (
                dispatcher.unique_callback_target_count
            ),
            "dispatcher_reachable_callback_invokes": (
                dispatcher.reachable_callback_invoke_count
            ),
            "dispatcher_syntactic_callback_invokes": (
                dispatcher.syntactic_callback_invoke_count
            ),
            "dispatcher_distinct_opcodes": (
                dispatcher.distinct_casefolded_opcode_count
            ),
            "artifact_missing_interface_rows": (
                artifact.interface_parity.missing_public_row_count
            ),
            "artifact_exclusive_classified_methods": (
                artifact.exclusive_classified_method_count
            ),
            "artifact_unhandled_dynamic_receiver_actions": (
                artifact.dynamic_receiver_surface.primary_unhandled_action_count
            ),
            "artifact_unresolved_native_declarations": (
                artifact.native_surface.unresolved_native_declaration_count
            ),
            "artifact_rooted_jni_entries_reviewed": (
                artifact.native_surface.rooted_jni_entry_count
            ),
            "artifact_owned_reflective_invokes": (
                artifact.dynamic_activation_surface.owned_reflective_invoke_count
            ),
            "artifact_standalone_dial_external_references": (
                artifact.dynamic_activation_surface
                .standalone_dial_external_descriptor_reference_count
            ),
            "artifact_relevant_binder_outbound_invokes": (
                artifact.dynamic_activation_surface
                .app_relevant_binder_outbound_invoke_count
            ),
            "request_routes": dict(sorted(Counter(
                entry.route for entry in requests
            ).items())),
            "callback_sources": dict(sorted(Counter(
                entry.source for entry in callbacks
            ).items())),
        },
        "requests": [asdict(entry) for entry in requests],
        "callbacks": [asdict(entry) for entry in callbacks],
        "supplemental": {
            "binder_evidence": {
                **asdict(binder),
                "total_transaction_count": binder.total_transaction_count,
                "maturity": binder.maturity,
                "evidence_scope": binder.evidence_scope,
                "runnable": binder.runnable,
                "hardware_eligible": binder.hardware_eligible,
                "hardware_verified": binder.hardware_verified,
            },
            "app_use_evidence": {
                **asdict(app_use),
                "direct_request_target_count": app_use.direct_request_target_count,
                "direct_request_invoke_count": app_use.direct_request_invoke_count,
                "directly_invoked_callback_count": (
                    app_use.directly_invoked_callback_count
                ),
                "direct_callback_invoke_count": (
                    app_use.direct_callback_invoke_count
                ),
                "main_response_callback_target_count": (
                    app_use.main_response_callback_target_count
                ),
                "main_response_callback_invoke_count": (
                    app_use.main_response_callback_invoke_count
                ),
                "raw_response_callback_target_count": (
                    app_use.raw_response_callback_target_count
                ),
                "raw_response_callback_invoke_count": (
                    app_use.raw_response_callback_invoke_count
                ),
                "outside_dispatcher_callback_target_count": (
                    app_use.outside_dispatcher_callback_target_count
                ),
                "outside_dispatcher_callback_invoke_count": (
                    app_use.outside_dispatcher_callback_invoke_count
                ),
                "maturity": app_use.maturity,
                "evidence_scope": app_use.evidence_scope,
                "runnable": app_use.runnable,
                "hardware_eligible": app_use.hardware_eligible,
                "hardware_verified": app_use.hardware_verified,
            },
            "request_routing": {
                **asdict(request_routing),
                "standalone_deterministic_offline_count": (
                    request_routing.standalone_deterministic_offline_count
                ),
                "statically_identifiable_layout_count": (
                    request_routing.statically_identifiable_layout_count
                ),
                "main_layout_count": request_routing.main_layout_count,
                "raw_layout_count": request_routing.raw_layout_count,
                "stateful_shared_layout_count": (
                    request_routing.stateful_shared_layout_count
                ),
                "dynamic_payload_count": request_routing.dynamic_payload_count,
                "descriptor_control_count": request_routing.descriptor_control_count,
                "internal_dfu_count": request_routing.internal_dfu_count,
                "no_fixed_packet_count": request_routing.no_fixed_packet_count,
                "maturity": request_routing.maturity,
                "evidence_scope": request_routing.evidence_scope,
                "runnable": request_routing.runnable,
                "python_callable": request_routing.python_callable,
                "hardware_eligible": request_routing.hardware_eligible,
                "hardware_verified": request_routing.hardware_verified,
                "owner_authorized": request_routing.owner_authorized,
            },
            "request_builder_evidence": {
                "families": [
                    {
                        **{
                            key: value
                            for key, value in asdict(row).items()
                            if key != "frame_length"
                        },
                        "fixed_length": row.frame_length,
                    }
                    for row in request_builders.families
                ],
                "main_queue_facts": request_builders.main_queue_facts,
                "raw_queue_facts": request_builders.raw_queue_facts,
                "omitted_runtime_behavior": request_builders.omitted_runtime_behavior,
                "byte_exact_family_count": request_builders.byte_exact_family_count,
                "maturity": request_builders.maturity,
                "runnable": request_builders.runnable,
                "python_callable": request_builders.python_callable,
                "hardware_eligible": request_builders.hardware_eligible,
                "hardware_verified": request_builders.hardware_verified,
            },
            "request_callback_correlations": {
                **asdict(request_correlations),
                "unspecified_count": request_correlations.unspecified_count,
                "explicitly_unresolved_count": (
                    request_correlations.explicitly_unresolved_count
                ),
                "rows_with_unresolved_reasons_count": (
                    request_correlations.rows_with_unresolved_reasons_count
                ),
                "terminal_rule_counts": [
                    {"rule": rule, "count": count}
                    for rule, count in request_correlations.terminal_rule_counts
                ],
                "maturity": request_correlations.maturity,
                "runnable": request_correlations.runnable,
                "python_callable": request_correlations.python_callable,
                "hardware_eligible": request_correlations.hardware_eligible,
                "hardware_verified": request_correlations.hardware_verified,
                "owner_authorized": request_correlations.owner_authorized,
            },
            "codec_registry": {
                "requests": [
                    {
                        "name": name,
                        **asdict(locator),
                        "maturity": locator.maturity,
                        "runnable": locator.runnable,
                        "hardware_eligible": locator.hardware_eligible,
                    }
                    for name, locator in REQUEST_CODEC_LOCATORS.items()
                ],
                "callbacks": [
                    {
                        "name": name,
                        **asdict(locator),
                        "maturity": locator.maturity,
                        "runnable": locator.runnable,
                        "hardware_eligible": locator.hardware_eligible,
                    }
                    for name, locator in CALLBACK_CODEC_LOCATORS.items()
                ],
            },
            "dispatcher_evidence": {
                **asdict(dispatcher),
                "maturity": dispatcher.maturity,
                "runnable": dispatcher.runnable,
                "python_callable": dispatcher.python_callable,
                "hardware_eligible": dispatcher.hardware_eligible,
                "hardware_verified": dispatcher.hardware_verified,
            },
            "callback_behavior_surfaces": [
                {
                    **asdict(item),
                    "maturity": item.maturity,
                    "runnable": item.runnable,
                    "python_callable": item.python_callable,
                    "hardware_eligible": item.hardware_eligible,
                    "hardware_verified": item.hardware_verified,
                }
                for item in callback_surfaces
            ],
            "session_sequence": {
                "interface_entries": False,
                "maturity": session.maturity,
                "evidence_scope": session.evidence_scope,
                "runnable": session.runnable,
                "hardware_eligible": session.hardware_eligible,
                "hardware_verified": session.hardware_verified,
                "owner_authorized": session.owner_authorized,
                "transitions": [asdict(item) for item in session.transitions],
                "races": [asdict(item) for item in session.races],
                "binding_reactions": [
                    asdict(item) for item in session.binding_reactions
                ],
            },
            "decompilation_coverage": {
                "interface_entries": decompilation.interface_entries,
                "maturity": decompilation.maturity,
                "evidence_scope": decompilation.evidence_scope,
                "artifact_ref": decompilation.artifact_ref,
                "tool_family": decompilation.tool_family,
                "tool_version": decompilation.tool_version,
                "structured_configuration_ref": (
                    decompilation.structured_configuration_ref
                ),
                "fallback_configuration_ref": (
                    decompilation.fallback_configuration_ref
                ),
                "namespace_classifier_version": (
                    decompilation.namespace_classifier_version
                ),
                "marker_rule_version": decompilation.marker_rule_version,
                "primary_pass": asdict(decompilation.primary_pass),
                "fallback_pass": asdict(decompilation.fallback_pass),
                "scopes": [asdict(item) for item in decompilation.scopes],
                "count_reconciliation": decompilation.count_reconciliation,
                "run_to_marker_mapping_established": (
                    decompilation.run_to_marker_mapping_established
                ),
                "source_recovery_completeness": (
                    decompilation.source_recovery_completeness
                ),
                "semantic_correctness_established": (
                    decompilation.semantic_correctness_established
                ),
                "complete_semantic_source_review_completed": (
                    decompilation.complete_semantic_source_review_completed
                ),
                "complete_smali_review_completed": (
                    decompilation.complete_smali_review_completed
                ),
                "complete_dex_instruction_review_completed": (
                    decompilation.complete_dex_instruction_review_completed
                ),
                "complete_dex_coverage": decompilation.complete_dex_coverage,
                "no_recognized_owned_scope_hard_failure_files": (
                    decompilation.no_recognized_owned_scope_hard_failure_files
                ),
                "static_review_authorized": (
                    decompilation.static_review_authorized
                ),
                "hardware_authority": decompilation.hardware_authority,
                "runnable": decompilation.runnable,
                "python_callable": decompilation.python_callable,
                "hardware_eligible": decompilation.hardware_eligible,
                "hardware_verified": decompilation.hardware_verified,
                "limitations": decompilation.limitations,
            },
            "warning_audit": {
                "interface_entries": warning_audit.interface_entries,
                "maturity": warning_audit.maturity,
                "evidence_scope": warning_audit.evidence_scope,
                "source_recovery_completeness": (
                    warning_audit.source_recovery_completeness
                ),
                "semantic_correctness_established": (
                    warning_audit.semantic_correctness_established
                ),
                "instruction_review_complete": (
                    warning_audit.instruction_review_complete
                ),
                "target_review_count": warning_audit.target_review_count,
                "bounded_fact_confirmed_count": (
                    warning_audit.bounded_fact_confirmed_count
                ),
                "bounded_fact_contradicted_count": (
                    warning_audit.bounded_fact_contradicted_count
                ),
                "inconclusive_review_count": (
                    warning_audit.inconclusive_review_count
                ),
                "instruction_review_not_performed_count": (
                    warning_audit.instruction_review_not_performed_count
                ),
                "all_target_reviews_attempted": (
                    warning_audit.all_target_reviews_attempted
                ),
                "all_bounded_facts_resolved": (
                    warning_audit.all_bounded_facts_resolved
                ),
                "exhaustive_bluetooth_dependency_audit": (
                    warning_audit.exhaustive_bluetooth_dependency_audit
                ),
                "runnable": warning_audit.runnable,
                "python_callable": warning_audit.python_callable,
                "hardware_eligible": warning_audit.hardware_eligible,
                "hardware_verified": warning_audit.hardware_verified,
                "scopes": [asdict(item) for item in warning_audit.scopes],
                "comparisons": [
                    asdict(item) for item in warning_audit.comparisons
                ],
            },
            "artifact_surface": {
                **asdict(artifact),
                "packaged_dex_scope": {
                    **asdict(artifact.packaged_dex_scope),
                    "classified_unit_count": (
                        artifact.packaged_dex_scope.classified_unit_count
                    ),
                    "inventory_scope_classification_complete": (
                        artifact.packaged_dex_scope.inventory_scope_classification_complete
                    ),
                    "runnable": artifact.packaged_dex_scope.runnable,
                    "python_callable": artifact.packaged_dex_scope.python_callable,
                    "hardware_eligible": artifact.packaged_dex_scope.hardware_eligible,
                    "hardware_verified": artifact.packaged_dex_scope.hardware_verified,
                    "owner_authorized": artifact.packaged_dex_scope.owner_authorized,
                },
                "interface_entries": artifact.interface_entries,
                "source_recovery_completeness": (
                    artifact.source_recovery_completeness
                ),
                "complete_artifact_coverage": artifact.complete_artifact_coverage,
                "reflection_or_dynamic_activation_exhaustively_disproved": (
                    artifact.reflection_or_dynamic_activation_exhaustively_disproved
                ),
                "semantic_correctness_established": (
                    artifact.semantic_correctness_established
                ),
                "evidence_scope": artifact.evidence_scope,
                "maturity": artifact.maturity,
                "runnable": artifact.runnable,
                "python_callable": artifact.python_callable,
                "hardware_eligible": artifact.hardware_eligible,
                "hardware_verified": artifact.hardware_verified,
            },
        },
    }


def _print_protocol_coverage(payload: dict[str, object]) -> None:
    summary = payload["summary"]
    guidance = payload["user_guidance"]
    parity = payload["bluetooth_capability_parity"]
    parity_dimensions = parity["dimensions"]
    aidl = parity_dimensions["known_aidl_declaration_accounting"]
    live = parity_dimensions["live_vendor_availability"]
    hardware = parity_dimensions["hardware_verification"]
    registry = payload["operation_registry"]
    decompilation = payload["supplemental"]["decompilation_coverage"]
    scopes = {item["scope"]: item for item in decompilation["scopes"]}
    print("OFFLINE PROTOCOL COVERAGE — no ring contacted")
    parity_label = "YES — complete" if parity["complete"] else "NO — not established"
    print(f"Complete APK-to-Python Bluetooth capability parity: {parity_label}.")
    aidl_label = "COMPLETE" if aidl["complete"] else "INCOMPLETE"
    print(
        f"Known AIDL declaration accounting: {aidl_label} within recovered scope "
        f"({aidl['request_declared']} requests, {aidl['callback_declared']} callbacks; "
        f"{aidl['missing_rows']} missing, {aidl['extra_rows']} extra)."
    )
    source = parity_dimensions["source_semantics"]
    source_label = "COMPLETE" if source["complete"] else "NOT ESTABLISHED"
    print(f"Source semantics: {source_label}.")
    live_label = "COMPLETE" if live["complete"] else "NOT COMPLETE"
    print(
        f"Live vendor availability: {live_label} — "
        f"{live['live_vendor_operations']} live vendor operations."
    )
    hardware_label = "COMPLETE" if hardware["complete"] else "NOT COMPLETE"
    print(
        f"Hardware verification: {hardware_label} — "
        f"{hardware['hardware_verified_vendor_operations']} hardware-verified vendor "
        "operations."
    )
    statuses = registry["terminal_status_counts"]
    print(
        "Operation registry: "
        f"{registry['ring_facing_count']} ring-facing; "
        f"{statuses.get('offline_only', 0)} offline-only, "
        f"{statuses.get('unsafe', 0)} unsafe, and "
        f"{statuses.get('excluded_non_ring', 0)} excluded non-ring rows."
    )
    print("What you can do now: local evidence inspection and simulator preview only.")
    for action in guidance["safe_now"]:
        print(f"- {action['command']}: {action['purpose']}.")
    print("Not available: " + "; ".join(guidance["unavailable"]) + ".")
    print(f"Next safe action: {guidance['next_safe_action']}")
    print("Static row accounting does not satisfy semantic, live, or hardware gates.")
    print("Static source recovery completeness: not established.")
    print(
        "Decompiler run: "
        f"{summary['decompiler_processed_classes']:,} classes processed; "
        f"{summary['decompiler_run_reported_failures']} run-reported failures."
    )
    print(
        "Structured output: "
        f"{summary['decompiler_failed_method_stubs']} failed-method stubs across "
        f"{summary['decompiler_hard_failure_files']} files."
    )
    print(
        "Emitted error or incorrect-code markers: "
        f"{summary['decompiler_error_or_incorrect_markers']}."
    )
    print(
        "JRing application scope: 0 hard-failure files among "
        f"{scopes['jring_application']['structured_files_scanned']} outputs scanned."
    )
    print(
        "Embedded BLE SDK scope: 0 hard-failure files among "
        f"{scopes['embedded_ble_sdk']['structured_files_scanned']} outputs scanned."
    )
    print(
        "Warning-bearing files remain: "
        f"{scopes['jring_application']['structured_warning_files']} application; "
        f"{scopes['embedded_ble_sdk']['structured_warning_files']} embedded SDK."
    )
    print("Fallback-mode decompiler pass: completed; run failure count unavailable.")
    print("Run failures, failed-method stubs, and markers are different measurements.")
    print("Complete semantic source review: not performed.")
    print("Complete smali/instruction review: not performed.")
    print("Complete DEX coverage: not claimed.")
    warning_audit = payload["supplemental"]["warning_audit"]
    warning_scopes = {item["scope"]: item for item in warning_audit["scopes"]}
    print("Owned-scope warning audit: semantic correctness not established.")
    print(
        "Bluetooth-related warning-bearing files: "
        f"{warning_scopes['application']['selected_file_count']} application; "
        f"{warning_scopes['embedded_sdk']['selected_file_count']} embedded SDK; "
        f"{warning_scopes['excluded_dependency']['selected_file_count']} dependency "
        "files excluded."
    )
    print(
        "Owned warning occurrences: "
        f"{warning_scopes['application']['warning_occurrence_count']} application; "
        f"{warning_scopes['embedded_sdk']['warning_occurrence_count']} embedded SDK."
    )
    print(
        "Same-tool surface corroborations: "
        f"{summary['same_tool_surface_corroborations']}; "
        f"comparison divergences: {summary['warning_comparison_divergences']}."
    )
    print(
        "Instruction-reviewed facts contradicted: "
        f"{summary['instruction_bounded_facts_contradicted']}."
    )
    print(
        "Instruction reviews inconclusive: "
        f"{summary['instruction_reviews_inconclusive']}."
    )
    print(
        "Bounded instruction facts confirmed: "
        f"{summary['instruction_bounded_facts_confirmed']}."
    )
    print(
        "Target instruction reviews not performed: "
        f"{summary['instruction_reviews_not_performed']}."
    )
    print(
        "Dispatcher structure: "
        f"{summary['dispatcher_unique_callback_targets']} targets; "
        f"{summary['dispatcher_syntactic_callback_invokes']} "
        "syntactic invokes "
        f"({summary['dispatcher_reachable_callback_invokes']} reachable); "
        f"{summary['dispatcher_distinct_opcodes']} distinct opcodes."
    )
    print("This audit is not exhaustive for dependency or transitive Bluetooth behavior.")
    artifact = payload["supplemental"]["artifact_surface"]
    print("Artifact-surface completeness: not established.")
    dex_scope = artifact["packaged_dex_scope"]
    print(
        "Packaged DEX scope inventory: "
        f"{dex_scope['classified_unit_count']}/"
        f"{dex_scope['inventory_unit_count']} units classified; "
        f"{dex_scope['owned_application_or_sdk_scope_unit_count']} owned scope; "
        f"{dex_scope['no_owned_application_or_sdk_scope_unit_count']} no owned scope; "
        "complete instruction review not established."
    )
    print(
        "Dynamic receiver gaps: "
        f"{artifact['dynamic_receiver_surface']['primary_unhandled_action_count']} "
        "registered actions without cases; process/system registration mismatch remains."
    )
    print(
        "Native declarations unresolved: "
        f"{artifact['native_surface']['unresolved_native_declaration_count']}; "
        "native Bluetooth absence not established."
    )
    print(
        "Native JNI roots: "
        f"{artifact['native_surface']['rooted_jni_entry_count']} "
        "image/wallpaper entries reviewed; no rooted Bluetooth transport edge."
    )
    print(
        "Owned reflection: "
        f"{artifact['dynamic_activation_surface']['owned_reflective_invoke_count']} "
        "calls resolved to constant Android helper targets; no dial-transfer flow."
    )
    print(
        "Standalone dial static activation: no edge in reviewed Binder/resource "
        "paths; runtime activation remains inconclusive."
    )
    print(
        "Dial-transfer dynamic activation: "
        f"{artifact['dynamic_activation_surface']['review_state'].value}."
    )
    print(
        "Known AIDL declaration accounting (not capability parity): "
        f"{artifact['interface_parity']['request_declaration_count']} requests; "
        f"{artifact['interface_parity']['callback_declaration_count']} callbacks; "
        f"{artifact['interface_parity']['missing_public_row_count']} missing rows."
    )
    print(
        "Exclusive owned method classification: "
        f"{artifact['exclusive_classified_method_count']} methods across "
        f"{artifact['exclusive_classified_class_count']} classes."
    )
    instruction_scopes = artifact["android_instruction_aggregates"]
    print(
        "Owned-scope direct Android Bluetooth API references: "
        f"{sum(item['reference_method_count'] for item in instruction_scopes)} "
        "methods across "
        f"{sum(item['reference_class_count'] for item in instruction_scopes)} "
        "classes; "
        f"{sum(item['unclassified_reference_method_count'] for item in instruction_scopes)} "
        "unclassified."
    )
    print(
        "Overlapping API-reference categories (do not sum): GATT lifecycle/I/O; "
        "descriptor/notification setup; MTU/priority/RSSI; scanning/discovery; "
        "bonding/classic/RFCOMM; adapter power."
    )
    print(
        "Absent direct-reference categories: descriptor read, PHY, LE advertising, "
        "L2CAP, GATT server, HID device; absence is not non-support."
    )
    print(
        "Owned scopes only; semantic, dependency/transitive, runtime, and hardware "
        "status remain unestablished."
    )
    print("Artifact-surface evidence is static, sanitized, and non-runnable.")
    print(f"Requests: {summary['request_total']}")
    print(f"Callbacks: {summary['callback_total']}")
    print(f"Offline request codecs: {summary['offline_request_codecs']}")
    print(f"Offline control models: {summary['offline_control_models']}")
    print(f"Offline behavior evidence: {summary['offline_behavior_evidence']}")
    print(f"Unclassified requests: {summary['unclassified_requests']}")
    print(f"Offline response codecs: {summary['offline_response_codecs']}")
    print(f"Offline local projections: {summary['offline_local_projections']}")
    print(
        "Offline callback behavior evidence: "
        f"{summary['offline_callback_behavior_evidence']}"
    )
    print(
        "Offline callback declaration evidence: "
        f"{summary['offline_callback_declaration_evidence']}"
    )
    print(f"Unclassified callbacks: {summary['unclassified_callbacks']}")
    print(
        "Codec traceability: "
        f"{summary['request_codec_locators']}/85 request rows; "
        f"{summary['callback_codec_locators']}/86 callback rows; "
        f"{summary['unresolved_codec_family_bindings']} family bindings unresolved."
    )
    print(
        "Request packet routes: "
        f"{summary['request_main_layouts']} main; "
        f"{summary['request_raw_layouts']} raw; 1 stateful shared; 1 dynamic; "
        "1 descriptor; 1 DFU; "
        f"{summary['request_no_fixed_packets']} without a fixed packet."
    )
    print(
        "Reviewed builder parity: "
        f"{summary['request_builder_families']} byte-exact families on accepted "
        f"Python domains; {summary['request_builder_main_queue']} main queue; "
        f"{summary['request_builder_raw_queue']} raw queue; "
        f"{summary['request_builder_front_inserted']} front-inserted."
    )
    print(
        "Request/callback correlation: "
        f"{summary['request_correlation_rows']}/85 deterministic request rows; "
        f"{summary['request_correlation_unspecified']} unspecified; "
        f"{summary['request_correlation_explicitly_unresolved']} remain in the "
        "generic topology bucket; "
        f"{summary['request_correlation_rows_with_caveats']} carry explicit caveats."
    )
    if summary["request_correlation_explicitly_unresolved"] == 0:
        print(
            "Zero generic rows means every request has a more specific static "
            "classification only; "
            f"{summary['request_correlation_rows_with_caveats']} rows still have "
            "explicit caveats, and no live or hardware support follows."
        )
    terminal_rules = {
        item["rule"]: item["count"]
        for item in summary["request_correlation_terminal_rules"]
    }
    print(
        "Terminal rules: "
        f"{terminal_rules['single_matched_response']} single matched response; "
        f"{terminal_rules['none_proven']} none proven; "
        f"{terminal_rules['per_frame_only']} per-frame only; "
        f"{terminal_rules['local_quiet_unknown']} local quiet unknown; "
        f"{terminal_rules['metadata_or_explicit_marker_else_local_quiet_unknown']} "
        "metadata/marker or local quiet unknown."
    )
    print(
        "Fake singleton classification (static only): "
        f"{summary['request_fake_singleton_matched_terminal']} statically "
        "matched-terminal rows may enter the fake engine; "
        f"{summary['request_fake_singleton_typed_nonterminal_projection']} typed "
        "projections, "
        f"{summary['request_fake_singleton_ambiguous_or_batched_projection']} "
        "ambiguous or batched per-frame rows, "
        f"{summary['request_fake_singleton_no_proven_terminal']} no-proven-terminal "
        "rows, and "
        f"{summary['request_fake_singleton_local_or_marker_bounded_stream']} local or "
        "marker-bounded streams are rejected from fake singleton success. This grants "
        "no live eligibility, owner authorization, or hardware eligibility."
    )
    print(
        "Owned app interface use: "
        f"{summary['app_direct_request_targets']}/112 request targets across "
        f"{summary['app_direct_request_invokes']} direct invokes; "
        f"{summary['directly_invoked_callbacks']}/105 callbacks have a direct "
        f"invoke ({summary['direct_callback_invokes']} sites: "
        f"{summary['main_response_callback_invokes']} main, "
        f"{summary['raw_response_callback_invokes']} raw, "
        f"{summary['outside_dispatcher_callback_invokes']} outside dispatchers)."
    )
    print(
        "Binder parity: "
        f"{summary['binder_transactions']} transactions; "
        f"{summary['binder_synchronous_transactions']} synchronous; "
        f"{summary['binder_parcel_order_mismatches']} Parcel-order mismatches."
    )
    print(
        "Supplemental session transitions (not interface entries): "
        f"{summary['supplemental_session_transitions']}"
    )
    print(f"Adversarial session races: {summary['supplemental_session_races']}")
    print(
        "Source-labeled binding reactions: "
        f"{summary['supplemental_binding_reactions']}"
    )
    print(f"Live vendor operations: {summary['live_vendor_operations']}")
    print(
        "Hardware-eligible vendor operations: "
        f"{summary['hardware_eligible_vendor_operations']}"
    )
    print(
        "Hardware-verified vendor operations: "
        f"{summary['hardware_verified_vendor_operations']}"
    )
    print("Static coverage never authorizes Bluetooth writes or subscriptions.")
    print("Supplemental session evidence is static and non-runnable.")
    print(
        "These are static-analysis measurements; they do not show that a feature "
        "works on your ring."
    )
    print("Hardware status remains: 0 hardware-verified vendor operations.")


def _non_health_payload() -> dict[str, object]:
    return {
        "live_ring_input": "unavailable",
        "capabilities": [asdict(item) for item in static_non_health_capabilities()],
    }


def _print_non_health_capabilities(payload: dict[str, object]) -> None:
    print("LIVE RING INPUT UNAVAILABLE — no ring contacted")
    print(
        "JRing is not a live HID driver. Linux uinput is simulator-only today and "
        "a future translation sink for verified events."
    )
    print(
        "JRing can inspect standard metadata and static candidates offline; "
        "none is enabled as live input."
    )
    print(
        "Developer-test scripted fake decoder coverage exists for device actions, "
        "cumulative steps, Classic information and redacted-name metadata, and "
        "host-volume requests. It also covers a passive exact 78/09 touch-mode "
        "setting projection with zero fake writes; this is not a tap, gesture, sensor "
        "event, or input action. Scripted fake only; zero writes. Exact opcode 78 "
        "selectors 00 or 01 project nine private, neutral signed channel values; "
        "values are redacted. This does not show live motion, sensor activation, a "
        "gesture, tap, step, button, or input action. Exact opcode 4E projects one "
        "private chat action-code candidate on the scripted fake with zero writes. "
        "No request is owned by this fake run; its protocol relationship to nearby "
        "requests is unknown. This does not execute ChatGPT or parse or retain prompt, "
        "response, text, audio, image, or other content; it does not acknowledge a "
        "request, establish a terminal, or create input. Exact 54/04 projects one "
        "private Wi-Fi callback state code on the scripted fake with zero writes. "
        "Private address material is discarded; there is no credential processing, "
        "host or ring networking, or radio change. Its meaning and request relationship "
        "are unknown; it does not report whether Wi-Fi is enabled, connected, joined, "
        "current, or internet-reachable. It is not an acknowledgement, terminal, live "
        "hardware, or input. Wi-Fi "
        "network-name response "
        "assembly is covered "
        "separately; "
        "there is no user command, no host or ring Wi-Fi scan, and no live ring is "
        "contacted."
    )
    print(
        "A separate device-system scripted fake transaction performs one synthetic "
        "54/11 query write and accepts one exact 54/12 fake response. Fake success "
        "means only that this response matched; it is not current device state, "
        "Bluetooth readiness or connection, battery or power, firmware health, owner "
        "binding, a live ring, hardware verification, or input."
    )
    print(
        "Global state for every row: runnable no; hardware eligible no; hardware "
        "verified no; live available no; input eligible no."
    )
    print(
        "Media, volume, and shutter actions cannot yet be previewed or mapped; the "
        "input simulator generates only a separate synthetic step event."
    )

    def print_item(item: dict[str, object]) -> None:
        candidate = "yes" if item["input_candidate"] else "no"
        scripted_fake = (
            "yes" if item["scripted_fake_decoder_available"] else "no"
        )
        scripted_transaction = (
            "yes" if item["scripted_fake_transaction_available"] else "no"
        )
        fake_write = (
            "yes" if item["scripted_fake_transaction_performs_write"] else "no"
        )
        print(f"- {item['label']}: {item['description']}")
        print(
            f"  evidence/maturity: {item['evidence']}/{item['maturity']}; "
            f"future input candidate: {candidate}; "
            f"scripted fake decoder: {scripted_fake}; "
            f"scripted fake transaction: {scripted_transaction}; "
            f"fake transaction performs write: {fake_write}; "
            f"fake transaction scope: {item['scripted_fake_transaction_scope']}; "
            f"privacy: {', '.join(item['privacy_classes'])}"
        )

    headings = (
        ("sensor_candidates", "Sensor-derived candidates"),
        ("standard_metadata", "Standards metadata"),
        ("classic_bluetooth", "Classic Bluetooth evidence"),
        ("host_integration", "Host integration"),
        ("general_use", "General-use static codecs"),
        ("raw_channel", "Raw non-health framing"),
    )
    device_actions = [
        item for item in payload["capabilities"] if item["group"] == "device_actions"
    ]
    print("Static device actions")
    print("Possible future input candidates")
    for item in device_actions:
        if item["input_candidate"]:
            print_item(item)
    print("Blocked side-effect actions")
    for item in device_actions:
        if not item["input_candidate"]:
            print_item(item)
    for group, heading in headings:
        print(heading)
        for item in payload["capabilities"]:
            if item["group"] != group:
                continue
            print_item(item)
    print(
        "This inventory never authorizes live Bluetooth writes, subscriptions, or input."
    )
    print("Next safe actions")
    print("- jring input-actions — list the local input vocabulary")
    print(
        "- jring input --simulate --map step=key:space — preview one separate, "
        "synthetic step event"
    )
    print("- jring doctor — check hardware prerequisites without scanning")
    print("Live vendor-event collection is not implemented.")


def _capability_payload(
    inventory: object, *, include_observation_targets: bool = False
) -> dict[str, object]:
    characteristics = [asdict(item) for item in inventory.characteristics]
    payload = {
        "inventory_state": inventory.inventory_state,
        "metadata_state": inventory.metadata_state,
        "standard_heart_rate": asdict(inventory.standard_heart_rate),
        "standard_hid": {
            "service_state": inventory.hid_service_state,
            "characteristics": characteristics,
            "report_instances": [
                asdict(item) for item in inventory.hid_report_instances
            ],
            "report_reference_descriptor": {
                "state": inventory.report_reference_state,
            },
            "report_map_contents": "not_read",
            "usability_state": inventory.usability_state,
            "os_attachment_state": inventory.os_attachment_state,
        },
        "neutral_events": {
            "state": inventory.neutral_event_state,
            "events": list(inventory.neutral_events),
        },
        "vendor_gatt": [asdict(item) for item in inventory.vendor_gatt],
        "vendor_routes": [asdict(item) for item in inventory.vendor_routes],
    }
    if include_observation_targets:
        payload["observation_targets"] = [
            asdict(item) for item in inventory.observation_targets
        ]
    return payload


def _capability_issue_draft_url(payload: dict[str, object]) -> str:
    """Return a reviewable public handoff containing only coarse metadata states."""

    body = "\n".join((
        "## Unverified metadata-only compatibility probe",
        "",
        "This draft contains no device identifier, characteristic value, packet, path, or health data.",
        "",
        f"inventory_state: {payload['inventory_state']}",
        f"metadata_state: {payload['metadata_state']}",
        f"vendor_route_count: {len(payload['vendor_routes'])}",
        "",
        "The result is unverified comparative evidence only; it does not establish compatibility or authorize runtime behavior.",
    ))
    return "https://github.com/Pipeliner/jring-client/issues/new?" + urlencode(
        {
            "title": "Unverified metadata-only compatibility probe",
            "body": body,
        },
        quote_via=quote,
    )


def _observation_issue_draft_url(payload: dict[str, object]) -> str:
    """Render a local review URL from an already value-free observation summary."""

    status = payload.get("capture_status")
    count = payload.get("record_count")
    if (
        status not in {item.value for item in ObservationStatus}
        or isinstance(count, bool)
        or not isinstance(count, int)
        or not 0 <= count <= 128
        or payload.get("decoder") != "none"
        or payload.get("runtime_authorized") is not False
    ):
        raise ValueError("invalid sanitized observation summary")
    body = "\n".join((
        "Owner-local bounded notification observation (unverified)",
        "",
        f"capture_status: {status}",
        f"record_count: {count}",
        "decoder: none",
        "runtime_authorized: false",
        "",
        "No raw frames, identifiers, target metadata, private paths, or compatibility claim are included.",
    ))
    return "https://github.com/Pipeliner/jring-client/issues/new?" + urlencode({
        "title": "Unverified private notification observation",
        "body": body,
    })


def _print_owner_evidence_summary(
    payload: dict[str, object], *, interrupted: bool = False
) -> None:
    cleanup = payload["cleanup"]
    assert isinstance(cleanup, dict)
    print(f"Attempt: {str(payload['attempt_status']).replace('_', ' ')}")
    print(f"Write dispatch: {str(payload['write_dispatch']).replace('_', ' ')}")
    print(f"Response terminal: {str(payload['response_terminal']).replace('_', ' ')}")
    print(
        "Cleanup: "
        f"unsubscribe {str(cleanup['unsubscribe']).replace('_', ' ')}; "
        f"close {str(cleanup['close']).replace('_', ' ')}; "
        f"overall {str(payload['cleanup_status']).replace('_', ' ')}"
    )
    print(
        "Attempt evidence commit: "
        f"{str(payload['evidence_commit_status']).replace('_', ' ')}"
    )
    if payload["evidence_commit_status"] == "committed":
        prefix = "interrupted; " if interrupted else ""
        print(
            f"Recovery: {prefix}review the requested private record offline; "
            "never retry automatically"
        )
    else:
        prefix = "interrupted; " if interrupted else ""
        print(
            f"Recovery: {prefix}no reviewable record exists; "
            "do not retry automatically"
        )


def _simulator_profiles_payload() -> list[dict[str, object]]:
    return [asdict(profile) for profile in SIMULATOR_PROFILES]


def _print_capability_inventory(payload: dict[str, object], source: str) -> None:
    print("SIMULATION — no ring contacted" if source == "simulator" else "HARDWARE — explicitly selected ring")
    if source == "simulator":
        print(f"Simulator profile: {payload['simulator_profile']}")
    hid = payload["standard_hid"]
    print(f"Inventory metadata: {payload['inventory_state']}")
    heart_rate = payload["standard_heart_rate"]
    print("Standard Heart Rate metadata")
    print(f"Service: {heart_rate['service_state'].replace('_', ' ')}")
    print(
        "Measurement notifications: "
        f"{heart_rate['measurement_characteristic_state'].replace('_', ' ')}; "
        f"{heart_rate['instance_count']} instance(s); "
        f"{heart_rate['instance_resolution_state'].replace('_', ' ')}"
    )
    print(f"CCCD: {heart_rate['cccd_state'].replace('_', ' ')}")
    print("Value: not read; subscription: not attempted")
    print(
        "Live delivery: not tested; metadata does not establish model or firmware support"
    )
    print(f"Standard HID service: {hid['service_state']}")
    for feature in hid["characteristics"]:
        label = feature["name"].replace("_", " ").title().replace("Hid", "HID")
        instance_detail = (
            f"; {feature['instance_count']} instance(s); "
            f"{feature['instance_resolution_state'].replace('_', ' ')}"
            if feature["instance_count"]
            else ""
        )
        print(f"{label}: {feature['state']}{instance_detail}")
    print(f"Report Reference descriptor: {hid['report_reference_descriptor']['state']}")
    print(f"HID Report instances: {len(hid['report_instances'])}")
    for report in hid["report_instances"]:
        print(
            f"- Report instance {report['instance']}: {report['state']}; "
            f"Report Reference {report['report_reference_state']}; value not read; "
            f"{report['targeting_state'].replace('_', ' ')}"
        )
    print("Report Map contents: not read")
    print(f"HID usability: {hid['usability_state'].replace('_', ' ')}")
    print(f"OS attachment: {hid['os_attachment_state'].replace('_', ' ')}")
    print("Verified hardware events: none (unsupported)")
    vendor = payload["vendor_gatt"]
    if vendor:
        print(f"Known vendor UUID observations: {len(vendor)}")
        for observation in vendor:
            print(
                f"- {observation['uuid']}: {observation['observed_as']}; "
                f"meaning {observation['meaning']}"
            )
    else:
        print("Known vendor UUID observations: none")
    print("Vendor routes (metadata only; no vendor characteristic I/O)")
    for route in payload["vendor_routes"]:
        route_label = route["route"].replace("_", " ")
        structural_state = route["structural_state"].replace("_", " ")
        target_state = route["transport_target_state"].replace("_", " ")
        print(
            f"Vendor {route_label} route: {structural_state}; "
            f"targets {target_state}; service inventory "
            f"{route['service_inventory_state'].replace('_', ' ')}; metadata "
            f"{route['metadata_inventory_state'].replace('_', ' ')}"
        )
    print(
        "Vendor routes are metadata only: values not read; subscriptions not "
        "attempted; writes disabled"
    )
    print(
        "Route readiness grants no live eligibility, owner authorization, or "
        "hardware eligibility"
    )
    print(
        "For private observation selectors, rerun with --include-observation-targets "
        "--json; UUIDs and instance IDs are metadata only and are not shown in this human view"
    )
    print("Vendor meanings: unknown; values not read; writes disabled")
    if "issue_draft_url" in payload:
        print("Sanitized issue draft: generated locally; review before opening.")
        print(payload["issue_draft_url"])


async def _run(args: argparse.Namespace) -> int:
    if args.command == "completion":
        _print_completion(args.shell)
        return ExitCode.OK
    if args.command == "review-observation":
        payload = load_private_observation(args.private_input)
        if args.issue_draft_url:
            payload["issue_draft_url"] = _observation_issue_draft_url(payload)
        if args.json:
            _print_json_success("review_private_observation", "private_local", payload)
        else:
            print("OFFLINE PRIVATE-OBSERVATION REVIEW — no Bluetooth operation")
            print(f"Capture: {payload['capture_status'].replace('_', ' ')}")
            print(f"Private records: {payload['record_count']}")
            print("Decoder: none; runtime behavior: unchanged")
            print("Values, identifiers, target identity, and private path: withheld")
            if "issue_draft_url" in payload:
                print("Sanitized issue draft: generated locally; review before opening.")
                print(payload["issue_draft_url"])
        return ExitCode.OK
    if args.command == "review-owner-evidence":
        result = load_private_owner_evidence(args.private_input)
        payload = result.review_payload()
        candidate = None
        receipt_created = False
        if args.decision is not None:
            candidate = render_approved_compatibility_row(
                result,
                review_decision=args.decision,
                approved_evidence_reference=args.evidence_reference,
            )
        if args.review_output is not None:
            write_owner_evidence_review(
                args.private_input,
                args.review_output,
                review_decision=args.decision,
                approved_evidence_reference=args.evidence_reference,
            )
            receipt_created = True
        payload = {
            **payload,
            "candidate_public_row": candidate,
            "review_receipt_created": receipt_created,
        }
        if args.json:
            _print_json_success("review_owner_evidence", "private_local", payload)
        else:
            print("OFFLINE OWNER-EVIDENCE REVIEW — no Bluetooth operation")
            print(f"Attempt: {payload['attempt_status'].replace('_', ' ')}")
            print(f"Write dispatch: {payload['write_dispatch'].replace('_', ' ')}")
            print(f"Response terminal: {payload['response_terminal'].replace('_', ' ')}")
            print(
                "Cleanup: "
                f"unsubscribe {payload['cleanup']['unsubscribe'].replace('_', ' ')}; "
                f"close {payload['cleanup']['close'].replace('_', ' ')}; "
                f"overall {payload['cleanup_status'].replace('_', ' ')}"
            )
            print(
                "Attempt evidence commit: "
                f"{payload['evidence_commit_status'].replace('_', ' ')}"
            )
            print(
                f"Declared scope: {payload['declared_model_family']} / "
                f"firmware {payload['declared_firmware_major']}"
            )
            print(
                "Environment proposed for publication: "
                f"Linux {payload['linux_family']}; Python {payload['python_minor']}; "
                f"BlueZ {payload['bluez_major']}; Bleak {payload['bleak_major']}"
            )
            print("Prospective public fields:")
            print(json.dumps(candidate, indent=2, sort_keys=True) if candidate else "  supply --decision and --evidence-reference to preview")
            print(
                "Review receipt: created as a new mode-0600 private file"
                if receipt_created
                else "Review receipt: not requested (preview only)"
            )
            print("Private values and paths: withheld")
            print(
                "Recovery: derive only from a created private review receipt; "
                "runtime support remains unchanged"
            )
        return ExitCode.OK
    if args.command == "derive-owner-evidence":
        row = write_reviewed_compatibility_row(
            args.private_input,
            args.review_receipt,
            args.public_output,
        )
        if args.json:
            _print_json_success("derive_owner_evidence", "private_local", row)
        else:
            print("PUBLIC EVIDENCE ROW CREATED — no Bluetooth operation")
            print(f"Decision: {row['review_decision']}")
            print(f"Operation status: {row['operation_status'].replace('_', ' ')}")
            print("Output: new sanitized public file; path withheld")
            print("Runtime registry: unchanged")
        return ExitCode.OK
    if args.command == "non-health-capabilities":
        payload = _non_health_payload()
        if args.json:
            _print_json_success("non_health_capabilities", "local", payload)
        else:
            _print_non_health_capabilities(payload)
        return ExitCode.OK
    if args.command == "protocol-coverage":
        payload = _protocol_coverage_payload()
        if args.json:
            _print_json_success("protocol_coverage", "local", payload)
        else:
            _print_protocol_coverage(payload)
        return ExitCode.OK
    if args.command == "input-actions":
        inventory = input_action_inventory()
        inventory["simulator_profiles"] = _simulator_profiles_payload()
        if args.json:
            _print_json_success("input_actions", "local", inventory)
        else:
            _print_input_actions(inventory)
        return ExitCode.OK
    if args.command == "doctor":
        report = diagnose()
        requirement_failed = (
            args.require_hardware and not (
                report.hardware_ready and report.adapter_operational is True
            )
        ) or (
            args.require_input and not report.input_ready
        )
        if args.json:
            if requirement_failed:
                requirement = "hardware" if args.require_hardware else "desktop-input"
                _print_json_error(
                    RuntimeError(f"required {requirement} prerequisites are unavailable"),
                    operation="doctor",
                    source="local",
                    contract=_UNAVAILABLE,
                    payload=report.to_dict(),
                )
            else:
                _print_json_success("doctor", "local", report.to_dict())
        else:
            _print_readiness(report)
        return ExitCode.UNAVAILABLE if requirement_failed else ExitCode.OK
    if args.command == "verify-device-info":
        validate_owner_evidence_prerequisites(
            operation_id="getDeviceInfo",
            allow_connect=args.allow_connect,
            allow_subscribe=args.allow_notifications,
            allow_write=args.allow_write,
            negative_control=args.negative_control,
            timeout=args.timeout,
            private_output=args.private_output,
            model_family=args.model_family,
            firmware_major=args.firmware_major,
        )
        if args.select:
            print("ACTIVE SCAN — sends BLE scan requests; no connection has started.")
            candidates = await discover_for_selection(timeout=args.timeout)
            address = _choose_candidate(candidates, purpose=args.command)
            if address is None:
                return ExitCode.OK
        else:
            address = _selected_address(args)
        selection = prepare_owner_evidence_selection((address,))
        negative_control = prepare_owner_negative_control("getDeviceInfo")
        plan = prepare_owner_evidence_run(
            operation_id="getDeviceInfo",
            selection=selection,
            allow_connect=args.allow_connect,
            allow_subscribe=args.allow_notifications,
            allow_write=args.allow_write,
            negative_control=negative_control if args.negative_control else None,
            timeout=args.timeout,
            private_output=args.private_output,
            model_family=args.model_family,
            firmware_major=args.firmware_major,
        )
        if not args.json:
            print("OWNER-HARDWARE TRANSPORT CANARY — no connection has started")
            print(f"Declared scope: {args.model_family} / firmware {args.firmware_major}")
            print(
                "Will transmit: one connection, one MAIN notification subscription, "
                "and one response-requesting vendor device-info query"
            )
            print("Safety check: a positive-duration pre-write negative-control window")
            print("Private evidence: one new mode-0600 file; path withheld")
            print("The response value is discarded; device-info contents and firmware support are not verified")
        runner = OwnerHardwareEvidenceRunner(transport_factory=BleakTransport)
        try:
            result = await runner.run(plan)
        except asyncio.CancelledError as exc:
            interrupted_result = runner.interrupted_result
            if interrupted_result is None:
                raise
            raise _OwnerEvidenceInterrupted(
                interrupted_result.public_payload()
            ) from exc
        payload = result.public_payload()
        if args.json:
            if result.status is OwnerEvidenceStatus.SUCCEEDED:
                _print_json_success("owner_hardware_evidence", "hardware", payload)
            else:
                contracts = {
                    OwnerEvidenceStatus.TIMED_OUT: ErrorContract(
                        "owner_evidence_timeout", ExitCode.TIMEOUT, False
                    ),
                    OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED: ErrorContract(
                        "owner_evidence_commit_failed", ExitCode.PERMISSION_DENIED, False
                    ),
                    OwnerEvidenceStatus.NEGATIVE_CONTROL_FAILED: ErrorContract(
                        "owner_evidence_control_contaminated",
                        ExitCode.PROTOCOL_INCOMPATIBLE,
                        False,
                    ),
                    OwnerEvidenceStatus.DEVICE_REJECTED: ErrorContract(
                        "owner_evidence_device_rejected",
                        ExitCode.PROTOCOL_INCOMPATIBLE,
                        False,
                    ),
                    OwnerEvidenceStatus.MALFORMED_RESPONSE: ErrorContract(
                        "owner_evidence_malformed_response",
                        ExitCode.PROTOCOL_INCOMPATIBLE,
                        False,
                    ),
                    OwnerEvidenceStatus.ROUTE_UNAVAILABLE: ErrorContract(
                        "owner_evidence_route_unavailable", ExitCode.UNAVAILABLE, False
                    ),
                }
                contract = contracts.get(
                    result.status,
                    ErrorContract(
                        f"owner_evidence_{result.status.value}",
                        ExitCode.UNAVAILABLE,
                        False,
                    ),
                )
                _print_json_error(
                    RuntimeError("owner evidence attempt did not produce an accepted candidate"),
                    operation="owner_hardware_evidence",
                    source="hardware",
                    contract=contract,
                    payload=payload,
                )
        else:
            print("RESULT — owner-hardware transport canary")
            _print_owner_evidence_summary(payload)
        if result.status is OwnerEvidenceStatus.SUCCEEDED:
            return ExitCode.OK
        if result.status is OwnerEvidenceStatus.TIMED_OUT:
            return ExitCode.TIMEOUT
        if result.status in {
            OwnerEvidenceStatus.NEGATIVE_CONTROL_FAILED,
            OwnerEvidenceStatus.MALFORMED_RESPONSE,
            OwnerEvidenceStatus.DEVICE_REJECTED,
        }:
            return ExitCode.PROTOCOL_INCOMPATIBLE
        if result.status is OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED:
            return ExitCode.PERMISSION_DENIED
        return ExitCode.UNAVAILABLE
    if args.command == "observe":
        address = _selected_address(args)
        plan = prepare_observation_plan(
            address=address,
            allow_connect=args.allow_connect,
            allow_notifications=args.allow_notifications,
            allow_observation=args.allow_observation,
            timeout=args.timeout,
            max_records=args.max_records,
            private_output=args.private_output,
        )
        if not args.json:
            print("PRIVATE OBSERVATION — no connection has started")
            print(
                f"Will perform: one connection, one metadata-selected notification subscription, "
                f"up to {args.max_records} private record(s), within {args.timeout:g} seconds"
            )
            print("Will not perform: characteristic reads, vendor writes, decoding, input actions, uploads, or retries")
            print("Private record: one new mode-0600 file; path and captured values withheld")
        result = await PrivateObservationRunner(transport_factory=BleakTransport).run(
            plan,
            service_uuid=args.service_uuid,
            characteristic_uuid=args.characteristic_uuid,
            instance_id=args.instance_id,
        )
        payload = result.public_payload()
        if args.json:
            if payload["capture_status"] == ObservationStatus.COMPLETED.value:
                _print_json_success("private_observation", "hardware", payload)
            else:
                _print_json_error(
                    RuntimeError("private observation did not complete"),
                    operation="private_observation",
                    source="hardware",
                    contract=ErrorContract(
                        f"private_observation_{payload['capture_status']}",
                        ExitCode.TIMEOUT if payload["capture_status"] == "timed_out" else ExitCode.UNAVAILABLE,
                        False,
                    ),
                    payload=payload,
                )
        else:
            print("RESULT — private observation")
            print(f"Capture: {payload['capture_status'].replace('_', ' ')}")
            print(f"Private records: {payload['record_count']}")
            print(
                "Cleanup: "
                f"unsubscribe {payload['cleanup']['unsubscribe']}; "
                f"close {payload['cleanup']['close']}"
            )
            print("Values, target identity, and private path: withheld")
            print("Runtime behavior: unchanged")
        return (
            ExitCode.OK
            if payload["capture_status"] == ObservationStatus.COMPLETED.value
            else ExitCode.TIMEOUT
            if payload["capture_status"] == ObservationStatus.TIMED_OUT.value
            else ExitCode.UNAVAILABLE
        )
    if args.command == "input":
        binding = parse_binding(args.mapping)
        if not args.simulate:
            raise NotImplementedError(
                "hardware motion-event protocol is not verified; use --simulate"
            )
        preview = synthetic_vendor_step_preview()
        event = preview.event
        mapper = InputMapper((binding,))
        action = mapper.action_for(event)
        if action is None:
            raise ValueError("the simulated step has no input mapping")
        if not args.allow_input:
            if args.json:
                _print_json_success("input", "simulator", {
                    "event": event.kind,
                    "action": action.description,
                    "emitted": False,
                    "simulator_profile": args.simulator_profile,
                    "event_source": preview.source,
                    "counter_semantics": preview.counter_semantics,
                    "baseline_established": preview.baseline_established,
                    "exact_single_increment": preview.exact_single_increment,
                    "live_event_available": preview.live_available,
                    "hardware_event_verified": preview.hardware_verified,
                })
            else:
                print("SIMULATION — no ring contacted")
                print(f"Simulator profile: {args.simulator_profile}")
                print(
                    "Synthetic vendor cumulative-step preview: first sample "
                    "established a baseline; one exact increment produced one step"
                )
                print(f"Preview: {event.kind} -> {action.description}")
                print("No input emitted. Add --allow-input to authorize this one simulated event.")
            return 0
        sink = create_uinput_sink((action,))
        try:
            mapper.dispatch(event, sink)
        finally:
            sink.close()
        if args.json:
            _print_json_success("input", "simulator", {
                "event": event.kind,
                "action": action.description,
                "emitted": True,
                "simulator_profile": args.simulator_profile,
                "event_source": preview.source,
                "counter_semantics": preview.counter_semantics,
                "baseline_established": preview.baseline_established,
                "exact_single_increment": preview.exact_single_increment,
                "live_event_available": preview.live_available,
                "hardware_event_verified": preview.hardware_verified,
            })
        else:
            print("SIMULATION — no ring contacted")
            print(f"Simulator profile: {args.simulator_profile}")
            print(
                "Synthetic vendor cumulative-step source only; no live ring event "
                "was used"
            )
            print(f"Emitted: {event.kind} -> {action.description}")
        return 0
    if args.command == "pair":
        address = _selected_address(args)
        result = pair_device(
            address,
            timeout=args.timeout,
            allow_pairing=args.allow_pairing,
            allow_trust=args.allow_trust,
        )
        payload = {
            "pairing_status": result.status,
            "detail": result.detail,
            "trust_changed": result.status == "trusted",
            "application_binding_changed": False,
        }
        if args.json:
            if result.status in {"paired", "already_paired", "trusted"}:
                _print_json_success("pair", "hardware", payload)
            else:
                _print_json_error(
                    RuntimeError(result.detail),
                    operation="pair",
                    source="hardware",
                    contract=(
                        _TIMEOUT if result.status in {"timed_out", "trust_timed_out"} else _UNAVAILABLE
                    ),
                    payload=payload,
                )
        else:
            print("OS PAIRING — explicitly selected device")
            print(f"Result: {result.status.replace('_', ' ')}")
            print(result.detail)
            print(
                "Trust: changed by explicit confirmation"
                if result.status == "trusted"
                else "Trust: unchanged; application/vendor binding: unchanged"
            )
        return (
            ExitCode.OK
            if result.status in {"paired", "already_paired", "trusted"}
            else ExitCode.TIMEOUT
            if result.status in {"timed_out", "trust_timed_out"}
            else ExitCode.UNAVAILABLE
        )
    if args.command == "discover":
        results = await discover(timeout=args.timeout)
        if args.json:
            _print_json_success("discover", "hardware", {"devices": results})
        else:
            _print_discovery(results)
        return 0
    source = "simulator" if args.simulate else "hardware"
    if getattr(args, "select", False):
        print("ACTIVE SCAN — sends BLE scan requests; no connection has started.")
        candidates = await discover_for_selection(timeout=args.timeout)
        address = _choose_candidate(candidates, purpose=args.command)
        if address is None:
            return ExitCode.OK
    else:
        address = None if args.simulate else _selected_address(args)
    transport = (
        FakeTransport.for_simulator_profile(args.simulator_profile or "basic")
        if args.simulate
        else BleakTransport(address)
    )
    if args.command == "heart-rate":
        async with JRingClient(transport, timeout=args.timeout) as client:
            if source == "simulator":
                sample_task = asyncio.create_task(client.heart_rate_sample())
                try:
                    while transport.heart_rate_subscription_count == 0:
                        if sample_task.done():
                            sample_task.result()
                        await asyncio.sleep(0)
                    await asyncio.sleep(0)
                    transport.emit(HEART_RATE_MEASUREMENT, b"\x00\x48")
                    sample = await sample_task
                except BaseException:
                    sample_task.cancel()
                    await asyncio.gather(sample_task, return_exceptions=True)
                    raise
            else:
                sample = await client.heart_rate_sample()
        payload = _heart_rate_payload(
            sample,
            source=source,
            simulator_profile=args.simulator_profile,
        )
        if args.json:
            _print_json_success("heart_rate", source, payload)
        else:
            _print_heart_rate(payload, source)
        return ExitCode.OK
    async with JRingClient(transport, timeout=args.timeout) as client:
        if args.command == "capabilities":
            inventory = await client.capability_inventory()
            payload = _capability_payload(
                inventory,
                include_observation_targets=args.include_observation_targets,
            )
            if args.issue_draft_url:
                payload["issue_draft_url"] = _capability_issue_draft_url(payload)
            if source == "simulator":
                payload["simulator_profile"] = args.simulator_profile
            if args.json:
                _print_json_success("capabilities", source, payload)
            else:
                _print_capability_inventory(payload, source)
        elif args.command == "status":
            status = await client.status()
            capabilities = {
                "device_info_service_advertised": status.capabilities.device_info,
                "heart_rate_service_advertised": status.capabilities.heart_rate,
                "hid_service_advertised": status.capabilities.hid,
                "vendor_services_seen": status.capabilities.vendor_services_seen,
                "vendor_writes": status.capabilities.vendor_writes,
                "inventory_state": status.capabilities_state,
            }
            result = {
                "schema_version": 1,
                "source": source,
                "battery_percent": status.battery_percent,
                "battery_available": status.battery_available,
                "battery_state": status.battery_state,
                "device_info": asdict(status.device_info),
                "device_info_states": asdict(status.device_info_states),
                "capabilities": capabilities,
            }
            if source == "simulator":
                result["simulator_profile"] = args.simulator_profile
            if args.json:
                _print_json_success("status", source, result)
            else:
                _print_status(result)
        elif args.command == "time-sync":
            await client.sync_time(datetime.now().astimezone(), allow_write=args.allow_write)
            message = (
                "Simulated time write completed; no ring contacted."
                if args.simulate else
                "Ring time synchronized using the standard Bluetooth Current Time service."
            )
            if args.json:
                _print_json_success("time_sync", source, {})
            else:
                print(message)
        elif args.command == "history":
            records = await client.history()
            client.export_history(records, args.output, source=source, force=args.force)
            adjective = "simulated " if args.simulate else ""
            print(f"Exported {len(records)} {adjective}record(s) to {args.output}.")
    return 0


def _timeout(value: str) -> float:
    timeout = float(value)
    if not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise argparse.ArgumentTypeError("timeout must be finite and between 0 and 30 seconds")
    return timeout


def _add_simulator_profile_option(
    parser: argparse.ArgumentParser, *, suppress: bool
) -> None:
    parser.add_argument(
        "--simulate-profile",
        dest="simulator_profile",
        choices=tuple(profile.name for profile in SIMULATOR_PROFILES),
        default=argparse.SUPPRESS if suppress else None,
        help=(
            "with --simulate, select basic (default) or hid; the hid profile "
            "advertises metadata but never reads or emits HID reports"
        ),
    )


def _add_runtime_options(
    parser: argparse.ArgumentParser,
    *,
    suppress: bool = False,
    simulator_profiles: bool = False,
) -> None:
    default: object = argparse.SUPPRESS if suppress else None
    parser.add_argument("--address", default=default, help="exact selected ring Bluetooth address")
    parser.add_argument("--address-file", type=Path, default=default,
                        help="mode-0600 file containing the selected ring address")
    parser.add_argument("--simulate", action="store_true",
                        default=argparse.SUPPRESS if suppress else False,
                        help="use an offline simulated ring")
    if simulator_profiles:
        _add_simulator_profile_option(parser, suppress=suppress)
    parser.add_argument("--timeout", type=_timeout,
                        default=argparse.SUPPRESS if suppress else 8.0,
                        help="Bluetooth operation timeout in seconds (default: 8)")
    parser.add_argument("--json", action="store_true",
                        default=argparse.SUPPRESS if suppress else False,
                        help="print structured JSON where supported")


def _add_json_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="print structured JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jring", description="Privacy-first JRing Linux client")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}",
        help="show the installed JRing version and exit",
    )
    _add_runtime_options(parser, suppress=True, simulator_profiles=True)
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser(
        "doctor", help="passively check local simulator and hardware prerequisites"
    )
    _add_json_option(doctor)
    doctor.add_argument(
        "--require-hardware", action="store_true",
        help="exit nonzero when optional hardware prerequisites are missing",
    )
    doctor.add_argument(
        "--require-input", action="store_true",
        help="exit nonzero when desktop-input prerequisites are missing",
    )
    input_actions = sub.add_parser(
        "input-actions", help="list local simulator events and allowlisted input actions"
    )
    _add_json_option(input_actions)
    sub.add_parser(
        "tui", help="open a safe, simulator-first terminal menu (no device selected)"
    )
    completion = sub.add_parser(
        "completion", help="print an installed shell completion script"
    )
    completion.add_argument(
        "shell", choices=("bash",), help="shell to generate (currently: bash)"
    )
    protocol_coverage = sub.add_parser(
        "protocol-coverage",
        help="inspect offline APK-to-Python parity without Bluetooth",
    )
    _add_json_option(protocol_coverage)
    non_health = sub.add_parser(
        "non-health-capabilities",
        help="list offline non-health, HID, sensor, and input candidates",
    )
    _add_json_option(non_health)
    input_command = sub.add_parser(
        "input", help="simulator-only preview or emission; live ring events are unavailable"
    )
    input_command.add_argument("--simulate", action="store_true", default=argparse.SUPPRESS,
                               help="required: use one offline simulated step event")
    _add_simulator_profile_option(input_command, suppress=True)
    _add_json_option(input_command)
    input_command.add_argument("--address", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    input_command.add_argument("--address-file", type=Path, default=argparse.SUPPRESS,
                               help=argparse.SUPPRESS)
    input_command.add_argument("--timeout", type=_timeout, default=argparse.SUPPRESS,
                               help=argparse.SUPPRESS)
    input_command.add_argument(
        "--map", dest="mapping", required=True,
        help="mapping such as step=key:space or step=click:left",
    )
    input_command.add_argument(
        "--allow-input", action="store_true",
        help="authorize one simulated event through Linux uinput",
    )
    discovery = sub.add_parser(
        "discover", help="actively scan with explicit consent; redacts addresses and never connects"
    )
    discovery.add_argument("--simulate", action="store_true", default=argparse.SUPPRESS,
                           help="unsupported: discovery requires a real radio scan")
    discovery.add_argument("--timeout", type=_timeout, default=argparse.SUPPRESS,
                           help="scan timeout in seconds (default: 8)")
    _add_json_option(discovery)
    discovery.add_argument(
        "--active-scan", action="store_true",
        help="authorize BLE scan requests; does not connect",
    )
    pairing = sub.add_parser(
        "pair", help="pair one selected device through local BlueZ (never trusts it)"
    )
    pairing.add_argument(
        "--address-file", type=Path, required=True,
        help="mode-0600 file containing the one explicitly selected ring address",
    )
    pairing.add_argument(
        "--allow-pairing", action="store_true", required=True,
        help="authorize one OS pairing operation; no trust or vendor binding is changed",
    )
    pairing.add_argument(
        "--allow-trust", action="store_true",
        help="separately authorize the following local BlueZ trust operation",
    )
    pairing.add_argument(
        "--timeout", type=_timeout, default=8.0,
        help="pairing deadline in seconds (default: 8; timeout outcome is uncertain)",
    )
    _add_json_option(pairing)
    status = sub.add_parser("status", help="read battery, device information, and capabilities")
    _add_runtime_options(status, suppress=True, simulator_profiles=True)
    status.add_argument(
        "--select", action="store_true",
        help="interactively select an ephemeral discovery alias in this process",
    )
    status.add_argument(
        "--active-scan", action="store_true",
        help="authorize BLE scan requests for interactive selection",
    )
    capabilities = sub.add_parser(
        "capabilities",
        help="inventory standard HID and known vendor metadata without reading values",
    )
    _add_runtime_options(capabilities, suppress=True, simulator_profiles=True)
    capabilities.add_argument(
        "--select", action="store_true",
        help="interactively select an ephemeral discovery alias in this process",
    )
    capabilities.add_argument(
        "--active-scan", action="store_true",
        help="authorize BLE scan requests for interactive selection",
    )
    capabilities.add_argument(
        "--issue-draft-url", action="store_true",
        help="include a reviewable sanitized GitHub issue-draft URL",
    )
    capabilities.add_argument(
        "--include-observation-targets", action="store_true",
        help=(
            "include exact notify-target selector metadata in JSON; values and "
            "addresses remain excluded"
        ),
    )
    heart_rate = sub.add_parser(
        "heart-rate",
        help="collect one bounded standard Heart Rate notification",
    )
    _add_runtime_options(heart_rate, suppress=True, simulator_profiles=True)
    heart_rate.add_argument(
        "--select", action="store_true",
        help="interactively select an ephemeral discovery alias in this process",
    )
    heart_rate.add_argument(
        "--active-scan", action="store_true",
        help="authorize BLE scan requests for interactive selection",
    )
    heart_rate.add_argument(
        "--allow-notifications", action="store_true",
        help=(
            "authorize one standard Heart Rate notification; BlueZ may perform "
            "standard CCCD control traffic"
        ),
    )
    sync = sub.add_parser("time-sync", help="write standard Bluetooth Current Time")
    _add_runtime_options(sync, suppress=True)
    sync.add_argument(
        "--allow-write", "--yes", dest="allow_write", action="store_true",
        help="required for time sync: confirm this one standard Bluetooth time write",
    )
    history = sub.add_parser("history", help="export history (simulator only until verified)")
    history.add_argument("--simulate", action="store_true", default=argparse.SUPPRESS,
                         help="required: use offline simulated history")
    _add_json_option(history)
    history.add_argument(
        "--output", type=Path, required=True, help="destination JSON export file"
    )
    history.add_argument("--force", action="store_true", help="replace an existing export")
    evidence = sub.add_parser(
        "verify-device-info",
        help="run one owner-hardware device-info transport canary",
    )
    evidence.add_argument(
        "--address-file",
        type=Path,
        help="mode-0600 file containing the one explicitly selected ring address",
    )
    evidence.add_argument(
        "--private-output",
        type=Path,
        required=True,
        help="new destination for the exclusively created mode-0600 private evidence file",
    )
    evidence.add_argument("--model-family", required=True, help="coarse reviewed model family")
    evidence.add_argument("--firmware-major", required=True, help="coarse reviewed firmware major")
    evidence.add_argument(
        "--timeout", type=_timeout, default=8.0,
        help=(
            "one overall canary deadline covering setup, response, and cleanup "
            "(default: 8 seconds; an early expiry is uncertain and non-retryable)"
        ),
    )
    _add_json_option(evidence)
    evidence.add_argument(
        "--allow-connect", action="store_true", required=True,
        help="authorize one connection to the selected ring",
    )
    evidence.add_argument(
        "--allow-notifications", action="store_true", required=True,
        help="authorize one MAIN notification subscription",
    )
    evidence.add_argument(
        "--allow-write", action="store_true", required=True,
        help="authorize one response-requesting vendor canary write",
    )
    evidence.add_argument(
        "--negative-control", action="store_true", required=True,
        help="require the bounded pre-write negative-control window",
    )
    evidence.add_argument(
        "--select", action="store_true",
        help="interactively select an ephemeral discovery alias in this process",
    )
    evidence.add_argument(
        "--active-scan", action="store_true",
        help="authorize the BLE scan required by --select",
    )
    observe = sub.add_parser(
        "observe",
        help="privately collect bounded unknown notifications from one explicit metadata target",
    )
    observe.add_argument(
        "--address-file", type=Path, required=True,
        help="mode-0600 file containing the one explicitly selected ring address",
    )
    observe.add_argument(
        "--private-output", type=Path, required=True,
        help="new destination for the exclusively created mode-0600 private record",
    )
    observe.add_argument("--service-uuid", required=True, help="exact locally enumerated service UUID")
    observe.add_argument("--characteristic-uuid", required=True, help="exact locally enumerated notify characteristic UUID")
    observe.add_argument("--instance-id", required=True, help="exact locally enumerated characteristic instance ID")
    observe.add_argument("--max-records", type=int, default=8, help="private record cap, 1 through 128 (default: 8)")
    observe.add_argument("--timeout", type=_timeout, default=8.0, help="one overall observation deadline in seconds (default: 8)")
    _add_json_option(observe)
    observe.add_argument("--allow-connect", action="store_true", required=True, help="authorize one connection to the selected ring")
    observe.add_argument("--allow-notifications", action="store_true", required=True, help="authorize one metadata-selected notification subscription")
    observe.add_argument("--allow-observation", action="store_true", required=True, help="confirm private capture of unknown notification bytes")
    review_observation = sub.add_parser(
        "review-observation", help="review one private observation without Bluetooth I/O"
    )
    review_observation.add_argument(
        "--private-input", type=Path, required=True,
        help="mode-0600 private observation record",
    )
    _add_json_option(review_observation)
    review_observation.add_argument(
        "--issue-draft-url", action="store_true",
        help="include a reviewable sanitized GitHub issue-draft URL",
    )
    review = sub.add_parser(
        "review-owner-evidence",
        help="review one private owner-evidence record without Bluetooth I/O",
    )
    review.add_argument(
        "--private-input", type=Path, required=True,
        help="mode-0600 private evidence record",
    )
    review.add_argument(
        "--decision", choices=("promote", "reject"),
        help="decision to preview or seal in a private review receipt",
    )
    review.add_argument(
        "--evidence-reference",
        help="approved non-sensitive source-control review reference",
    )
    review.add_argument(
        "--review-output", type=Path,
        help="new mode-0600 destination for a private review receipt",
    )
    review.add_argument(
        "--allow-review-decision", action="store_true",
        help="confirm creation of this one private review receipt",
    )
    _add_json_option(review)
    derive = sub.add_parser(
        "derive-owner-evidence",
        help="create one sanitized public compatibility row without Bluetooth I/O",
    )
    derive.add_argument(
        "--private-input", type=Path, required=True,
        help="mode-0600 reviewed private evidence record",
    )
    derive.add_argument(
        "--public-output", type=Path, required=True,
        help="new destination for the sanitized public JSON row",
    )
    derive.add_argument(
        "--review-receipt", type=Path, required=True,
        help="mode-0600 review receipt bound to the private evidence",
    )
    derive.add_argument(
        "--allow-public-evidence", action="store_true", required=True,
        help="confirm creation of this one sanitized public row",
    )
    _add_json_option(derive)
    return parser


_MAC = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")
_BLUEZ_PATH = re.compile(r"/org/bluez(?:/[A-Za-z0-9_]+)+")
_LONG_HEX = re.compile(r"(?i)\b[0-9a-f]{16,}\b")


def _sanitize_error(error: BaseException) -> str:
    message = _MAC.sub("[redacted device]", str(error))
    message = _BLUEZ_PATH.sub("[redacted Bluetooth path]", message)
    return _LONG_HEX.sub("[redacted data]", message)


def _classify_error(error: BaseException) -> ErrorContract:
    if isinstance(error, OwnerEvidenceError):
        permission_codes = {
            "unsafe_private_output", "private_output_exists",
            "unsafe_review_output", "review_output_exists",
            "unsafe_review_receipt", "unsafe_public_output", "public_output_exists",
        }
        exit_code = (
            ExitCode.PERMISSION_DENIED
            if error.code in permission_codes
            else ExitCode.PROTOCOL_INCOMPATIBLE
            if error.code.startswith("invalid_private")
            or error.code.startswith("invalid_review_receipt")
            or error.code == "review_receipt_mismatch"
            else ExitCode.USAGE
        )
        return ErrorContract(error.code, exit_code, False)
    if isinstance(error, PermissionError):
        return _PERMISSION
    if isinstance(error, TimeoutError):
        return _TIMEOUT
    if isinstance(error, (UnavailableError, ModuleNotFoundError, ImportError, ConnectionError)):
        return _UNAVAILABLE
    if isinstance(error, (ProtocolError, LookupError, NotImplementedError)):
        return _PROTOCOL
    if isinstance(error, OSError):
        return _UNAVAILABLE
    if isinstance(error, ValueError):
        return _USAGE
    return _INTERNAL


def _print_json_error(
    error: BaseException,
    *,
    operation: str,
    source: str,
    contract: ErrorContract | None = None,
    payload: dict[str, Any] | None = None,
) -> ErrorContract:
    selected = contract or _classify_error(error)
    message = (
        "unexpected client failure"
        if selected is _INTERNAL
        else _sanitize_error(error)
    )
    print(json.dumps(_json_envelope(
        operation=operation,
        source=source,
        ok=False,
        payload=payload,
        error={
            "code": selected.code,
            "message": message,
            "retryable": selected.retryable,
        },
    ), sort_keys=True))
    return selected


_OPERATIONS = {
    "doctor": "doctor",
    "protocol-coverage": "protocol_coverage",
    "non-health-capabilities": "non_health_capabilities",
    "input-actions": "input_actions",
    "tui": "tui",
    "completion": "completion",
    "input": "input",
    "capabilities": "capabilities",
    "heart-rate": "heart_rate",
    "discover": "discover",
    "pair": "pair",
    "status": "status",
    "time-sync": "time_sync",
    "history": "history",
    "verify-device-info": "owner_hardware_evidence",
    "observe": "private_observation",
    "review-observation": "review_private_observation",
    "review-owner-evidence": "review_owner_evidence",
    "derive-owner-evidence": "derive_owner_evidence",
}


def _intent_from_argv(argv: list[str]) -> tuple[str, str]:
    operation = next((_OPERATIONS[value] for value in argv if value in _OPERATIONS), "cli")
    if operation in {
        "doctor", "input_actions", "protocol_coverage", "non_health_capabilities"
    }:
        source = "local"
    elif "--simulate" in argv or "--simulate-profile" in argv:
        source = "simulator"
    elif operation == "cli":
        source = "unknown"
    elif operation in {"review_owner_evidence", "derive_owner_evidence", "review_private_observation"}:
        source = "private_local"
    else:
        source = "hardware"
    return operation, source


def _source_from_args(args: argparse.Namespace) -> str:
    if args.command in {"review-owner-evidence", "derive-owner-evidence", "review-observation"}:
        return "private_local"
    if args.command in {
        "doctor", "input-actions", "tui", "protocol-coverage", "non-health-capabilities"
    }:
        return "local"
    return "simulator" if getattr(args, "simulate", False) else "hardware"


def _argument_error_message(rendered: str) -> str:
    lines = [line.strip() for line in rendered.splitlines() if line.strip()]
    if not lines:
        return "invalid command arguments"
    message = lines[-1]
    marker = ": error: "
    if marker in message:
        message = message.split(marker, 1)[1]
    return _sanitize_error(ValueError(message))


def _selected_address(args: argparse.Namespace) -> str:
    if args.address:
        return select_exact(args.address)
    path = args.address_file
    try:
        details = path.lstat()
    except OSError as exc:
        raise PermissionError("address file is unavailable or unsafe") from exc
    if (
        not stat.S_ISREG(details.st_mode)
        or details.st_uid != os.getuid()
        or stat.S_IMODE(details.st_mode) != 0o600
        or details.st_nlink != 1
    ):
        raise PermissionError("address file must be a regular file owned by this user with mode 0600")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PermissionError("address file is unavailable or unsafe") from exc
    try:
        opened = os.fstat(descriptor)
        if (
            opened.st_dev != details.st_dev
            or opened.st_ino != details.st_ino
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or stat.S_IMODE(opened.st_mode) != 0o600
            or opened.st_nlink != 1
        ):
            raise PermissionError(
                "address file must be a regular file owned by this user with mode 0600"
            )
        try:
            raw = os.read(descriptor, 257)
        except OSError as exc:
            raise PermissionError("address file is unavailable or unsafe") from exc
    finally:
        os.close(descriptor)
    if len(raw) > 256:
        raise ValueError("address file must contain exactly one Bluetooth address")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("address file must contain exactly one Bluetooth address") from exc
    lines = [line.strip() for line in decoded.splitlines() if line.strip()]
    if len(lines) != 1:
        raise ValueError("address file must contain exactly one Bluetooth address")
    return select_exact(lines[0])


def _parse_cli_args(argv: list[str]) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    provided = set(vars(args))
    address = getattr(args, "address", None)
    address_file = getattr(args, "address_file", None)
    simulate = getattr(args, "simulate", False)
    simulator_profile_explicit = "simulator_profile" in provided
    simulator_profile_name = getattr(args, "simulator_profile", None)
    json_output = getattr(args, "json", False)
    guided_selection = getattr(args, "select", False)
    active_scan = getattr(args, "active_scan", False)
    has_hardware = bool(address or address_file)
    if args.command == "verify-device-info":
        if address:
            parser.error(
                "verify-device-info requires --address-file; direct addresses are not accepted"
            )
        if simulate:
            parser.error("verify-device-info does not support simulation")
        if not address_file and not guided_selection:
            parser.error("verify-device-info requires --address-file or --select --active-scan")
    if args.command in {"observe", "pair"}:
        if address:
            parser.error(f"{args.command} requires --address-file; direct addresses are not accepted")
        if simulate or guided_selection or active_scan:
            parser.error(f"{args.command} requires one mode-0600 --address-file and does not scan or simulate")
    if args.command in {"review-owner-evidence", "derive-owner-evidence", "review-observation"}:
        if simulate or has_hardware or guided_selection or active_scan:
            parser.error(f"{args.command} is offline and does not accept device selection")
    if args.command == "review-owner-evidence":
        decision_fields = (args.decision is not None, args.evidence_reference is not None)
        if decision_fields[0] != decision_fields[1]:
            parser.error("review preview requires both --decision and --evidence-reference")
        receipt_fields = (args.review_output is not None, args.allow_review_decision)
        if receipt_fields[0] != receipt_fields[1]:
            parser.error(
                "review receipt creation requires both --review-output and "
                "--allow-review-decision"
            )
        if any(receipt_fields) and not all(decision_fields):
            parser.error(
                "review receipt creation requires --decision and --evidence-reference"
            )
    if simulator_profile_explicit and not simulate:
        parser.error("--simulate-profile requires --simulate")
    if simulator_profile_explicit and args.command not in {
        "status", "capabilities", "heart-rate", "input"
    }:
        parser.error(
            "--simulate-profile is supported only by status, capabilities, "
            "heart-rate, and input"
        )
    if guided_selection and (simulate or has_hardware):
        parser.error("--select is mutually exclusive with simulation and address selectors")
    if guided_selection and not active_scan:
        parser.error("--select requires --active-scan because it sends BLE scan requests")
    if args.command in {"status", "capabilities", "heart-rate", "verify-device-info"} and active_scan and not guided_selection:
        parser.error(f"--active-scan on {args.command} requires --select")
    if guided_selection and json_output:
        parser.error("guided selection is human-only; automation should use --address-file")
    if guided_selection and not sys.stdin.isatty():
        parser.error("guided selection requires an interactive terminal; use --address-file")
    if simulate and has_hardware:
        parser.error("--simulate and hardware selection are mutually exclusive")
    if address and address_file:
        parser.error("--address and --address-file are mutually exclusive")
    if args.command == "doctor":
        ignored = provided & {"address", "address_file", "simulate", "timeout"}
        if ignored:
            option = sorted(ignored)[0].replace("_", "-")
            parser.error(f"--{option} is not supported by doctor")
    if args.command == "input-actions":
        ignored = provided & {"address", "address_file", "simulate", "timeout"}
        if ignored:
            option = sorted(ignored)[0].replace("_", "-")
            parser.error(f"--{option} is not supported by input-actions")
    if args.command == "completion":
        ignored = provided & {"address", "address_file", "simulate", "timeout", "json"}
        if ignored:
            option = sorted(ignored)[0].replace("_", "-")
            parser.error(f"--{option} is not supported by completion")
    if args.command == "pair" and address:
        parser.error("pair requires --address-file; direct addresses are not accepted")
    if args.command == "protocol-coverage":
        ignored = provided & {"address", "address_file", "simulate", "timeout"}
        if ignored:
            option = sorted(ignored)[0].replace("_", "-")
            parser.error(f"--{option} is not supported by protocol-coverage")
    if args.command == "non-health-capabilities":
        ignored = provided & {"address", "address_file", "simulate", "timeout"}
        if ignored:
            option = sorted(ignored)[0].replace("_", "-")
            parser.error(f"--{option} is not supported by non-health-capabilities")
    if args.command == "discover":
        if simulate:
            parser.error("discover does not support simulation; it is a radio-active operation")
        if has_hardware:
            parser.error("discover does not accept device selection")
        if not args.active_scan:
            parser.error("discover requires --active-scan because it sends BLE scan requests")
    if args.command == "history" and json_output:
        parser.error("--json is not supported by history; choose a .jsonl output path")
    if args.command == "capabilities" and getattr(args, "include_observation_targets", False) and not json_output:
        parser.error("--include-observation-targets requires --json")
    if args.command == "input" and provided & {"address", "address_file", "timeout"}:
        parser.error("input does not accept hardware selection or --timeout; use --simulate")
    if args.command == "input" and not simulate:
        parser.error("input currently requires --simulate; hardware motion is not verified")
    if args.command == "history" and provided & {"address", "address_file", "timeout"}:
        parser.error("history is simulator-only and does not accept hardware selection or --timeout")
    if (
        args.command not in {
            "discover", "doctor", "input", "input-actions", "completion", "protocol-coverage",
            "non-health-capabilities", "review-owner-evidence", "derive-owner-evidence", "review-observation",
        }
        and not simulate
        and not has_hardware
        and not guided_selection
    ):
        parser.error(
            "this command needs one selected device: use --address-file (preferred) "
            "or --address; for a safe first run, use `jring status --simulate`; "
            "run `jring doctor` before hardware"
        )
    if args.command == "history" and not simulate:
        parser.error("hardware history is not verified; use --simulate")
    if args.command == "heart-rate":
        allow_notifications = getattr(args, "allow_notifications", False)
        if simulate and allow_notifications:
            parser.error(
                "--allow-notifications is hardware-only; simulation uses no Bluetooth"
            )
        if not simulate and not allow_notifications:
            parser.error(
                "hardware heart-rate requires --allow-notifications because BlueZ "
                "may perform standard CCCD control traffic"
            )
    if args.command == "time-sync" and not getattr(args, "allow_write", False):
        parser.error("time-sync requires --allow-write/--yes")
    for name, value in {
        "address": address,
        "address_file": address_file,
        "simulate": simulate,
        "timeout": getattr(args, "timeout", 8.0),
        "json": json_output,
        "simulator_profile": (
            simulator_profile_name
            if simulator_profile_explicit
            else "basic"
            if simulate and args.command in {
                "status", "capabilities", "heart-rate", "input"
            }
            else None
        ),
    }.items():
        if not hasattr(args, name):
            setattr(args, name, value)
    return args


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    json_requested = "--json" in raw_argv
    if not raw_argv:
        _print_terminal_home()
        return ExitCode.OK
    if raw_argv == ["tui"]:
        return _run_tui()
    if json_requested:
        rendered_error = StringIO()
        try:
            with redirect_stderr(rendered_error):
                args = _parse_cli_args(raw_argv)
        except SystemExit as exc:
            if exc.code == 0:
                return ExitCode.OK
            operation, source = _intent_from_argv(raw_argv)
            contract = _print_json_error(
                ValueError(_argument_error_message(rendered_error.getvalue())),
                operation=operation,
                source=source,
                contract=_USAGE,
            )
            return contract.exit_code
    else:
        args = _parse_cli_args(raw_argv)

    operation = _OPERATIONS[args.command]
    source = _source_from_args(args)
    try:
        return asyncio.run(_run(args))
    except _OwnerEvidenceInterrupted as exc:
        contract = ErrorContract(
            "owner_evidence_interrupted", ExitCode.INTERRUPTED, False
        )
        if args.json:
            _print_json_error(
                exc,
                operation=operation,
                source=source,
                contract=contract,
                payload=exc.payload,
            )
        else:
            print("RESULT — interrupted owner-hardware transport canary")
            _print_owner_evidence_summary(exc.payload, interrupted=True)
        return contract.exit_code
    except KeyboardInterrupt:
        interrupted_contract = (
            ErrorContract("owner_evidence_interrupted", ExitCode.INTERRUPTED, False)
            if args.command == "verify-device-info"
            else _INTERRUPTED
        )
        interrupted_message = (
            "owner evidence interrupted; a write may have been dispatched; inspect "
            "the requested private record before any manual rerun"
            if args.command == "verify-device-info"
            else "operation interrupted"
        )
        if args.json:
            contract = _print_json_error(
                RuntimeError(interrupted_message),
                operation=operation,
                source=source,
                contract=interrupted_contract,
            )
        else:
            print(f"jring: {interrupted_message}", file=sys.stderr)
            contract = interrupted_contract
        return contract.exit_code
    except Exception as exc:
        contract = _classify_error(exc)
        if args.json:
            _print_json_error(
                exc,
                operation=operation,
                source=source,
                contract=contract,
            )
        else:
            print(f"jring: error: {_sanitize_error(exc)}", file=sys.stderr)
        return contract.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
