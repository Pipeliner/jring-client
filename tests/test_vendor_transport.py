import math

import pytest

from jring.protocol import ProtocolError
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F6,
)
from jring.vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    encode_day_query,
    encode_static_query,
)
from jring.vendor_transport import (
    EnginePhase,
    NotificationDisposition,
    NotificationSubscriptionOutcome,
    OfflineVendorOperation,
    OfflineVendorTransactionEngine,
    TransactionCloseReason,
    TransactionCompleteness,
    WriteOutcome,
)
from jring.vendor_settings import (
    HourFormat,
    SensorSessionMode,
    encode_device_name,
    encode_hour_format,
    encode_sensor_session_start,
)
from jring.vendor_personal_settings import encode_reminder_text
from jring.vendor_behavior_settings import AlarmBatchRequest, VibrationRequest
from jring.vendor_main_commands import (
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
    ScreenLightTimeRequest,
)
from jring.vendor_commands import encode_ai_language, encode_device_time
from jring.vendor_phone_integration import encode_user_info


def _operation(name: str = "battery") -> OfflineVendorOperation:
    queries = {
        "battery": StaticQuery.BATTERY,
        "device_info": StaticQuery.DEVICE_INFO,
    }
    if name == "screen_light":
        return OfflineVendorOperation.screen_light_time()
    return OfflineVendorOperation.from_static_request(
        encode_static_query(queries[name])
    )


def _ready_engine(*, timeout: float = 2.0) -> OfflineVendorTransactionEngine:
    engine = OfflineVendorTransactionEngine(operation_timeout=timeout)
    subscription = engine.mark_connected(now=0.0)
    engine.confirm_subscription(
        token=subscription.token,
        characteristic_uuid=subscription.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.1,
    )
    return engine


def test_notification_subscription_confirmation_is_required_before_any_write_intent():
    engine = OfflineVendorTransactionEngine(operation_timeout=5.0)
    subscription = engine.mark_connected(now=0.0)
    token = engine.enqueue(_operation(), now=0.1)

    assert engine.phase is EnginePhase.SUBSCRIPTION_REQUIRED
    assert subscription.characteristic_uuid == VENDOR_CHARACTERISTIC_33F4
    assert not hasattr(subscription, "descriptor_uuid")
    assert not hasattr(subscription, "notifications_enabled")
    assert subscription.hardware_eligible is False
    assert engine.take_write(now=0.2).write_intent is None

    engine.confirm_subscription(
        token=subscription.token,
        characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.3,
    )
    update = engine.take_write(now=0.4)

    assert engine.phase is EnginePhase.READY
    assert update.write_intent is not None
    assert update.write_intent.token == token
    assert update.write_intent.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert update.write_intent.hardware_eligible is False


@pytest.mark.parametrize(
    "characteristic,outcome",
    [
        (
            VENDOR_CHARACTERISTIC_33F3,
            NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        ),
        (VENDOR_CHARACTERISTIC_33F4, "activated"),
    ],
)
def test_subscription_confirmation_fails_closed_on_wrong_readiness_shape(
    characteristic, outcome
):
    engine = OfflineVendorTransactionEngine()
    intent = engine.mark_connected(now=0.0)

    with pytest.raises((ProtocolError, TypeError)):
        engine.confirm_subscription(
            token=intent.token,
            characteristic_uuid=characteristic,
            outcome=outcome,
            now=0.1,
        )

    assert engine.phase is EnginePhase.SUBSCRIPTION_REQUIRED


def test_late_subscription_confirmation_from_old_connection_cannot_ready_a_reconnect():
    engine = OfflineVendorTransactionEngine()
    old_intent = engine.mark_connected(now=0.0)
    engine.record_disconnected()
    current_intent = engine.mark_connected(now=0.1)

    with pytest.raises(ProtocolError, match="stale"):
        engine.confirm_subscription(
            token=old_intent.token,
            characteristic_uuid=current_intent.characteristic_uuid,
            outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
            now=0.2,
        )

    assert engine.phase is EnginePhase.SUBSCRIPTION_REQUIRED
    engine.confirm_subscription(
        token=current_intent.token,
        characteristic_uuid=current_intent.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.3,
    )
    assert engine.phase is EnginePhase.READY


