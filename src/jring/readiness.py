from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ok: bool
    detail: str
    remedy: str | None = None
    state: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple[ReadinessCheck, ...]
    simulator_ready: bool
    hardware_ready: bool
    input_ready: bool
    next_step: str
    adapter_operational: bool | None = None
    ring_compatibility: str = "not_checked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [check.to_dict() for check in self.checks],
            "simulator_ready": self.simulator_ready,
            "hardware_ready": self.hardware_ready,
            "input_ready": self.input_ready,
            "next_step": self.next_step,
            "adapter_operational": self.adapter_operational,
            "ring_compatibility": self.ring_compatibility,
        }


@dataclass(frozen=True)
class ProbeValue:
    state: str
    detail: str


@dataclass(frozen=True)
class BluezProbe:
    dbus: ProbeValue
    daemon: ProbeValue
    adapter: ProbeValue
    power: ProbeValue
    permission: ProbeValue


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _executable_available(name: str) -> bool:
    return shutil.which(name) is not None


def _path_writable(path: str) -> bool:
    return os.path.exists(path) and os.access(path, os.W_OK)


def _system_bus_exists() -> bool:
    return Path("/run/dbus/system_bus_socket").exists()


def _adapter_names() -> tuple[str, ...]:
    root = Path("/sys/class/bluetooth")
    try:
        names = sorted(
            entry.name for entry in root.iterdir()
            if re.fullmatch(r"hci[0-9]{1,3}", entry.name)
        )
    except FileNotFoundError:
        return ()
    return tuple(names[:8])


def _uninspected(detail: str) -> ProbeValue:
    return ProbeValue("uninspected", detail)


def _parse_busctl_data(output: str) -> Any:
    value = json.loads(output)
    if not isinstance(value, dict) or "data" not in value:
        raise ValueError("busctl JSON envelope is invalid")
    return value["data"]


def _single_value(value: Any) -> Any:
    while isinstance(value, dict) and "data" in value:
        value = value["data"]
    while isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value


