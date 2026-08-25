"""RED contract for the network-free authorization-gate foundation."""

from __future__ import annotations

import builtins
import importlib
import json
from pathlib import Path
import sys

import pytest


_MODULE = "jring.vendor_authorization_gate"
_OPERATION = "getDeviceInfo"
_MODEL = "ring-family-a"
_BUILD = "7.2.4"
_BACKEND = "bleak"
_DECISION = 1


def _api():
    try:
        return importlib.import_module(_MODULE)
    except ModuleNotFoundError as exc:
        if exc.name == _MODULE:
            pytest.fail("missing production authorization-gate classifier")
        raise


def _evidence(
    *, outcome: str = "generic_failure", operation_id: str = _OPERATION,
    model_scope: str = _MODEL, firmware_build_scope: str = _BUILD,
    backend_scope: str = _BACKEND, decision_version: int = _DECISION,
    dispatch_state: str = "possibly_sent", control_state: str = "passed",
    cleanup_state: str = "confirmed",
):
    return _api().synthetic_gate_evidence(
        operation_id=operation_id,
        model_scope=model_scope,
        firmware_build_scope=firmware_build_scope,
        backend_scope=backend_scope,
        decision_version=decision_version,
        local_outcome=outcome,
        dispatch_state=dispatch_state,
        control_state=control_state,
        cleanup_state=cleanup_state,
    )


def _classify(primary, *, comparison=None, **scope):
    expected = {
        "operation_id": _OPERATION,
        "model_scope": _MODEL,
        "firmware_build_scope": _BUILD,
        "backend_scope": _BACKEND,
        "decision_version": _DECISION,
    }
    expected.update(scope)
    return _api().classify_authorization_gate(
        primary, controlled_after=comparison, **expected
    )


def _expected_payload(*, verdict: str, basis: str, dispatch: str, cleanup: str):
    recovery = {
        "ambiguous": "review_existing_evidence_no_replay",
        "offline": "fix_local_availability_then_new_consent",
        "timed_out": "inspect_dispatch_and_cleanup_no_replay",
    }[verdict]
    return {
        "schema_version": 1,
        "record_type": "vendor_authorization_gate_verdict",
        "operation_id": _OPERATION,
        "classification_scope": {
            "model_scope": _MODEL,
            "firmware_build_scope": _BUILD,
            "backend_scope": _BACKEND,
            "decision_version": _DECISION,
        },
        "scope_reviewed": False,
        "gate_verdict": verdict,
        "evidence_basis": basis,
        "evidence_provenance": "synthetic",
        "dispatch_state": dispatch,
        "cleanup_state": cleanup,
        "interpretation": "no_gate_conclusion",
        "conclusion_scope": "exact_operation_and_classification_scope_only",
        "recovery": recovery,
        "authority": {
            "runtime_eligible": False,
            "runtime_registry_changed": False,
            "repeat_authorized": False,
            "binding_authorized": False,
            "network_authorized": False,
            "bypass_available": False,
        },
        "automatic_retry": "prohibited",
        "bluetooth_access": "not_attempted_by_classifier",
        "network_access": "not_attempted",
    }


@pytest.mark.parametrize(
    "outcome,dispatch,control,cleanup,basis",
    (
        ("exact_success", "response_observed", "passed", "confirmed", "synthetic_evidence_only"),
        ("exact_authorization_denial", "response_observed", "passed", "confirmed", "synthetic_evidence_only"),
        ("generic_failure", "response_observed", "passed", "confirmed", "synthetic_evidence_only"),
        ("disconnected", "not_sent", "passed", "not_required", "disconnect_before_dispatch"),
        ("disconnected", "possibly_sent", "passed", "uncertain", "disconnect_after_dispatch"),
        ("malformed", "response_observed", "passed", "confirmed", "malformed_traffic"),
        ("route_unavailable", "not_sent", "not_reached", "not_required", "route_unavailable"),
        ("generic_failure", "not_sent", "failed", "confirmed", "failed_negative_control"),
        ("generic_failure", "possibly_sent", "passed", "uncertain", "cleanup_uncertain"),
    ),
)
def test_synthetic_or_non_specific_evidence_can_only_be_ambiguous(
    outcome, dispatch, control, cleanup, basis
):
    result = _classify(_evidence(
        outcome=outcome, dispatch_state=dispatch, control_state=control,
        cleanup_state=cleanup,
    ))
    assert result.public_payload() == _expected_payload(
        verdict="ambiguous", basis=basis, dispatch=dispatch, cleanup=cleanup
    )