def test_definite_subscription_failure_aborts_queued_work_and_requires_reconnect():
    engine = OfflineVendorTransactionEngine()
    intent = engine.mark_connected(now=0.0)
    operation_token = engine.enqueue(_operation(), now=0.1)

    failed = engine.confirm_subscription(
        token=intent.token,
        characteristic_uuid=intent.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.FAILED,
        now=0.2,
    )

    assert failed.closure.token == operation_token
    assert failed.closure.reason is TransactionCloseReason.SUBSCRIPTION_FAILURE
    assert failed.closure.completeness is TransactionCompleteness.ABORTED
    assert engine.active_token is None
    assert engine.phase is EnginePhase.RECONNECT_REQUIRED
    assert engine.requires_reconnect is True
    with pytest.raises(ProtocolError, match="disconnect"):
        engine.enqueue(_operation(), now=0.25)
    with pytest.raises(ProtocolError, match="disconnect"):
        engine.confirm_subscription(
            token=intent.token,
            characteristic_uuid=intent.characteristic_uuid,
            outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
            now=0.3,
        )


def test_only_one_operation_can_be_queued_or_in_flight():
    engine = _ready_engine()
    engine.enqueue(_operation(), now=0.2)

    with pytest.raises(ProtocolError, match="in flight|queued"):
        engine.enqueue(_operation("device_info"), now=0.3)

    engine.take_write(now=0.4)
    with pytest.raises(ProtocolError, match="in flight|queued"):
        engine.enqueue(_operation("device_info"), now=0.5)


def test_matcher_requires_exact_endpoint_opcode_and_subcommand():
    engine = _ready_engine()
    operation = _operation("screen_light")
    token = engine.enqueue(operation, now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.35)

    wrong_endpoint = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F6,
        data=bytes((0x78, 0x0B)) + bytes(18),
        now=0.4,
    )
    wrong_opcode = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x77, 0x0B)) + bytes(18),
        now=0.5,
    )
    wrong_subcommand = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x78, 0x0A)) + bytes(18),
        now=0.6,
    )
    short_wrong_subcommand = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x78, 0x0A)),
        now=0.65,
    )

    assert wrong_endpoint.disposition is NotificationDisposition.UNRELATED
    assert wrong_opcode.disposition is NotificationDisposition.UNRELATED
    assert wrong_subcommand.disposition is NotificationDisposition.UNRELATED
    assert short_wrong_subcommand.disposition is NotificationDisposition.UNRELATED
    matched = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4.upper(),
        data=bytes((0x78, 0x0B)) + bytes(18),
        now=0.7,
    )
    assert matched.disposition is NotificationDisposition.MATCHED_SUCCESS
    assert matched.closure.reason is TransactionCloseReason.SUCCESS
    assert matched.closure.completeness is TransactionCompleteness.SUCCEEDED


def test_exact_failure_opcode_closes_failed_and_is_not_guessed():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.35)

    result = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x8B,)) + bytes(19),
        now=0.4,
    )

    assert result.disposition is NotificationDisposition.MATCHED_FAILURE
    assert result.closure.reason is TransactionCloseReason.DEVICE_FAILURE
    assert result.closure.completeness is TransactionCompleteness.FAILED
    assert result.closure.hardware_verified is False


def test_notification_cannot_complete_before_characteristic_write_confirmation():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    premature = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 50)) + bytes(18),
        now=0.4,
    )

    assert premature.disposition is NotificationDisposition.NOT_IN_FLIGHT
    assert premature.closure is None
    assert engine.active_token == token
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.5)
    matched = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 50)) + bytes(18),
        now=0.6,
    )
    assert matched.disposition is NotificationDisposition.MATCHED_SUCCESS


