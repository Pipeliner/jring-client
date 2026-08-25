import math

import pytest

from jring.protocol import ProtocolError
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F6,
    uuid16,
)
from jring.vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    encode_day_query,
    encode_static_query,
    static_protocol_coverage,
)
from jring.vendor_transport import (
    EnginePhase,
    NotificationDisposition,
    OfflineVendorOperation,
    OfflineVendorTransactionEngine,
    TransactionCloseReason,
    TransactionCompleteness,
)


CCCD = uuid16(0x2902)


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
    descriptor = engine.mark_connected(now=0.0)
    engine.confirm_cccd(
        token=descriptor.token,
        characteristic_uuid=descriptor.characteristic_uuid,
        descriptor_uuid=descriptor.descriptor_uuid,
        enabled=True,
        now=0.1,
    )
    return engine


def test_cccd_confirmation_is_required_before_any_write_intent():
    engine = OfflineVendorTransactionEngine(operation_timeout=5.0)
    descriptor = engine.mark_connected(now=0.0)
    token = engine.enqueue(_operation(), now=0.1)

    assert engine.phase is EnginePhase.DESCRIPTOR_REQUIRED
    assert descriptor.characteristic_uuid == VENDOR_CHARACTERISTIC_33F4
    assert descriptor.descriptor_uuid == CCCD
    assert descriptor.notifications_enabled is True
    assert descriptor.hardware_eligible is False
    assert engine.take_write(now=0.2).write_intent is None

    engine.confirm_cccd(
        token=descriptor.token,
        characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
        descriptor_uuid=CCCD,
        enabled=True,
        now=0.3,
    )
    update = engine.take_write(now=0.4)

    assert engine.phase is EnginePhase.READY
    assert update.write_intent is not None
    assert update.write_intent.token == token
    assert update.write_intent.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert update.write_intent.hardware_eligible is False


@pytest.mark.parametrize(
    "characteristic,descriptor,enabled",
    [
        (VENDOR_CHARACTERISTIC_33F3, CCCD, True),
        (VENDOR_CHARACTERISTIC_33F4, uuid16(0x2901), True),
    ],
)
def test_cccd_confirmation_fails_closed_on_wrong_readiness_shape(
    characteristic, descriptor, enabled
):
    engine = OfflineVendorTransactionEngine()
    intent = engine.mark_connected(now=0.0)

    with pytest.raises(ProtocolError):
        engine.confirm_cccd(
            token=intent.token,
            characteristic_uuid=characteristic,
            descriptor_uuid=descriptor,
            enabled=enabled,
            now=0.1,
        )

    assert engine.phase is EnginePhase.DESCRIPTOR_REQUIRED


def test_late_cccd_confirmation_from_old_connection_cannot_ready_a_reconnect():
    engine = OfflineVendorTransactionEngine()
    old_intent = engine.mark_connected(now=0.0)
    engine.disconnect()
    current_intent = engine.mark_connected(now=0.1)

    with pytest.raises(ProtocolError, match="stale"):
        engine.confirm_cccd(
            token=old_intent.token,
            characteristic_uuid=current_intent.characteristic_uuid,
            descriptor_uuid=current_intent.descriptor_uuid,
            enabled=True,
            now=0.2,
        )

    assert engine.phase is EnginePhase.DESCRIPTOR_REQUIRED
    engine.confirm_cccd(
        token=current_intent.token,
        characteristic_uuid=current_intent.characteristic_uuid,
        descriptor_uuid=current_intent.descriptor_uuid,
        enabled=True,
        now=0.3,
    )
    assert engine.phase is EnginePhase.READY


def test_definite_cccd_failure_closes_queued_work_and_cannot_be_replayed():
    engine = OfflineVendorTransactionEngine()
    intent = engine.mark_connected(now=0.0)
    operation_token = engine.enqueue(_operation(), now=0.1)

    failed = engine.confirm_cccd(
        token=intent.token,
        characteristic_uuid=intent.characteristic_uuid,
        descriptor_uuid=intent.descriptor_uuid,
        enabled=False,
        now=0.2,
    )

    assert failed.closure.token == operation_token
    assert failed.closure.reason is TransactionCloseReason.DESCRIPTOR_FAILURE
    assert failed.closure.completeness is TransactionCompleteness.FAILED
    assert engine.active_token is None
    assert engine.phase is EnginePhase.DESCRIPTOR_REQUIRED
    with pytest.raises(ProtocolError, match="stale"):
        engine.confirm_cccd(
            token=intent.token,
            characteristic_uuid=intent.characteristic_uuid,
            descriptor_uuid=intent.descriptor_uuid,
            enabled=True,
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
    engine.confirm_write(token, succeeded=True, now=0.35)

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

    assert wrong_endpoint.disposition is NotificationDisposition.UNRELATED
    assert wrong_opcode.disposition is NotificationDisposition.UNRELATED
    assert wrong_subcommand.disposition is NotificationDisposition.UNRELATED
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
    engine.confirm_write(token, succeeded=True, now=0.35)

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
    engine.confirm_write(token, succeeded=True, now=0.5)
    matched = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B, 50)) + bytes(18),
        now=0.6,
    )
    assert matched.disposition is NotificationDisposition.MATCHED_SUCCESS


