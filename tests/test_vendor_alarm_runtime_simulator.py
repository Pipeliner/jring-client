import asyncio
import ast
from dataclasses import asdict, fields
import inspect
import json
import time

import pytest

import jring.vendor_alarm_runtime_simulator as alarm_runtime
from jring.uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4
from jring.vendor_alarm_runtime_simulator import (
    AlarmBatchCompleteness,
    AlarmBatchSimulationReason,
    AlarmBatchSimulationTaintedError,
    FakeVendorAlarmBatchSimulator,
)
from jring.vendor_behavior_settings import (
    AlarmBatchRequest,
    AlarmRequest,
    AlarmWeekdays,
    ClockTime,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport


def run(coro):
    return asyncio.run(coro)


def test_fake_alarm_runtime_has_no_live_bluetooth_host_or_input_imports():
    tree = ast.parse(inspect.getsource(alarm_runtime))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    }

    assert imported_roots.isdisjoint(
        {"bleak", "dbus", "evdev", "os", "pathlib", "pydbus", "socket", "subprocess"}
    )


def _alarm(alarm_id: int, content: str) -> AlarmRequest:
    return AlarmRequest(
        alarm_id=alarm_id,
        enabled=True,
        time=ClockTime(7 + alarm_id, 30),
        weekdays=AlarmWeekdays.every_day(),
        single=False,
        content=content,
    )


def _batch() -> AlarmBatchRequest:
    return AlarmBatchRequest((
        _alarm(1, "private wake up"),
        _alarm(2, "private medication reminder"),
    ))


def _ack(opcode: int) -> bytes:
    return bytes((opcode,)) + bytes(19)


def test_exact_alarm_frames_write_in_order_but_never_establish_batch_success():
    batch = _batch()
    expected = tuple(frame.synthetic_bytes_for_test() for frame in batch.frames())
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _ack(0x0D)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(
        batch, quiet_timeout=0.01
    ))

    assert result.reason is AlarmBatchSimulationReason.LOCAL_QUIET
    assert result.completeness is AlarmBatchCompleteness.UNKNOWN
    assert result.write_invoked is True
    assert result.all_planned_fake_write_calls_returned is True
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.success_shaped_callback_observed is True
    assert result.failure_shaped_callback_observed is False
    assert result.batch_success_established is False
    assert result.batch_terminal_observed is False
    assert result.protocol_delivery == "unknown"
    assert result.acknowledgement_correlation == "unavailable"
    assert result.correlated_application_acknowledgement_observed is False
    assert result.batch_acknowledgement_observed is False
    assert result.callback_count_equality_means_success is False
    assert result.failure_stop_policy == (
        "stop_not_yet_invoked_after_uncorrelated_failure"
    )
    assert result.source_partial_enqueue_semantics_reproduced is False
    assert result.quiet_means_success is False
    assert result.simulation_only is True
    assert result.live_available is False
    assert result.owner_authorized is False
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    assert result.input_eligible is False
    assert result.private_alarm_data_retained is False
    assert result.ring_contacted is False
    assert result.ring_alarm_state_changed is False
    assert result.host_alarm_state_changed is False
    assert result.input_emitted is False
    assert result.tainted is False
    assert transport.targeted_write_count == len(expected)
    assert transport.generic_write_count == 0
    assert tuple(
        call.data_for_test() for call in transport.response_write_calls
    ) == expected
    assert all(
        call.characteristic_uuid == VENDOR_CHARACTERISTIC_33F3
        for call in transport.response_write_calls
    )
    rendered = json.dumps(asdict(result), default=str, sort_keys=True)
    assert "private wake up" not in rendered
    assert "medication" not in rendered
    assert "07:30" not in rendered
    fixed = {
        "protocol_delivery",
        "acknowledgement_correlation",
        "correlated_application_acknowledgement_observed",
        "batch_acknowledgement_observed",
        "batch_success_established",
        "batch_terminal_observed",
        "quiet_means_success",
        "callback_count_equality_means_success",
        "failure_stop_policy",
        "simulation_only",
        "live_available",
        "owner_authorized",
        "hardware_eligible",
        "hardware_verified",
        "input_eligible",
        "private_alarm_data_retained",
        "ring_contacted",
        "ring_alarm_state_changed",
        "host_alarm_state_changed",
        "input_emitted",
        "source_partial_enqueue_semantics_reproduced",
    }
    by_name = {item.name: item for item in fields(type(result))}
    assert fixed <= set(by_name)
    assert all(not by_name[name].init for name in fixed)