@pytest.mark.parametrize(
    "outcome,dispatch,cleanup,verdict,basis",
    (
        ("offline", "not_sent", "not_required", "offline", "local_unavailable"),
        ("timed_out", "not_sent", "not_required", "timed_out", "deadline_expired"),
        ("timed_out", "possibly_sent", "uncertain", "timed_out", "deadline_expired"),
    ),
)
def test_offline_and_timeout_remain_distinct_without_authority(
    outcome, dispatch, cleanup, verdict, basis
):
    result = _classify(_evidence(
        outcome=outcome, dispatch_state=dispatch,
        control_state="not_reached" if dispatch == "not_sent" else "passed",
        cleanup_state=cleanup,
    ))
    assert result.public_payload() == _expected_payload(
        verdict=verdict, basis=basis, dispatch=dispatch, cleanup=cleanup
    )


@pytest.mark.parametrize(
    "scope,error_code",
    (
        ({"operation_id": "getDeviceBatery"}, "authorization_evidence_operation_mismatch"),
        ({"model_scope": "ring-family-b"}, "authorization_evidence_scope_mismatch"),
        ({"firmware_build_scope": "7.2.5"}, "authorization_evidence_scope_mismatch"),
        ({"backend_scope": "bluepy"}, "authorization_evidence_backend_mismatch"),
        ({"decision_version": 2}, "authorization_evidence_decision_stale"),
    ),
)
def test_expected_scope_mismatch_is_a_value_free_error_not_a_verdict(scope, error_code):
    api = _api()
    secret = next(iter(scope.values()))
    with pytest.raises(api.AuthorizationGateError) as raised:
        _classify(_evidence(), **scope)
    assert raised.value.code == error_code
    assert str(secret) not in str(raised.value)
    assert raised.value.retryable is False


def test_controlled_pair_cannot_be_minted_from_synthetic_rows():
    before = _evidence(
        outcome="exact_authorization_denial", dispatch_state="response_observed"
    )
    after = _evidence(outcome="exact_success", dispatch_state="response_observed")
    api = _api()
    with pytest.raises(api.AuthorizationGateError) as raised:
        _classify(before, comparison=after)
    assert raised.value.code == "authorization_evidence_differential_unreviewed"
    assert raised.value.retryable is False


@pytest.mark.parametrize(
    "kwargs",
    (
        {"outcome": "offline", "dispatch_state": "not_sent", "control_state": "passed", "cleanup_state": "not_required"},
        {"outcome": "offline", "dispatch_state": "not_sent", "control_state": "not_reached", "cleanup_state": "confirmed"},
        {"outcome": "timed_out", "dispatch_state": "response_observed", "control_state": "passed", "cleanup_state": "confirmed"},
        {"outcome": "timed_out", "dispatch_state": "not_sent", "control_state": "passed", "cleanup_state": "not_required"},
        {"outcome": "exact_success", "dispatch_state": "not_sent", "control_state": "not_reached", "cleanup_state": "not_required"},
        {"outcome": "exact_authorization_denial", "dispatch_state": "response_observed", "control_state": "failed", "cleanup_state": "confirmed"},
        {"outcome": "route_unavailable", "dispatch_state": "possibly_sent", "control_state": "passed", "cleanup_state": "uncertain"},
        {"outcome": "malformed", "dispatch_state": "not_sent", "control_state": "not_reached", "cleanup_state": "not_required"},
    ),
)
def test_incoherent_observation_cross_products_are_rejected(kwargs):
    api = _api()
    with pytest.raises(api.AuthorizationGateError) as raised:
        _evidence(**kwargs)
    assert raised.value.code == "authorization_evidence_invalid"


@pytest.mark.parametrize(
    "outcome,dispatch,control,cleanup,verdict,basis",
    (
        ("route_unavailable", "not_sent", "not_reached", "confirmed", "ambiguous", "route_unavailable"),
        ("route_unavailable", "not_sent", "not_reached", "uncertain", "ambiguous", "route_unavailable"),
        ("timed_out", "not_sent", "not_reached", "confirmed", "timed_out", "deadline_expired"),
        ("timed_out", "not_sent", "not_reached", "uncertain", "timed_out", "deadline_expired"),
        ("disconnected", "not_sent", "not_reached", "not_required", "ambiguous", "disconnect_before_dispatch"),
        ("disconnected", "not_sent", "not_reached", "confirmed", "ambiguous", "disconnect_before_dispatch"),
        ("disconnected", "not_sent", "not_reached", "uncertain", "ambiguous", "disconnect_before_dispatch"),
    ),
)
def test_pre_dispatch_transport_cleanup_is_preserved_independently(
    outcome, dispatch, control, cleanup, verdict, basis
):
    result = _classify(_evidence(
        outcome=outcome, dispatch_state=dispatch, control_state=control,
        cleanup_state=cleanup,
    ))
    assert result.public_payload() == _expected_payload(
        verdict=verdict, basis=basis, dispatch=dispatch, cleanup=cleanup
    )


