"""Closed ownership ledger for bounded clean-room analysis gaps (#53)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CleanRoomGapDisposition(str, Enum):
    TRACKED_ANALYSIS = "tracked_analysis"
    OWNER_HARDWARE_EVIDENCE = "owner_hardware_evidence"
    EXPLICIT_NON_BLUETOOTH_BOUNDARY = "explicit_non_bluetooth_boundary"


@dataclass(frozen=True, init=False, repr=False)
class CleanRoomGap:
    identifier: str
    specification: str
    disposition: CleanRoomGapDisposition
    tracker_issue: int
    bluetooth_relevance: str

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("clean-room gaps are closed")


_GAPS = (
    ("native-unresolved-declarations", "APK_FUNCTIONAL_SPEC.md", "tracked_analysis", 53, "possible_transitive_bluetooth_binding"),
    ("resource-and-locale-activation", "APK_FUNCTIONAL_SPEC.md", "tracked_analysis", 53, "activation_scope_unknown"),
    ("dynamic-receiver-and-reflection-activation", "APK_FUNCTIONAL_SPEC.md", "tracked_analysis", 53, "activation_scope_unknown"),
    ("warning-sensitive-app-branches", "APK_UI_SPEC.md", "tracked_analysis", 53, "may_precede_bluetooth_projection"),
    ("unknown-selector-meanings", "APK_FUNCTIONAL_SPEC.md", "owner_hardware_evidence", 55, "protocol_semantics_unknown"),
    ("firmware-model-matrix", "APK_FUNCTIONAL_SPEC.md", "owner_hardware_evidence", 57, "runtime_scope_unknown"),
    ("peripheral-delivery-and-terminal-order", "APK_REQUEST_SPEC.md", "owner_hardware_evidence", 35, "live_transaction_unknown"),
    ("vendor-authorization-and-server-outcomes", "APK_FUNCTIONAL_SPEC.md", "owner_hardware_evidence", 23, "vendor_gate_unknown"),
    ("ota-runtime-contract", "APK_OTA_SPEC.md", "owner_hardware_evidence", 47, "firmware_delivery_unknown"),
    ("runtime-permission-api-branches", "APK_PLATFORM_SPEC.md", "tracked_analysis", 53, "platform_activation_unknown"),
    ("uri-resolution-edge-contract", "APK_UI_SPEC.md", "explicit_non_bluetooth_boundary", 53, "non_bluetooth_platform_only"),
    ("google-fit-query-edge-contract", "APK_UI_SPEC.md", "explicit_non_bluetooth_boundary", 53, "non_bluetooth_platform_only"),
)


def recovered_clean_room_gaps() -> tuple[CleanRoomGap, ...]:
    rows = []
    for identifier, specification, disposition, issue, relevance in _GAPS:
        row = object.__new__(CleanRoomGap)
        object.__setattr__(row, "identifier", identifier)
        object.__setattr__(row, "specification", specification)
        object.__setattr__(row, "disposition", CleanRoomGapDisposition(disposition))
        object.__setattr__(row, "tracker_issue", issue)
        object.__setattr__(row, "bluetooth_relevance", relevance)
        rows.append(row)
    if len({row.identifier for row in rows}) != len(rows) or any(row.tracker_issue <= 0 for row in rows):
        raise RuntimeError("unowned_clean_room_gap")
    return tuple(rows)


def clean_room_gap_payload() -> dict[str, object]:
    rows = recovered_clean_room_gaps()
    return {"schema_version": 1, "complete": False, "gap_count": len(rows), "gaps": [{"id": row.identifier, "specification": row.specification, "disposition": row.disposition.value, "tracker_issue": row.tracker_issue, "bluetooth_relevance": row.bluetooth_relevance} for row in rows]}
