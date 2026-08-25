"""Stable, privacy-minimal contracts for events and operation results.

The models intentionally contain control-plane metadata only. They cannot hold packet
bytes, measurements, private content, device identifiers, stable addresses, or clock
values. Operation-specific typed values require a separate closed schema.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import json
from threading import Lock
from weakref import ref

from .vendor_operation_registry import (
    OperationTerminalStatus,
    VendorOperationRegistryError,
    operation_registry_entry,
    require_hardware_verified_operation,
)
from .vendor_request_callback_correlation import (
    recovered_request_callback_correlations,
)


MAX_ORDER_VALUE = 9_007_199_254_740_991


class NeutralEventKind(str, Enum):
    UNKNOWN = "unknown"
    DEVICE_ACTION = "device_action"
    MOTION = "motion"
    STEP_COUNTER = "step_counter"
    SENSOR_STATE = "sensor_state"
    RAW_NOTIFICATION = "raw_notification"
    TRANSACTION_CALLBACK = "transaction_callback"


class EventRelationship(str, Enum):
    UNKNOWN = "unknown"
    UNOWNED = "unowned"
    OPERATION_CORRELATED = "operation_correlated"


class ContractProvenance(str, Enum):
    SYNTHETIC = "synthetic"
    LIVE_OWNER_DEVICE = "live_owner_device"


class ContractConfidence(str, Enum):
    SYNTHETIC = "synthetic"
    STATIC_CANDIDATE = "static_candidate"
    HARDWARE_VERIFIED = "hardware_verified"


class ObservationWallTimeState(str, Enum):
    NOT_RECORDED = "not_recorded"
    WITHHELD = "withheld"


class DeviceTimeState(str, Enum):
    NOT_PRESENT = "not_present"
    OPAQUE_WITHHELD = "opaque_withheld"
    TYPED_WITHHELD = "typed_withheld"


class DeadlineState(str, Enum):
    NOT_APPLICABLE = "not_applicable"
    ACTIVE = "active"
    SATISFIED = "satisfied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class OperationOutcome(str, Enum):
    ABORTED = "aborted"
    ACCEPTED = "accepted"
    RESPONSE_MATCHED = "response_matched"
    UNCERTAIN = "uncertain"
    UNSUPPORTED = "unsupported"
    PROVEN_UNAVAILABLE = "proven_unavailable"


class OperationStage(str, Enum):
    PREFLIGHT = "preflight"
    SUBSCRIPTION = "subscription"
    WRITE = "write"
    RESPONSE = "response"
    CLEANUP = "cleanup"
    COMPLETE = "complete"


class OperationCompletion(str, Enum):
    IN_PROGRESS = "in_progress"
    SUCCEEDED = "succeeded"
    TERMINAL_WITHOUT_SUCCESS = "terminal_without_success"
    UNKNOWN = "unknown"


class OperationReason(str, Enum):
    NONE = "none"
    PRE_DISPATCH_FAILURE = "pre_dispatch_failure"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    DISCONNECTED = "disconnected"
    TRANSPORT_FAILURE = "transport_failure"
    MALFORMED_RESPONSE = "malformed_response"
    CLEANUP_FAILED = "cleanup_failed"
    DEVICE_REJECTED = "device_rejected"
    UNSUPPORTED_ENVIRONMENT = "unsupported_environment"
    POLICY_DENIED = "policy_denied"
    STATIC_ONLY = "static_only"
    REGISTRY_EVIDENCE = "registry_evidence"


class RecoveryDirective(str, Enum):
    NONE = "none"
    RETRY_AFTER_FIX = "retry_after_fix"
    RECONNECT_NO_REPLAY = "reconnect_no_replay"


class TerminalBasis(str, Enum):
    NOT_OBSERVED = "not_observed"
    NOT_APPLICABLE = "not_applicable"
    EXACT_SUCCESS_RESPONSE = "exact_success_response"
    EXACT_FAILURE_RESPONSE = "exact_failure_response"
    EXPLICIT_TERMINAL_MARKER = "explicit_terminal_marker"
    TERMINAL_METADATA = "terminal_metadata"


class DispatchState(str, Enum):
    NOT_SENT = "not_sent"
    LOCALLY_ACCEPTED = "locally_accepted"
    POSSIBLY_SENT = "possibly_sent"
    RESPONSE_OBSERVED = "response_observed"


class DeviceEffectState(str, Enum):
    NOT_ATTEMPTED = "not_attempted"
    UNKNOWN = "unknown"


class ContractError(ValueError):
    """A machine-stable, value-free rejection safe for public diagnostics."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class _WeakRefable:
    __slots__ = ("__weakref__",)


