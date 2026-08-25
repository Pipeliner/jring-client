from dataclasses import FrozenInstanceError, asdict, fields, replace
from copy import copy, deepcopy
import json

import pytest

from jring.event_contracts import (
    ContractConfidence,
    ContractError,
    ContractProvenance,
    DeadlineState,
    DeviceEffectState,
    DeviceTimeState,
    DispatchState,
    EventOrderGuard,
    EventRelationship,
    MAX_ORDER_VALUE,
    NeutralEventKind,
    ObservationWallTimeState,
    OperationCompletion,
    OperationOutcome,
    OperationReason,
    OperationResult,
    OperationResultOrderGuard,
    OperationStage,
    RecoveryDirective,
    RingEvent,
    TerminalBasis,
    create_operation_result,
    create_ring_event,
    operation_result_to_dict,
    parse_operation_result,
    parse_ring_event,
    ring_event_to_dict,
    serialize_operation_result,
    serialize_ring_event,
)


def synthetic_event(*, sequence=1, generation=1):
    return create_ring_event(
        semantic_kind=NeutralEventKind.TRANSACTION_CALLBACK,
        relationship=EventRelationship.OPERATION_CORRELATED,
        source_operation="getDeviceInfo",
        sequence=sequence,
        connection_generation=generation,
        provenance=ContractProvenance.SYNTHETIC,
        confidence=ContractConfidence.SYNTHETIC,
        wall_time_state=ObservationWallTimeState.WITHHELD,
        device_time_state=DeviceTimeState.NOT_PRESENT,
        deadline_state=DeadlineState.ACTIVE,
    )


def passive_event(*, sequence=1, generation=1, kind=NeutralEventKind.DEVICE_ACTION):
    return create_ring_event(
        semantic_kind=kind,
        relationship=EventRelationship.UNOWNED,
        source_operation=None,
        sequence=sequence,
        connection_generation=generation,
        provenance=ContractProvenance.SYNTHETIC,
        confidence=ContractConfidence.STATIC_CANDIDATE,
        wall_time_state=ObservationWallTimeState.NOT_RECORDED,
        device_time_state=DeviceTimeState.OPAQUE_WITHHELD,
        deadline_state=DeadlineState.NOT_APPLICABLE,
    )


def operation_result(
    *,
    sequence=1,
    operation_sequence=1,
    generation=1,
    operation_id="getDeviceInfo",
    outcome=OperationOutcome.ACCEPTED,
    stage=OperationStage.WRITE,
    completion=OperationCompletion.IN_PROGRESS,
    terminal_basis=None,
    reason=OperationReason.NONE,
    recovery=RecoveryDirective.NONE,
    deadline=DeadlineState.ACTIVE,
    provenance=ContractProvenance.SYNTHETIC,
    confidence=ContractConfidence.SYNTHETIC,
):
    if terminal_basis is None:
        if outcome is OperationOutcome.RESPONSE_MATCHED:
            terminal_basis = (
                TerminalBasis.EXACT_FAILURE_RESPONSE
                if completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS
                else TerminalBasis.EXACT_SUCCESS_RESPONSE
            )
        elif outcome in {
            OperationOutcome.ABORTED,
            OperationOutcome.UNSUPPORTED,
            OperationOutcome.PROVEN_UNAVAILABLE,
        }:
            terminal_basis = TerminalBasis.NOT_APPLICABLE
        else:
            terminal_basis = TerminalBasis.NOT_OBSERVED
    return create_operation_result(
        operation_id=operation_id,
        sequence=sequence,
        operation_sequence=operation_sequence,
        connection_generation=generation,
        outcome=outcome,
        stage=stage,
        completion=completion,
        terminal_basis=terminal_basis,
        reason=reason,
        recovery=recovery,
        provenance=provenance,
        confidence=confidence,
        wall_time_state=ObservationWallTimeState.WITHHELD,
        device_time_state=DeviceTimeState.NOT_PRESENT,
        deadline_state=deadline,
    )


