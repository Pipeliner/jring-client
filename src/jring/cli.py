from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from . import __version__
from .bleak_transport import BleakTransport
from .client import JRingClient
from .discovery import discover, select_exact
from .input import InputMapper, SensorEvent, create_uinput_sink, parse_binding
from .readiness import ReadinessReport, diagnose
from .transport import FakeTransport


def _print_status(result: dict[str, Any]) -> None:
    info = result["device_info"]
    capabilities = result["capabilities"]
    print(f"Battery: {result['battery_percent']}%")
    print(f"Model: {info['model'] or 'not reported'}")
    print(f"Manufacturer: {info['manufacturer'] or 'not reported'}")
    print(f"Firmware: {info['firmware'] or 'not reported'}")
    print(f"Heart rate: {'available' if capabilities['heart_rate'] else 'not available'}")
    print(f"Standard HID: {'available' if capabilities['hid'] else 'not available'}")
    vendor_count = len(capabilities["vendor_services_seen"])
    print(f"Vendor services: {vendor_count} detected; writes disabled")


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
    print("then pass its exact address to a hardware command with --address.")


def _print_readiness(report: ReadinessReport) -> None:
    print("JRing setup check")
    for check in report.checks:
        print(f"[{'ok' if check.ok else 'fix'}] {check.detail}")
        if check.remedy:
            print(f"      Remedy: {check.remedy}")
    print(f"Simulator: {'ready' if report.simulator_ready else 'not ready'}")
    print(f"Hardware: {'ready' if report.hardware_ready else 'not ready'}")
    print(f"Desktop input: {'ready' if report.input_ready else 'not ready'}")
    print(f"Next: {report.next_step}")


async def _run(args: argparse.Namespace) -> int:
    if args.command == "doctor":
        report = diagnose()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        else:
            _print_readiness(report)
        requirement_failed = (
            args.require_hardware and not report.hardware_ready
        ) or (
            args.require_input and not report.input_ready
        )
        return int(requirement_failed)
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
            print(f"Preview: {event.kind} -> {action.description}")
            print("No input emitted. Add --allow-input to authorize this one simulated event.")
            return 0
        sink = create_uinput_sink()
        try:
            mapper.dispatch(event, sink)
        finally:
            sink.close()
        print(f"Emitted: {event.kind} -> {action.description}")
        return 0
    if args.command == "discover":
        results = await discover(timeout=args.timeout)
        if args.json:
            print(json.dumps(results, indent=2, sort_keys=True))
        else:
            _print_discovery(results)
        return 0
    transport = FakeTransport.standard_ring() if args.simulate else BleakTransport(select_exact(args.address))
    async with JRingClient(transport, timeout=args.timeout) as client:
        if args.command == "status":
            result = {"battery_percent": await client.battery(),
                      "device_info": asdict(await client.device_info()),
                      "capabilities": asdict(await client.capabilities())}
            if args.json:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                _print_status(result)
        elif args.command == "time-sync":
            await client.sync_time(datetime.now().astimezone(), allow_write=args.allow_write)
            print("Ring time synchronized using the standard Bluetooth Current Time service.")
        elif args.command == "history":
            records = await client.history()
            client.export_history(records, args.output)
            print(f"Exported {len(records)} record(s) to {args.output}.")
    return 0


def _add_runtime_options(parser: argparse.ArgumentParser, *, suppress: bool = False) -> None:
    default: object = argparse.SUPPRESS if suppress else None
    parser.add_argument("--address", default=default, help="exact selected ring Bluetooth address")
    parser.add_argument("--simulate", action="store_true",
                        default=argparse.SUPPRESS if suppress else False,
                        help="use an offline simulated ring")
    parser.add_argument("--timeout", type=float,
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
    _add_runtime_options(parser)
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
    input_command = sub.add_parser(
        "input", help="preview or emit an allowlisted action from a sensor event"
    )
    _add_runtime_options(input_command, suppress=True)
    input_command.add_argument(
        "--map", dest="mapping", required=True,
        help="mapping such as step=key:space or step=click:left",
    )
    input_command.add_argument(
        "--allow-input", action="store_true",
        help="authorize one simulated event through Linux uinput",
    )
    discovery = sub.add_parser(
        "discover", help="passively scan and print redacted candidates; never connects"
    )
    _add_runtime_options(discovery, suppress=True)
    status = sub.add_parser("status", help="read battery, device information, and capabilities")
    _add_runtime_options(status, suppress=True)
    sync = sub.add_parser("time-sync", help="write standard Bluetooth Current Time")
    _add_runtime_options(sync, suppress=True)
    sync.add_argument(
        "--allow-write", "--yes", dest="allow_write", action="store_true", required=True,
        help="confirm this one standard Bluetooth time write",
    )
    history = sub.add_parser("history", help="export history (simulator only until verified)")
    _add_runtime_options(history, suppress=True)
    history.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command not in {"discover", "doctor"} and not args.simulate and not args.address:
        parser.error("hardware commands require --address")
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        print("jring: interrupted", file=sys.stderr)
        return 130
    except (ConnectionError, LookupError, NotImplementedError, OSError, PermissionError,
            RuntimeError, TimeoutError, ValueError) as exc:
        print(f"jring: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
