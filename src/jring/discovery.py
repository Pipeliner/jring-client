import re

from .diagnostics import Redactor
from .errors import UnavailableError


_ADDRESS = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


def select_exact(address: str | None) -> str:
    if not address or not _ADDRESS.fullmatch(address):
        raise ValueError("an explicit Bluetooth address is required")
    return address.upper()


async def discover(*, timeout: float = 5.0) -> list[dict[str, object]]:
    """Active radio scan returning redacted, non-selectable summaries."""
    if not 0 < timeout <= 30:
        raise ValueError("discovery timeout must be between 0 and 30 seconds")
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise UnavailableError("discovery requires: pip install '.[ble]'") from exc
    redactor = Redactor()
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    results = []
    for address, (device, advertisement) in found.items():
        services = sorted(value.lower() for value in (advertisement.service_uuids or []))
        # Names can contain stable identifiers; report only a coarse likely-JRing flag.
        name = (device.name or advertisement.local_name or "").lower()
        results.append({"alias": redactor.address(address), "likely_jring": "jring" in name,
                        "service_uuids": services, "rssi": advertisement.rssi})
    return sorted(results, key=lambda item: str(item["alias"]))
