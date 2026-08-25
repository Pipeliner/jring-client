from collections import Counter
from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_app_use_evidence as app_use_module
from jring.vendor_app_use_evidence import (
    CallbackDispatchState,
    RequestAppUseState,
    recovered_vendor_app_use_evidence,
)
from jring.vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)


def test_every_request_has_one_exact_app_use_classification():
    evidence = recovered_vendor_app_use_evidence()

    assert len(evidence.requests) == 112
    assert len({row.name for row in evidence.requests}) == 112
    assert {row.name for row in evidence.requests} == {
        row.name for row in static_vendor_operation_coverage()
    }
    assert Counter(row.state for row in evidence.requests) == {
        RequestAppUseState.DIRECT_APP_INTERFACE_INVOKE: 51,
        RequestAppUseState.SDK_WIRE_ENTRY_WITHOUT_APP_INVOKE: 43,
        RequestAppUseState.SDK_LOCAL_COMPOSITE_WITHOUT_APP_INVOKE: 14,
        RequestAppUseState.NO_OP_STUB_WITHOUT_APP_INVOKE: 4,
    }


def test_direct_app_use_counts_are_occurrences_not_distinct_methods():
    evidence = recovered_vendor_app_use_evidence()
    rows = {row.name: row for row in evidence.requests}

    assert evidence.direct_request_target_count == 51
    assert evidence.direct_request_invoke_count == 152
    assert rows["isConnectBt"].direct_invoke_count == 16
    assert rows["setOption"].direct_invoke_count == 11
    assert rows["getDeviceInfo"].direct_invoke_count == 1
    assert all(
        row.direct_invoke_count == 0
        for row in evidence.requests
        if row.state is not RequestAppUseState.DIRECT_APP_INTERFACE_INVOKE
    )


def test_every_callback_is_directly_dispatched_or_explicitly_unobserved():
    evidence = recovered_vendor_app_use_evidence()

    assert len(evidence.callbacks) == 105
    assert len({row.name for row in evidence.callbacks}) == 105
    assert {row.name for row in evidence.callbacks} == {
        row.name for row in static_vendor_callback_coverage()
    }
    assert Counter(row.state for row in evidence.callbacks) == {
        CallbackDispatchState.DIRECT_SDK_DISPATCH: 103,
        CallbackDispatchState.DECLARED_WITHOUT_DIRECT_DISPATCH: 2,
    }
    assert {
        row.name
        for row in evidence.callbacks
        if row.state is CallbackDispatchState.DECLARED_WITHOUT_DIRECT_DISPATCH
    } == {"onGetDeviceTime", "onSendWeather"}


def test_request_and_callback_namespaces_remain_descriptor_distinct():
    evidence = recovered_vendor_app_use_evidence()

    assert evidence.cross_namespace_name_collisions == ("setAutoHeartMode",)
    request = next(row for row in evidence.requests if row.name == "setAutoHeartMode")
    callback = next(row for row in evidence.callbacks if row.name == "setAutoHeartMode")
    assert request.interface_role == "request"
    assert callback.interface_role == "callback"


def test_app_use_evidence_is_closed_sanitized_and_non_runnable():
    evidence = recovered_vendor_app_use_evidence()

    with pytest.raises(TypeError):
        type(evidence)()
    with pytest.raises(TypeError):
        type(evidence.requests[0])()
    with pytest.raises(TypeError):
        type(evidence.callbacks[0])()
    with pytest.raises(FrozenInstanceError):
        evidence.requests = ()
    forbidden = {
        "source", "path", "descriptor", "prototype", "fingerprint",
        "instruction_offset", "dex_digest", "payload", "frame",
    }
    for model in (type(evidence), type(evidence.requests[0]), type(evidence.callbacks[0])):
        assert forbidden.isdisjoint(field.name for field in fields(model))
    serialized = json.dumps(asdict(evidence), sort_keys=True).lower()
    assert "sha256" not in serialized
    assert ".smali" not in serialized
    source = inspect.getsource(app_use_module).lower()
    assert "bleak" not in source
    assert "import subprocess" not in source
    assert "open(" not in source
    assert evidence.dynamic_request_interface_invokes_observed is False
    assert evidence.runnable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