@dataclass(frozen=True, init=False, slots=True)
class RingEvent(_WeakRefable):
    record_type: str
    schema_version: int
    semantic_kind: NeutralEventKind
    relationship: EventRelationship
    source_operation: str | None
    sequence: int
    connection_generation: int
    provenance: ContractProvenance
    confidence: ContractConfidence
    wall_time_state: ObservationWallTimeState
    device_time_state: DeviceTimeState
    deadline_state: DeadlineState
    automation_eligible: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use create_ring_event")

    def __copy__(self):
        return self

    def __deepcopy__(self, _memo):
        return self


@dataclass(frozen=True, init=False, slots=True)
class OperationResult(_WeakRefable):
    record_type: str
    schema_version: int
    operation_id: str
    sequence: int
    operation_sequence: int
    connection_generation: int
    outcome: OperationOutcome
    stage: OperationStage
    completion: OperationCompletion
    terminal_basis: TerminalBasis
    reason: OperationReason
    recovery: RecoveryDirective
    provenance: ContractProvenance
    confidence: ContractConfidence
    wall_time_state: ObservationWallTimeState
    device_time_state: DeviceTimeState
    deadline_state: DeadlineState
    compatibility_scope: str | None

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use create_operation_result")

    def __copy__(self):
        return self

    def __deepcopy__(self, _memo):
        return self

    @property
    def uncertain(self) -> bool:
        return self.completion is OperationCompletion.UNKNOWN

    @property
    def dispatch_state(self) -> DispatchState:
        if self.outcome is OperationOutcome.UNCERTAIN:
            if self.stage is OperationStage.WRITE:
                return DispatchState.POSSIBLY_SENT
            return DispatchState.LOCALLY_ACCEPTED
        return _DISPATCH_BY_OUTCOME[self.outcome]

    @property
    def device_effect(self) -> DeviceEffectState:
        if self.dispatch_state is DispatchState.NOT_SENT:
            return DeviceEffectState.NOT_ATTEMPTED
        return DeviceEffectState.UNKNOWN


def _is_order_value(value: object) -> bool:
    return type(value) is int and 0 < value <= MAX_ORDER_VALUE


def _set_frozen(instance: object, values: Mapping[str, object]) -> None:
    for name, value in values.items():
        object.__setattr__(instance, name, value)


_SEALED_STATES: dict[int, tuple[object, tuple[object, ...]]] = {}
_SEALED_STATES_LOCK = Lock()


def _seal_state(instance: object, state: tuple[object, ...]) -> None:
    instance_key = id(instance)

    def discard(expired_reference: object) -> None:
        with _SEALED_STATES_LOCK:
            current = _SEALED_STATES.get(instance_key)
            if current is not None and current[0] is expired_reference:
                del _SEALED_STATES[instance_key]

    reference = ref(instance, discard)
    with _SEALED_STATES_LOCK:
        _SEALED_STATES[instance_key] = (reference, state)


def _require_sealed_state(
    instance: object, state: tuple[object, ...], code: str
) -> None:
    with _SEALED_STATES_LOCK:
        sealed = _SEALED_STATES.get(id(instance))
    if sealed is None or sealed[0]() is not instance or sealed[1] != state:
        raise ContractError(code)


def _exact_enum(value: object, enum_type: type[Enum], code: str) -> None:
    if type(value) is not enum_type:
        raise ContractError(code)


def _enum_from_payload(enum_type: type[Enum], value: object, code: str) -> Enum:
    if type(value) is not str:
        raise ContractError(code)
    try:
        return enum_type(value)
    except ValueError:
        raise ContractError(code) from None


def _registry_entry(operation_id: object):
    if type(operation_id) is not str:
        raise ContractError("unknown_operation")
    try:
        return operation_registry_entry(operation_id)
    except VendorOperationRegistryError as error:
        raise ContractError(error.code) from None


def _require_hardware(operation_id: str) -> None:
    try:
        require_hardware_verified_operation(operation_id)
    except VendorOperationRegistryError as error:
        raise ContractError(error.code) from None


_MATCHABLE_TERMINAL_RULES = frozenset({
    "single_matched_response",
    "metadata_or_explicit_marker_else_local_quiet_unknown",
})
_FAILURE_TERMINAL_OPERATIONS = frozenset(
    row.request
    for row in recovered_request_callback_correlations().rows
    if any(
        predicate.startswith(("failure_", "failures_"))
        for predicate in row.accepted_response_predicates
    )
)