def test_uncorrelated_failure_shaped_callback_stops_only_future_fake_writes():
    batch = _batch()
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _ack(0x8D)
    )
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(batch, quiet_timeout=0.01))

    assert result.reason is (
        AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
    )
    assert result.completeness is AlarmBatchCompleteness.UNKNOWN
    assert result.failure_shaped_callback_observed is True
    assert result.success_shaped_callback_observed is False
    assert result.all_planned_fake_write_calls_returned is False
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.future_writes_stopped_after_failure is True
    assert result.batch_terminal_observed is False
    assert result.tainted is True
    assert transport.targeted_write_count == 1
    with pytest.raises(AlarmBatchSimulationTaintedError, match="tainted"):
        run(simulator.simulate(batch))


def test_late_failure_does_not_claim_that_nonexistent_writes_were_stopped():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _ack(0x8D)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert result.all_planned_fake_write_calls_returned is True
    assert result.future_writes_stopped_after_failure is False
    assert "no synthetic writes remained to stop" in result.user_guidance
    assert "remaining synthetic writes were stopped" not in result.user_guidance


def test_callback_multiplicity_is_preserved_without_inventing_correlation():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_many(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _ack(0x0D))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _ack(0x0D))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _ack(0x8D))

    transport.before_write = emit_many
    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert result.success_shaped_callback_count == 2
    assert result.failure_shaped_callback_count == 1
    assert result.batch_acknowledgement_observed is False
    assert result.batch_success_established is False
    assert result.acknowledgement_correlation == "unavailable"


def test_failure_observation_stops_counting_at_the_caller_limit():
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_many_failures(fake, _call):
        for _ in range(5):
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _ack(0x8D))

    transport.before_write = emit_many_failures
    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(
        batch, observation_limit=1
    ))

    assert result.reason is (
        AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
    )
    assert result.failure_shaped_callback_count == 1
    assert result.future_writes_stopped_after_failure is True


def test_multiple_owned_failure_callbacks_preserve_multiplicity_before_stop():
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_failures(fake, _call):
        for _ in range(3):
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _ack(0x8D))

    transport.before_write = emit_failures
    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert result.reason is (
        AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
    )
    assert result.failure_shaped_callback_count == 3
    assert result.future_writes_stopped_after_failure is True


def test_failure_remains_primary_when_unrelated_frame_reaches_limit():
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_mixed(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _ack(0x8D))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x1C,)) + bytes(19))

    transport.before_write = emit_mixed
    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(
        batch, observation_limit=2
    ))

    assert result.reason is (
        AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
    )
    assert result.failure_shaped_callback_count == 1
    assert result.unrelated_notification_observed is True
    assert result.future_writes_stopped_after_failure is True


def test_delayed_failure_burst_cannot_overshoot_observation_limit():
    async def scenario():
        transport = ScriptedVendorFakeTransport.vendor_route()

        def schedule_failures(fake, _call):
            loop = asyncio.get_running_loop()
            for _ in range(5):
                loop.call_later(
                    0.001, fake.emit, VENDOR_CHARACTERISTIC_33F4, _ack(0x8D)
                )

        transport.before_write = schedule_failures
        return await FakeVendorAlarmBatchSimulator(transport).simulate(
            AlarmBatchRequest((_alarm(1, ""),)),
            observation_limit=1,
            quiet_timeout=0.1,
        )

    result = run(scenario())

    assert result.reason is (
        AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
    )
    assert result.failure_shaped_callback_count == 1