def test_excluded_or_unsafe_operation_cannot_receive_a_gate_observation():
    api = _api()
    for operation_id in ("openSDKLog", "writeCharacteristic"):
        with pytest.raises(api.AuthorizationGateError) as raised:
            _evidence(operation_id=operation_id, outcome="offline",
                      dispatch_state="not_sent", control_state="not_reached",
                      cleanup_state="not_required")
        assert raised.value.code == "authorization_evidence_operation_unsupported"


def test_closed_state_scalars_require_exact_builtin_strings_without_coercion():
    api = _api()

    class PrivateText(str):
        def __str__(self):
            return "private-credential-sentinel"

    for field, value in (
        ("outcome", PrivateText("generic_failure")),
        ("dispatch_state", PrivateText("possibly_sent")),
        ("control_state", PrivateText("passed")),
        ("cleanup_state", PrivateText("confirmed")),
    ):
        with pytest.raises(api.AuthorizationGateError) as raised:
            _evidence(**{field: value})
        assert raised.value.code == "authorization_evidence_invalid"
        assert "private-credential-sentinel" not in str(raised.value)


@pytest.mark.parametrize(
    "field,value",
    (
        ("model_scope", "A0B1C2D3E4F5"),
        ("model_scope", "0123456789abcdef0123456789abcdef"),
        ("firmware_build_scope", "1700000000.123456"),
        ("firmware_build_scope", "0123456789abcdef.1"),
        ("backend_scope", "0123456789abcdef0123456789abcdef"),
        ("backend_scope", "private/owner"),
        ("model_scope", "-".join(("A0", "B1", "C2", "D3", "E4", "F5"))),
        ("model_scope", "-".join(("550e8400", "e29b", "41d4", "a716", "446655440000"))),
        ("firmware_build_scope", "2026-08-" + "25T12.34.56"),
        ("backend_scope", "sk_" + "_".join(("live", "private", "token"))),
        ("backend_scope", "-".join(("550e8400", "e29b", "41d4", "a716", "446655440000"))),
    ),
)
def test_emitted_scope_rejects_identifier_timestamp_token_and_path_shapes(field, value):
    api = _api()
    with pytest.raises(api.AuthorizationGateError) as raised:
        _evidence(**{field: value})
    assert raised.value.code == "authorization_evidence_invalid"
    assert value not in str(raised.value)


def test_synthetic_decision_version_is_closed_and_cannot_echo_a_timestamp_integer():
    api = _api()
    with pytest.raises(api.AuthorizationGateError) as raised:
        _evidence(decision_version=1700000000)
    assert raised.value.code == "authorization_evidence_invalid"
    assert "1700000000" not in str(raised.value)


def test_classification_does_not_mutate_the_operation_registry():
    from jring.vendor_operation_registry import vendor_operation_registry_payload

    before = vendor_operation_registry_payload()
    result = _classify(_evidence(outcome="generic_failure"))
    after = vendor_operation_registry_payload()
    assert before == after
    assert result.public_payload()["authority"]["runtime_registry_changed"] is False


def _claimed_review(**extra):
    return {
        "schema_version": 1,
        "record_type": "reviewed_local_authorization_observation",
        "operation_id": _OPERATION,
        "model_scope": _MODEL,
        "firmware_build_scope": _BUILD,
        "backend_scope": _BACKEND,
        "decision_version": _DECISION,
        "local_outcome": "exact_authorization_denial",
        "approved_evidence_reference": "untrusted-claim",
        **extra,
    }


def test_production_approval_ledger_is_empty_and_claimed_review_is_rejected():
    api = _api()
    assert api.production_approved_gate_evidence_count() == 0
    with pytest.raises(api.AuthorizationGateError) as raised:
        api.reviewed_gate_evidence(_claimed_review())
    assert raised.value.code == "authorization_evidence_unreviewed"
    assert "untrusted-claim" not in str(raised.value)


@pytest.mark.parametrize(
    "field,value",
    (
        ("device_address", ":".join(("A0", "B1", "C2", "D3", "E4", "F5"))),
        ("raw_frame", "0c" * 20),
        ("private_path", "/" + "/".join(("private", "owner", "evidence.json"))),
        ("vendor_endpoint", "https" + "://vendor.invalid/authorize"),
    ),
)
def test_claimed_review_schema_rejects_sensitive_or_extra_fields_without_echo(field, value):
    api = _api()
    with pytest.raises(api.AuthorizationGateError) as raised:
        api.reviewed_gate_evidence(_claimed_review(**{field: value}))
    assert raised.value.code == "authorization_evidence_invalid"
    assert value not in str(raised.value)


