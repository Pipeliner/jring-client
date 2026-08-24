from __future__ import annotations

import argparse
import asyncio
from contextlib import redirect_stderr
import json
import math
import os
import re
import stat
import sys
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
    SensorEvent,
    create_uinput_sink,
    input_action_inventory,
    parse_binding,
)
from .protocol import ProtocolError
from .readiness import ReadinessReport, diagnose
from .transport import FakeTransport


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


def _print_discovery(results: list[dict[str, object]]) -> None:
    if not results:
        print("No nearby Bluetooth devices found.")
        print("Keep the ring close, wake it, and try again.")
        return
    print(f"Found {len(results)} nearby Bluetooth device(s):")
    for item in results:
        likelihood = "possible JRing" if item["likely_jring"] else "unidentified"
        rssi = item["rssi"] if item["rssi"] is not None else "unknown"
        print(f"- {item['alias']}: {likelihood}, signal {rssi} dBm")
    print("Addresses stay hidden during discovery. Use BlueZ to identify your ring,")
    print("then store its exact address in a mode-0600 file and use --address-file.")
    print("Or run jring status --select --active-scan for same-process guided selection.")


def _choose_candidate(candidates: list[SelectionCandidate]) -> str | None:
    if not candidates:
        raise UnavailableError("no nearby Bluetooth devices found; no connection attempted")
    print(f"Found {len(candidates)} nearby Bluetooth device(s):")
    for index, candidate in enumerate(candidates, start=1):
        likelihood = "possible JRing" if candidate.likely_jring else "unidentified"
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
        confirmation = input("Connect to this device for status? [y/N]: ").strip().lower()
    except EOFError:
        confirmation = ""
    if confirmation not in {"y", "yes"}:
        print("Cancelled; no connection made.")
        return None
    print(f"CONNECTION AUTHORIZED — connecting to {selected.alias} for status.")
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
        print(f"[{'ok' if check.ok else 'fix'}] {check.detail}")
        if check.remedy:
            print(f"      Remedy: {check.remedy}")
    print(f"Next: {report.next_step}")


def _print_input_actions(inventory: dict[str, list[dict[str, object]]]) -> None:
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


async def _run(args: argparse.Namespace) -> int:
    if args.command == "input-actions":
        inventory = input_action_inventory()
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
    if args.command == "input":
        binding = parse_binding(args.mapping)
        if not args.simulate:
            raise NotImplementedError(
                "hardware motion-event protocol is not verified; use --simulate"
            )
        event = SensorEvent("step")
        mapper = InputMapper((binding,))
        action = mapper.action_for(event)
        if action is None:
            raise ValueError("the simulated step has no input mapping")
        if not args.allow_input:
            if args.json:
                _print_json_success("input", "simulator", {
                    "event": event.kind,
                    "action": action.description, "emitted": False,
                })
            else:
                print("SIMULATION — no ring contacted")
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
                "action": action.description, "emitted": True,
            })
        else:
            print("SIMULATION — no ring contacted")
            print(f"Emitted: {event.kind} -> {action.description}")
        return 0
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
        address = _choose_candidate(candidates)
        if address is None:
            return ExitCode.OK
    else:
        address = None if args.simulate else _selected_address(args)
    transport = FakeTransport.standard_ring() if args.simulate else BleakTransport(address)
    async with JRingClient(transport, timeout=args.timeout) as client:
        if args.command == "status":
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


def _add_runtime_options(parser: argparse.ArgumentParser, *, suppress: bool = False) -> None:
    default: object = argparse.SUPPRESS if suppress else None
    parser.add_argument("--address", default=default, help="exact selected ring Bluetooth address")
    parser.add_argument("--address-file", type=Path, default=default,
                        help="mode-0600 file containing the selected ring address")
    parser.add_argument("--simulate", action="store_true",
                        default=argparse.SUPPRESS if suppress else False,
                        help="use an offline simulated ring")
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
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _add_runtime_options(parser, suppress=True)
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
    input_command = sub.add_parser(
        "input", help="simulator-only preview or emission; live ring events are unavailable"
    )
    input_command.add_argument("--simulate", action="store_true", default=argparse.SUPPRESS,
                               help="required: use one offline simulated step event")
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
    status = sub.add_parser("status", help="read battery, device information, and capabilities")
    _add_runtime_options(status, suppress=True)
    status.add_argument(
        "--select", action="store_true",
        help="interactively select an ephemeral discovery alias in this process",
    )
    status.add_argument(
        "--active-scan", action="store_true",
        help="authorize BLE scan requests for interactive selection",
    )
    sync = sub.add_parser("time-sync", help="write standard Bluetooth Current Time")
    _add_runtime_options(sync, suppress=True)
    sync.add_argument(
        "--allow-write", "--yes", dest="allow_write", action="store_true", required=True,
        help="confirm this one standard Bluetooth time write",
    )
    history = sub.add_parser("history", help="export history (simulator only until verified)")
    history.add_argument("--simulate", action="store_true", default=argparse.SUPPRESS,
                         help="required: use offline simulated history")
    _add_json_option(history)
    history.add_argument("--output", type=Path, required=True)
    history.add_argument("--force", action="store_true", help="replace an existing export")
    return parser