def test_forged_empty_exact_batch_is_revalidated_before_connect():
    forged = object.__new__(AlarmBatchRequest)
    object.__setattr__(forged, "alarms", ())
    transport = ScriptedVendorFakeTransport.vendor_route()

    with pytest.raises(ValueError, match="at least one alarm"):
        run(FakeVendorAlarmBatchSimulator(transport).simulate(forged))

    assert transport.connect_count == 0
    assert transport.subscribe_count == 0
    assert transport.write_count == 0


@pytest.mark.parametrize("nested_field", ("time", "weekdays"))
def test_forged_nested_alarm_values_are_revalidated_before_connect(nested_field):
    alarm = _alarm(1, "private")
    if nested_field == "time":
        object.__setattr__(alarm.time, "hour", 99)
    else:
        object.__setattr__(alarm.weekdays, "monday", 1)
    batch = AlarmBatchRequest((alarm,))
    transport = ScriptedVendorFakeTransport.vendor_route()

    with pytest.raises((TypeError, ValueError)):
        run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert transport.connect_count == 0
    assert transport.subscribe_count == 0
    assert transport.write_count == 0


@pytest.mark.parametrize(
    ("transport_kwargs", "expected_reason"),
    (
        (
            {"connect_error": RuntimeError("private connect detail")},
            AlarmBatchSimulationReason.CONNECT_FAILURE,
        ),
        (
            {"service_inventory_error": RuntimeError("private inventory detail")},
            AlarmBatchSimulationReason.PREFLIGHT_FAILURE,
        ),
        (
            {"subscribe_error": RuntimeError("private subscribe detail")},
            AlarmBatchSimulationReason.SUBSCRIPTION_FAILURE,
        ),
    ),
)
def test_setup_failures_report_exact_stage_without_leaking_details(
    transport_kwargs, expected_reason
):
    transport = ScriptedVendorFakeTransport.vendor_route(**transport_kwargs)

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(_batch()))

    assert result.reason is expected_reason
    assert result.completeness is AlarmBatchCompleteness.ABORTED
    assert result.write_invoked is False
    assert "private connect detail" not in repr(result)
    assert "private inventory detail" not in repr(result)
    assert "private subscribe detail" not in repr(result)


def test_callback_burst_is_classified_as_queue_overflow_not_write_failure():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def overflow(fake, _call):
        for _ in range(300):
            fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x1C,)) + bytes(19))

    transport.before_write = overflow
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(AlarmBatchRequest((_alarm(1, ""),))))

    assert result.reason is AlarmBatchSimulationReason.QUEUE_OVERFLOW
    assert result.completeness is AlarmBatchCompleteness.UNCERTAIN
    assert result.transport_call_uncertain is False
    assert result.tainted is True


def test_prewrite_alarm_callback_is_unowned_and_cannot_stop_dispatch():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _ack(0x8D)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(
        batch, quiet_timeout=0.01
    ))

    assert result.reason is AlarmBatchSimulationReason.LOCAL_QUIET
    assert result.failure_shaped_callback_observed is False
    assert result.all_planned_fake_write_calls_returned is True
    assert transport.targeted_write_count == len(batch.frames())


def test_inbound_content_opcode_is_unrelated_not_a_matching_alarm_callback():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x1C, 0x81)) + bytes(18)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(
        batch, quiet_timeout=0.01
    ))

    assert result.completeness is AlarmBatchCompleteness.UNKNOWN
    assert result.unrelated_notification_observed is True
    assert result.success_shaped_callback_observed is False
    assert result.failure_shaped_callback_observed is False


def test_observation_limit_after_all_writes_is_unknown_not_success():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x1C, 0x81)) + bytes(18)
    )
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(batch, observation_limit=1))

    assert result.reason is AlarmBatchSimulationReason.OBSERVATION_LIMIT
    assert result.completeness is AlarmBatchCompleteness.UNKNOWN
    assert result.all_planned_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.batch_success_established is False
    assert result.tainted is False


