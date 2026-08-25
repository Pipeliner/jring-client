"""Adversarial contract tests for the fake-only vendor GATT transaction lane.

These tests deliberately model callbacks instead of a convenience ``subscribe`` or
``write`` coroutine.  A runtime adapter must therefore prove dispatch and completion
for one exact, connection-owned target before the state machine advances.
"""

from dataclasses import asdict, replace
import json

import pytest

from jring.protocol import ProtocolError
from jring.event_contracts import (
    DispatchState,
    DeviceEffectState,
    OperationOutcome,
    OperationReason,
)
from jring.transport import GattCharacteristicTarget, GattDescriptorTarget
from jring.uuids import (
    CLIENT_CHARACTERISTIC_CONFIGURATION,
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F5,
    VENDOR_CHARACTERISTIC_33F6,
    VENDOR_SERVICE_56FF,
)
from jring.vendor_gatt_preflight import (
    VendorGattPreflightCode,
    VendorGattPreflightResult,
    VendorGattRoute,
)
from jring.vendor_gatt_transaction import (
    GattActionKind,
    GattCompletionOutcome,
    GattDispatchOutcome,
    StrictVendorGattTransactionEngine,
    VendorGattEnginePhase,
    VendorGattNotificationDisposition,
)
from jring.vendor_protocol import StaticQuery, encode_static_query
from jring.vendor_transport import OfflineVendorOperation


def _route(route: VendorGattRoute, generation: int) -> VendorGattPreflightResult:
    if route is VendorGattRoute.MAIN:
        request_uuid, response_uuid = (
            VENDOR_CHARACTERISTIC_33F3,
            VENDOR_CHARACTERISTIC_33F4,
        )
        prefix = "main"
    else:
        request_uuid, response_uuid = (
            VENDOR_CHARACTERISTIC_33F5,
            VENDOR_CHARACTERISTIC_33F6,
        )
        prefix = "raw"
    request = GattCharacteristicTarget(
        generation,
        VENDOR_SERVICE_56FF,
        request_uuid,
        f"{prefix}-request-{generation}",
    )
    response = GattCharacteristicTarget(
        generation,
        VENDOR_SERVICE_56FF,
        response_uuid,
        f"{prefix}-response-{generation}",
    )
    descriptor = GattDescriptorTarget(
        generation,
        VENDOR_SERVICE_56FF,
        response_uuid,
        response.instance_id,
        CLIENT_CHARACTERISTIC_CONFIGURATION,
        f"{prefix}-cccd-{generation}",
    )
    return VendorGattPreflightResult(
        route=route,
        code=VendorGattPreflightCode.STRUCTURALLY_READY,
        request_target=request,
        response_target=response,
        cccd_target=descriptor,
        cccd_advertised=True,
    )


def _operation() -> OfflineVendorOperation:
    return OfflineVendorOperation.from_static_request(
        encode_static_query(StaticQuery.BATTERY)
    )


def _copy_route(
    route: VendorGattPreflightResult, **changes: object
) -> VendorGattPreflightResult:
    values = {
        "route": route.route,
        "code": route.code,
        "request_target": route.request_target,
        "response_target": route.response_target,
        "cccd_target": route.cccd_target,
        "cccd_advertised": route.cccd_advertised,
    }
    values.update(changes)
    return VendorGattPreflightResult(**values)


def _dispatch_and_complete(
    engine, action, *, dispatched_at: float, completed_at: float
):
    dispatched = engine.record_dispatch(
        action.token,
        outcome=GattDispatchOutcome.DISPATCHED,
        now=dispatched_at,
    )
    assert dispatched.action is None
    target = action.descriptor_target or action.characteristic_target
    return engine.record_completion(
        action.token,
        target=target,
        outcome=GattCompletionOutcome.SUCCEEDED,
        now=completed_at,
    )