def create_ring_event(
    *,
    semantic_kind: NeutralEventKind,
    relationship: EventRelationship,
    source_operation: str | None,
    sequence: int,
    connection_generation: int,
    provenance: ContractProvenance,
    confidence: ContractConfidence,
    wall_time_state: ObservationWallTimeState,
    device_time_state: DeviceTimeState,
    deadline_state: DeadlineState,
) -> RingEvent:
    """Create an event without accepting caller-supplied automation authority."""

    for value, enum_type in (
        (semantic_kind, NeutralEventKind),
        (relationship, EventRelationship),
        (provenance, ContractProvenance),
        (confidence, ContractConfidence),
        (wall_time_state, ObservationWallTimeState),
        (device_time_state, DeviceTimeState),
        (deadline_state, DeadlineState),
    ):
        _exact_enum(value, enum_type, "invalid_event")
    if not _is_order_value(sequence) or not _is_order_value(connection_generation):
        raise ContractError("invalid_event")

    source_entry = None
    if semantic_kind is NeutralEventKind.UNKNOWN:
        if (
            relationship is not EventRelationship.UNKNOWN
            or source_operation is not None
            or deadline_state is not DeadlineState.NOT_APPLICABLE
        ):
            raise ContractError("invalid_event")
    elif relationship is EventRelationship.UNOWNED:
        if source_operation is not None or deadline_state is not DeadlineState.NOT_APPLICABLE:
            raise ContractError("invalid_event")
    elif (
        relationship is EventRelationship.OPERATION_CORRELATED
        and semantic_kind is NeutralEventKind.TRANSACTION_CALLBACK
    ):
        source_entry = _registry_entry(source_operation)
        if (
            not source_entry.ring_facing
            or source_entry.response_terminal_rule not in _MATCHABLE_TERMINAL_RULES
            or deadline_state not in {DeadlineState.ACTIVE, DeadlineState.SATISFIED}
        ):
            raise ContractError("invalid_event")
    else:
        raise ContractError("invalid_event")

    live_claim = provenance is ContractProvenance.LIVE_OWNER_DEVICE
    verified_claim = confidence is ContractConfidence.HARDWARE_VERIFIED
    if live_claim != verified_claim:
        raise ContractError("invalid_event")
    automation_eligible = False
    if live_claim:
        if source_entry is None:
            raise ContractError("invalid_event")
        _require_hardware(source_entry.operation_id)
        automation_eligible = True

    event = object.__new__(RingEvent)
    _set_frozen(event, {
        "record_type": "ring_event",
        "schema_version": 1,
        "semantic_kind": semantic_kind,
        "relationship": relationship,
        "source_operation": source_operation,
        "sequence": sequence,
        "connection_generation": connection_generation,
        "provenance": provenance,
        "confidence": confidence,
        "wall_time_state": wall_time_state,
        "device_time_state": device_time_state,
        "deadline_state": deadline_state,
        "automation_eligible": automation_eligible,
    })
    _seal_state(event, _event_state(event))
    return event


_EVENT_FIELDS = (
    "record_type", "schema_version", "semantic_kind", "relationship",
    "source_operation", "sequence", "connection_generation", "provenance",
    "confidence", "wall_time_state", "device_time_state", "deadline_state",
    "automation_eligible",
)


def _event_state(event: RingEvent) -> tuple[object, ...]:
    return (
        event.record_type,
        event.schema_version,
        event.semantic_kind,
        event.relationship,
        event.source_operation,
        event.sequence,
        event.connection_generation,
        event.provenance,
        event.confidence,
        event.wall_time_state,
        event.device_time_state,
        event.deadline_state,
        event.automation_eligible,
    )


def _validated_event(event: RingEvent) -> RingEvent:
    if type(event) is not RingEvent:
        raise ContractError("invalid_event")
    _require_sealed_state(event, _event_state(event), "invalid_event")
    if event.record_type != "ring_event" or event.schema_version != 1:
        raise ContractError("invalid_event")
    rebuilt = create_ring_event(
        semantic_kind=event.semantic_kind,
        relationship=event.relationship,
        source_operation=event.source_operation,
        sequence=event.sequence,
        connection_generation=event.connection_generation,
        provenance=event.provenance,
        confidence=event.confidence,
        wall_time_state=event.wall_time_state,
        device_time_state=event.device_time_state,
        deadline_state=event.deadline_state,
    )
    if event.automation_eligible != rebuilt.automation_eligible:
        raise ContractError("invalid_event")
    return event


