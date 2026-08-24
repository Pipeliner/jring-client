from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    ok: bool
    detail: str
    remedy: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadinessReport:
    checks: tuple[ReadinessCheck, ...]
    simulator_ready: bool
    hardware_ready: bool
    input_ready: bool
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [check.to_dict() for check in self.checks],
            "simulator_ready": self.simulator_ready,
            "hardware_ready": self.hardware_ready,
            "input_ready": self.input_ready,
            "next_step": self.next_step,
        }


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _executable_available(name: str) -> bool:
    return shutil.which(name) is not None


def _path_writable(path: str) -> bool:
    return os.path.exists(path) and os.access(path, os.W_OK)


def diagnose(
    *,
    platform: str = sys.platform,
    python_version: tuple[int, int] = sys.version_info[:2],
    module_available: Callable[[str], bool] = _module_available,
    executable_available: Callable[[str], bool] = _executable_available,
    path_writable: Callable[[str], bool] = _path_writable,
) -> ReadinessReport:
    """Inspect local prerequisites without scanning, connecting, or using the network."""
    major, minor = python_version
    python_ok = python_version >= (3, 10)
    linux_ok = platform.startswith("linux")
    bleak_ok = module_available("bleak")
    bluez_ok = executable_available("bluetoothctl")
    evdev_ok = module_available("evdev")
    uinput_ok = path_writable("/dev/uinput")

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
    input_ready = python_ok and linux_ok and evdev_ok and uinput_ok
    if hardware_ready:
        next_step = "jring discover --active-scan"
    elif simulator_ready:
        next_step = "jring status --simulate"
    else:
        next_step = "Install Python 3.10 or newer"
    return ReadinessReport(checks, simulator_ready, hardware_ready, input_ready, next_step)