def _ready_engine(*, raw: bool = False, timeout: float = 1.0):
    engine = StrictVendorGattTransactionEngine(operation_timeout=timeout)
    main = _route(VendorGattRoute.MAIN, 1)
    optional = _route(VendorGattRoute.RAW, 1) if raw else None
    started = engine.begin_connection(main, raw_preflight=optional, now=0.0)
    primary = started.action
    assert primary.kind is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS
    update = _dispatch_and_complete(
        engine, primary, dispatched_at=0.01, completed_at=0.02
    )
    if raw:
        optional_action = update.action
        assert optional_action.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS
        update = _dispatch_and_complete(
            engine, optional_action, dispatched_at=0.03, completed_at=0.04
        )
    assert update.action is None
    assert engine.phase is VendorGattEnginePhase.READY
    return engine, main, optional, primary.connection_token


def test_primary_cccd_requires_exact_descriptor_callback_before_ready():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    main = _route(VendorGattRoute.MAIN, 1)
    primary = engine.begin_connection(main, now=0.0).action

    assert primary.kind is GattActionKind.ENABLE_PRIMARY_NOTIFICATIONS
    assert primary.descriptor_target is main.cccd_target
    assert engine.phase is VendorGattEnginePhase.PRIMARY_SUBSCRIPTION_REQUIRED
    engine.record_dispatch(
        primary.token, outcome=GattDispatchOutcome.DISPATCHED, now=0.1
    )
    assert engine.phase is VendorGattEnginePhase.PRIMARY_SUBSCRIPTION_REQUIRED

    wrong_descriptor = replace(
        main.cccd_target, instance_id="another-current-generation-cccd"
    )
    with pytest.raises(ProtocolError, match="descriptor|target"):
        engine.record_completion(
            primary.token,
            target=wrong_descriptor,
            outcome=GattCompletionOutcome.SUCCEEDED,
            now=0.2,
        )

    assert engine.phase is VendorGattEnginePhase.PRIMARY_SUBSCRIPTION_REQUIRED
    completed = engine.record_completion(
        primary.token,
        target=main.cccd_target,
        outcome=GattCompletionOutcome.SUCCEEDED,
        now=0.3,
    )
    assert completed.action is None
    assert engine.phase is VendorGattEnginePhase.READY


def test_primary_callback_failure_never_becomes_ready():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    main = _route(VendorGattRoute.MAIN, 1)
    action = engine.begin_connection(main, now=0.0).action
    engine.record_dispatch(
        action.token, outcome=GattDispatchOutcome.DISPATCHED, now=0.1
    )

    failed = engine.record_completion(
        action.token,
        target=main.cccd_target,
        outcome=GattCompletionOutcome.FAILED,
        now=0.2,
    )

    assert failed.action is None
    assert failed.status == "primary_subscription_failed"
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED
    with pytest.raises(ProtocolError, match="reconnect"):
        engine.start_operation(_operation(), now=0.3)


def test_optional_raw_cccd_failure_degrades_but_does_not_block_main_operations():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    main = _route(VendorGattRoute.MAIN, 1)
    raw = _route(VendorGattRoute.RAW, 1)
    primary = engine.begin_connection(main, raw_preflight=raw, now=0.0).action
    optional = _dispatch_and_complete(
        engine, primary, dispatched_at=0.01, completed_at=0.02
    ).action

    assert optional.kind is GattActionKind.ENABLE_OPTIONAL_RAW_NOTIFICATIONS
    assert optional.descriptor_target is raw.cccd_target
    engine.record_dispatch(
        optional.token, outcome=GattDispatchOutcome.DISPATCHED, now=0.03
    )
    degraded = engine.record_completion(
        optional.token,
        target=raw.cccd_target,
        outcome=GattCompletionOutcome.FAILED,
        now=0.04,
    )

    assert degraded.status == "optional_raw_subscription_failed"
    assert degraded.recovery == "continue_without_optional_capability"
    assert degraded.unavailable_capabilities == ("raw_notifications",)
    assert engine.phase is VendorGattEnginePhase.READY_DEGRADED
    write = engine.start_operation(_operation(), now=0.1).action
    assert write.kind is GattActionKind.WRITE_OPERATION
    assert write.characteristic_target is main.request_target


