from collections import Counter
from dataclasses import FrozenInstanceError, asdict
import json

import pytest

from jring.vendor_codec_registry import REQUEST_CODEC_LOCATORS
from jring.vendor_request_callback_correlation import (
    recovered_request_callback_correlations,
)
from jring.vendor_runtime_eligibility import (
    FakeSingletonEligibilityState,
    VendorFakeSingletonEligibilityRow,
    fake_singleton_terminal_request_names,
    recovered_vendor_fake_singleton_eligibility,
    require_fake_singleton_terminal,
)
from jring.vendor_transport import fake_singleton_factory_request_names


TYPED_NONTERMINAL_PROJECTIONS = frozenset(
    {
        "setAiConnectionMethod",
        "setBindedInfo",
        "setBloodOxygenMode",
        "setEcgMode",
        "setEqInfo2",
        "setOfflineSpeechRecognitionState",
        "setTemperatureMode",
        "setTouchMode",
        "startFactoryTestMode",
        "openWifiApMode",
        "setWorshipInfo",
    }
)

AMBIGUOUS_OR_BATCHED_PER_FRAME = frozenset(
    {
        "setAlarm",
        "setNotify",
        "setBloodPressureMode",
        "setSpoMode",
        "setSugarMode",
        "setPressureMode",
    }
)


def test_every_deterministic_codec_has_one_closed_fake_singleton_eligibility_row():
    evidence = recovered_vendor_fake_singleton_eligibility()
    rows = {row.request: row for row in evidence.rows}

    assert len(evidence.rows) == len(rows) == 85
    assert set(rows) == set(REQUEST_CODEC_LOCATORS)
    assert Counter(row.state for row in evidence.rows) == {
        FakeSingletonEligibilityState.SINGLETON_MATCHED_TERMINAL: 36,
        FakeSingletonEligibilityState.TYPED_NONTERMINAL_PROJECTION: 11,
        FakeSingletonEligibilityState.AMBIGUOUS_OR_BATCHED_PER_FRAME: 6,
        FakeSingletonEligibilityState.NO_PROVEN_TERMINAL: 29,
        FakeSingletonEligibilityState.LOCAL_OR_MARKER_BOUNDED_STREAM: 3,
    }
    assert evidence.singleton_terminal_count == 36
    assert evidence.runnable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert evidence.eligibility_scope == "fake_singleton_only"
    assert evidence.live_eligible is False
    assert evidence.owner_authorized is False
    assert fake_singleton_terminal_request_names() == frozenset(
        request
        for request, row in rows.items()
        if row.state is FakeSingletonEligibilityState.SINGLETON_MATCHED_TERMINAL
    )
    assert (
        fake_singleton_factory_request_names()
        == fake_singleton_terminal_request_names()
    )


def test_singleton_eligibility_requires_a_proven_wire_terminal():
    correlations = {
        row.request: row
        for row in recovered_request_callback_correlations().rows
    }
    rows = {
        row.request: row
        for row in recovered_vendor_fake_singleton_eligibility().rows
    }

    assert {
        request
        for request, row in rows.items()
        if row.state is FakeSingletonEligibilityState.TYPED_NONTERMINAL_PROJECTION
    } == TYPED_NONTERMINAL_PROJECTIONS
    assert {
        request
        for request, row in rows.items()
        if row.state is FakeSingletonEligibilityState.AMBIGUOUS_OR_BATCHED_PER_FRAME
    } == AMBIGUOUS_OR_BATCHED_PER_FRAME

    for request, row in rows.items():
        correlation = correlations[request]
        if row.singleton_factory_eligible:
            assert row.state is FakeSingletonEligibilityState.SINGLETON_MATCHED_TERMINAL
            assert correlation.terminal_rule == "single_matched_response"
            assert correlation.callbacks
            assert correlation.accepted_response_predicates
            assert correlation.relationship_state in {"exact_single", "exact_branching"}
            assert require_fake_singleton_terminal(request) is row
        else:
            with pytest.raises(TypeError, match=row.state.value):
                require_fake_singleton_terminal(request)


def test_fake_singleton_eligibility_schema_is_static_redacted_and_immutable():
    evidence = recovered_vendor_fake_singleton_eligibility()
    row = evidence.rows[0]
    serialized = [asdict(item) for item in evidence.rows]
    rendered = json.dumps(serialized, sort_keys=True)

    assert set().union(*(item.keys() for item in serialized)).isdisjoint(
        {"payload", "frame", "address", "path"}
    )
    assert "bluetooth_address" not in rendered
    assert all(item.maturity == "static_apk_only" for item in evidence.rows)
    assert all(item.eligibility_scope == "fake_singleton_only" for item in evidence.rows)
    assert all(item.runnable is False for item in evidence.rows)
    assert all(item.live_eligible is False for item in evidence.rows)
    assert all(item.owner_authorized is False for item in evidence.rows)
    assert all(item.hardware_eligible is False for item in evidence.rows)
    assert all(item.hardware_verified is False for item in evidence.rows)
    with pytest.raises(FrozenInstanceError):
        row.singleton_factory_eligible = True
    with pytest.raises(TypeError, match="closed"):
        VendorFakeSingletonEligibilityRow()