def test_mid_plan_observation_limit_is_local_abort_without_call_uncertainty():
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x1C,)) + bytes(19)
    )
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(batch, observation_limit=1))

    assert result.reason is AlarmBatchSimulationReason.OBSERVATION_LIMIT
    assert result.completeness is AlarmBatchCompleteness.ABORTED
    assert result.all_planned_fake_write_calls_returned is False
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.tainted is True
    with pytest.raises(AlarmBatchSimulationTaintedError, match="unsafe prior"):
        run(simulator.simulate(batch))


def test_invoked_write_timeout_is_uncertain_and_distinct_from_setup_timeout():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(
        AlarmBatchRequest((_alarm(1, "private"),)), stage_timeout=0.01
    ))

    assert result.reason is AlarmBatchSimulationReason.WRITE_TIMEOUT
    assert result.completeness is AlarmBatchCompleteness.UNCERTAIN
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert transport.targeted_write_count == 1


def test_overall_observation_deadline_after_returned_writes_stays_unknown():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(
        batch, quiet_timeout=0.1, overall_timeout=0.02
    ))

    assert result.reason is AlarmBatchSimulationReason.OVERALL_TIMEOUT
    assert result.completeness is AlarmBatchCompleteness.UNKNOWN
    assert result.all_planned_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.tainted is False


@pytest.mark.parametrize("opcode", (0x0D, 0x8D))
def test_malformed_matching_callback_after_dispatch_is_uncertain_and_tainted(opcode):
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((opcode,)) + bytes(18)
    )
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(batch, quiet_timeout=0.01))

    assert result.reason is AlarmBatchSimulationReason.MALFORMED_MATCHING_CALLBACK
    assert result.completeness is AlarmBatchCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.tainted is True
    assert result.batch_success_established is False


def test_invoked_write_failure_is_uncertain_tainted_and_never_retried():
    batch = AlarmBatchRequest((_alarm(1, "private"),))
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=RuntimeError("private backend detail")
    )
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(batch))

    assert result.reason is AlarmBatchSimulationReason.WRITE_FAILURE
    assert result.completeness is AlarmBatchCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.all_planned_fake_write_calls_returned is False
    assert result.all_invoked_fake_write_calls_returned is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert transport.targeted_write_count == 1
    assert "private backend detail" not in repr(result)
    with pytest.raises(AlarmBatchSimulationTaintedError, match="tainted"):
        run(simulator.simulate(batch))


def test_owned_failure_callback_survives_write_error_without_false_stop_causality():
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=RuntimeError("private write detail")
    )
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _ack(0x8D)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert result.reason is AlarmBatchSimulationReason.WRITE_FAILURE
    assert result.failure_shaped_callback_count == 1
    assert result.future_writes_stopped_after_failure is False
    assert result.transport_call_uncertain is True


def test_owned_failure_callback_survives_blocked_write_timeout():
    gate = ScriptGate.blocked()
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _ack(0x8D)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(
        batch, stage_timeout=0.01
    ))

    assert result.reason is AlarmBatchSimulationReason.WRITE_TIMEOUT
    assert result.failure_shaped_callback_count == 1
    assert result.future_writes_stopped_after_failure is False
    assert result.transport_call_uncertain is True
    assert "attempt ended before the planned fake calls returned" in result.user_guidance
    assert "after every fake write call returned" not in result.user_guidance


def test_successful_write_return_is_preserved_when_disconnect_finishes_together():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: (
        asyncio.get_running_loop().call_soon(fake.emit_disconnect)
    )

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert result.reason is AlarmBatchSimulationReason.DISCONNECTED
    assert result.all_planned_fake_write_calls_returned is True
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False