def test_completion_at_exact_operation_deadline_loses_to_timeout():
    engine, main, _raw, _connection = _ready_engine(timeout=1.0)
    write = engine.start_operation(_operation(), now=1.0).action
    assert write.deadline == 2.0
    engine.record_dispatch(
        write.token, outcome=GattDispatchOutcome.DISPATCHED, now=1.1
    )

    timed_out = engine.record_completion(
        write.token,
        target=main.request_target,
        outcome=GattCompletionOutcome.SUCCEEDED,
        now=2.0,
    )

    assert timed_out.status == "operation_timed_out"
    assert timed_out.completeness == "uncertain"
    assert timed_out.recovery == "reconnect_no_replay"
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


def test_notification_at_exact_operation_deadline_cannot_report_success():
    engine, main, _raw, connection = _ready_engine(timeout=1.0)
    write = engine.start_operation(_operation(), now=1.0).action
    _dispatch_and_complete(engine, write, dispatched_at=1.1, completed_at=1.2)

    result = engine.receive_notification(
        connection,
        main.response_target,
        bytes((0x0B, 50, 1)) + bytes(17),
        now=2.0,
    )

    assert (
        result.notification_disposition
        is VendorGattNotificationDisposition.TIMED_OUT
    )
    assert result.status == "operation_timed_out"
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


def test_stale_connection_and_action_callbacks_cannot_mutate_reconnect():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    old_main = _route(VendorGattRoute.MAIN, 1)
    old_action = engine.begin_connection(old_main, now=0.0).action
    old_connection = old_action.connection_token
    engine.record_disconnected(old_connection, now=0.1)

    current_main = _route(VendorGattRoute.MAIN, 2)
    current_action = engine.begin_connection(current_main, now=0.2).action
    stale_disconnect = engine.record_disconnected(old_connection, now=0.3)
    stale_dispatch = engine.record_dispatch(
        old_action.token, outcome=GattDispatchOutcome.DISPATCHED, now=0.4
    )
    stale_completion = engine.record_completion(
        old_action.token,
        target=old_main.cccd_target,
        outcome=GattCompletionOutcome.SUCCEEDED,
        now=0.5,
    )

    assert stale_disconnect.status == "stale_callback_ignored"
    assert stale_dispatch.status == "stale_callback_ignored"
    assert stale_completion.status == "stale_callback_ignored"
    assert engine.phase is VendorGattEnginePhase.PRIMARY_SUBSCRIPTION_REQUIRED
    _dispatch_and_complete(
        engine, current_action, dispatched_at=0.6, completed_at=0.7
    )
    assert engine.phase is VendorGattEnginePhase.READY


def test_disconnect_clears_queued_or_pending_work_without_replay():
    engine, _main, _raw, connection = _ready_engine(timeout=2.0)
    write = engine.start_operation(_operation(), now=1.0).action
    engine.record_dispatch(
        write.token, outcome=GattDispatchOutcome.DISPATCHED, now=1.1
    )
    disconnected = engine.record_disconnected(connection, now=1.2)

    assert disconnected.status == "operation_disconnected"
    assert disconnected.completeness == "uncertain"
    assert engine.active_operation_token is None
    assert engine.phase is VendorGattEnginePhase.DISCONNECTED

    main2 = _route(VendorGattRoute.MAIN, 2)
    primary2 = engine.begin_connection(main2, now=2.0).action
    ready = _dispatch_and_complete(
        engine, primary2, dispatched_at=2.1, completed_at=2.2
    )
    assert ready.action is None
    assert engine.phase is VendorGattEnginePhase.READY
    assert engine.poll(now=2.3).action is None
    assert engine.active_operation_token is None


def test_late_duplicate_notification_is_quarantined_after_success():
    engine, main, _raw, connection = _ready_engine(timeout=2.0)
    write = engine.start_operation(_operation(), now=1.0).action
    _dispatch_and_complete(engine, write, dispatched_at=1.1, completed_at=1.2)
    payload = bytes((0x0B, 50, 1)) + bytes(17)

    success = engine.receive_notification(
        connection, main.response_target, payload, now=1.3
    )
    duplicate = engine.receive_notification(
        connection, main.response_target, payload, now=1.4
    )

    assert (
        success.notification_disposition
        is VendorGattNotificationDisposition.MATCHED_SUCCESS
    )
    assert duplicate.notification_disposition is VendorGattNotificationDisposition.STALE
    assert duplicate.closure is None
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED
    with pytest.raises(ProtocolError, match="reconnect"):
        engine.start_operation(_operation(), now=1.5)


