"""RED-first contract for source-controlled, exact-scope eligibility (#49)."""

from dataclasses import FrozenInstanceError, asdict
import json

import pytest

import jring.vendor_runtime_scope_eligibility as eligibility


OPERATION = "getDeviceInfo"
MODEL = "ring-family-a"
BUILD = "ring-7-2-4"
BACKEND = "bleak-linux-v1"
REFERENCE = "reviewed-device-info-ring-a-7-2-4-v1"


def reviewed_row(**changes: object) -> dict[str, object]:
    row: dict[str, object] = {
        "operation_id": OPERATION,
        "model_scope": MODEL,
        "firmware_build_scope": BUILD,
        "backend_scope": BACKEND,
        "decision_version": 1,
        "decision": "verified",
        "reviewed_evidence_reference": REFERENCE,
    }
    row.update(changes)
    return row


def build(*rows: dict[str, object]):
    return eligibility._build_source_controlled_runtime_registry(tuple(rows))


def require(registry, **changes: object):
    scope: dict[str, object] = {
        "operation_id": OPERATION,
        "model_scope": MODEL,
        "firmware_build_scope": BUILD,
        "backend_scope": BACKEND,
        "decision_version": 1,
    }
    scope.update(changes)
    return registry.require_exact_scope(**scope)


def test_only_a_complete_exact_scope_can_return_a_verified_decision():
    registry = build(reviewed_row())
    decision = require(registry)

    assert decision.operation_id == OPERATION
    assert decision.decision is eligibility.RuntimeScopeDecision.VERIFIED
    assert not hasattr(decision, "reviewed_evidence_reference")
    assert eligibility.recovered_runtime_scope_eligibility().rows == ()
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        eligibility.require_runtime_scope(
            operation_id=OPERATION,
            model_scope=MODEL,
            firmware_build_scope=BUILD,
            backend_scope=BACKEND,
            decision_version=1,
        )
    assert raised.value.code == "runtime_scope_not_reviewed"


@pytest.mark.parametrize(
    "scope,error_code",
    (
        ({"firmware_build_scope": "ring-7-2-5"}, "runtime_scope_not_reviewed"),
        ({"firmware_build_scope": "unknown"}, "missing_runtime_scope"),
        ({"backend_scope": "bluepy-linux-v1"}, "runtime_scope_not_reviewed"),
        ({"decision_version": 2}, "unsupported_decision_version"),
    ),
)
def test_point_build_backend_and_version_never_fall_back(scope, error_code):
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        require(build(reviewed_row()), **scope)
    assert raised.value.code == error_code


@pytest.mark.parametrize(
    "missing", ("operation_id", "model_scope", "firmware_build_scope", "backend_scope", "decision_version")
)
def test_lookup_without_every_dimension_fails_closed(missing):
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        require(build(reviewed_row()), **{missing: None})
    assert raised.value.code == "missing_runtime_scope"


def test_duplicate_scope_or_replayed_review_reference_rejects_whole_candidate():
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        build(reviewed_row(), reviewed_row(decision="blocked_vendor_authorization", reviewed_evidence_reference="blocked-v1"))
    assert raised.value.code == "contradictory_scope_decision"
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        build(reviewed_row(), reviewed_row(model_scope="ring-family-b"))
    assert raised.value.code == "replayed_reviewed_evidence"
    assert eligibility.recovered_runtime_scope_eligibility().rows == ()


@pytest.mark.parametrize("build_scope", ("7", "7-2", "ring-7-2-*", "unknown"))
def test_major_only_or_range_builds_cannot_enter_source_controlled_relation(build_scope):
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        build(reviewed_row(firmware_build_scope=build_scope))
    assert raised.value.code in {"firmware_build_not_exact", "invalid_firmware_build_scope"}


def test_closed_rows_and_public_payload_cannot_leak_review_reference_or_authority():
    registry = build(reviewed_row())
    row = registry.rows[0]
    with pytest.raises(TypeError, match="closed"):
        eligibility.RuntimeScopeEligibilityRow()
    with pytest.raises(FrozenInstanceError):
        row.decision = eligibility.RuntimeScopeDecision.VERIFIED
    payload = eligibility.runtime_scope_eligibility_payload()
    rendered = repr(registry) + json.dumps(asdict(row), sort_keys=True) + json.dumps(payload, sort_keys=True)
    assert REFERENCE not in rendered
    assert "reviewed_evidence_reference" not in rendered
    assert payload["reviewed_scope_count"] == payload["verified_scope_count"] == 0


def test_owner_compatibility_rows_cannot_be_forged_into_runtime_decisions():
    with pytest.raises(eligibility.RuntimeScopeEligibilityError) as raised:
        build({
            "schema_version": 1,
            "record_type": "sanitized_owner_hardware_evidence",
            "declared_model_family": MODEL,
            "declared_firmware_major": "7",
        })
    assert raised.value.code == "invalid_source_controlled_decision"
    assert not hasattr(eligibility, "promote_runtime_evidence")
