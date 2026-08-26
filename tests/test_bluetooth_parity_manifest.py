from dataclasses import FrozenInstanceError

import pytest

from jring.bluetooth_parity_manifest import (
    BluetoothParityManifestRow,
    ParitySurfaceFamily,
    ParityTerminalStatus,
    bluetooth_parity_manifest_payload,
    recovered_bluetooth_parity_manifest,
)
from jring.vendor_coverage import static_vendor_callback_coverage, static_vendor_operation_coverage
from jring.vendor_session_evidence import recovered_session_evidence


def test_manifest_reconciles_every_existing_clean_room_bluetooth_ledger():
    manifest = recovered_bluetooth_parity_manifest()
    rows = {row.identifier: row for row in manifest.rows}
    assert manifest.schema_version == 1
    assert len(rows) == len(manifest.rows)
    assert {name.removeprefix("request:") for name in rows if name.startswith("request:")} == {item.name for item in static_vendor_operation_coverage()}
    assert {name.removeprefix("callback:") for name in rows if name.startswith("callback:")} == {item.name for item in static_vendor_callback_coverage()}
    assert sum(name.startswith("session:") for name in rows) == len(recovered_session_evidence().transitions)
    assert sum(name.startswith("binding:") for name in rows) == len(recovered_session_evidence().binding_reactions)
    assert {row.family for row in rows.values()} == set(ParitySurfaceFamily)
    assert manifest.complete is False


def test_manifest_has_a_linked_terminal_disposition_for_every_row_without_claiming_hardware():
    payload = bluetooth_parity_manifest_payload()
    assert payload["complete"] is False
    assert payload["row_count"] == len(payload["rows"])
    assert all(row["specification"].endswith(".md") and row["tracker_issue"] > 0 for row in payload["rows"])
    assert all(row["model_firmware_scope"] == "clean-room-static" for row in payload["rows"])
    assert {row["terminal_status"] for row in payload["rows"]} <= {item.value for item in ParityTerminalStatus}
    assert all("hardware" not in row for row in payload["rows"])


def test_manifest_rows_are_closed_and_excluded_android_plumbing_is_explicit():
    row = recovered_bluetooth_parity_manifest().rows[0]
    with pytest.raises(TypeError, match="closed"):
        BluetoothParityManifestRow()
    with pytest.raises(FrozenInstanceError):
        row.identifier = "forged"
    excluded = [row for row in recovered_bluetooth_parity_manifest().rows if row.family is ParitySurfaceFamily.EXCLUDED_NON_RING]
    assert len(excluded) == 9
    assert all(row.terminal_status is ParityTerminalStatus.EXCLUDED_NON_RING for row in excluded)