def test_definitely_not_dispatched_write_aborts_without_retry_or_taint():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    failed = engine.confirm_write(
        token, outcome=WriteOutcome.DEFINITELY_NOT_DISPATCHED, now=0.4
    )

    assert failed.closure.reason is TransactionCloseReason.WRITE_FAILURE
    assert failed.closure.completeness is TransactionCompleteness.ABORTED
    assert engine.requires_reconnect is False
    assert engine.active_token is None
    assert engine.take_write(now=0.5).write_intent is None


def test_unknown_write_outcome_is_uncertain_and_blocks_work_until_disconnect():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    failed = engine.confirm_write(
        token, outcome=WriteOutcome.OUTCOME_UNKNOWN, now=0.4
    )

    assert failed.closure.reason is TransactionCloseReason.WRITE_FAILURE
    assert failed.closure.completeness is TransactionCompleteness.UNCERTAIN
    assert engine.requires_reconnect is True
    assert engine.phase is EnginePhase.RECONNECT_REQUIRED
    assert engine.active_token is None
    with pytest.raises(ProtocolError, match="disconnect"):
        engine.enqueue(_operation(), now=0.5)
    engine.record_disconnected()
    assert engine.requires_reconnect is False
    subscription = engine.mark_connected(now=0.6)
    engine.confirm_subscription(
        token=subscription.token,
        characteristic_uuid=subscription.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.7,
    )
    assert engine.enqueue(_operation(), now=0.8) is not None


def test_reconnect_required_phase_refuses_all_progress_until_observed_teardown():
    engine = OfflineVendorTransactionEngine()
    subscription = engine.mark_connected(now=0.0)
    engine.confirm_subscription(
        token=subscription.token,
        characteristic_uuid=subscription.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.1,
    )
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.OUTCOME_UNKNOWN, now=0.4)

    with pytest.raises(ProtocolError, match="disconnect"):
        engine.mark_connected(now=0.5)
    with pytest.raises(ProtocolError, match="disconnect"):
        engine.enqueue(_operation(), now=0.6)
    with pytest.raises(ProtocolError, match="disconnect"):
        engine.confirm_subscription(
            token=subscription.token,
            characteristic_uuid=subscription.characteristic_uuid,
            outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
            now=0.7,
        )
    assert engine.take_write(now=0.8).write_intent is None
    assert (
        engine.confirm_write(
            token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.9
        ).closure
        is None
    )
    assert engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 50)) + bytes(18),
        now=1.0,
    ).disposition is NotificationDisposition.STALE
    assert engine.poll(now=1.1).closure is None
    assert engine.phase is EnginePhase.RECONNECT_REQUIRED
    assert not hasattr(engine, "disconnect")


def test_write_confirmation_requires_a_previously_issued_write_intent():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)

    with pytest.raises(ProtocolError):
        engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.3)

    assert engine.active_token == token


def test_missing_characteristic_write_confirmation_times_out_uncertain():
    engine = _ready_engine(timeout=1.0)
    engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    closure = engine.poll(now=1.2).closure

    assert closure.reason is TransactionCloseReason.TIMEOUT
    assert closure.completeness is TransactionCompleteness.UNCERTAIN
    assert engine.requires_reconnect is True
    assert engine.phase is EnginePhase.RECONNECT_REQUIRED
    assert engine.take_write(now=1.3).write_intent is None
    with pytest.raises(ProtocolError, match="disconnect"):
        engine.enqueue(_operation(), now=1.4)


def test_current_generation_notification_at_deadline_times_out_before_stage_check():
    engine = _ready_engine(timeout=1.0)
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    result = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 50)) + bytes(18),
        now=1.2,
    )

    assert result.disposition is NotificationDisposition.TIMED_OUT
    assert result.closure.reason is TransactionCloseReason.TIMEOUT


def test_one_end_to_end_deadline_never_restarts_at_dispatch_or_write_ack():
    engine = _ready_engine(timeout=2.0)
    token = engine.enqueue(_operation(), now=0.2)
    expected = engine.deadline
    intent = engine.take_write(now=1.0).write_intent
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=1.5)

    assert expected == 2.2
    assert intent.deadline == expected
    assert engine.deadline == expected