@pytest.mark.parametrize(
    "dispatch_outcome",
    (
        GattDispatchOutcome.DISPATCHED,
        GattDispatchOutcome.OUTCOME_UNKNOWN,
    ),
)
def test_escaped_or_uncertain_write_is_never_replayed_on_same_connection(
    dispatch_outcome,
):
    engine, _main, _raw, connection = _ready_engine(timeout=1.0)
    write = engine.start_operation(_operation(), now=1.0).action
    update = engine.record_dispatch(write.token, outcome=dispatch_outcome, now=1.1)

    if dispatch_outcome is GattDispatchOutcome.DISPATCHED:
        update = engine.poll(now=2.0)
    assert update.action is None
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED
    with pytest.raises(ProtocolError, match="reconnect"):
        engine.start_operation(_operation(), now=2.1)

    engine.record_disconnected(connection, now=2.2)
    main2 = _route(VendorGattRoute.MAIN, 2)
    primary2 = engine.begin_connection(main2, now=2.3).action
    _dispatch_and_complete(
        engine, primary2, dispatched_at=2.4, completed_at=2.5
    )
    assert engine.poll(now=2.6).action is None
    assert engine.active_operation_token is None


def test_actions_are_closed_redacted_and_not_dataclass_serializable():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    main = _route(VendorGattRoute.MAIN, 1)
    action = engine.begin_connection(main, now=0.0).action

    with pytest.raises(TypeError):
        asdict(action)
    with pytest.raises(TypeError):
        type(action)()

    rendered = repr(action)
    payload = json.dumps(action.public_payload(), sort_keys=True)
    for private_value in (
        main.cccd_target.instance_id,
        main.response_target.instance_id,
        main.response_target.uuid,
    ):
        assert private_value not in rendered
        assert private_value not in payload
    assert action.hardware_eligible is False


def test_mutated_operation_is_rejected_again_at_strict_admission():
    engine, _main, _raw, _connection = _ready_engine()
    operation = _operation()
    object.__setattr__(operation, "operation_id", "writeCharacteristic")

    with pytest.raises(ValueError, match="execution shape was mutated"):
        engine.start_operation(operation, now=0.1)

    assert engine.active_operation_token is None
    assert engine.phase is VendorGattEnginePhase.READY


def test_primary_dispatch_rejection_is_durable_without_an_operation():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    main = _route(VendorGattRoute.MAIN, 1)
    action = engine.begin_connection(main, now=0.0).action

    update = engine.record_dispatch(
        action.token,
        outcome=GattDispatchOutcome.DEFINITELY_NOT_DISPATCHED,
        now=0.1,
    )

    assert update.status == "primary_subscription_dispatch_rejected"
    assert update.completeness == "aborted"
    assert update.recovery == "reconnect_then_retry_setup"
    assert engine.status == update.status
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


def test_primary_timeout_after_descriptor_dispatch_is_setup_uncertain():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    action = engine.begin_connection(
        _route(VendorGattRoute.MAIN, 1), now=0.0
    ).action
    engine.record_dispatch(
        action.token, outcome=GattDispatchOutcome.DISPATCHED, now=0.1
    )

    update = engine.poll(now=1.0)

    assert update.status == "primary_subscription_timed_out"
    assert update.completeness == "uncertain"
    assert update.recovery == "reconnect_then_retry_setup"
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


def test_optional_dispatch_uncertainty_cannot_degrade_to_ready():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    main = _route(VendorGattRoute.MAIN, 1)
    raw = _route(VendorGattRoute.RAW, 1)
    primary = engine.begin_connection(main, raw_preflight=raw, now=0.0).action
    optional = _dispatch_and_complete(
        engine, primary, dispatched_at=0.01, completed_at=0.02
    ).action

    update = engine.record_dispatch(
        optional.token, outcome=GattDispatchOutcome.OUTCOME_UNKNOWN, now=0.03
    )

    assert update.status == "optional_raw_subscription_dispatch_unknown"
    assert update.completeness == "uncertain"
    assert update.recovery == "reconnect_then_retry_setup"
    assert update.unavailable_capabilities == ()
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