def test_ring_event_schema_is_stable_metadata_only_and_round_trips():
    event = synthetic_event()
    expected = {
        "record_type": "ring_event",
        "schema_version": 1,
        "semantic_kind": "transaction_callback",
        "relationship": "operation_correlated",
        "source_operation": "getDeviceInfo",
        "sequence": 1,
        "connection_generation": 1,
        "provenance": "synthetic",
        "confidence": "synthetic",
        "wall_time_state": "withheld",
        "device_time_state": "not_present",
        "deadline_state": "active",
        "automation_eligible": False,
    }

    assert ring_event_to_dict(event) == expected
    assert serialize_ring_event(event) == json.dumps(
        expected, separators=(",", ":"), ensure_ascii=False
    )
    assert parse_ring_event(dict(reversed(tuple(expected.items())))) == event
    assert parse_ring_event(json.loads(serialize_ring_event(event))) == event

    serialized = serialize_ring_event(event).lower()
    for forbidden in (
        "payload", "frame", "address", "identifier", "measurement", "content",
        "observed_at", "device_epoch", "deadline_at",
    ):
        assert forbidden not in serialized


def test_unknown_and_passive_events_are_unowned_opaque_and_not_automatable():
    unknown = create_ring_event(
        semantic_kind=NeutralEventKind.UNKNOWN,
        relationship=EventRelationship.UNKNOWN,
        source_operation=None,
        sequence=1,
        connection_generation=2,
        provenance=ContractProvenance.SYNTHETIC,
        confidence=ContractConfidence.STATIC_CANDIDATE,
        wall_time_state=ObservationWallTimeState.NOT_RECORDED,
        device_time_state=DeviceTimeState.OPAQUE_WITHHELD,
        deadline_state=DeadlineState.NOT_APPLICABLE,
    )

    assert unknown.automation_eligible is False
    assert passive_event().automation_eligible is False
    assert "value" not in {field.name for field in fields(RingEvent)}
    assert "raw" not in serialize_ring_event(unknown)


@pytest.mark.parametrize(
    "change,code",
    [
        (("schema_version", 2), "unsupported_schema"),
        (("schema_version", True), "unsupported_schema"),
        (("record_type", "operation_result"), "invalid_event"),
        (("semantic_kind", "future_kind"), "invalid_event"),
        (("sequence", 0), "invalid_event"),
        (("sequence", True), "invalid_event"),
        (("connection_generation", MAX_ORDER_VALUE + 1), "invalid_event"),
        (("automation_eligible", True), "invalid_event"),
        (("unknown_field", "private-canary"), "invalid_event"),
    ],
)
def test_event_parser_rejects_schema_drift_false_authority_and_unsafe_numbers(change, code):
    payload = ring_event_to_dict(synthetic_event())
    payload[change[0]] = change[1]

    with pytest.raises(ContractError) as raised:
        parse_ring_event(payload)
    assert raised.value.code == code
    assert "private-canary" not in str(raised.value)


def test_parsers_reject_mapping_subclasses_with_custom_behavior():
    class HostileDictionary(dict):
        pass

    with pytest.raises(ContractError) as raised:
        parse_ring_event(HostileDictionary(ring_event_to_dict(synthetic_event())))
    assert raised.value.code == "invalid_event"

    with pytest.raises(ContractError) as raised:
        parse_operation_result(
            HostileDictionary(operation_result_to_dict(operation_result()))
        )
    assert raised.value.code == "invalid_operation_result"


@pytest.mark.parametrize(
    "kind,relationship,source,deadline",
    [
        (
            NeutralEventKind.UNKNOWN,
            EventRelationship.UNKNOWN,
            "getDeviceInfo",
            DeadlineState.NOT_APPLICABLE,
        ),
        (
            NeutralEventKind.UNKNOWN,
            EventRelationship.UNOWNED,
            None,
            DeadlineState.NOT_APPLICABLE,
        ),
        (
            NeutralEventKind.DEVICE_ACTION,
            EventRelationship.UNOWNED,
            "sendPhoneVolume",
            DeadlineState.NOT_APPLICABLE,
        ),
        (
            NeutralEventKind.DEVICE_ACTION,
            EventRelationship.OPERATION_CORRELATED,
            "sendPhoneVolume",
            DeadlineState.ACTIVE,
        ),
        (
            NeutralEventKind.TRANSACTION_CALLBACK,
            EventRelationship.OPERATION_CORRELATED,
            "sendPhoneVolume",
            DeadlineState.ACTIVE,
        ),
    ],
)
def test_event_relationship_cannot_invent_source_causality(
    kind, relationship, source, deadline
):
    with pytest.raises(ContractError):
        create_ring_event(
            semantic_kind=kind,
            relationship=relationship,
            source_operation=source,
            sequence=1,
            connection_generation=1,
            provenance=ContractProvenance.SYNTHETIC,
            confidence=ContractConfidence.SYNTHETIC,
            wall_time_state=ObservationWallTimeState.WITHHELD,
            device_time_state=DeviceTimeState.NOT_PRESENT,
            deadline_state=deadline,
        )