def ring_event_to_dict(event: RingEvent) -> dict[str, object]:
    event = _validated_event(event)
    return {
        "record_type": event.record_type,
        "schema_version": event.schema_version,
        "semantic_kind": event.semantic_kind.value,
        "relationship": event.relationship.value,
        "source_operation": event.source_operation,
        "sequence": event.sequence,
        "connection_generation": event.connection_generation,
        "provenance": event.provenance.value,
        "confidence": event.confidence.value,
        "wall_time_state": event.wall_time_state.value,
        "device_time_state": event.device_time_state.value,
        "deadline_state": event.deadline_state.value,
        "automation_eligible": event.automation_eligible,
    }


def serialize_ring_event(event: RingEvent) -> str:
    return json.dumps(
        ring_event_to_dict(event), separators=(",", ":"), ensure_ascii=False
    )


def parse_ring_event(payload: Mapping[str, object]) -> RingEvent:
    if type(payload) is not dict or set(payload) != set(_EVENT_FIELDS):
        raise ContractError("invalid_event")
    if payload["record_type"] != "ring_event":
        raise ContractError("invalid_event")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ContractError("unsupported_schema")
    event = create_ring_event(
        semantic_kind=_enum_from_payload(
            NeutralEventKind, payload["semantic_kind"], "invalid_event"
        ),
        relationship=_enum_from_payload(
            EventRelationship, payload["relationship"], "invalid_event"
        ),
        source_operation=payload["source_operation"],
        sequence=payload["sequence"],
        connection_generation=payload["connection_generation"],
        provenance=_enum_from_payload(
            ContractProvenance, payload["provenance"], "invalid_event"
        ),
        confidence=_enum_from_payload(
            ContractConfidence, payload["confidence"], "invalid_event"
        ),
        wall_time_state=_enum_from_payload(
            ObservationWallTimeState, payload["wall_time_state"], "invalid_event"
        ),
        device_time_state=_enum_from_payload(
            DeviceTimeState, payload["device_time_state"], "invalid_event"
        ),
        deadline_state=_enum_from_payload(
            DeadlineState, payload["deadline_state"], "invalid_event"
        ),
    )
    if (
        type(payload["automation_eligible"]) is not bool
        or payload["automation_eligible"] != event.automation_eligible
    ):
        raise ContractError("invalid_event")
    return event


class EventOrderGuard:
    """Validate one complete connection-wide stream; rejected events are atomic."""

    def __init__(self, *, connection_generation: int):
        if not _is_order_value(connection_generation):
            raise ContractError("invalid_generation_transition")
        self._connection_generation = connection_generation
        self._last_sequence = 0
        self._lock = Lock()

    @property
    def connection_generation(self) -> int:
        with self._lock:
            return self._connection_generation

    @property
    def last_sequence(self) -> int:
        with self._lock:
            return self._last_sequence

    def accept(self, event: RingEvent) -> RingEvent:
        event = _validated_event(event)
        with self._lock:
            if event.connection_generation < self._connection_generation:
                raise ContractError("stale_generation")
            if event.connection_generation > self._connection_generation:
                raise ContractError("unexpected_generation")
            expected = self._last_sequence + 1
            if event.sequence < expected:
                raise ContractError("out_of_order_event")
            if event.sequence > expected:
                raise ContractError("event_sequence_gap")
            self._last_sequence = event.sequence
        return event

    def advance_generation(self, connection_generation: int) -> None:
        with self._lock:
            if (
                not _is_order_value(connection_generation)
                or connection_generation != self._connection_generation + 1
            ):
                raise ContractError("invalid_generation_transition")
            self._connection_generation = connection_generation
            self._last_sequence = 0


_DISPATCH_BY_OUTCOME = {
    OperationOutcome.ABORTED: DispatchState.NOT_SENT,
    OperationOutcome.ACCEPTED: DispatchState.LOCALLY_ACCEPTED,
    OperationOutcome.RESPONSE_MATCHED: DispatchState.RESPONSE_OBSERVED,
    OperationOutcome.UNCERTAIN: DispatchState.POSSIBLY_SENT,
    OperationOutcome.UNSUPPORTED: DispatchState.NOT_SENT,
    OperationOutcome.PROVEN_UNAVAILABLE: DispatchState.NOT_SENT,
}


