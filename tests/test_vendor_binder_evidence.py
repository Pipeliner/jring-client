from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_binder_evidence as binder_module
from jring.vendor_binder_evidence import (
    BinderDirection,
    recovered_vendor_binder_evidence,
)
from jring.vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)


def test_request_and_callback_binder_surfaces_have_exact_contiguous_parity():
    evidence = recovered_vendor_binder_evidence()
    request = evidence.request
    callback = evidence.callback

    assert request.direction is BinderDirection.REQUEST
    assert request.transaction_ids == tuple(range(1, 113))
    assert [row.transaction_id for row in request.rows] == list(range(1, 113))
    assert {row.ledger_name for row in request.rows} == {
        row.name for row in static_vendor_operation_coverage()
    }
    assert request.declaration_count == 112
    assert request.proxy_method_count == 112
    assert request.stub_dispatch_count == 112
    assert request.implementation_count == 112
    assert callback.direction is BinderDirection.CALLBACK
    assert callback.transaction_ids == tuple(range(1, 106))
    assert [row.transaction_id for row in callback.rows] == list(range(1, 106))
    assert {row.ledger_name for row in callback.rows} == {
        row.name for row in static_vendor_callback_coverage()
    }
    assert callback.declaration_count == 105
    assert callback.proxy_method_count == 105
    assert callback.stub_dispatch_count == 105
    assert callback.implementation_count == 105
    assert evidence.total_transaction_count == 217


def test_every_binder_transaction_is_synchronous_and_parcel_order_matches():
    evidence = recovered_vendor_binder_evidence()
    request = evidence.request
    callback = evidence.callback

    for surface in (request, callback):
        assert surface.synchronous_transaction_count == surface.declaration_count
        assert surface.one_way_transaction_count == 0
        assert surface.reply_parcel_count == surface.declaration_count
        assert surface.exception_handshake_count == surface.declaration_count
        assert surface.proxy_stub_id_mismatch_count == 0
        assert surface.prototype_mismatch_count == 0
        assert surface.parcel_order_mismatch_count == 0
        assert surface.overloaded_method_count == 0
        assert all(row.call_mode == "synchronous" for row in surface.rows)
        assert all(
            row.interface_proxy_stub_implementation_match is True
            for row in surface.rows
        )
    assert request.distinct_semantic_shape_count == 36
    assert request.distinct_parcel_shape_count == 28
    assert callback.distinct_semantic_shape_count == 33
    assert callback.distinct_parcel_shape_count == 31
    assert evidence.trailing_data_rejection_observed is False


def test_binder_return_and_arity_counts_are_exact_and_not_semantic_aliases():
    evidence = recovered_vendor_binder_evidence()

    assert dict(evidence.request.semantic_result_kind_counts) == {
        "int32": 102,
        "void": 6,
        "string": 2,
        "bool": 2,
    }
    assert dict(evidence.request.parcel_result_kind_counts) == {
        "int32": 104, "void": 6, "string": 2,
    }
    assert dict(evidence.callback.semantic_result_kind_counts) == {
        "void": 103, "int32": 2,
    }
    assert dict(evidence.request.arity_counts) == {
        0: 27, 1: 54, 2: 11, 3: 6, 4: 7, 5: 2, 6: 1, 7: 2, 8: 1, 16: 1,
    }
    assert dict(evidence.callback.arity_counts) == {
        0: 6, 1: 57, 2: 18, 3: 5, 4: 9, 5: 5, 6: 1, 8: 2, 9: 1, 11: 1,
    }
    assert evidence.exhaustive_semantic_alias_partition_established is False


def test_semantic_boolean_kinds_remain_distinct_from_parcel_int32():
    evidence = recovered_vendor_binder_evidence()
    requests = {row.ledger_name: row for row in evidence.request.rows}
    callbacks = {row.ledger_name: row for row in evidence.callback.rows}

    assert requests["scanDevice"].semantic_argument_kinds == ("bool",)
    assert requests["scanDevice"].parcel_argument_kinds == ("int32",)
    assert requests["isConnectBt"].semantic_result_kind == "bool"
    assert requests["isConnectBt"].parcel_result_kind == "int32"
    assert callbacks["onGetDeviceState"].semantic_argument_kinds == (
        "bool", "bool", "bool",
    )
    assert callbacks["onGetDeviceState"].parcel_argument_kinds == (
        "int32", "int32", "int32",
    )


def test_binder_evidence_is_closed_sanitized_and_non_runnable():
    evidence = recovered_vendor_binder_evidence()

    with pytest.raises(TypeError):
        type(evidence)()
    with pytest.raises(TypeError):
        type(evidence.request)()
    with pytest.raises(TypeError):
        type(evidence.request.rows[0])()
    with pytest.raises(FrozenInstanceError):
        evidence.request = evidence.callback
    forbidden = {
        "source", "path", "descriptor", "prototype", "fingerprint",
        "instruction_offset", "dex_digest", "payload", "frame",
    }
    for model in (type(evidence), type(evidence.request), type(evidence.request.rows[0])):
        assert forbidden.isdisjoint(field.name for field in fields(model))
    serialized = json.dumps(asdict(evidence), sort_keys=True).lower()
    assert "sha256" not in serialized
    assert ".smali" not in serialized
    source = inspect.getsource(binder_module).lower()
    assert "bleak" not in source
    assert "import subprocess" not in source
    assert "open(" not in source
    assert evidence.runnable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert all(row.runnable is False for row in evidence.request.rows)
    assert all(row.hardware_eligible is False for row in evidence.callback.rows)