def test_live_event_cannot_be_claimed_from_offline_registry():
    with pytest.raises(ContractError) as raised:
        create_ring_event(
            semantic_kind=NeutralEventKind.TRANSACTION_CALLBACK,
            relationship=EventRelationship.OPERATION_CORRELATED,
            source_operation="getDeviceInfo",
            sequence=1,
            connection_generation=1,
            provenance=ContractProvenance.LIVE_OWNER_DEVICE,
            confidence=ContractConfidence.HARDWARE_VERIFIED,
            wall_time_state=ObservationWallTimeState.WITHHELD,
            device_time_state=DeviceTimeState.NOT_PRESENT,
            deadline_state=DeadlineState.SATISFIED,
        )
    assert raised.value.code == "operation_not_hardware_verified"


def test_event_order_guard_requires_contiguous_stream_and_atomic_rejections():
    guard = EventOrderGuard(connection_generation=2)
    assert guard.accept(synthetic_event(sequence=1, generation=2)).sequence == 1
    assert guard.accept(passive_event(sequence=2, generation=2)).sequence == 2

    for event, code in (
        (synthetic_event(sequence=2, generation=2), "out_of_order_event"),
        (synthetic_event(sequence=4, generation=2), "event_sequence_gap"),
        (synthetic_event(sequence=3, generation=1), "stale_generation"),
        (synthetic_event(sequence=3, generation=3), "unexpected_generation"),
    ):
        with pytest.raises(ContractError) as raised:
            guard.accept(event)
        assert raised.value.code == code
        assert guard.last_sequence == 2

    assert guard.accept(synthetic_event(sequence=3, generation=2)).sequence == 3
    for generation in (2, 4, True, 0):
        with pytest.raises(ContractError):
            guard.advance_generation(generation)
    guard.advance_generation(3)
    assert guard.accept(synthetic_event(sequence=1, generation=3)).sequence == 1