def _valid_result_state(
    outcome: OperationOutcome,
    stage: OperationStage,
    completion: OperationCompletion,
    terminal_basis: TerminalBasis,
    reason: OperationReason,
    recovery: RecoveryDirective,
    deadline: DeadlineState,
) -> bool:
    if outcome is OperationOutcome.ACCEPTED:
        return (stage is OperationStage.WRITE and completion is OperationCompletion.IN_PROGRESS
                and terminal_basis is TerminalBasis.NOT_OBSERVED
                and reason is OperationReason.NONE and recovery is RecoveryDirective.NONE
                and deadline is DeadlineState.ACTIVE)
    if outcome is OperationOutcome.RESPONSE_MATCHED:
        return (
            recovery is RecoveryDirective.NONE
            and deadline is DeadlineState.SATISFIED
            and (
                (
                    stage is OperationStage.RESPONSE
                    and completion is OperationCompletion.IN_PROGRESS
                    and (
                        (
                            terminal_basis is TerminalBasis.EXACT_FAILURE_RESPONSE
                            and reason is OperationReason.DEVICE_REJECTED
                        )
                        or (
                            terminal_basis in {
                                TerminalBasis.EXACT_SUCCESS_RESPONSE,
                                TerminalBasis.EXPLICIT_TERMINAL_MARKER,
                                TerminalBasis.TERMINAL_METADATA,
                            }
                            and reason is OperationReason.NONE
                        )
                    )
                )
                or (
                    stage is OperationStage.COMPLETE
                    and terminal_basis is TerminalBasis.EXACT_FAILURE_RESPONSE
                    and completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS
                    and reason is OperationReason.DEVICE_REJECTED
                )
                or (
                    stage is OperationStage.COMPLETE
                    and terminal_basis in {
                        TerminalBasis.EXACT_SUCCESS_RESPONSE,
                        TerminalBasis.EXPLICIT_TERMINAL_MARKER,
                        TerminalBasis.TERMINAL_METADATA,
                    }
                    and completion is OperationCompletion.SUCCEEDED
                    and reason is OperationReason.NONE
                )
            )
        ) or (
            stage is OperationStage.CLEANUP and completion is OperationCompletion.UNKNOWN
            and terminal_basis in {
                TerminalBasis.EXACT_SUCCESS_RESPONSE,
                TerminalBasis.EXACT_FAILURE_RESPONSE,
                TerminalBasis.EXPLICIT_TERMINAL_MARKER,
                TerminalBasis.TERMINAL_METADATA,
            }
            and reason is OperationReason.CLEANUP_FAILED
            and recovery is RecoveryDirective.RECONNECT_NO_REPLAY
            and deadline is DeadlineState.SATISFIED
        )
    if outcome is OperationOutcome.UNCERTAIN:
        return (
            stage in {OperationStage.WRITE, OperationStage.RESPONSE, OperationStage.CLEANUP}
            and completion is OperationCompletion.UNKNOWN
            and terminal_basis is TerminalBasis.NOT_OBSERVED
            and reason in {OperationReason.TIMEOUT, OperationReason.CANCELLED,
                           OperationReason.DISCONNECTED, OperationReason.MALFORMED_RESPONSE,
                           OperationReason.CLEANUP_FAILED,
                           OperationReason.TRANSPORT_FAILURE}
            and recovery is RecoveryDirective.RECONNECT_NO_REPLAY
            and deadline in {DeadlineState.EXPIRED, DeadlineState.CANCELLED}
        )
    if outcome is OperationOutcome.ABORTED:
        expected = {
            OperationReason.PRE_DISPATCH_FAILURE: DeadlineState.NOT_APPLICABLE,
            OperationReason.TIMEOUT: DeadlineState.EXPIRED,
            OperationReason.CANCELLED: DeadlineState.CANCELLED,
            OperationReason.DISCONNECTED: DeadlineState.CANCELLED,
        }
        return (
            stage in {OperationStage.PREFLIGHT, OperationStage.SUBSCRIPTION, OperationStage.WRITE}
            and completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS
            and terminal_basis is TerminalBasis.NOT_APPLICABLE
            and recovery is RecoveryDirective.RETRY_AFTER_FIX
            and expected.get(reason) is deadline
        )
    if outcome is OperationOutcome.UNSUPPORTED:
        return (
            stage is OperationStage.PREFLIGHT
            and completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS
            and terminal_basis is TerminalBasis.NOT_APPLICABLE
            and reason in {OperationReason.UNSUPPORTED_ENVIRONMENT,
                           OperationReason.POLICY_DENIED, OperationReason.STATIC_ONLY}
            and recovery is RecoveryDirective.NONE
            and deadline is DeadlineState.NOT_APPLICABLE
        )
    return (
        outcome is OperationOutcome.PROVEN_UNAVAILABLE
        and stage is OperationStage.PREFLIGHT
        and completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS
        and terminal_basis is TerminalBasis.NOT_APPLICABLE
        and reason is OperationReason.REGISTRY_EVIDENCE
        and recovery is RecoveryDirective.NONE
        and deadline is DeadlineState.NOT_APPLICABLE
    )


