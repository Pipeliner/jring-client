"""Fail-closed, exact-scope runtime eligibility decisions.

This is deliberately independent of the fake-singleton simulator crosswalk.  A
source-controlled decision is only a reviewed statement about one operation and
one exact public scope tuple; it is never assembled from a canary, a public
compatibility row, or a historical runtime request.  The checked-in production
ledger is intentionally empty until issue #57 supplies exact-build evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from .vendor_operation_registry import operation_registry_entry


class RuntimeScopeEligibilityError(LookupError):
    """A sanitized failure code; never includes caller-supplied scope text."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RuntimeScopeDecision(str, Enum):
    VERIFIED = "verified"
    PROVEN_UNAVAILABLE = "proven_unavailable"
    BLOCKED_VENDOR_AUTHORIZATION = "blocked_vendor_authorization"


@dataclass(frozen=True, init=False, repr=False)
class RuntimeScopeEligibilityRow:
    operation_id: str
    model_scope: str
    firmware_build_scope: str
    backend_scope: str
    decision_version: int
    decision: RuntimeScopeDecision

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("runtime scope eligibility rows are closed")

    def __repr__(self) -> str:
        return (
            "RuntimeScopeEligibilityRow("
            f"operation_id={self.operation_id!r}, model_scope={self.model_scope!r}, "
            f"firmware_build_scope={self.firmware_build_scope!r}, "
            f"backend_scope={self.backend_scope!r}, "
            f"decision_version={self.decision_version!r}, "
            f"decision={self.decision.value!r})"
        )


@dataclass(frozen=True, init=False, repr=False)
class RecoveredRuntimeScopeEligibility:
    schema_version: int
    rows: tuple[RuntimeScopeEligibilityRow, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("runtime scope eligibility registry is closed")

    @property
    def verified_count(self) -> int:
        return sum(row.decision is RuntimeScopeDecision.VERIFIED for row in self.rows)

    def require_exact_scope(
        self,
        *,
        operation_id: str,
        model_scope: str,
        firmware_build_scope: str,
        backend_scope: str,
        decision_version: int,
    ) -> RuntimeScopeEligibilityRow:
        """Inspect one immutable relation by its whole key, never a partial key."""

        if type(operation_id) is not str:
            raise RuntimeScopeEligibilityError("missing_runtime_scope")
        _scope(model_scope, code="missing_runtime_scope")
        _scope(firmware_build_scope, code="missing_runtime_scope")
        _scope(backend_scope, code="missing_runtime_scope")
        if type(decision_version) is not int:
            raise RuntimeScopeEligibilityError("missing_runtime_scope")
        if decision_version != _CURRENT_DECISION_VERSION:
            raise RuntimeScopeEligibilityError("unsupported_decision_version")
        row = {
            (
                item.operation_id,
                item.model_scope,
                item.firmware_build_scope,
                item.backend_scope,
                item.decision_version,
            ): item
            for item in self.rows
        }.get(
            (operation_id, model_scope, firmware_build_scope, backend_scope, decision_version)
        )
        if row is None:
            raise RuntimeScopeEligibilityError("runtime_scope_not_reviewed")
        if row.decision is not RuntimeScopeDecision.VERIFIED:
            raise RuntimeScopeEligibilityError(row.decision.value)
        return row


_SCHEMA_VERSION = 1
_CURRENT_DECISION_VERSION = 1
_DECISION_KEYS = frozenset(
    {
        "operation_id",
        "model_scope",
        "firmware_build_scope",
        "backend_scope",
        "decision_version",
        "decision",
        "reviewed_evidence_reference",
    }
)
_SLUG_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")


def _scope(value: object, *, code: str) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 64
        or value in {"unknown", "untested", "withheld", ".", ".."}
        or value[0] not in _SLUG_CHARS
        or any(character not in _SLUG_CHARS for character in value)
        or value.endswith("-")
        or "--" in value
        or "*" in value
    ):
        raise RuntimeScopeEligibilityError(code)
    return value