def test_subscription_confirmation_cannot_stand_in_for_write_confirmation():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    with pytest.raises(ProtocolError):
        engine.confirm_subscription(
            token=token,
            characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
            outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
            now=0.4,
        )
    premature = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 50)) + bytes(18),
        now=0.5,
    )
    assert premature.disposition is NotificationDisposition.NOT_IN_FLIGHT


def test_success_requires_the_closed_operation_specific_parser():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.4)

    malformed = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 101)) + bytes(18),
        now=0.5,
    )

    assert malformed.disposition is NotificationDisposition.MALFORMED
    assert malformed.closure.reason is TransactionCloseReason.MALFORMED_RESPONSE
    assert malformed.closure.completeness is TransactionCompleteness.UNCERTAIN
    assert malformed.parsed_value is None
    assert engine.active_token is None
    assert engine.take_write(now=0.6).write_intent is None


def test_success_returns_typed_value_without_raw_notification_bytes():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.4)
    data = bytes((0x0B, 64, 7)) + bytes(17)

    result = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=data,
        now=0.5,
    )

    assert result.parsed_value.percent == 64
    assert result.parsed_value.state_code == 7
    assert not hasattr(result, "data")
    assert data.hex() not in repr(result)


def test_unrelated_frames_never_refresh_the_immutable_deadline():
    engine = _ready_engine(timeout=2.0)
    token = engine.enqueue(_operation(), now=0.2)
    intent = engine.take_write(now=0.3).write_intent
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.35)
    assert intent.deadline == 2.2

    unrelated = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0C,)) + bytes(19),
        now=2.1,
    )

    assert unrelated.disposition is NotificationDisposition.UNRELATED
    assert engine.deadline == 2.2
    closure = engine.poll(now=2.2).closure
    assert closure.reason is TransactionCloseReason.TIMEOUT
    assert closure.completeness is TransactionCompleteness.UNCERTAIN


def test_timeout_wins_over_a_matching_frame_at_the_exact_deadline():
    engine = _ready_engine(timeout=1.0)
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.4)

    result = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B,)) + bytes(19),
        now=1.2,
    )

    assert result.disposition is NotificationDisposition.TIMED_OUT
    assert result.closure.reason is TransactionCloseReason.TIMEOUT


def test_stale_or_cross_engine_tokens_are_ignored_without_touching_current_work():
    engine = _ready_engine()
    old = engine.enqueue(_operation(), now=0.2)
    engine.cancel()
    current = engine.enqueue(_operation(), now=0.3)
    engine.take_write(now=0.4)
    engine.confirm_write(current, outcome=WriteOutcome.ACKNOWLEDGED, now=0.45)

    stale = engine.receive(
        old,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B,)) + bytes(19),
        now=0.5,
    )
    other_engine = _ready_engine()
    other = other_engine.enqueue(_operation(), now=0.2)
    cross_engine = engine.receive(
        other,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B,)) + bytes(19),
        now=0.6,
    )

    assert stale.disposition is NotificationDisposition.STALE
    assert cross_engine.disposition is NotificationDisposition.STALE
    assert engine.active_token == current
    assert engine.poll(now=0.7).closure is None


@pytest.mark.parametrize(
    "state,completeness",
    [
        ("queued", TransactionCompleteness.ABORTED),
        ("write_pending", TransactionCompleteness.UNCERTAIN),
        ("in_flight", TransactionCompleteness.UNCERTAIN),
    ],
)
def test_disconnect_closes_once_and_clears_every_pending_layer(state, completeness):
    engine = OfflineVendorTransactionEngine()
    subscription = engine.mark_connected(now=0.0)
    token = engine.enqueue(_operation(), now=0.1)
    if state != "queued":
        engine.confirm_subscription(
            token=subscription.token,
            characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
            outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
            now=0.2,
        )
        engine.take_write(now=0.3)
    if state == "in_flight":
        engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.35)

    first = engine.record_disconnected()
    second = engine.record_disconnected()

    assert first.closure.reason is TransactionCloseReason.DISCONNECTED
    assert first.closure.completeness is completeness
    assert first.closure.token == token
    assert second.closure is None
    assert engine.phase is EnginePhase.DISCONNECTED
    assert engine.active_token is None
    subscription = engine.mark_connected(now=0.4)
    engine.confirm_subscription(
        token=subscription.token,
        characteristic_uuid=subscription.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.5,
    )
    assert engine.take_write(now=0.6).write_intent is None