def create_operation_result(
    *, operation_id: str, sequence: int, operation_sequence: int,
    connection_generation: int, outcome: OperationOutcome, stage: OperationStage,
    completion: OperationCompletion, terminal_basis: TerminalBasis,
    reason: OperationReason,
    recovery: RecoveryDirective, provenance: ContractProvenance,
    confidence: ContractConfidence, wall_time_state: ObservationWallTimeState,
    device_time_state: DeviceTimeState, deadline_state: DeadlineState,
) -> OperationResult:
    """Create a result whose primary status never implies peripheral effect."""

    registry_entry = _registry_entry(operation_id)
    if not registry_entry.ring_facing:
        raise ContractError("operation_not_ring_facing")
    if not all(_is_order_value(value) for value in (
        sequence, operation_sequence, connection_generation
    )):
        raise ContractError("invalid_operation_result")
    for value, enum_type in (
        (outcome, OperationOutcome), (stage, OperationStage),
        (completion, OperationCompletion), (terminal_basis, TerminalBasis),
        (reason, OperationReason),
        (recovery, RecoveryDirective), (provenance, ContractProvenance),
        (confidence, ContractConfidence),
        (wall_time_state, ObservationWallTimeState),
        (device_time_state, DeviceTimeState), (deadline_state, DeadlineState),
    ):
        _exact_enum(value, enum_type, "invalid_operation_result")
    if not _valid_result_state(
        outcome, stage, completion, terminal_basis, reason, recovery, deadline_state
    ):
        raise ContractError("invalid_operation_result")
    if outcome is OperationOutcome.RESPONSE_MATCHED and (
        registry_entry.response_terminal_rule not in _MATCHABLE_TERMINAL_RULES
    ):
        raise ContractError("operation_has_no_matchable_terminal")
    if outcome is OperationOutcome.RESPONSE_MATCHED:
        if registry_entry.response_terminal_rule == "single_matched_response" and (
            terminal_basis not in {
                TerminalBasis.EXACT_SUCCESS_RESPONSE,
                TerminalBasis.EXACT_FAILURE_RESPONSE,
            }
        ):
            raise ContractError("invalid_terminal_basis")
        if registry_entry.response_terminal_rule == (
            "metadata_or_explicit_marker_else_local_quiet_unknown"
        ) and terminal_basis not in {
            TerminalBasis.EXACT_FAILURE_RESPONSE,
            TerminalBasis.EXPLICIT_TERMINAL_MARKER,
            TerminalBasis.TERMINAL_METADATA,
        }:
            raise ContractError("invalid_terminal_basis")
        if (
            terminal_basis is TerminalBasis.EXACT_FAILURE_RESPONSE
            and operation_id not in _FAILURE_TERMINAL_OPERATIONS
        ):
            raise ContractError("invalid_terminal_basis")
    if outcome is OperationOutcome.PROVEN_UNAVAILABLE and (
        registry_entry.terminal_status is not OperationTerminalStatus.PROVEN_UNAVAILABLE
        or registry_entry.firmware_scope == "untested"
        or registry_entry.hardware_evidence_reference is None
    ):
        raise ContractError("operation_not_proven_unavailable")
    if registry_entry.terminal_status in {
        OperationTerminalStatus.UNSAFE, OperationTerminalStatus.EXCLUDED_NON_RING,
    } and outcome in {
        OperationOutcome.ACCEPTED, OperationOutcome.RESPONSE_MATCHED,
        OperationOutcome.UNCERTAIN,
    }:
        raise ContractError("operation_not_runtime_eligible")

    live_claim = provenance is ContractProvenance.LIVE_OWNER_DEVICE
    verified_claim = confidence is ContractConfidence.HARDWARE_VERIFIED
    if live_claim != verified_claim:
        raise ContractError("invalid_operation_result")
    if live_claim:
        _require_hardware(operation_id)
    scope = registry_entry.firmware_scope if (
        live_claim or outcome is OperationOutcome.PROVEN_UNAVAILABLE
    ) else None

    result = object.__new__(OperationResult)
    _set_frozen(result, {
        "record_type": "operation_result", "schema_version": 1,
        "operation_id": operation_id, "sequence": sequence,
        "operation_sequence": operation_sequence,
        "connection_generation": connection_generation, "outcome": outcome,
        "stage": stage, "completion": completion,
        "terminal_basis": terminal_basis, "reason": reason,
        "recovery": recovery, "provenance": provenance, "confidence": confidence,
        "wall_time_state": wall_time_state, "device_time_state": device_time_state,
        "deadline_state": deadline_state, "compatibility_scope": scope,
    })
    _seal_state(result, _result_state(result))
    return result