def _decision_row(record: object) -> tuple[RuntimeScopeEligibilityRow, str]:
    if type(record) is not dict or set(record) != _DECISION_KEYS:
        raise RuntimeScopeEligibilityError("invalid_source_controlled_decision")
    operation_id = record["operation_id"]
    if type(operation_id) is not str:
        raise RuntimeScopeEligibilityError("invalid_operation_scope")
    try:
        operation = operation_registry_entry(operation_id)
    except Exception as exc:
        raise RuntimeScopeEligibilityError("invalid_operation_scope") from exc
    if not operation.ring_facing:
        raise RuntimeScopeEligibilityError("invalid_operation_scope")
    model_scope = _scope(record["model_scope"], code="invalid_model_scope")
    firmware_build_scope = _scope(
        record["firmware_build_scope"], code="invalid_firmware_build_scope"
    )
    # A major-only value is deliberately not an exact build statement.
    if firmware_build_scope.count("-") < 2:
        raise RuntimeScopeEligibilityError("firmware_build_not_exact")
    backend_scope = _scope(record["backend_scope"], code="invalid_backend_scope")
    decision_version = record["decision_version"]
    if type(decision_version) is not int or decision_version != _CURRENT_DECISION_VERSION:
        raise RuntimeScopeEligibilityError("unsupported_decision_version")
    try:
        decision = RuntimeScopeDecision(record["decision"])
    except (TypeError, ValueError) as exc:
        raise RuntimeScopeEligibilityError("invalid_runtime_decision") from exc
    evidence_reference = _scope(
        record["reviewed_evidence_reference"], code="invalid_reviewed_evidence_reference"
    )
    row = object.__new__(RuntimeScopeEligibilityRow)
    for name, value in {
        "operation_id": operation_id,
        "model_scope": model_scope,
        "firmware_build_scope": firmware_build_scope,
        "backend_scope": backend_scope,
        "decision_version": decision_version,
        "decision": decision,
    }.items():
        object.__setattr__(row, name, value)
    return row, evidence_reference


def _build_source_controlled_runtime_registry(
    records: tuple[dict[str, object], ...],
) -> RecoveredRuntimeScopeEligibility:
    """Atomically validate a complete reviewed source change before publishing it.

    This deliberately private helper accepts only literal source-controlled
    records for RED tests and packaging review.  It has no file, network, owner
    evidence, or runtime-promotion input; callers cannot incrementally mutate a
    registry after validation.
    """

    if type(records) is not tuple:
        raise RuntimeScopeEligibilityError("invalid_source_controlled_registry")
    rows_and_references = tuple(_decision_row(record) for record in records)
    rows = tuple(item[0] for item in rows_and_references)
    references = tuple(item[1] for item in rows_and_references)
    keys = tuple(
        (
            row.operation_id,
            row.model_scope,
            row.firmware_build_scope,
            row.backend_scope,
            row.decision_version,
        )
        for row in rows
    )
    if len(set(keys)) != len(keys):
        raise RuntimeScopeEligibilityError("contradictory_scope_decision")
    if len(set(references)) != len(references):
        raise RuntimeScopeEligibilityError("replayed_reviewed_evidence")
    registry = object.__new__(RecoveredRuntimeScopeEligibility)
    object.__setattr__(registry, "schema_version", _SCHEMA_VERSION)
    object.__setattr__(registry, "rows", rows)
    return registry


# A reviewed source change must replace this entire tuple.  It is not a mutable
# compatibility cache and intentionally contains no authorized operation yet.
_SOURCE_CONTROLLED_DECISIONS: tuple[dict[str, object], ...] = ()
_REGISTRY = _build_source_controlled_runtime_registry(_SOURCE_CONTROLLED_DECISIONS)


def recovered_runtime_scope_eligibility() -> RecoveredRuntimeScopeEligibility:
    """Return the immutable, source-controlled scope ledger."""

    return _REGISTRY


def require_runtime_scope(
    *,
    operation_id: str,
    model_scope: str,
    firmware_build_scope: str,
    backend_scope: str,
    decision_version: int,
) -> RuntimeScopeEligibilityRow:
    """Require one exact reviewed scope decision, with no global fallthrough."""

    return _REGISTRY.require_exact_scope(
        operation_id=operation_id,
        model_scope=model_scope,
        firmware_build_scope=firmware_build_scope,
        backend_scope=backend_scope,
        decision_version=decision_version,
    )


def runtime_scope_eligibility_payload() -> dict[str, object]:
    """Return a redacted deterministic inspection payload with no authority."""

    return {
        "schema_version": _REGISTRY.schema_version,
        "decision_version": _CURRENT_DECISION_VERSION,
        "reviewed_scope_count": len(_REGISTRY.rows),
        "verified_scope_count": _REGISTRY.verified_count,
        "rows": [
            {
                "operation_id": row.operation_id,
                "model_scope": row.model_scope,
                "firmware_build_scope": row.firmware_build_scope,
                "backend_scope": row.backend_scope,
                "decision_version": row.decision_version,
                "decision": row.decision.value,
            }
            for row in _REGISTRY.rows
        ],
    }


__all__ = [
    "RecoveredRuntimeScopeEligibility",
    "RuntimeScopeDecision",
    "RuntimeScopeEligibilityError",
    "RuntimeScopeEligibilityRow",
    "recovered_runtime_scope_eligibility",
    "require_runtime_scope",
    "runtime_scope_eligibility_payload",
]