def test_disconnect_caused_write_exception_is_classified_as_disconnect():
    batch = AlarmBatchRequest((_alarm(1, ""),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit_disconnect()

    result = run(FakeVendorAlarmBatchSimulator(transport).simulate(batch))

    assert result.reason is AlarmBatchSimulationReason.DISCONNECTED
    assert result.all_invoked_fake_write_calls_returned is False
    assert result.transport_call_uncertain is True


def test_owned_observation_is_counted_when_disconnect_finishes_together():
    async def scenario():
        transport = ScriptedVendorFakeTransport.vendor_route()

        def after_write(fake, _call):
            loop = asyncio.get_running_loop()
            loop.call_later(0.001, fake.emit, VENDOR_CHARACTERISTIC_33F4, _ack(0x0D))
            loop.call_later(0.001, fake.emit_disconnect)

        transport.before_write = after_write
        return await FakeVendorAlarmBatchSimulator(transport).simulate(
            AlarmBatchRequest((_alarm(1, ""),)), quiet_timeout=0.1
        )

    result = run(scenario())

    assert result.reason is AlarmBatchSimulationReason.DISCONNECTED
    assert result.success_shaped_callback_count == 1


def test_partial_plan_overall_timeout_taints_reuse_without_call_uncertainty():
    batch = AlarmBatchRequest((_alarm(1, "multiple frames"),))
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda _fake, _call: time.sleep(0.02)
    simulator = FakeVendorAlarmBatchSimulator(transport)

    result = run(simulator.simulate(batch, overall_timeout=0.01))

    assert result.reason is AlarmBatchSimulationReason.OVERALL_TIMEOUT
    assert result.completeness is AlarmBatchCompleteness.ABORTED
    assert result.all_planned_fake_write_calls_returned is False
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.tainted is True
    with pytest.raises(AlarmBatchSimulationTaintedError, match="unsafe prior"):
        run(simulator.simulate(batch))


def test_exact_types_and_preconnected_transport_fail_before_fake_io():
    class UnsafeFakeSubclass(ScriptedVendorFakeTransport):
        pass

    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorAlarmBatchSimulator(UnsafeFakeSubclass(services=set(), metadata=()))

    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorAlarmBatchSimulator(transport)
    with pytest.raises(TypeError, match="exact AlarmBatchRequest"):
        run(simulator.simulate(object()))
    assert transport.connect_count == 0

    preconnected = ScriptedVendorFakeTransport.vendor_route()
    run(preconnected.connect())
    with pytest.raises(RuntimeError, match="already connected or in use"):
        run(FakeVendorAlarmBatchSimulator(preconnected).simulate(_batch()))
    assert preconnected.write_count == 0


def test_cancellation_during_invoked_write_taints_and_finishes_cleanup():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorAlarmBatchSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.simulate(_batch(), stage_timeout=0.1))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        gate.release()
        with pytest.raises(AlarmBatchSimulationTaintedError, match="tainted"):
            await simulator.simulate(_batch())

    run(scenario())
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1


def test_cleanup_failure_uses_pre_and_post_write_uncertainty_boundary():
    post = ScriptedVendorFakeTransport.vendor_route(
        close_error=RuntimeError("private close detail")
    )
    post_result = run(FakeVendorAlarmBatchSimulator(post).simulate(
        AlarmBatchRequest((_alarm(1, ""),)), quiet_timeout=0.01
    ))
    assert post_result.reason is AlarmBatchSimulationReason.CLEANUP_FAILURE
    assert post_result.completeness is AlarmBatchCompleteness.UNCERTAIN
    assert post_result.tainted is True

    pre = ScriptedVendorFakeTransport.vendor_route(
        subscribe_error=RuntimeError("private subscribe detail"),
        close_error=RuntimeError("private close detail"),
    )
    pre_result = run(FakeVendorAlarmBatchSimulator(pre).simulate(_batch()))
    assert pre_result.reason is AlarmBatchSimulationReason.CLEANUP_FAILURE
    assert pre_result.completeness is AlarmBatchCompleteness.ABORTED
    assert pre_result.write_invoked is False
    assert pre_result.tainted is True
