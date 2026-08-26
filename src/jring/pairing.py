"""Explicit, local BlueZ pairing with conservative outcome reporting."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess


_MAC = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")
_BLUEZ_PATH = re.compile(r"/org/bluez(?:/[A-Za-z0-9_]+)+")


@dataclass(frozen=True)
class PairingResult:
    status: str
    detail: str


def _sanitize(text: str) -> str:
    text = _MAC.sub("[redacted device]", text)
    return _BLUEZ_PATH.sub("[redacted Bluetooth path]", text).strip()


def pair_device(
    address: str, *, timeout: float, allow_pairing: bool, allow_trust: bool = False
) -> PairingResult:
    """Pair exactly one selected address through BlueZ, without trusting it.

    The caller must provide explicit pairing consent. A timeout is uncertain and
    deliberately not retried because the OS may have completed the operation.
    """

    if not allow_pairing:
        return PairingResult("consent_required", "pairing requires --allow-pairing")
    if shutil.which("bluetoothctl") is None:
        return PairingResult("unavailable", "bluetoothctl is not installed")
    def run_action(action: str) -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["bluetoothctl", action, address],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None
        except OSError as exc:
            raise RuntimeError(_sanitize(str(exc)) or "bluetoothctl unavailable") from exc

    try:
        completed = run_action("pair")
        if completed is None:
            return PairingResult(
                "timed_out",
                "pairing outcome is uncertain; inspect BlueZ state before another attempt",
            )
        output = _sanitize(" ".join(part for part in (completed.stdout, completed.stderr) if part))
        lowered = output.lower()
        paired = completed.returncode == 0 and ("successful" in lowered or "already" in lowered or lowered == "success")
        if not paired:
            if "not available" in lowered or "no default controller" in lowered:
                return PairingResult("unavailable", "BlueZ could not access a usable adapter")
            return PairingResult("rejected", "BlueZ rejected pairing; trust was not changed")
        if not allow_trust:
            return PairingResult(
                "already_paired" if "already" in lowered else "paired",
                "BlueZ reports the selected device is paired; trust was not changed",
            )
        trusted = run_action("trust")
        if trusted is None:
            return PairingResult("trust_timed_out", "trust outcome is uncertain; inspect BlueZ state before another attempt")
        trust_output = _sanitize(" ".join(part for part in (trusted.stdout, trusted.stderr) if part)).lower()
        if trusted.returncode == 0 and ("successful" in trust_output or "trust succeeded" in trust_output or trust_output == "success"):
            return PairingResult("trusted", "BlueZ paired and trusted the selected device")
        return PairingResult("trust_rejected", "BlueZ pairing succeeded but trust was rejected")
    except RuntimeError as exc:
        return PairingResult("unavailable", str(exc))


def trust_device(address: str, *, timeout: float, allow_trust: bool) -> PairingResult:
    """Trust one already-paired address; never invokes pairing."""
    if not allow_trust:
        return PairingResult("consent_required", "trust requires explicit consent")
    if shutil.which("bluetoothctl") is None:
        return PairingResult("unavailable", "bluetoothctl is not installed")
    try:
        completed = subprocess.run(
            ["bluetoothctl", "trust", address], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return PairingResult("trust_timed_out", "trust outcome is uncertain; inspect BlueZ state before another attempt")
    except OSError as exc:
        return PairingResult("unavailable", _sanitize(str(exc)) or "bluetoothctl unavailable")
    output = _sanitize(" ".join(part for part in (completed.stdout, completed.stderr) if part)).lower()
    if completed.returncode == 0 and ("successful" in output or "trust succeeded" in output or output == "success"):
        return PairingResult("trusted", "BlueZ reports the selected device is trusted")
    return PairingResult("trust_rejected", "BlueZ rejected trust; pairing was not changed")