@pytest.mark.parametrize(
    "mutate",
    (
        lambda route: _copy_route(
            route,
            request_target=replace(
                route.request_target, uuid=VENDOR_CHARACTERISTIC_33F5
            ),
        ),
        lambda route: _copy_route(
            route,
            request_target=replace(
                route.request_target,
                service_uuid="0000180a-0000-1000-8000-00805f9b34fb",
            ),
        ),
        lambda route: _copy_route(
            route,
            response_target=replace(
                route.response_target, uuid=VENDOR_CHARACTERISTIC_33F6
            ),
        ),
        lambda route: _copy_route(
            route,
            cccd_target=replace(route.cccd_target, uuid=VENDOR_CHARACTERISTIC_33F4),
        ),
        lambda route: _copy_route(route, cccd_advertised=False),
    ),
)
def test_publicly_constructible_preflight_cannot_forge_closed_main_route(mutate):
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)

    with pytest.raises(ProtocolError, match="route|target|CCCD"):
        engine.begin_connection(mutate(_route(VendorGattRoute.MAIN, 1)), now=0.0)

    assert engine.phase is VendorGattEnginePhase.DISCONNECTED


def test_optional_raw_notification_is_unrelated_to_active_main_operation():
    engine, main, raw, connection = _ready_engine(raw=True, timeout=2.0)
    write = engine.start_operation(_operation(), now=1.0).action
    _dispatch_and_complete(engine, write, dispatched_at=1.1, completed_at=1.2)
    deadline = write.deadline

    unrelated = engine.receive_notification(
        connection, raw.response_target, bytes((0x01,)) + bytes(19), now=1.3
    )

    assert (
        unrelated.notification_disposition
        is VendorGattNotificationDisposition.UNRELATED
    )
    assert engine.status == "waiting_for_application_response"
    assert engine.active_operation_token is not None
    assert write.deadline == deadline
    matched = engine.receive_notification(
        connection,
        main.response_target,
        bytes((0x0B, 50, 1)) + bytes(17),
        now=1.4,
    )
    assert (
        matched.notification_disposition
        is VendorGattNotificationDisposition.MATCHED_SUCCESS
    )


def test_stale_callback_at_current_deadline_expires_current_setup_first():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    old = engine.begin_connection(_route(VendorGattRoute.MAIN, 1), now=0.0).action
    engine.record_disconnected(old.connection_token, now=0.1)
    current = engine.begin_connection(
        _route(VendorGattRoute.MAIN, 2), now=0.2
    ).action

    update = engine.record_dispatch(
        old.token, outcome=GattDispatchOutcome.DISPATCHED, now=current.deadline
    )

    assert update.status == "primary_subscription_timed_out"
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


def test_nonfinite_calculated_deadline_is_rejected():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1e308)

    with pytest.raises(ValueError, match="deadline must be finite"):
        engine.begin_connection(_route(VendorGattRoute.MAIN, 1), now=1e308)


def test_write_and_terminal_updates_use_normalized_privacy_safe_results():
    engine, main, _raw, connection = _ready_engine(timeout=2.0)
    write = engine.start_operation(_operation(), now=1.0).action
    engine.record_dispatch(
        write.token, outcome=GattDispatchOutcome.DISPATCHED, now=1.1
    )
    accepted = engine.record_completion(
        write.token,
        target=main.request_target,
        outcome=GattCompletionOutcome.SUCCEEDED,
        now=1.2,
    )

    assert accepted.operation_result.outcome is OperationOutcome.ACCEPTED
    assert accepted.operation_stage == "response"
    terminal = engine.receive_notification(
        connection,
        main.response_target,
        bytes((0x0B, 50, 1)) + bytes(17),
        now=1.3,
    )

    assert terminal.operation_result.outcome is OperationOutcome.RESPONSE_MATCHED
    assert terminal.operation_result.device_effect is DeviceEffectState.UNKNOWN
    assert terminal.completeness == "response_matched"
    assert terminal.closure.response_outcome == "exact_success"
    assert terminal.recovery == "disconnect_then_new_connection"
    assert terminal.connection_phase is VendorGattEnginePhase.RECONNECT_REQUIRED
    assert terminal.operation_stage == "complete"
    assert terminal.input_eligible is False
    assert terminal.automatic_retry == "prohibited"
    assert terminal.replay_allowed is False
    with pytest.raises(TypeError):
        asdict(terminal)
    public = json.dumps(terminal.public_payload(), sort_keys=True)
    assert "getDeviceBatery" not in public
    assert "50" not in public