_MAC = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")
_BLUEZ_PATH = re.compile(r"/org/bluez(?:/[A-Za-z0-9_]+)+")
_LONG_HEX = re.compile(r"(?i)\b[0-9a-f]{16,}\b")


def _sanitize_error(error: BaseException) -> str:
    message = _MAC.sub("[redacted device]", str(error))
    message = _BLUEZ_PATH.sub("[redacted Bluetooth path]", message)
    return _LONG_HEX.sub("[redacted data]", message)


def _classify_error(error: BaseException) -> ErrorContract:
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
    "input-actions": "input_actions",
    "input": "input",
    "discover": "discover",
    "status": "status",
    "time-sync": "time_sync",
    "history": "history",
}


def _intent_from_argv(argv: list[str]) -> tuple[str, str]:
    operation = next((_OPERATIONS[value] for value in argv if value in _OPERATIONS), "cli")
    if operation in {"doctor", "input_actions"}:
        source = "local"
    elif "--simulate" in argv:
        source = "simulator"
    elif operation == "cli":
        source = "unknown"
    else:
        source = "hardware"
    return operation, source


def _source_from_args(args: argparse.Namespace) -> str:
    if args.command in {"doctor", "input-actions"}:
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
    details = path.stat()
    if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid() or details.st_mode & 0o077:
        raise PermissionError("address file must be a regular file owned by this user with mode 0600")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
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
    json_output = getattr(args, "json", False)
    guided_selection = getattr(args, "select", False)
    active_scan = getattr(args, "active_scan", False)
    has_hardware = bool(address or address_file)
    if guided_selection and (simulate or has_hardware):
        parser.error("--select is mutually exclusive with simulation and address selectors")
    if guided_selection and not active_scan:
        parser.error("--select requires --active-scan because it sends BLE scan requests")
    if args.command == "status" and active_scan and not guided_selection:
        parser.error("--active-scan on status requires --select")
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
    if args.command == "discover":
        if simulate:
            parser.error("discover does not support simulation; it is a radio-active operation")
        if has_hardware:
            parser.error("discover does not accept device selection")
        if not args.active_scan:
            parser.error("discover requires --active-scan because it sends BLE scan requests")
    if args.command == "history" and json_output:
        parser.error("--json is not supported by history; choose a .jsonl output path")
    if args.command == "input" and provided & {"address", "address_file", "timeout"}:
        parser.error("input does not accept hardware selection or --timeout; use --simulate")
    if args.command == "input" and not simulate:
        parser.error("input currently requires --simulate; hardware motion is not verified")
    if args.command == "history" and provided & {"address", "address_file", "timeout"}:
        parser.error("history is simulator-only and does not accept hardware selection or --timeout")
    if (
        args.command not in {"discover", "doctor", "input", "input-actions"}
        and not simulate
        and not has_hardware
        and not guided_selection
    ):
        parser.error("choose --simulate, --address-file, or --address for this command")
    if args.command == "history" and not simulate:
        parser.error("hardware history is not verified; use --simulate")
    for name, value in {
        "address": address,
        "address_file": address_file,
        "simulate": simulate,
        "timeout": getattr(args, "timeout", 8.0),
        "json": json_output,
    }.items():
        if not hasattr(args, name):
            setattr(args, name, value)
    return args


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    json_requested = "--json" in raw_argv
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
    except KeyboardInterrupt:
        if args.json:
            contract = _print_json_error(
                RuntimeError("operation interrupted"),
                operation=operation,
                source=source,
                contract=_INTERRUPTED,
            )
        else:
            print("jring: interrupted", file=sys.stderr)
            contract = _INTERRUPTED
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