def test_gate_types_are_closed_and_repr_and_payload_are_redacted():
    api = _api()
    with pytest.raises(TypeError):
        api.AuthorizationGateEvidence()
    with pytest.raises(TypeError):
        api.AuthorizationGateResult()
    evidence = _evidence(outcome="generic_failure")
    result = _classify(evidence)
    rendered = repr(evidence) + repr(result) + json.dumps(result.public_payload())
    for forbidden in (
        "address", "frame", "path", "credential", "endpoint", "timestamp",
        "app_status", "evidence_reference", "digest",
    ):
        assert forbidden not in rendered.casefold()


@pytest.mark.parametrize(
    "outcome,dispatch,cleanup,heading,next_line",
    (
        (
            "generic_failure", "possibly_sent", "uncertain",
            "AUTHORIZATION GATE EXAMPLE: UNKNOWN — EVIDENCE IS AMBIGUOUS — SYNTHETIC EVIDENCE",
            "Next: Review the existing evidence; do not replay the operation.",
        ),
        (
            "offline", "not_sent", "not_required",
            "AUTHORIZATION GATE EXAMPLE: UNKNOWN — LOCAL AVAILABILITY UNCONFIRMED — SYNTHETIC EVIDENCE",
            "Next: Check local adapter, power, and proximity; any later test needs fresh selection and consent.",
        ),
        (
            "timed_out", "possibly_sent", "uncertain",
            "AUTHORIZATION GATE EXAMPLE: UNKNOWN — ATTEMPT TIMED OUT — SYNTHETIC EVIDENCE",
            "Next: Inspect the private dispatch and cleanup record; do not replay the operation.",
        ),
    ),
)
def test_human_output_is_conclusion_first_fixed_order_and_no_bypass_copy(
    outcome, dispatch, cleanup, heading, next_line
):
    api = _api()
    result = _classify(_evidence(
        outcome=outcome, dispatch_state=dispatch,
        control_state="not_reached" if dispatch == "not_sent" else "passed",
        cleanup_state=cleanup,
    ))
    lines = api.render_authorization_gate_result(result).splitlines()
    assert lines[0] == heading
    assert [line.split(":", 1)[0] for line in lines[1:]] == [
        "Verdict", "Operation", "Classification scope", "Evidence provenance",
        "Evidence basis", "Dispatch",
        "Cleanup", "Runtime eligibility", "Network, binding, and bypass", "Next",
    ]
    assert lines[-1] == next_line
    lowered = " ".join(lines).casefold()
    for forbidden in ("log in", "official app", "copy credential", "safe to retry"):
        assert forbidden not in lowered


def test_classifier_import_and_execution_have_no_network_or_bluetooth_capability(monkeypatch):
    real_import = builtins.__import__
    forbidden_imports: list[str] = []
    forbidden_roots = {
        "aiohttp", "bleak", "http", "httpx", "requests", "socket", "subprocess",
        "urllib", "websockets",
    }

    def guarded_import(name, *args, **kwargs):
        if name.split(".", 1)[0] in forbidden_roots:
            forbidden_imports.append(name)
            raise AssertionError("classifier imported an I/O capability")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    sys.modules.pop(_MODULE, None)
    api = _api()
    result = api.classify_authorization_gate(
        api.synthetic_gate_evidence(
            operation_id=_OPERATION, model_scope=_MODEL,
            firmware_build_scope=_BUILD, backend_scope=_BACKEND,
            decision_version=_DECISION, local_outcome="offline",
            dispatch_state="not_sent", control_state="not_reached",
            cleanup_state="not_required",
        ),
        operation_id=_OPERATION, model_scope=_MODEL,
        firmware_build_scope=_BUILD, backend_scope=_BACKEND,
        decision_version=_DECISION,
    )
    assert result.public_payload()["network_access"] == "not_attempted"
    assert forbidden_imports == []


def test_classifier_source_contains_no_endpoint_secret_or_io_client():
    spec = importlib.util.find_spec(_MODULE)
    assert spec is not None and spec.origin is not None
    source = Path(spec.origin).read_text(encoding="utf-8").casefold()
    for forbidden in (
        "http://", "https://", "requests.", "httpx.", "aiohttp.", "socket.",
        "urllib.request", "bleak", "subprocess", "open(", "os.",
        "vendor credential", "sdk secret",
    ):
        assert forbidden not in source
