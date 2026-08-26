from dataclasses import FrozenInstanceError

import pytest

from jring.vendor_callback_event_registry import (
    CallbackEventRegistryRow,
    callback_event_registry_payload,
    recovered_callback_event_registry,
)
from jring.vendor_coverage import static_vendor_callback_coverage


def test_every_callback_has_one_closed_non_authorizing_event_row():
    rows = recovered_callback_event_registry()
    assert len(rows) == len(static_vendor_callback_coverage()) == 105
    assert {row.callback_id for row in rows} == {row.name for row in static_vendor_callback_coverage()}
    assert all(row.origin and row.privacy and row.confidence and row.ordering_policy for row in rows)
    assert all(not row.input_eligible and not row.live_eligible for row in rows)


def test_callback_registry_is_closed_and_payload_is_authority_free():
    row = recovered_callback_event_registry()[0]
    with pytest.raises(TypeError, match="closed"):
        CallbackEventRegistryRow()
    with pytest.raises(FrozenInstanceError):
        row.live_eligible = True
    payload = callback_event_registry_payload()
    assert payload["callback_count"] == 105
    assert payload["live_eligible_count"] == payload["input_eligible_count"] == 0