def test_characteristic_write_failure_closes_without_retry():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    failed = engine.confirm_write(token, succeeded=False, now=0.4)

    assert failed.closure.reason is TransactionCloseReason.WRITE_FAILURE
    assert failed.closure.completeness is TransactionCompleteness.FAILED
    assert engine.active_token is None
    assert engine.take_write(now=0.5).write_intent is None


def test_write_confirmation_requires_a_previously_issued_write_intent():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)

    with pytest.raises(ProtocolError):
        engine.confirm_write(token, succeeded=True, now=0.3)

    assert engine.active_token == token


def test_missing_characteristic_write_confirmation_times_out_uncertain():
    engine = _ready_engine(timeout=1.0)
    engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    closure = engine.poll(now=1.2).closure

    assert closure.reason is TransactionCloseReason.TIMEOUT
    assert closure.completeness is TransactionCompleteness.UNCERTAIN
    assert engine.take_write(now=1.3).write_intent is None


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
    engine.confirm_write(token, succeeded=True, now=1.5)

    assert expected == 2.2
    assert intent.deadline == expected
    assert engine.deadline == expected


def test_cccd_confirmation_cannot_stand_in_for_characteristic_write_confirmation():
    engine = _ready_engine()
    token = engine.enqueue(_operation(), now=0.2)
    engine.take_write(now=0.3)

    with pytest.raises(ProtocolError):
        engine.confirm_cccd(
            token=token,
            characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
            descriptor_uuid=CCCD,
            enabled=True,
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
    engine.confirm_write(token, succeeded=True, now=0.4)

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
    engine.confirm_write(token, succeeded=True, now=0.4)
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
    engine.confirm_write(token, succeeded=True, now=0.35)
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
    engine.confirm_write(token, succeeded=True, now=0.4)

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
    engine.confirm_write(current, succeeded=True, now=0.45)

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
    descriptor = engine.mark_connected(now=0.0)
    token = engine.enqueue(_operation(), now=0.1)
    if state != "queued":
        engine.confirm_cccd(
            token=descriptor.token,
            characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
            descriptor_uuid=CCCD,
            enabled=True,
            now=0.2,
        )
        engine.take_write(now=0.3)
    if state == "in_flight":
        engine.confirm_write(token, succeeded=True, now=0.35)

    first = engine.disconnect()
    second = engine.disconnect()

    assert first.closure.reason is TransactionCloseReason.DISCONNECTED
    assert first.closure.completeness is completeness
    assert first.closure.token == token
    assert second.closure is None
    assert engine.phase is EnginePhase.DISCONNECTED
    assert engine.active_token is None
    descriptor = engine.mark_connected(now=0.4)
    engine.confirm_cccd(
        token=descriptor.token,
        characteristic_uuid=descriptor.characteristic_uuid,
        descriptor_uuid=descriptor.descriptor_uuid,
        enabled=True,
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


def test_queued_work_times_out_even_if_descriptor_never_becomes_ready():
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
    engine.confirm_write(token, succeeded=True, now=0.4)

    result = engine.receive(
        token,
        endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
        data=bytes((0x0B,)),
        now=1.0,
    )

    assert result.disposition is NotificationDisposition.MALFORMED
    assert result.closure.reason is TransactionCloseReason.MALFORMED_RESPONSE
    assert result.closure.completeness is TransactionCompleteness.UNCERTAIN
    assert engine.deadline is None


def test_operation_and_action_repr_never_expose_frames_or_cccd_value():
    operation = _operation()
    frame = operation.synthetic_request_for_test()
    engine = OfflineVendorTransactionEngine()
    descriptor = engine.mark_connected(now=0.0)
    engine.enqueue(operation, now=0.1)
    engine.confirm_cccd(
        token=descriptor.token,
        characteristic_uuid=descriptor.characteristic_uuid,
        descriptor_uuid=descriptor.descriptor_uuid,
        enabled=True,
        now=0.2,
    )
    write = engine.take_write(now=0.3).write_intent

    assert frame.hex() not in repr(operation)
    assert frame.hex() not in repr(write)
    assert "0100" not in repr(descriptor)
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


def test_all_seven_static_queries_build_closed_hardware_ineligible_operations():
    coverage = {entry.operation: entry for entry in static_protocol_coverage()}
    for query in StaticQuery:
        request = (
            encode_static_query(query)
            if query in {
                StaticQuery.CURRENT_SPORT,
                StaticQuery.BATTERY,
                StaticQuery.DEVICE_INFO,
                StaticQuery.BAND_FUNCTIONS,
            }
            else encode_day_query(query, day_offset=3)
        )

        operation = OfflineVendorOperation.from_static_request(request)

        assert operation.request_endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
        assert operation.response_endpoint_uuid == VENDOR_CHARACTERISTIC_33F4
        assert operation.success_opcodes == coverage[query].success_opcodes
        assert operation.failure_opcodes == coverage[query].failure_opcodes
        assert operation.hardware_eligible is False