@pytest.mark.parametrize(
    "kwargs,dispatch,effect,uncertain",
    [
        ({"outcome": OperationOutcome.ABORTED, "stage": OperationStage.PREFLIGHT,
          "completion": OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
          "reason": OperationReason.PRE_DISPATCH_FAILURE,
          "recovery": RecoveryDirective.RETRY_AFTER_FIX,
          "deadline": DeadlineState.NOT_APPLICABLE},
         DispatchState.NOT_SENT, DeviceEffectState.NOT_ATTEMPTED, False),
        ({}, DispatchState.LOCALLY_ACCEPTED, DeviceEffectState.UNKNOWN, False),
        ({"outcome": OperationOutcome.RESPONSE_MATCHED, "stage": OperationStage.RESPONSE,
          "completion": OperationCompletion.IN_PROGRESS,
          "deadline": DeadlineState.SATISFIED},
         DispatchState.RESPONSE_OBSERVED, DeviceEffectState.UNKNOWN, False),
        ({"outcome": OperationOutcome.RESPONSE_MATCHED, "stage": OperationStage.COMPLETE,
          "completion": OperationCompletion.SUCCEEDED,
          "deadline": DeadlineState.SATISFIED},
         DispatchState.RESPONSE_OBSERVED, DeviceEffectState.UNKNOWN, False),
        ({"outcome": OperationOutcome.RESPONSE_MATCHED, "stage": OperationStage.CLEANUP,
          "completion": OperationCompletion.UNKNOWN,
          "reason": OperationReason.CLEANUP_FAILED,
          "recovery": RecoveryDirective.RECONNECT_NO_REPLAY,
          "deadline": DeadlineState.SATISFIED},
         DispatchState.RESPONSE_OBSERVED, DeviceEffectState.UNKNOWN, True),
        ({"outcome": OperationOutcome.UNCERTAIN, "stage": OperationStage.WRITE,
          "completion": OperationCompletion.UNKNOWN,
          "reason": OperationReason.TIMEOUT,
          "recovery": RecoveryDirective.RECONNECT_NO_REPLAY,
          "deadline": DeadlineState.EXPIRED},
         DispatchState.POSSIBLY_SENT, DeviceEffectState.UNKNOWN, True),
        ({"outcome": OperationOutcome.UNSUPPORTED, "stage": OperationStage.PREFLIGHT,
          "completion": OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
          "reason": OperationReason.STATIC_ONLY,
          "deadline": DeadlineState.NOT_APPLICABLE},
         DispatchState.NOT_SENT, DeviceEffectState.NOT_ATTEMPTED, False),
    ],
)
def test_operation_result_states_preserve_dispatch_effect_and_recovery(
    kwargs, dispatch, effect, uncertain
):
    result = operation_result(**kwargs)
    assert result.dispatch_state is dispatch
    assert result.device_effect is effect
    assert result.uncertain is uncertain
    assert parse_operation_result(operation_result_to_dict(result)) == result


def test_operation_result_has_stable_golden_json_and_independent_clock_domains():
    result = operation_result()
    expected = {
        "record_type": "operation_result",
        "schema_version": 1,
        "operation_id": "getDeviceInfo",
        "sequence": 1,
        "operation_sequence": 1,
        "connection_generation": 1,
        "outcome": "accepted",
        "stage": "write",
        "completion": "in_progress",
        "uncertain": False,
        "terminal_basis": "not_observed",
        "reason": "none",
        "recovery": "none",
        "dispatch_state": "locally_accepted",
        "device_effect": "unknown",
        "provenance": "synthetic",
        "confidence": "synthetic",
        "wall_time_state": "withheld",
        "device_time_state": "not_present",
        "deadline_state": "active",
        "compatibility_scope": None,
    }
    assert operation_result_to_dict(result) == expected
    assert serialize_operation_result(result) == json.dumps(
        expected, separators=(",", ":"), ensure_ascii=False
    )
    assert parse_operation_result(dict(reversed(tuple(expected.items())))) == result


@pytest.mark.parametrize(
    "changes",
    [
        {"completion": OperationCompletion.SUCCEEDED},
        {"deadline": DeadlineState.EXPIRED},
        {"outcome": OperationOutcome.RESPONSE_MATCHED,
         "stage": OperationStage.COMPLETE,
         "completion": OperationCompletion.SUCCEEDED},
        {"outcome": OperationOutcome.UNCERTAIN,
         "completion": OperationCompletion.UNKNOWN,
         "reason": OperationReason.TIMEOUT,
         "recovery": RecoveryDirective.RECONNECT_NO_REPLAY},
        {"outcome": OperationOutcome.UNSUPPORTED,
         "stage": OperationStage.PREFLIGHT,
         "completion": OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
         "reason": OperationReason.STATIC_ONLY,
         "deadline": DeadlineState.NOT_APPLICABLE,
         "recovery": RecoveryDirective.RECONNECT_NO_REPLAY},
    ],
)
def test_operation_result_rejects_state_deadline_and_recovery_contradictions(changes):
    with pytest.raises(ContractError) as raised:
        operation_result(**changes)
    assert raised.value.code == "invalid_operation_result"


def test_response_success_requires_exact_terminal_and_unsafe_routes_cannot_dispatch():
    with pytest.raises(ContractError) as raised:
        operation_result(
            operation_id="sendPhoneVolume",
            outcome=OperationOutcome.RESPONSE_MATCHED,
            stage=OperationStage.COMPLETE,
            completion=OperationCompletion.SUCCEEDED,
            deadline=DeadlineState.SATISFIED,
        )
    assert raised.value.code == "operation_has_no_matchable_terminal"

    with pytest.raises(ContractError) as raised:
        operation_result(operation_id="writeCharacteristic")
    assert raised.value.code == "operation_not_runtime_eligible"