def test_cancel_closes_once_clears_work_and_never_retries():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    first_write = engine.take_write(now=0.3).write_intent

    assert first_write.token == token
    assert engine.take_write(now=0.4).write_intent is None
    first = engine.cancel()
    second = engine.cancel()

    assert first.closure.reason is TransactionCloseReason.CANCELLED
    assert first.closure.completeness is TransactionCompleteness.UNCERTAIN
    assert second.closure is None
    assert engine.take_write(now=0.5).write_intent is None
    assert engine.active_token is None
    assert engine.requires_reconnect is True
    assert engine.phase is EnginePhase.RECONNECT_REQUIRED


@pytest.mark.parametrize("action", ["cancel", "timeout"])
@pytest.mark.parametrize(
    "stage,completeness,reconnect",
    [
        ("queued", TransactionCompleteness.ABORTED, False),
        ("write_pending", TransactionCompleteness.UNCERTAIN, True),
        ("in_flight", TransactionCompleteness.UNCERTAIN, True),
    ],
)
def test_cancel_and_timeout_taint_only_after_write_intent_issuance(
    action, stage, completeness, reconnect
):
    engine = _ready_engine(timeout=1.0)
    token = engine.enqueue(_operation(), now=0.2)
    if stage != "queued":
        engine.take_write(now=0.3)
    if stage == "in_flight":
        engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.4)

    update = engine.cancel() if action == "cancel" else engine.poll(now=1.2)

    assert update.closure.completeness is completeness
    assert update.closure.reason is (
        TransactionCloseReason.CANCELLED
        if action == "cancel"
        else TransactionCloseReason.TIMEOUT
    )
    assert engine.requires_reconnect is reconnect
    assert engine.phase is (
        EnginePhase.RECONNECT_REQUIRED if reconnect else EnginePhase.READY
    )


def test_queued_work_times_out_even_if_subscription_never_becomes_ready():
    engine = OfflineVendorTransactionEngine(operation_timeout=1.0)
    engine.mark_connected(now=0.0)
    engine.enqueue(_operation(), now=0.1)

    closure = engine.poll(now=1.1).closure

    assert closure.reason is TransactionCloseReason.TIMEOUT
    assert closure.completeness is TransactionCompleteness.ABORTED
    assert engine.take_write(now=1.2).write_intent is None


def test_deadline_and_clock_inputs_are_strictly_finite_and_monotonic():
    for timeout in (0, -1, math.inf, math.nan, True):
        with pytest.raises((TypeError, ValueError)):
            OfflineVendorTransactionEngine(operation_timeout=timeout)

    engine = OfflineVendorTransactionEngine(operation_timeout=2.0)
    engine.mark_connected(now=10.0)
    with pytest.raises(ValueError, match="monotonic"):
        engine.enqueue(_operation(), now=9.0)


def test_right_endpoint_with_malformed_frame_fails_closed_without_rescheduling():
    engine = _ready_engine(timeout=2.0)
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)
    engine.confirm_write(token, outcome=WriteOutcome.ACKNOWLEDGED, now=0.4)

    result = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B,)),
        now=1.0,
    )

    assert result.disposition is NotificationDisposition.MALFORMED
    assert result.closure.reason is TransactionCloseReason.MALFORMED_RESPONSE
    assert result.closure.completeness is TransactionCompleteness.UNCERTAIN
    assert engine.requires_reconnect is True
    assert engine.phase is EnginePhase.RECONNECT_REQUIRED
    assert engine.deadline is None