_RESULT_FIELDS = (
    "record_type", "schema_version", "operation_id", "sequence",
    "operation_sequence", "connection_generation", "outcome", "stage",
    "completion", "uncertain", "terminal_basis", "reason", "recovery",
    "dispatch_state",
    "device_effect", "provenance", "confidence", "wall_time_state",
    "device_time_state", "deadline_state", "compatibility_scope",
)


def _result_state(result: OperationResult) -> tuple[object, ...]:
    return (
        result.record_type,
        result.schema_version,
        result.operation_id,
        result.sequence,
        result.operation_sequence,
        result.connection_generation,
        result.outcome,
        result.stage,
        result.completion,
        result.terminal_basis,
        result.reason,
        result.recovery,
        result.provenance,
        result.confidence,
        result.wall_time_state,
        result.device_time_state,
        result.deadline_state,
        result.compatibility_scope,
    )


def _validated_result(result: OperationResult) -> OperationResult:
    if type(result) is not OperationResult:
        raise ContractError("invalid_operation_result")
    _require_sealed_state(
        result, _result_state(result), "invalid_operation_result"
    )
    if result.record_type != "operation_result" or result.schema_version != 1:
        raise ContractError("invalid_operation_result")
    rebuilt = create_operation_result(
        operation_id=result.operation_id, sequence=result.sequence,
        operation_sequence=result.operation_sequence,
        connection_generation=result.connection_generation, outcome=result.outcome,
        stage=result.stage, completion=result.completion,
        terminal_basis=result.terminal_basis, reason=result.reason,
        recovery=result.recovery, provenance=result.provenance,
        confidence=result.confidence, wall_time_state=result.wall_time_state,
        device_time_state=result.device_time_state, deadline_state=result.deadline_state,
    )
    if result.compatibility_scope != rebuilt.compatibility_scope:
        raise ContractError("invalid_operation_result")
    return result


def operation_result_to_dict(result: OperationResult) -> dict[str, object]:
    result = _validated_result(result)
    return {
        "record_type": result.record_type, "schema_version": result.schema_version,
        "operation_id": result.operation_id, "sequence": result.sequence,
        "operation_sequence": result.operation_sequence,
        "connection_generation": result.connection_generation,
        "outcome": result.outcome.value, "stage": result.stage.value,
        "completion": result.completion.value, "uncertain": result.uncertain,
        "terminal_basis": result.terminal_basis.value,
        "reason": result.reason.value, "recovery": result.recovery.value,
        "dispatch_state": result.dispatch_state.value,
        "device_effect": result.device_effect.value,
        "provenance": result.provenance.value, "confidence": result.confidence.value,
        "wall_time_state": result.wall_time_state.value,
        "device_time_state": result.device_time_state.value,
        "deadline_state": result.deadline_state.value,
        "compatibility_scope": result.compatibility_scope,
    }


def serialize_operation_result(result: OperationResult) -> str:
    return json.dumps(
        operation_result_to_dict(result), separators=(",", ":"), ensure_ascii=False
    )


def parse_operation_result(payload: Mapping[str, object]) -> OperationResult:
    if type(payload) is not dict or set(payload) != set(_RESULT_FIELDS):
        raise ContractError("invalid_operation_result")
    if payload["record_type"] != "operation_result":
        raise ContractError("invalid_operation_result")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ContractError("unsupported_schema")
    result = create_operation_result(
        operation_id=payload["operation_id"], sequence=payload["sequence"],
        operation_sequence=payload["operation_sequence"],
        connection_generation=payload["connection_generation"],
        outcome=_enum_from_payload(
            OperationOutcome, payload["outcome"], "invalid_operation_result"
        ),
        stage=_enum_from_payload(
            OperationStage, payload["stage"], "invalid_operation_result"
        ),
        completion=_enum_from_payload(
            OperationCompletion, payload["completion"], "invalid_operation_result"
        ),
        terminal_basis=_enum_from_payload(
            TerminalBasis, payload["terminal_basis"], "invalid_operation_result"
        ),
        reason=_enum_from_payload(
            OperationReason, payload["reason"], "invalid_operation_result"
        ),
        recovery=_enum_from_payload(
            RecoveryDirective, payload["recovery"], "invalid_operation_result"
        ),
        provenance=_enum_from_payload(
            ContractProvenance, payload["provenance"], "invalid_operation_result"
        ),
        confidence=_enum_from_payload(
            ContractConfidence, payload["confidence"], "invalid_operation_result"
        ),
        wall_time_state=_enum_from_payload(
            ObservationWallTimeState,
            payload["wall_time_state"],
            "invalid_operation_result",
        ),
        device_time_state=_enum_from_payload(
            DeviceTimeState,
            payload["device_time_state"],
            "invalid_operation_result",
        ),
        deadline_state=_enum_from_payload(
            DeadlineState, payload["deadline_state"], "invalid_operation_result"
        ),
    )
    derived = {
        "uncertain": result.uncertain,
        "dispatch_state": result.dispatch_state.value,
        "device_effect": result.device_effect.value,
        "compatibility_scope": result.compatibility_scope,
    }
    if any(
        type(payload[key]) is not type(value) or payload[key] != value
        for key, value in derived.items()
    ):
        raise ContractError("invalid_operation_result")
    return result