def test_matched_failure_terminal_is_preserved_without_claiming_success():
    result = operation_result(
        operation_id="setDeviceTime",
        outcome=OperationOutcome.RESPONSE_MATCHED,
        stage=OperationStage.COMPLETE,
        completion=OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
        reason=OperationReason.DEVICE_REJECTED,
        deadline=DeadlineState.SATISFIED,
    )

    assert result.terminal_basis is TerminalBasis.EXACT_FAILURE_RESPONSE
    assert result.completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS
    assert result.dispatch_state is DispatchState.RESPONSE_OBSERVED
    assert result.device_effect is DeviceEffectState.UNKNOWN


def test_conditional_terminal_requires_marker_or_metadata_not_quiet_or_generic_match():
    common = {
        "operation_id": "getDataByDay",
        "outcome": OperationOutcome.RESPONSE_MATCHED,
        "stage": OperationStage.COMPLETE,
        "completion": OperationCompletion.SUCCEEDED,
        "deadline": DeadlineState.SATISFIED,
    }
    with pytest.raises(ContractError) as raised:
        operation_result(**common)
    assert raised.value.code == "invalid_terminal_basis"

    marker = operation_result(
        **common, terminal_basis=TerminalBasis.EXPLICIT_TERMINAL_MARKER
    )
    metadata = operation_result(
        **common, terminal_basis=TerminalBasis.TERMINAL_METADATA
    )
    assert marker.completion is OperationCompletion.SUCCEEDED
    assert metadata.completion is OperationCompletion.SUCCEEDED

    failure = operation_result(
        **{
            **common,
            "completion": OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
            "reason": OperationReason.DEVICE_REJECTED,
            "terminal_basis": TerminalBasis.EXACT_FAILURE_RESPONSE,
        }
    )
    assert failure.completion is OperationCompletion.TERMINAL_WITHOUT_SUCCESS


def test_operation_without_failure_evidence_cannot_invent_a_failure_terminal():
    with pytest.raises(ContractError) as raised:
        operation_result(
            operation_id="getDeviceDial",
            outcome=OperationOutcome.RESPONSE_MATCHED,
            stage=OperationStage.COMPLETE,
            completion=OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
            terminal_basis=TerminalBasis.EXACT_FAILURE_RESPONSE,
            reason=OperationReason.DEVICE_REJECTED,
            deadline=DeadlineState.SATISFIED,
        )
    assert raised.value.code == "invalid_terminal_basis"


def test_proven_unavailable_and_live_result_require_scoped_registry_evidence():
    with pytest.raises(ContractError) as raised:
        operation_result(
            outcome=OperationOutcome.PROVEN_UNAVAILABLE,
            stage=OperationStage.PREFLIGHT,
            completion=OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
            reason=OperationReason.REGISTRY_EVIDENCE,
            deadline=DeadlineState.NOT_APPLICABLE,
        )
    assert raised.value.code == "operation_not_proven_unavailable"

    with pytest.raises(ContractError) as raised:
        operation_result(
            provenance=ContractProvenance.LIVE_OWNER_DEVICE,
            confidence=ContractConfidence.HARDWARE_VERIFIED,
        )
    assert raised.value.code == "operation_not_hardware_verified"


def test_result_parser_rejects_drift_forged_derived_state_and_private_canary():
    for key, value, code in (
        ("schema_version", 2, "unsupported_schema"),
        ("record_type", "ring_event", "invalid_operation_result"),
        ("sequence", True, "invalid_operation_result"),
        ("uncertain", True, "invalid_operation_result"),
        ("dispatch_state", "response_observed", "invalid_operation_result"),
        ("private-canary", "do-not-echo", "invalid_operation_result"),
    ):
        payload = operation_result_to_dict(operation_result())
        payload[key] = value
        with pytest.raises(ContractError) as raised:
            parse_operation_result(payload)
        assert raised.value.code == code
        assert "do-not-echo" not in str(raised.value)


