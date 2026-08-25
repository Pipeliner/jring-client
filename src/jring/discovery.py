import re
from dataclasses import dataclass, field
from typing import Iterable

from .diagnostics import Redactor
from .errors import UnavailableError


_ADDRESS = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


@dataclass(frozen=True)
class DiscoveryObservation:
    address: str = field(repr=False)
    name: str = field(repr=False)
    service_uuids: tuple[str, ...]
    rssi: int | None


@dataclass(frozen=True)
class SelectionCandidate:
    alias: str
    likely_jring: bool
    service_uuids: tuple[str, ...]
    rssi: int | None
    _address: str = field(repr=False, compare=False)

    def public_summary(self) -> dict[str, object]:
        return {
            "alias": self.alias,
            "likely_jring": self.likely_jring,
            "likely_jring_basis": "client_name_heuristic",
            "service_uuids": list(self.service_uuids),
            "rssi": self.rssi,
        }

    def connection_address(self) -> str:
        """Return the private address only for an explicitly confirmed connection."""
        return self._address


def select_exact(address: str | None) -> str:
    if not address or not _ADDRESS.fullmatch(address):
        raise ValueError("an explicit Bluetooth address is required")
    return address.upper()


def build_selection_candidates(
    observations: Iterable[DiscoveryObservation], *, salt: bytes | None = None
) -> list[SelectionCandidate]:
    redactor = Redactor(salt=salt)
    results = [
        SelectionCandidate(
            alias=redactor.address(observation.address),
            likely_jring="jring" in observation.name.lower(),
            service_uuids=tuple(sorted(value.lower() for value in observation.service_uuids)),
            rssi=observation.rssi,
            _address=select_exact(observation.address),
        )
        for observation in observations
    ]
    return sorted(results, key=lambda item: item.alias)


async def _scan(*, timeout: float) -> tuple[DiscoveryObservation, ...]:
    if not 0 < timeout <= 30:
        raise ValueError("discovery timeout must be between 0 and 30 seconds")
    try:
        from bleak import BleakScanner
    except ImportError as exc:
        raise UnavailableError("discovery requires: pip install '.[ble]'") from exc
    found = await BleakScanner.discover(timeout=timeout, return_adv=True)
    observations = []
    for address, (device, advertisement) in found.items():
        observations.append(DiscoveryObservation(
            address=address,
            name=device.name or advertisement.local_name or "",
            service_uuids=tuple(advertisement.service_uuids or ()),
            rssi=advertisement.rssi,
        ))
    return tuple(observations)


async def discover(*, timeout: float = 5.0) -> list[dict[str, object]]:
    """Active radio scan returning redacted, non-selectable summaries."""
    candidates = build_selection_candidates(await _scan(timeout=timeout))
    return [candidate.public_summary() for candidate in candidates]


async def discover_for_selection(*, timeout: float = 5.0) -> list[SelectionCandidate]:
    """Scan once and retain private addresses only for same-process confirmation."""
    return build_selection_candidates(await _scan(timeout=timeout))