def test_action_internal_shape_cannot_be_replaced_with_object_setattr():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    action = engine.begin_connection(
        _route(VendorGattRoute.MAIN, 1), now=0.0
    ).action

    with pytest.raises(AttributeError):
        object.__setattr__(action, "_deadline", float("inf"))
    with pytest.raises(AttributeError):
        object.__setattr__(action, "_descriptor_target", object())
    assert action.deadline == 1.0


def test_disconnect_during_primary_setup_names_stage_and_no_retry_automation():
    engine = StrictVendorGattTransactionEngine(operation_timeout=1.0)
    action = engine.begin_connection(
        _route(VendorGattRoute.MAIN, 1), now=0.0
    ).action

    update = engine.record_disconnected(action.connection_token, now=0.1)

    assert update.status == "disconnected_during_primary_subscription"
    assert update.completeness == "aborted"
    assert update.recovery == "reconnect_then_retry_setup"
    assert update.automatic_retry == "prohibited"
    assert update.connection_phase is VendorGattEnginePhase.DISCONNECTED


def test_failed_write_callback_is_normalized_uncertain_and_never_replayed():
    engine, main, _raw, _connection = _ready_engine(timeout=2.0)
    write = engine.start_operation(_operation(), now=1.0).action
    engine.record_dispatch(
        write.token, outcome=GattDispatchOutcome.DISPATCHED, now=1.1
    )

    update = engine.record_completion(
        write.token,
        target=main.request_target,
        outcome=GattCompletionOutcome.FAILED,
        now=1.2,
    )

    assert update.completeness == "uncertain"
    assert update.operation_result.outcome is OperationOutcome.UNCERTAIN
    assert update.operation_result.reason is OperationReason.TRANSPORT_FAILURE
    assert update.operation_result.dispatch_state is DispatchState.POSSIBLY_SENT
    assert update.recovery == "reconnect_no_replay"
    assert engine.phase is VendorGattEnginePhase.RECONNECT_REQUIRED


def test_definitely_not_dispatched_write_is_aborted_without_automatic_replay():
    engine, _main, _raw, _connection = _ready_engine(timeout=2.0)
    write = engine.start_operation(_operation(), now=1.0).action

    update = engine.record_dispatch(
        write.token,
        outcome=GattDispatchOutcome.DEFINITELY_NOT_DISPATCHED,
        now=1.1,
    )

    assert update.completeness == "aborted"
    assert update.operation_result.outcome is OperationOutcome.ABORTED
    assert update.operation_result.dispatch_state is DispatchState.NOT_SENT
    assert update.automatic_retry == "prohibited"
    assert update.action is None
    assert engine.active_operation_token is None


def test_disconnect_before_write_dispatch_is_normalized_aborted():
    engine, _main, _raw, connection = _ready_engine(timeout=2.0)
    engine.start_operation(_operation(), now=1.0)

    update = engine.record_disconnected(connection, now=1.1)

    assert update.completeness == "aborted"
    assert update.operation_result.outcome is OperationOutcome.ABORTED
    assert update.operation_result.reason is OperationReason.DISCONNECTED
    assert update.operation_result.dispatch_state is DispatchState.NOT_SENT
    assert update.recovery == "reconnect_then_retry_setup"
    assert engine.phase is VendorGattEnginePhase.DISCONNECTED