@pytest.mark.parametrize("outcome", [True, False, "acknowledged", None])
def test_write_confirmation_requires_closed_outcome_enum(outcome):
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    with pytest.raises(TypeError):
        engine.confirm_write(token, outcome=outcome, now=0.4)

    assert engine.active_token == token


def test_operation_and_action_repr_never_expose_frames_or_invent_cccd_state():
    operation = _operation()
    frame = operation.synthetic_request_for_test()
    engine = OfflineVendorTransactionEngine()
    subscription = engine.mark_connected(now=0.0)
    engine.enqueue(operation, now=0.1)
    engine.confirm_subscription(
        token=subscription.token,
        characteristic_uuid=subscription.characteristic_uuid,
        outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
        now=0.2,
    )
    write = engine.take_write(now=0.3).write_intent

    assert frame.hex() not in repr(operation)
    assert frame.hex() not in repr(write)
    assert "2902" not in repr(subscription)
    assert operation.hardware_eligible is False
    assert operation.maturity == "static_apk_only"
    assert write.hardware_eligible is False
    assert engine.hardware_eligible is False


def test_operation_constructor_is_closed_over_typed_static_requests():
    with pytest.raises(TypeError):
        OfflineVendorOperation()
    with pytest.raises(TypeError):
        OfflineVendorOperation(
            name="arbitrary",
            request_endpoint_uuid=VENDOR_CHARACTERISTIC_33F3,
            response_endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
            _request_frame=bytes(20),
            success_opcodes=(0x0B,),
        )
    forged = StaticVendorRequest(StaticQuery.BATTERY, bytes((0x0C,)) + bytes(19))
    with pytest.raises(ValueError):
        OfflineVendorOperation.from_static_request(forged)


@pytest.mark.parametrize(
    "query",
    [
        StaticQuery.CURRENT_SPORT,
        StaticQuery.BATTERY,
        StaticQuery.DEVICE_INFO,
        StaticQuery.BAND_FUNCTIONS,
    ],
)
def test_single_response_static_queries_build_hardware_ineligible_operations(query):
    operation = OfflineVendorOperation.from_static_request(encode_static_query(query))

    assert operation.request_endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert operation.response_endpoint_uuid == VENDOR_CHARACTERISTIC_33F4
    assert operation.hardware_eligible is False


@pytest.mark.parametrize(
    "query",
    [
        StaticQuery.MULTI_SPORT_DAY,
        StaticQuery.OXYGEN_DAY,
        StaticQuery.ADVANCED_SENSOR_DAY,
    ],
)
def test_streaming_day_queries_are_rejected_by_single_response_factory(query):
    request = encode_day_query(query, day_offset=3)

    with pytest.raises(TypeError, match="streaming day query.*state machine"):
        OfflineVendorOperation.from_static_request(request)


@pytest.mark.parametrize(
    "setting_request,name,success,failure",
    [
        (encode_hour_format(HourFormat.TWELVE), "hour_format", (0x1D,), (0x9D,)),
        (encode_device_name("Ring"), "device_name", (0x30,), ()),
        (
            encode_sensor_session_start(SensorSessionMode.MODE_2),
            "sensor_session_start",
            (0x23, 0x25),
            (0xA3,),
        ),
    ],
)
def test_typed_setting_requests_compose_fake_only_ack_operations(
    setting_request, name, success, failure
):
    operation = OfflineVendorOperation.from_setting_request(setting_request)

    assert operation.name == name
    assert operation.success_opcodes == success
    assert operation.failure_opcodes == failure
    assert operation.request_endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert operation.response_endpoint_uuid == VENDOR_CHARACTERISTIC_33F4
    assert operation.hardware_eligible is False
    assert "<redacted>" in repr(operation)


def test_setting_operation_matcher_returns_typed_ack_without_becoming_live():
    operation = OfflineVendorOperation.from_setting_request(
        encode_hour_format(HourFormat.TWENTY_FOUR)
    )

    disposition, parsed = operation._match(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x1D,)) + bytes(19)
    )

    assert disposition.value == "success"
    assert parsed.success is True
    assert parsed.operation.value == "hour_format"
    assert not hasattr(operation, "write")
    assert not hasattr(operation, "execute")