class OperationResultOrderGuard:
    """Order results and correlate repeated/concurrent attempts without identifiers."""

    _STAGE_ORDER = {stage: index for index, stage in enumerate(OperationStage)}

    def __init__(self, *, connection_generation: int):
        if not _is_order_value(connection_generation):
            raise ContractError("invalid_generation_transition")
        self._generation = connection_generation
        self._last_sequence = 0
        self._last_operation_sequence = 0
        self._attempts: dict[
            int, tuple[str, OperationOutcome, OperationStage, bool]
        ] = {}
        self._lock = Lock()

    def accept(self, result: OperationResult) -> OperationResult:
        result = _validated_result(result)
        with self._lock:
            if result.connection_generation < self._generation:
                raise ContractError("stale_generation")
            if result.connection_generation > self._generation:
                raise ContractError("unexpected_generation")
            expected = self._last_sequence + 1
            if result.sequence < expected:
                raise ContractError("out_of_order_result")
            if result.sequence > expected:
                raise ContractError("result_sequence_gap")
            prior = self._attempts.get(result.operation_sequence)
            if prior is None:
                if result.operation_sequence != self._last_operation_sequence + 1:
                    raise ContractError("operation_sequence_gap")
            else:
                prior_operation, prior_outcome, prior_stage, terminal = prior
                if prior_operation != result.operation_id:
                    raise ContractError("operation_identity_changed")
                if terminal:
                    raise ContractError("operation_already_terminal")
                if self._STAGE_ORDER[result.stage] < self._STAGE_ORDER[prior_stage]:
                    raise ContractError("operation_stage_regressed")
                if prior_outcome is OperationOutcome.ACCEPTED:
                    if result.outcome not in {
                        OperationOutcome.RESPONSE_MATCHED,
                        OperationOutcome.UNCERTAIN,
                    }:
                        raise ContractError("operation_evidence_regressed")
                elif (
                    prior_outcome is OperationOutcome.RESPONSE_MATCHED
                    and result.outcome is not OperationOutcome.RESPONSE_MATCHED
                ):
                    raise ContractError("operation_evidence_regressed")
                if result.stage is prior_stage:
                    raise ContractError("duplicate_operation_state")
            terminal = result.completion is not OperationCompletion.IN_PROGRESS
            self._attempts[result.operation_sequence] = (
                result.operation_id, result.outcome, result.stage, terminal
            )
            self._last_sequence = result.sequence
            if prior is None:
                self._last_operation_sequence = result.operation_sequence
        return result

    def advance_generation(self, connection_generation: int) -> None:
        with self._lock:
            if (
                not _is_order_value(connection_generation)
                or connection_generation != self._generation + 1
            ):
                raise ContractError("invalid_generation_transition")
            self._generation = connection_generation
            self._last_sequence = 0
            self._last_operation_sequence = 0
            self._attempts.clear()


__all__ = [
    "ContractConfidence", "ContractError", "ContractProvenance",
    "DeadlineState", "DeviceEffectState", "DeviceTimeState", "DispatchState",
    "EventOrderGuard", "EventRelationship", "MAX_ORDER_VALUE",
    "NeutralEventKind", "ObservationWallTimeState", "OperationCompletion",
    "OperationOutcome", "OperationReason", "OperationResult",
    "OperationResultOrderGuard", "OperationStage", "RecoveryDirective",
    "RingEvent", "TerminalBasis", "create_operation_result", "create_ring_event",
    "operation_result_to_dict", "parse_operation_result", "parse_ring_event",
    "ring_event_to_dict", "serialize_operation_result", "serialize_ring_event",
]
