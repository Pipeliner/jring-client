"""Closed fake-singleton eligibility for deterministic vendor requests.

Callback eligibility is not transaction completion.  This module classifies every
deterministic request by its proven terminal rule so a typed value/event projection
cannot accidentally enter the success-returning singleton simulator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from .vendor_codec_registry import REQUEST_CODEC_LOCATORS
from .vendor_request_callback_correlation import (
    RequestCallbackCorrelationRow,
    recovered_request_callback_correlations,
)


class FakeSingletonEligibilityState(str, Enum):
    SINGLETON_MATCHED_TERMINAL = "singleton_matched_terminal"
    TYPED_NONTERMINAL_PROJECTION = "typed_nonterminal_projection"
    AMBIGUOUS_OR_BATCHED_PER_FRAME = "ambiguous_or_batched_per_frame"
    NO_PROVEN_TERMINAL = "no_proven_terminal"
    LOCAL_OR_MARKER_BOUNDED_STREAM = "local_or_marker_bounded_stream"


@dataclass(frozen=True, init=False, repr=False)
class VendorFakeSingletonEligibilityRow:
    request: str
    state: FakeSingletonEligibilityState
    correlation_terminal_rule: str
    singleton_factory_eligible: bool
    eligibility_scope: str
    maturity: str
    runnable: bool
    live_eligible: bool
    owner_authorized: bool
    hardware_eligible: bool
    hardware_verified: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("fake singleton eligibility rows are closed")

    def __repr__(self) -> str:
        return (
            "VendorFakeSingletonEligibilityRow("
            f"request={self.request!r}, state={self.state.value!r}, "
            f"singleton_factory_eligible={self.singleton_factory_eligible!r}, "
            "eligibility_scope='fake_singleton_only', runnable=False, "
            "live_eligible=False, owner_authorized=False, hardware_eligible=False, "
            "hardware_verified=False)"
        )


@dataclass(frozen=True, init=False, repr=False)
class RecoveredVendorFakeSingletonEligibility:
    rows: tuple[VendorFakeSingletonEligibilityRow, ...]
    eligibility_scope: str
    maturity: str
    runnable: bool
    live_eligible: bool
    owner_authorized: bool
    hardware_eligible: bool
    hardware_verified: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor fake singleton eligibility evidence is closed")

    @property
    def state_counts(self) -> tuple[tuple[FakeSingletonEligibilityState, int], ...]:
        counts = Counter(row.state for row in self.rows)
        return tuple((state, counts[state]) for state in FakeSingletonEligibilityState)

    @property
    def singleton_terminal_count(self) -> int:
        return sum(row.singleton_factory_eligible for row in self.rows)


_PROJECTION_CAVEAT = "callback_is_value_or_event_projection_not_explicit_ack"
_LOCAL_OR_MARKER_RULES = frozenset(
    {
        "local_quiet_unknown",
        "metadata_or_explicit_marker_else_local_quiet_unknown",
    }
)


def _state(row: RequestCallbackCorrelationRow) -> FakeSingletonEligibilityState:
    if row.terminal_rule == "single_matched_response":
        if (
            row.relationship_state not in {"exact_single", "exact_branching"}
            or not row.callbacks
            or not row.accepted_response_predicates
        ):
            raise RuntimeError(
                "singleton matched terminal lacks exact callback/predicate evidence"
            )
        return FakeSingletonEligibilityState.SINGLETON_MATCHED_TERMINAL
    if row.terminal_rule == "per_frame_only":
        return (
            FakeSingletonEligibilityState.TYPED_NONTERMINAL_PROJECTION
            if _PROJECTION_CAVEAT in row.unresolved_reasons
            else FakeSingletonEligibilityState.AMBIGUOUS_OR_BATCHED_PER_FRAME
        )
    if row.terminal_rule == "none_proven":
        return FakeSingletonEligibilityState.NO_PROVEN_TERMINAL
    if row.terminal_rule in _LOCAL_OR_MARKER_RULES:
        return FakeSingletonEligibilityState.LOCAL_OR_MARKER_BOUNDED_STREAM
    raise RuntimeError("unclassified vendor fake singleton terminal rule")


def _row(
    correlation: RequestCallbackCorrelationRow,
) -> VendorFakeSingletonEligibilityRow:
    state = _state(correlation)
    row = object.__new__(VendorFakeSingletonEligibilityRow)
    values = {
        "request": correlation.request,
        "state": state,
        "correlation_terminal_rule": correlation.terminal_rule,
        "singleton_factory_eligible": (
            state is FakeSingletonEligibilityState.SINGLETON_MATCHED_TERMINAL
        ),
        "eligibility_scope": "fake_singleton_only",
        "maturity": "static_apk_only",
        "runnable": False,
        "live_eligible": False,
        "owner_authorized": False,
        "hardware_eligible": False,
        "hardware_verified": False,
    }
    for name, value in values.items():
        object.__setattr__(row, name, value)
    return row


_ROWS = tuple(
    _row(row) for row in recovered_request_callback_correlations().rows
)

if len(_ROWS) != len(REQUEST_CODEC_LOCATORS) or {
    row.request for row in _ROWS
} != set(REQUEST_CODEC_LOCATORS):
    raise RuntimeError(
        "vendor fake singleton eligibility does not cover every request codec"
    )

_BY_REQUEST = {row.request: row for row in _ROWS}
if len(_BY_REQUEST) != len(_ROWS):
    raise RuntimeError("duplicate vendor fake singleton eligibility request")

_EVIDENCE = object.__new__(RecoveredVendorFakeSingletonEligibility)
object.__setattr__(_EVIDENCE, "rows", _ROWS)
object.__setattr__(_EVIDENCE, "eligibility_scope", "fake_singleton_only")
object.__setattr__(_EVIDENCE, "maturity", "static_apk_only")
object.__setattr__(_EVIDENCE, "runnable", False)
object.__setattr__(_EVIDENCE, "live_eligible", False)
object.__setattr__(_EVIDENCE, "owner_authorized", False)
object.__setattr__(_EVIDENCE, "hardware_eligible", False)
object.__setattr__(_EVIDENCE, "hardware_verified", False)


def recovered_vendor_fake_singleton_eligibility(
) -> RecoveredVendorFakeSingletonEligibility:
    return _EVIDENCE


def fake_singleton_terminal_request_names() -> frozenset[str]:
    return frozenset(
        row.request for row in _ROWS if row.singleton_factory_eligible
    )


def require_fake_singleton_terminal(
    request: str,
) -> VendorFakeSingletonEligibilityRow:
    if not isinstance(request, str):
        raise TypeError("request name must be text")
    try:
        row = _BY_REQUEST[request]
    except KeyError as exc:
        raise ValueError(
            "request has no deterministic fake singleton eligibility row"
        ) from exc
    if not row.singleton_factory_eligible:
        raise TypeError(
            f"{row.state.value} request cannot enter the fake singleton transaction engine"
        )
    return row


__all__ = [
    "FakeSingletonEligibilityState",
    "RecoveredVendorFakeSingletonEligibility",
    "VendorFakeSingletonEligibilityRow",
    "fake_singleton_terminal_request_names",
    "recovered_vendor_fake_singleton_eligibility",
    "require_fake_singleton_terminal",
]