def probe_bluez(
    *,
    system_bus_exists: Callable[[], bool] = _system_bus_exists,
    find_executable: Callable[[str], str | None] = shutil.which,
    adapter_names: Callable[[], tuple[str, ...]] = _adapter_names,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> BluezProbe:
    """Read BlueZ operational state without scanning, connecting, or mutating it."""
    if not system_bus_exists():
        unavailable = ProbeValue("unavailable", "system D-Bus socket is absent")
        unknown = _uninspected("system D-Bus is unavailable")
        return BluezProbe(unavailable, unknown, unknown, unknown, unknown)

    busctl = find_executable("busctl")
    if not busctl:
        unknown = _uninspected("busctl is unavailable; state was not inspected")
        return BluezProbe(unknown, unknown, unknown, unknown, unknown)

    def query(arguments: list[str]) -> subprocess.CompletedProcess[str] | None:
        try:
            return runner(
                arguments,
                capture_output=True,
                text=True,
                timeout=1,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None

    owner = query([
        busctl, "--system", "--json=short", "call",
        "org.freedesktop.DBus", "/org/freedesktop/DBus",
        "org.freedesktop.DBus", "NameHasOwner", "s", "org.bluez",
    ])
    if owner is None:
        unknown = _uninspected("bounded system D-Bus query failed")
        return BluezProbe(unknown, unknown, unknown, unknown, unknown)
    if owner.returncode != 0:
        unknown = _uninspected("system D-Bus query was denied")
        denied = ProbeValue("denied", "session cannot query the system D-Bus")
        return BluezProbe(unknown, unknown, unknown, unknown, denied)
    try:
        daemon_present = _single_value(_parse_busctl_data(owner.stdout)) is True
    except (json.JSONDecodeError, ValueError, TypeError):
        unknown = _uninspected("system D-Bus returned unrecognized structured data")
        permission = ProbeValue("available", "session completed a system D-Bus query")
        return BluezProbe(unknown, unknown, unknown, unknown, permission)

    dbus = ProbeValue("available", "system D-Bus answered a bounded read query")
    permission = ProbeValue("available", "session can query the system D-Bus")
    if not daemon_present:
        daemon = ProbeValue("unavailable", "org.bluez has no D-Bus owner")
        unknown = _uninspected("BlueZ daemon is unavailable")
        return BluezProbe(dbus, daemon, unknown, unknown, permission)

    daemon = ProbeValue("available", "org.bluez owns its system D-Bus name")
    try:
        names = adapter_names()
    except OSError:
        unknown = _uninspected("local Bluetooth adapter inventory could not be read")
        return BluezProbe(dbus, daemon, unknown, unknown, permission)

    if not names:
        adapter = ProbeValue("unavailable", "no local Bluetooth adapter was found")
        power = _uninspected("no Bluetooth adapter is available")
        return BluezProbe(dbus, daemon, adapter, power, permission)

    adapter = ProbeValue("available", f"found {len(names)} local Bluetooth adapter(s)")
    power_values: list[bool] = []
    power_uninspected = False
    for name in names:
        powered = query([
            busctl, "--system", "--json=short", "get-property",
            "org.bluez", f"/org/bluez/{name}", "org.bluez.Adapter1", "Powered",
        ])
        if powered is None or powered.returncode != 0:
            power_uninspected = True
            continue
        try:
            value = _single_value(_parse_busctl_data(powered.stdout))
        except (json.JSONDecodeError, ValueError, TypeError):
            power_uninspected = True
            continue
        if isinstance(value, bool):
            power_values.append(value)
        else:
            power_uninspected = True
    if any(power_values):
        power = ProbeValue("available", "at least one Bluetooth adapter is powered")
    elif power_uninspected or len(power_values) != len(names):
        power = _uninspected("one or more adapter power states were not reported")
    else:
        power = ProbeValue("unavailable", "all Bluetooth adapters are powered off")
    return BluezProbe(dbus, daemon, adapter, power, permission)


def diagnose(
    *,
    platform: str = sys.platform,
    python_version: tuple[int, int] = sys.version_info[:2],
    module_available: Callable[[str], bool] = _module_available,
    executable_available: Callable[[str], bool] = _executable_available,
    path_writable: Callable[[str], bool] = _path_writable,
    bluez_probe: Callable[[], BluezProbe] = probe_bluez,
) -> ReadinessReport:
    """Inspect local prerequisites without scanning, connecting, or using the network."""
    major, minor = python_version
    python_ok = python_version >= (3, 10)
    linux_ok = platform.startswith("linux")
    bleak_ok = module_available("bleak")
    bluez_ok = executable_available("bluetoothctl")
    evdev_ok = module_available("evdev")
    uinput_ok = path_writable("/dev/uinput")
    if linux_ok:
        bluez = bluez_probe()
    else:
        uninspected = _uninspected("BlueZ operation is not inspected off Linux")
        bluez = BluezProbe(uninspected, uninspected, uninspected, uninspected, uninspected)

    def operational_check(
        name: str, value: ProbeValue, remedy: str
    ) -> ReadinessCheck:
        return ReadinessCheck(
            name,
            value.state == "available",
            value.detail,
            None if value.state == "available" else remedy,
            value.state,
        )

    checks = (
        ReadinessCheck(
            "python",
            python_ok,
            f"Python {major}.{minor} is {'supported' if python_ok else 'too old'}",
            None if python_ok else "Install Python 3.10 or newer.",
        ),
        ReadinessCheck(
            "platform",
            linux_ok,
            "Linux hardware support is available" if linux_ok else f"{platform} hardware is not supported",
            None if linux_ok else "Use Linux with BlueZ for hardware access; simulation still works.",
        ),
        ReadinessCheck(
            "bleak",
            bleak_ok,
            "Bleak Python support is installed" if bleak_ok else "Bleak Python support is missing",
            None if bleak_ok else "From this repository, run: python -m pip install -e '.[ble]'",
        ),
        ReadinessCheck(
            "bluetoothctl",
            bluez_ok,
            "BlueZ tools are installed" if bluez_ok else "BlueZ bluetoothctl is missing",
            None if bluez_ok else "Install your distribution's BlueZ package (must provide bluetoothctl).",
        ),
        operational_check(
            "system_dbus",
            bluez.dbus,
            "Start or repair the system D-Bus using your distribution service manager; do not loosen socket permissions.",
        ),
        operational_check(
            "bluez_daemon",
            bluez.daemon,
            "Start the distribution-provided bluetoothd service, then rerun doctor.",
        ),
        operational_check(
            "bluetooth_adapter",
            bluez.adapter,
            "Attach or unblock a supported Bluetooth adapter, then rerun doctor.",
        ),
        operational_check(
            "adapter_power",
            bluez.power,
            "Power on Bluetooth through the desktop settings or bluetoothctl, then rerun doctor.",
        ),
        operational_check(
            "bluez_permission",
            bluez.permission,
            "Use a local desktop/logind session or a narrowly scoped polkit rule; do not run JRing as root.",
        ),
        ReadinessCheck(
            "evdev",
            evdev_ok,
            "Python evdev support is installed" if evdev_ok else "Python evdev support is missing",
            None if evdev_ok else "From this repository, run: python -m pip install -e '.[input]'",
        ),
        ReadinessCheck(
            "uinput",
            uinput_ok,
            "/dev/uinput is writable" if uinput_ok else "/dev/uinput is unavailable to this user",
            None if uinput_ok else "Enable Linux uinput and grant this user access to /dev/uinput.",
        ),
    )
    simulator_ready = python_ok
    hardware_ready = python_ok and linux_ok and bleak_ok and bluez_ok
    adapter_operational = all(
        value.state == "available"
        for value in (bluez.dbus, bluez.daemon, bluez.adapter, bluez.power, bluez.permission)
    )
    input_ready = python_ok and linux_ok and evdev_ok and uinput_ok
    if hardware_ready and adapter_operational:
        next_step = "jring discover --active-scan"
    elif hardware_ready:
        next_step = next(
            check.remedy for check in checks
            if check.name in {
                "system_dbus", "bluez_daemon", "bluetooth_adapter",
                "adapter_power", "bluez_permission",
            } and not check.ok and check.remedy
        )
    elif simulator_ready:
        next_step = "jring status --simulate"
    else:
        next_step = "Install Python 3.10 or newer"
    return ReadinessReport(
        checks,
        simulator_ready,
        hardware_ready,
        input_ready,
        next_step,
        adapter_operational=adapter_operational,
        ring_compatibility="not_checked",
    )