def test_personal_setting_request_composes_success_only_fake_matcher_privately():
    request = encode_reminder_text(index=2, text="private reminder")

    operation = OfflineVendorOperation.from_personal_setting_request(request)

    assert operation.name == "reminder_text"
    assert operation.success_opcodes == (0x32,)
    assert operation.failure_opcodes == ()
    assert "private reminder" not in repr(operation)
    disposition, parsed = operation._match(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x32,)) + bytes(19)
    )
    assert disposition.value == "success"
    assert parsed.operation.value == "reminder_text"
    assert parsed.success is True


def test_single_frame_behavior_request_composes_fake_ack_matcher():
    operation = OfflineVendorOperation.from_behavior_request(VibrationRequest(3))

    assert operation.name == "vibration"
    assert operation.success_opcodes == (0x04,)
    assert operation.failure_opcodes == (0x84,)
    disposition, parsed = operation._match(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x04,)) + bytes(19)
    )
    assert disposition.value == "success"
    assert parsed.operation.value == "vibration"
    assert parsed.success is True


def test_multi_frame_alarm_batch_cannot_be_collapsed_into_single_transaction():
    batch = object.__new__(AlarmBatchRequest)
    object.__setattr__(batch, "alarms", ())

    with pytest.raises(TypeError, match="multi-frame"):
        OfflineVendorOperation.from_behavior_request(batch)


def test_closed_main_command_query_composes_subcommand_aware_fake_matcher():
    operation = OfflineVendorOperation.from_main_command_request(
        NoArgumentMainCommandRequest(NoArgumentMainCommand.DEVICE_SYSTEM_STATE)
    )

    assert operation.name == "get_device_system_state"
    assert operation.success_opcodes == (0x54,)
    assert operation.expected_subcommand == 0x12
    disposition, parsed = operation._match(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x54, 0x12, 7)) + bytes(17)
    )
    assert disposition.value == "success"
    assert parsed.event.value == "device_system_state"
    assert parsed.value == 7


def test_screen_light_typed_request_preserves_its_synthetic_value_privately():
    request = ScreenLightTimeRequest(17)
    operation = OfflineVendorOperation.from_main_command_request(request)

    assert operation.name == "set_screen_light_time"
    assert operation.synthetic_request_for_test()[:3] == bytes((0x78, 0x0A, 17))
    assert "17" not in repr(operation)


def test_streaming_wifi_scan_is_rejected_by_single_response_factory():
    request = NoArgumentMainCommandRequest(NoArgumentMainCommand.SCAN_WIFI)

    with pytest.raises(TypeError, match="streaming"):
        OfflineVendorOperation.from_main_command_request(request)


def test_typed_vendor_command_with_exact_ack_composes_fake_operation():
    request = encode_device_time(
        local_epoch_seconds=1_700_000_000, raw_utc_offset_hours=0
    )
    operation = OfflineVendorOperation.from_command_request(request)

    assert operation.name == "device_time"
    assert operation.success_opcodes == (0x01,)
    assert operation.failure_opcodes == (0x81,)
    disposition, parsed = operation._match(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x01,)) + bytes(19)
    )
    assert disposition.value == "success"
    assert parsed.operation.value == "device_time"


def test_command_without_exact_response_correlation_is_rejected():
    request = encode_ai_language("en")

    with pytest.raises(TypeError, match="correlation"):
        OfflineVendorOperation.from_command_request(request)


def test_phone_integration_request_with_ack_composes_without_exposing_profile():
    request = encode_user_info(
        gender_bit_set=False, age=30, height=170, weight=70, unit=0
    )
    operation = OfflineVendorOperation.from_phone_request(request)

    assert operation.name == "user_info"
    assert operation.success_opcodes == (0x02,)
    assert operation.failure_opcodes == (0x82,)
    assert "170" not in repr(operation)