def test_result_order_guard_correlates_concurrent_attempts_and_stages_atomically():
    guard = OperationResultOrderGuard(connection_generation=1)
    guard.accept(operation_result(sequence=1, operation_sequence=1))
    guard.accept(operation_result(
        sequence=2,
        operation_sequence=2,
        outcome=OperationOutcome.ABORTED,
        stage=OperationStage.PREFLIGHT,
        completion=OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
        reason=OperationReason.PRE_DISPATCH_FAILURE,
        recovery=RecoveryDirective.RETRY_AFTER_FIX,
        deadline=DeadlineState.NOT_APPLICABLE,
    ))
    guard.accept(operation_result(
        sequence=3,
        operation_sequence=1,
        outcome=OperationOutcome.RESPONSE_MATCHED,
        stage=OperationStage.RESPONSE,
        completion=OperationCompletion.IN_PROGRESS,
        deadline=DeadlineState.SATISFIED,
    ))
    guard.accept(operation_result(
        sequence=4,
        operation_sequence=1,
        outcome=OperationOutcome.RESPONSE_MATCHED,
        stage=OperationStage.COMPLETE,
        completion=OperationCompletion.SUCCEEDED,
        deadline=DeadlineState.SATISFIED,
    ))

    with pytest.raises(ContractError) as raised:
        guard.accept(operation_result(
            sequence=5,
            operation_sequence=1,
            outcome=OperationOutcome.RESPONSE_MATCHED,
            stage=OperationStage.COMPLETE,
            completion=OperationCompletion.SUCCEEDED,
            deadline=DeadlineState.SATISFIED,
        ))
    assert raised.value.code == "operation_already_terminal"

    # The rejection did not consume result sequence 5.
    guard.accept(operation_result(sequence=5, operation_sequence=3))
    guard.advance_generation(2)
    guard.accept(operation_result(sequence=1, operation_sequence=1, generation=2))


@pytest.mark.parametrize(
    "next_result",
    [
        {
            "outcome": OperationOutcome.ABORTED,
            "stage": OperationStage.WRITE,
            "completion": OperationCompletion.TERMINAL_WITHOUT_SUCCESS,
            "reason": OperationReason.PRE_DISPATCH_FAILURE,
            "recovery": RecoveryDirective.RETRY_AFTER_FIX,
            "deadline": DeadlineState.NOT_APPLICABLE,
        },
        {},
    ],
)
def test_result_order_guard_never_regresses_accepted_dispatch(next_result):
    guard = OperationResultOrderGuard(connection_generation=1)
    guard.accept(operation_result())
    with pytest.raises(ContractError) as raised:
        guard.accept(operation_result(sequence=2, **next_result))
    assert raised.value.code in {
        "operation_evidence_regressed", "duplicate_operation_state"
    }


def test_result_order_guard_preserves_a_matched_response_through_cleanup_failure():
    guard = OperationResultOrderGuard(connection_generation=1)
    guard.accept(operation_result(
        outcome=OperationOutcome.RESPONSE_MATCHED,
        stage=OperationStage.RESPONSE,
        completion=OperationCompletion.IN_PROGRESS,
        deadline=DeadlineState.SATISFIED,
    ))

    with pytest.raises(ContractError) as raised:
        guard.accept(operation_result(
            sequence=2,
            outcome=OperationOutcome.UNCERTAIN,
            stage=OperationStage.CLEANUP,
            completion=OperationCompletion.UNKNOWN,
            reason=OperationReason.CLEANUP_FAILED,
            recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
            deadline=DeadlineState.CANCELLED,
        ))
    assert raised.value.code == "operation_evidence_regressed"

    guard.accept(operation_result(
        sequence=2,
        outcome=OperationOutcome.RESPONSE_MATCHED,
        stage=OperationStage.CLEANUP,
        completion=OperationCompletion.UNKNOWN,
        reason=OperationReason.CLEANUP_FAILED,
        recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
        deadline=DeadlineState.SATISFIED,
    ))


