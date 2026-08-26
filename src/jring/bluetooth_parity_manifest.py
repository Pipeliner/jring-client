"""Deterministic clean-room Bluetooth parity manifest.

The manifest is an accounting boundary, not a support list.  It turns the separate
static ledgers into one closed population so a green request/callback count cannot
hide a missing transport, platform, session, or excluded surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vendor_coverage import static_vendor_callback_coverage, static_vendor_operation_coverage
from .vendor_session_evidence import recovered_session_evidence


class ParitySurfaceFamily(str, Enum):
    REQUEST = "request"
    CALLBACK = "callback"
    STANDARD_GATT = "standard_gatt"
    VENDOR_GATT = "vendor_gatt"
    PLATFORM_BLUETOOTH = "platform_bluetooth"
    SESSION = "session"
    BINDING = "binding"
    OTA_TRANSFER = "ota_transfer"
    EXCLUDED_NON_RING = "excluded_non_ring"


class ParityTerminalStatus(str, Enum):
    OFFLINE_ONLY = "offline_only"
    NOT_ESTABLISHED = "not_established"
    EXCLUDED_NON_RING = "excluded_non_ring"


class BluetoothParityManifestError(ValueError):
    pass


@dataclass(frozen=True, init=False, repr=False)
class BluetoothParityManifestRow:
    identifier: str
    family: ParitySurfaceFamily
    specification: str
    tracker_issue: int
    terminal_status: ParityTerminalStatus
    implementation_evidence: str
    model_firmware_scope: str

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("bluetooth parity rows are closed")


@dataclass(frozen=True, init=False, repr=False)
class BluetoothParityManifest:
    schema_version: int
    rows: tuple[BluetoothParityManifestRow, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("bluetooth parity manifest is closed")

    @property
    def complete(self) -> bool:
        return bool(self.rows) and all(
            row.terminal_status is ParityTerminalStatus.EXCLUDED_NON_RING
            for row in self.rows
        )


_PLATFORM_ROWS = (
    ("standard-gatt:device-information", ParitySurfaceFamily.STANDARD_GATT, "APK_TRANSPORT_SPEC.md", 50),
    ("standard-gatt:heart-rate", ParitySurfaceFamily.STANDARD_GATT, "APK_TRANSPORT_SPEC.md", 50),
    ("standard-gatt:cccd", ParitySurfaceFamily.STANDARD_GATT, "APK_TRANSPORT_SPEC.md", 50),
    ("vendor-gatt:main-route", ParitySurfaceFamily.VENDOR_GATT, "APK_TRANSPORT_SPEC.md", 35),
    ("vendor-gatt:raw-route", ParitySurfaceFamily.VENDOR_GATT, "APK_TRANSPORT_SPEC.md", 35),
    ("vendor-gatt:secondary-route", ParitySurfaceFamily.VENDOR_GATT, "APK_TRANSPORT_SPEC.md", 50),
    ("vendor-gatt:suota", ParitySurfaceFamily.VENDOR_GATT, "APK_OTA_SPEC.md", 47),
    ("platform:scan-link-discovery", ParitySurfaceFamily.PLATFORM_BLUETOOTH, "APK_PLATFORM_SPEC.md", 50),
    ("platform:dynamic-gatt", ParitySurfaceFamily.PLATFORM_BLUETOOTH, "APK_PLATFORM_SPEC.md", 50),
    ("platform:classic-bond-rfcomm", ParitySurfaceFamily.PLATFORM_BLUETOOTH, "APK_PLATFORM_SPEC.md", 50),
    ("ota-transfer:firmware-and-phone-transfer", ParitySurfaceFamily.OTA_TRANSFER, "APK_OTA_SPEC.md", 47),
)
_EXCLUDED = frozenset({"getDialServerInfo", "openSDKLog", "registerCallback", "registerCallback2", "saveFileToSystemAlbum", "setOption", "setScanMode", "translateBmpToBin", "unregisterCallback"})


def _row(**values: object) -> BluetoothParityManifestRow:
    result = object.__new__(BluetoothParityManifestRow)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def _validate(rows: tuple[BluetoothParityManifestRow, ...]) -> None:
    if not rows or len({row.identifier for row in rows}) != len(rows):
        raise BluetoothParityManifestError("duplicate_or_empty_parity_surface")
    required = set(ParitySurfaceFamily)
    present = {row.family for row in rows}
    if required - present:
        raise BluetoothParityManifestError("missing_parity_surface_family")
    if any(not row.specification.endswith(".md") or row.tracker_issue <= 0 for row in rows):
        raise BluetoothParityManifestError("invalid_parity_evidence_link")


def _build_manifest() -> BluetoothParityManifest:
    requests = static_vendor_operation_coverage()
    callbacks = static_vendor_callback_coverage()
    sessions = recovered_session_evidence()
    rows = tuple(
        _row(identifier=f"request:{item.name}", family=(ParitySurfaceFamily.EXCLUDED_NON_RING if item.name in _EXCLUDED else ParitySurfaceFamily.REQUEST), specification="APK_REQUEST_SPEC.md", tracker_issue=(51 if item.name in _EXCLUDED else 48), terminal_status=(ParityTerminalStatus.EXCLUDED_NON_RING if item.name in _EXCLUDED else ParityTerminalStatus.OFFLINE_ONLY), implementation_evidence=item.evidence_locator or "static-ledger-only", model_firmware_scope="clean-room-static")
        for item in requests
    ) + tuple(
        _row(identifier=f"callback:{item.name}", family=ParitySurfaceFamily.CALLBACK, specification="APK_CALLBACK_SPEC.md", tracker_issue=48, terminal_status=ParityTerminalStatus.OFFLINE_ONLY, implementation_evidence=item.evidence_locator or "static-ledger-only", model_firmware_scope="clean-room-static")
        for item in callbacks
    ) + tuple(
        _row(identifier=name, family=family, specification=spec, tracker_issue=issue, terminal_status=ParityTerminalStatus.NOT_ESTABLISHED, implementation_evidence="static-artifact-evidence", model_firmware_scope="clean-room-static")
        for name, family, spec, issue in _PLATFORM_ROWS
    ) + tuple(
        _row(identifier=f"session:{item.code.value}", family=ParitySurfaceFamily.SESSION, specification="APK_SESSION_SPEC.md", tracker_issue=52, terminal_status=ParityTerminalStatus.NOT_ESTABLISHED, implementation_evidence="vendor-session-evidence", model_firmware_scope="clean-room-static")
        for item in sessions.transitions
    ) + tuple(
        _row(identifier=f"binding:{index}", family=ParitySurfaceFamily.BINDING, specification="APK_BINDING_SPEC.md", tracker_issue=24, terminal_status=ParityTerminalStatus.NOT_ESTABLISHED, implementation_evidence="vendor-session-evidence", model_firmware_scope="clean-room-static")
        for index, _item in enumerate(sessions.binding_reactions, 1)
    )
    _validate(rows)
    manifest = object.__new__(BluetoothParityManifest)
    object.__setattr__(manifest, "schema_version", 1)
    object.__setattr__(manifest, "rows", tuple(sorted(rows, key=lambda row: row.identifier)))
    return manifest


_MANIFEST = _build_manifest()


def recovered_bluetooth_parity_manifest() -> BluetoothParityManifest:
    return _MANIFEST


def bluetooth_parity_manifest_payload() -> dict[str, object]:
    manifest = recovered_bluetooth_parity_manifest()
    return {"schema_version": manifest.schema_version, "complete": manifest.complete, "row_count": len(manifest.rows), "rows": [{"id": row.identifier, "family": row.family.value, "specification": row.specification, "tracker_issue": row.tracker_issue, "terminal_status": row.terminal_status.value, "implementation_evidence": row.implementation_evidence, "model_firmware_scope": row.model_firmware_scope} for row in manifest.rows]}


__all__ = ["BluetoothParityManifest", "BluetoothParityManifestError", "BluetoothParityManifestRow", "ParitySurfaceFamily", "ParityTerminalStatus", "bluetooth_parity_manifest_payload", "recovered_bluetooth_parity_manifest"]
