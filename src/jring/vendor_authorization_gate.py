"""Pure, authority-free classification of local authorization-gate evidence.

The production approval ledger is intentionally empty until exact runtime scope and
gate-specific owner review exist. Synthetic observations can preserve uncertainty for
tests and UX design, but they cannot produce runtime or registry authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from weakref import WeakKeyDictionary

from .vendor_operation_registry import operation_registry_entry


class AuthorizationGateError(ValueError):
    """Stable, value-free rejection of gate evidence or expected scope."""

    def __init__(self, code: str):
        self.code = code
        self.retryable = False
        super().__init__(code)


class GateVerdict(str, Enum):
    UNGATED_FOR_OPERATION = "ungated_for_operation"
    BLOCKED_VENDOR_AUTHORIZATION = "blocked_vendor_authorization"
    AMBIGUOUS = "ambiguous"
    OFFLINE = "offline"
    TIMED_OUT = "timed_out"


class GateEvidenceBasis(str, Enum):
    REVIEWED_EXACT_SUCCESS = "reviewed_exact_success"
    APPROVED_EXACT_LOCAL_DENIAL = "approved_exact_local_denial"
    CONTROLLED_SAME_SCOPE_DIFFERENTIAL = "controlled_same_scope_differential"
    SYNTHETIC_EVIDENCE_ONLY = "synthetic_evidence_only"
    GENERIC_FAILURE = "generic_failure"
    DISCONNECT_BEFORE_DISPATCH = "disconnect_before_dispatch"
    DISCONNECT_AFTER_DISPATCH = "disconnect_after_dispatch"
    MALFORMED_TRAFFIC = "malformed_traffic"
    FAILED_NEGATIVE_CONTROL = "failed_negative_control"
    ROUTE_UNAVAILABLE = "route_unavailable"
    CLEANUP_UNCERTAIN = "cleanup_uncertain"
    LOCAL_UNAVAILABLE = "local_unavailable"
    DEADLINE_EXPIRED = "deadline_expired"


@dataclass(frozen=True)
class _GateScope:
    operation_id: str
    model_scope: str
    firmware_build_scope: str
    backend_scope: str
    decision_version: int


@dataclass(frozen=True)
class _EvidenceState:
    scope: _GateScope
    local_outcome: str
    dispatch_state: str
    control_state: str
    cleanup_state: str
    provenance: str


@dataclass(frozen=True)
class _ResultState:
    scope: _GateScope
    verdict: GateVerdict
    basis: GateEvidenceBasis
    provenance: str
    dispatch_state: str
    cleanup_state: str


_EVIDENCE: WeakKeyDictionary[object, _EvidenceState] = WeakKeyDictionary()
_RESULTS: WeakKeyDictionary[object, _ResultState] = WeakKeyDictionary()


class AuthorizationGateEvidence:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("authorization gate evidence is closed")

    def __repr__(self) -> str:
        state = _evidence_state(self)
        return (
            "AuthorizationGateEvidence("
            f"provenance={state.provenance!r}, scope=<sealed>, authority=False)"
        )


class AuthorizationGateResult:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("authorization gate results are classifier-owned")

    @property
    def verdict(self) -> GateVerdict:
        return _result_state(self).verdict

    def public_payload(self) -> dict[str, object]:
        state = _result_state(self)
        scope = state.scope
        recovery = {
            GateVerdict.UNGATED_FOR_OPERATION: "none_gate_specific",
            GateVerdict.BLOCKED_VENDOR_AUTHORIZATION: "none_available_in_jring",
            GateVerdict.AMBIGUOUS: "review_existing_evidence_no_replay",
            GateVerdict.OFFLINE: "fix_local_availability_then_new_consent",
            GateVerdict.TIMED_OUT: "inspect_dispatch_and_cleanup_no_replay",
        }[state.verdict]
        interpretation = {
            GateVerdict.UNGATED_FOR_OPERATION: "gate_not_observed_not_proven_absent",
            GateVerdict.BLOCKED_VENDOR_AUTHORIZATION: (
                "gate_locally_observed_for_exact_scope"
            ),
            GateVerdict.AMBIGUOUS: "no_gate_conclusion",
            GateVerdict.OFFLINE: "no_gate_conclusion",
            GateVerdict.TIMED_OUT: "no_gate_conclusion",
        }[state.verdict]
        return {
            "schema_version": 1,
            "record_type": "vendor_authorization_gate_verdict",
            "operation_id": scope.operation_id,
            "classification_scope": {
                "model_scope": scope.model_scope,
                "firmware_build_scope": scope.firmware_build_scope,
                "backend_scope": scope.backend_scope,
                "decision_version": scope.decision_version,
            },
            "scope_reviewed": state.provenance == "reviewed_owner",
            "gate_verdict": state.verdict.value,
            "evidence_basis": state.basis.value,
            "evidence_provenance": state.provenance,
            "dispatch_state": state.dispatch_state,
            "cleanup_state": state.cleanup_state,
            "interpretation": interpretation,
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

    def __repr__(self) -> str:
        state = _result_state(self)
        return (
            "AuthorizationGateResult("
            f"verdict={state.verdict.value!r}, scope=<sealed>, authority=False)"
        )


_SLUG_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)
_LOCAL_OUTCOMES = frozenset({
    "exact_success",
    "exact_authorization_denial",
    "generic_failure",
    "disconnected",
    "malformed",
    "route_unavailable",
    "offline",
    "timed_out",
})
_DISPATCH_STATES = frozenset({"not_sent", "possibly_sent", "response_observed"})
_CONTROL_STATES = frozenset({"not_reached", "passed", "failed"})
_CLEANUP_STATES = frozenset({"confirmed", "uncertain", "not_required"})
_CLAIMED_REVIEW_FIELDS = frozenset({
    "schema_version",
    "record_type",
    "operation_id",
    "model_scope",
    "firmware_build_scope",
    "backend_scope",
    "decision_version",
    "local_outcome",
    "approved_evidence_reference",
})


def _slug(value: object, *, scope: bool = True) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 64
        or value in {".", "..", "unknown", "withheld", "any"}
        or value[0] not in _SLUG_CHARACTERS
        or any(character not in _SLUG_CHARACTERS for character in value)
        or (scope and "*" in value)
    ):
        raise AuthorizationGateError("authorization_evidence_invalid")
    lowered = value.casefold()
    hexadecimal = frozenset("0123456789abcdef")
    hyphenated = lowered.split("-")
    mac_shaped = len(hyphenated) == 6 and all(
        len(component) == 2
        and all(character in hexadecimal for character in component)
        for component in hyphenated
    )
    uuid_shaped = tuple(map(len, hyphenated)) == (8, 4, 4, 4, 12) and all(
        all(character in hexadecimal for character in component)
        for component in hyphenated
    )
    if scope and (
        mac_shaped
        or uuid_shaped
        or (
            len(value) >= 12
            and all(character in hexadecimal for character in lowered)
        )
        or any(
            len(component) >= 12
            and all(character in hexadecimal for character in component.casefold())
            for component in value.split(".")
        )
        or any(
            len(component) >= 10 and component.isdigit()
            for component in value.split(".")
        )
        or any(
            marker in lowered
            for marker in ("credential", "private", "secret", "token")
        )
        or lowered.startswith(("sk_", "pk_"))
    ):
        raise AuthorizationGateError("authorization_evidence_invalid")
    return value


def _scope(
    *, operation_id: object, model_scope: object,
    firmware_build_scope: object, backend_scope: object,
    decision_version: object, evidence_scope: bool = False,
) -> _GateScope:
    if type(operation_id) is not str:
        raise AuthorizationGateError("authorization_evidence_invalid")
    try:
        operation_registry_entry(operation_id)
    except Exception as exc:
        raise AuthorizationGateError("authorization_evidence_invalid") from exc
    model = _slug(model_scope)
    build = _slug(firmware_build_scope)
    build_parts = build.split(".")
    if (
        not model.startswith("ring-family-")
        or not 1 <= len(model.removeprefix("ring-family-")) <= 8
        or not model.removeprefix("ring-family-").isalnum()
        or model != model.casefold()
        or len(build_parts) != 3
        or any(
            not component.isdigit() or not 1 <= len(component) <= limit
            for component, limit in zip(build_parts, (3, 3, 4))
        )
    ):
        raise AuthorizationGateError("authorization_evidence_invalid")
    backend = _slug(backend_scope)
    if evidence_scope and backend != "ble" + "ak":
        raise AuthorizationGateError("authorization_evidence_invalid")
    if type(decision_version) is not int or decision_version < 1:
        raise AuthorizationGateError("authorization_evidence_invalid")
    if evidence_scope and decision_version != 1:
        raise AuthorizationGateError("authorization_evidence_invalid")
    return _GateScope(operation_id, model, build, backend, decision_version)


def _evidence_state(evidence: object) -> _EvidenceState:
    if type(evidence) is not AuthorizationGateEvidence:
        raise AuthorizationGateError("authorization_evidence_invalid")
    try:
        return _EVIDENCE[evidence]
    except KeyError as exc:
        raise AuthorizationGateError("authorization_evidence_invalid") from exc


def _result_state(result: object) -> _ResultState:
    if type(result) is not AuthorizationGateResult:
        raise AuthorizationGateError("authorization_evidence_invalid")
    try:
        return _RESULTS[result]
    except KeyError as exc:
        raise AuthorizationGateError("authorization_evidence_invalid") from exc


def synthetic_gate_evidence(
    *, operation_id: object, model_scope: object,
    firmware_build_scope: object, backend_scope: object,
    decision_version: object, local_outcome: object, dispatch_state: object,
    control_state: object, cleanup_state: object,
) -> AuthorizationGateEvidence:
    """Create one explicitly non-production observation for policy tests."""

    exact_scope = _scope(
        operation_id=operation_id,
        model_scope=model_scope,
        firmware_build_scope=firmware_build_scope,
        backend_scope=backend_scope,
        decision_version=decision_version,
        evidence_scope=True,
    )
    if operation_id != "getDeviceInfo":
        raise AuthorizationGateError("authorization_evidence_operation_unsupported")
    if any(
        type(value) is not str
        for value in (local_outcome, dispatch_state, control_state, cleanup_state)
    ) or (
        local_outcome not in _LOCAL_OUTCOMES
        or dispatch_state not in _DISPATCH_STATES
        or control_state not in _CONTROL_STATES
        or cleanup_state not in _CLEANUP_STATES
    ):
        raise AuthorizationGateError("authorization_evidence_invalid")
    terminal = local_outcome in {"exact_success", "exact_authorization_denial"}
    coherent = (
        terminal
        and dispatch_state == "response_observed"
        and control_state == "passed"
        and cleanup_state == "confirmed"
    ) or (
        local_outcome == "offline"
        and dispatch_state == "not_sent"
        and control_state == "not_reached"
        and cleanup_state == "not_required"
    ) or (
        local_outcome == "route_unavailable"
        and dispatch_state == "not_sent"
        and control_state == "not_reached"
        and cleanup_state in {"not_required", "confirmed", "uncertain"}
    ) or (
        local_outcome == "timed_out"
        and (
            (
                dispatch_state == "not_sent"
                and control_state == "not_reached"
                and cleanup_state in {"not_required", "confirmed", "uncertain"}
            )
            or (
                dispatch_state == "possibly_sent"
                and control_state == "passed"
                and cleanup_state in {"confirmed", "uncertain"}
            )
        )
    ) or (
        local_outcome == "disconnected"
        and dispatch_state in {"not_sent", "possibly_sent"}
        and control_state in (
            {"not_reached", "passed"}
            if dispatch_state == "not_sent"
            else {"passed"}
        )
        and (
            cleanup_state in {"not_required", "confirmed", "uncertain"}
            if dispatch_state == "not_sent"
            else cleanup_state in {"confirmed", "uncertain"}
        )
    ) or (
        local_outcome in {"generic_failure", "malformed"}
        and (
            (
                control_state == "failed"
                and dispatch_state == "not_sent"
                and cleanup_state in {"confirmed", "uncertain"}
            )
            or (
                control_state == "passed"
                and dispatch_state in {"possibly_sent", "response_observed"}
                and cleanup_state in {"confirmed", "uncertain"}
            )
        )
    )
    if not coherent:
        raise AuthorizationGateError("authorization_evidence_invalid")
    evidence = object.__new__(AuthorizationGateEvidence)
    _EVIDENCE[evidence] = _EvidenceState(
        exact_scope,
        local_outcome,
        dispatch_state,
        control_state,
        cleanup_state,
        "synthetic",
    )
    return evidence


def reviewed_gate_evidence(row: object) -> AuthorizationGateEvidence:
    """Reject claimed reviewed rows until a gate-specific trusted ledger exists."""

    if type(row) is not dict or set(row) != _CLAIMED_REVIEW_FIELDS:
        raise AuthorizationGateError("authorization_evidence_invalid")
    if (
        type(row.get("schema_version")) is not int
        or row.get("schema_version") != 1
        or row.get("record_type")
        != "reviewed_local_authorization_observation"
        or row.get("local_outcome") not in _LOCAL_OUTCOMES
    ):
        raise AuthorizationGateError("authorization_evidence_invalid")
    _scope(
        operation_id=row.get("operation_id"),
        model_scope=row.get("model_scope"),
        firmware_build_scope=row.get("firmware_build_scope"),
        backend_scope=row.get("backend_scope"),
        decision_version=row.get("decision_version"),
    )
    _slug(row.get("approved_evidence_reference"), scope=False)
    raise AuthorizationGateError("authorization_evidence_unreviewed")


def production_approved_gate_evidence_count() -> int:
    """Return the non-sensitive size of the intentionally empty approval ledger."""

    return 0


def _require_expected_scope(state: _EvidenceState, expected: _GateScope) -> None:
    actual = state.scope
    if actual.operation_id != expected.operation_id:
        raise AuthorizationGateError("authorization_evidence_operation_mismatch")
    if (
        actual.model_scope != expected.model_scope
        or actual.firmware_build_scope != expected.firmware_build_scope
    ):
        raise AuthorizationGateError("authorization_evidence_scope_mismatch")
    if actual.backend_scope != expected.backend_scope:
        raise AuthorizationGateError("authorization_evidence_backend_mismatch")
    if actual.decision_version != expected.decision_version:
        raise AuthorizationGateError("authorization_evidence_decision_stale")


def _basis(state: _EvidenceState) -> tuple[GateVerdict, GateEvidenceBasis]:
    if state.local_outcome == "offline":
        return GateVerdict.OFFLINE, GateEvidenceBasis.LOCAL_UNAVAILABLE
    if state.local_outcome == "timed_out":
        return GateVerdict.TIMED_OUT, GateEvidenceBasis.DEADLINE_EXPIRED
    if state.control_state == "failed":
        return GateVerdict.AMBIGUOUS, GateEvidenceBasis.FAILED_NEGATIVE_CONTROL
    if state.local_outcome == "disconnected":
        basis = (
            GateEvidenceBasis.DISCONNECT_BEFORE_DISPATCH
            if state.dispatch_state == "not_sent"
            else GateEvidenceBasis.DISCONNECT_AFTER_DISPATCH
        )
        return GateVerdict.AMBIGUOUS, basis
    if state.local_outcome == "malformed":
        return GateVerdict.AMBIGUOUS, GateEvidenceBasis.MALFORMED_TRAFFIC
    if state.local_outcome == "route_unavailable":
        return GateVerdict.AMBIGUOUS, GateEvidenceBasis.ROUTE_UNAVAILABLE
    if state.cleanup_state == "uncertain":
        return GateVerdict.AMBIGUOUS, GateEvidenceBasis.CLEANUP_UNCERTAIN
    if state.provenance == "synthetic":
        return GateVerdict.AMBIGUOUS, GateEvidenceBasis.SYNTHETIC_EVIDENCE_ONLY
    return GateVerdict.AMBIGUOUS, GateEvidenceBasis.GENERIC_FAILURE


def classify_authorization_gate(
    evidence: AuthorizationGateEvidence,
    *, operation_id: object, model_scope: object,
    firmware_build_scope: object, backend_scope: object,
    decision_version: object,
    controlled_after: AuthorizationGateEvidence | None = None,
) -> AuthorizationGateResult:
    """Classify sealed local evidence without performing I/O or granting authority."""

    expected = _scope(
        operation_id=operation_id,
        model_scope=model_scope,
        firmware_build_scope=firmware_build_scope,
        backend_scope=backend_scope,
        decision_version=decision_version,
    )
    primary = _evidence_state(evidence)
    _require_expected_scope(primary, expected)
    if controlled_after is not None:
        comparison = _evidence_state(controlled_after)
        _require_expected_scope(comparison, expected)
        if comparison.scope != primary.scope:
            raise AuthorizationGateError("authorization_evidence_scope_mismatch")
        raise AuthorizationGateError(
            "authorization_evidence_differential_unreviewed"
        )
    verdict, basis = _basis(primary)
    result = object.__new__(AuthorizationGateResult)
    _RESULTS[result] = _ResultState(
        expected,
        verdict,
        basis,
        primary.provenance,
        primary.dispatch_state,
        primary.cleanup_state,
    )
    return result


def render_authorization_gate_result(result: AuthorizationGateResult) -> str:
    """Render one fixed-order, non-color, screen-reader-friendly explanation."""

    state = _result_state(result)
    payload = result.public_payload()
    heading = {
        GateVerdict.UNGATED_FOR_OPERATION: (
            "AUTHORIZATION GATE: NOT OBSERVED FOR THIS OPERATION"
        ),
        GateVerdict.BLOCKED_VENDOR_AUTHORIZATION: (
            "AUTHORIZATION GATE: REVIEWED LOCAL GATE"
        ),
        GateVerdict.AMBIGUOUS: (
            "AUTHORIZATION GATE: UNKNOWN — EVIDENCE IS AMBIGUOUS"
        ),
        GateVerdict.OFFLINE: (
            "AUTHORIZATION GATE: UNKNOWN — LOCAL AVAILABILITY UNCONFIRMED"
        ),
        GateVerdict.TIMED_OUT: (
            "AUTHORIZATION GATE: UNKNOWN — ATTEMPT TIMED OUT"
        ),
    }[state.verdict]
    if state.provenance == "synthetic":
        heading = heading.replace("AUTHORIZATION GATE:", "AUTHORIZATION GATE EXAMPLE:")
        heading += " — SYNTHETIC EVIDENCE"
    next_line = {
        GateVerdict.UNGATED_FOR_OPERATION: (
            "No gate-specific action; absence is not proven and runtime remains "
            "separately gated."
        ),
        GateVerdict.BLOCKED_VENDOR_AUTHORIZATION: (
            "No bypass is available in JRing; do not retry this operation."
        ),
        GateVerdict.AMBIGUOUS: (
            "Review the existing evidence; do not replay the operation."
        ),
        GateVerdict.OFFLINE: (
            "Check local adapter, power, and proximity; any later test needs fresh "
            "selection and consent."
        ),
        GateVerdict.TIMED_OUT: (
            "Inspect the private dispatch and cleanup record; do not replay the "
            "operation."
        ),
    }[state.verdict]
    scope = state.scope
    return "\n".join((
        heading,
        f"Verdict: {state.verdict.value}",
        f"Operation: {scope.operation_id}",
        "Classification scope: "
        f"{scope.model_scope} / {scope.firmware_build_scope} / "
        f"{scope.backend_scope} / decision {scope.decision_version}",
        f"Evidence provenance: {state.provenance}",
        f"Evidence basis: {state.basis.value}",
        f"Dispatch: {state.dispatch_state}",
        f"Cleanup: {state.cleanup_state}",
        "Runtime eligibility: unchanged; this verdict authorizes no live run",
        "Network, binding, and bypass: not attempted",
        f"Next: {next_line}",
    ))


__all__ = [
    "AuthorizationGateError",
    "AuthorizationGateEvidence",
    "AuthorizationGateResult",
    "GateEvidenceBasis",
    "GateVerdict",
    "classify_authorization_gate",
    "production_approved_gate_evidence_count",
    "render_authorization_gate_result",
    "reviewed_gate_evidence",
    "synthetic_gate_evidence",
]