def test_result_order_guard_allows_uncertain_as_first_and_terminal_attempt_state():
    guard = OperationResultOrderGuard(connection_generation=1)
    guard.accept(operation_result(
        outcome=OperationOutcome.UNCERTAIN,
        stage=OperationStage.WRITE,
        completion=OperationCompletion.UNKNOWN,
        reason=OperationReason.TIMEOUT,
        recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
        deadline=DeadlineState.EXPIRED,
    ))
    with pytest.raises(ContractError) as raised:
        guard.accept(operation_result(
            sequence=2,
            outcome=OperationOutcome.UNCERTAIN,
            stage=OperationStage.CLEANUP,
            completion=OperationCompletion.UNKNOWN,
            reason=OperationReason.CLEANUP_FAILED,
            recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
            deadline=DeadlineState.EXPIRED,
        ))
    assert raised.value.code == "operation_already_terminal"


def test_accepted_can_become_uncertain_only_after_stage_progress_without_dispatch_regression():
    guard = OperationResultOrderGuard(connection_generation=1)
    guard.accept(operation_result())

    with pytest.raises(ContractError) as raised:
        guard.accept(operation_result(
            sequence=2,
            outcome=OperationOutcome.UNCERTAIN,
            stage=OperationStage.WRITE,
            completion=OperationCompletion.UNKNOWN,
            reason=OperationReason.TIMEOUT,
            recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
            deadline=DeadlineState.EXPIRED,
        ))
    assert raised.value.code == "duplicate_operation_state"

    uncertain = guard.accept(operation_result(
        sequence=2,
        outcome=OperationOutcome.UNCERTAIN,
        stage=OperationStage.RESPONSE,
        completion=OperationCompletion.UNKNOWN,
        reason=OperationReason.TIMEOUT,
        recovery=RecoveryDirective.RECONNECT_NO_REPLAY,
        deadline=DeadlineState.EXPIRED,
    ))
    assert uncertain.dispatch_state is DispatchState.LOCALLY_ACCEPTED


def test_contracts_close_construction_extra_fields_and_private_echoes():
    event = synthetic_event()
    result = operation_result()
    with pytest.raises(TypeError):
        RingEvent()
    with pytest.raises(TypeError):
        OperationResult()
    with pytest.raises(TypeError):
        replace(event, sequence=2)
    with pytest.raises(TypeError):
        replace(result, completion=OperationCompletion.SUCCEEDED)
    with pytest.raises(FrozenInstanceError):
        event.automation_eligible = True
    with pytest.raises(FrozenInstanceError):
        result.reason = OperationReason.POLICY_DENIED
    with pytest.raises(AttributeError):
        object.__setattr__(event, "payload", "private-canary")
    with pytest.raises(AttributeError):
        object.__setattr__(result, "payload", "private-canary")

    event_payload = ring_event_to_dict(event)
    result_payload = operation_result_to_dict(result)
    event_payload["source_operation"] = "private-canary"
    result_payload["operation_id"] = "private-canary"
    assert event.source_operation == "getDeviceInfo"
    assert result.operation_id == "getDeviceInfo"
    for payload, parser in (
        (event_payload, parse_ring_event), (result_payload, parse_operation_result)
    ):
        with pytest.raises(ContractError) as raised:
            parser(payload)
        assert "private-canary" not in str(raised.value)

    public_text = " ".join((
        repr(event), repr(result), json.dumps(asdict(event)),
        json.dumps(asdict(result)), serialize_ring_event(event),
        serialize_operation_result(result),
    )).lower()
    for forbidden in ("payload", "frame", "address", "measurement", "observed_at"):
        assert forbidden not in public_text


def test_process_local_seal_rejects_declared_field_mutation_and_copy_is_identity():
    event = synthetic_event()
    result = operation_result()
    assert copy(event) is event
    assert deepcopy(event) is event
    assert copy(result) is result
    assert deepcopy(result) is result

    object.__setattr__(event, "source_operation", "getBandFunction")
    object.__setattr__(result, "operation_id", "getBandFunction")
    with pytest.raises(ContractError) as raised:
        serialize_ring_event(event)
    assert raised.value.code == "invalid_event"
    with pytest.raises(ContractError) as raised:
        serialize_operation_result(result)
    assert raised.value.code == "invalid_operation_result"
