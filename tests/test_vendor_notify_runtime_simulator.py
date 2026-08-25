import asyncio
import ast
from dataclasses import asdict, fields, replace
import inspect
import json

import pytest

import jring.vendor_notify_runtime_simulator as notify_runtime
from jring.transport import GattCharacteristicMetadata
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from jring.vendor_notify import (
    NotifyDisposition,
    NotifyPlannerState,
    NotifyRequest,
    plan_notify,
)
from jring.vendor_notify_runtime_simulator import (
    FakeVendorNotifyBatchSimulator,
    NotifyBatchCompleteness,
    NotifyBatchSimulationReason,
    NotifyBatchSimulationTaintedError,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport
from jring.vendor_runtime_eligibility import require_fake_singleton_terminal


def run(coro):
    return asyncio.run(coro)


def _state(*, last_notification_id=None):
    return NotifyPlannerState.synthetic_for_test(
        next_uid=0, last_notification_id=last_notification_id
    )


def _request(
    *, notification_id="private-id", title="private title", content="x" * 20
):
    return NotifyRequest.create(
        notification_id=notification_id,
        category=7,
        title=title,
        content=content,
    )


def _success(marker):
    return bytes((0x12, 0, marker)) + bytes(17)


def _failure():
    return bytes((0x92,)) + bytes(19)


def test_fake_notify_runtime_has_no_live_host_network_or_input_imports():
    tree = ast.parse(inspect.getsource(notify_runtime))
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
    assert FakeVendorNotifyBatchSimulator.reproduced_request_names() == frozenset(
        {"setNotify"}
    )
    with pytest.raises(TypeError, match="ambiguous_or_batched_per_frame"):
        require_fake_singleton_terminal("setNotify")


def test_exact_marker_bound_notify_frames_never_establish_batch_delivery_or_commit_state():
    state = _state()
    request = _request()
    expected = plan_notify(state, request).synthetic_frames_for_test()
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _success(call.data_for_test()[2])
    )

    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        state, request, quiet_timeout=0.01
    ))

    assert result.disposition is NotifyDisposition.PLANNED
    assert result.reason is NotifyBatchSimulationReason.LOCAL_QUIET
    assert result.completeness is NotifyBatchCompleteness.UNKNOWN
    assert result.write_invoked is True
    assert result.all_planned_fake_write_calls_returned is True
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.marker_matched_callback_observed is True
    assert result.multiple_distinct_marker_callbacks_observed is True
    assert result.duplicate_marker_callback_observed is False
    assert result.unmarked_failure_callback_observed is False
    assert result.unmatched_marker_callback_observed is False
    assert result.protocol_delivery == "unknown"
    assert result.acknowledgement_correlation == "per_invoked_marker_only"
    assert result.disposition_scope == "offline_planner_only"
    assert result.transport_scope == "exact_scripted_fake_only"
    assert result.fake_write_plan == "planned_batch"
    assert result.batch_acknowledgement_observed is False
    assert result.batch_success_established is False
    assert result.batch_terminal_observed is False
    assert result.callback_marker_coverage_means_success is False
    assert result.planner_state_committed is False
    assert result.runtime_batch_atomic is False
    assert result.automatic_retry is False
    assert result.ring_contacted is False
    assert result.ring_display_changed is False
    assert result.host_notification_changed is False
    assert result.input_emitted is False
    assert result.simulation_only is True
    assert result.live_available is False
    assert result.owner_authorized is False
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    assert result.input_eligible is False
    assert result.result_retains_private_notification_data is False
    assert result.scripted_transport_contains_private_test_frames is True
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
    for private in ("private-id", "private title", "0000", "78787878"):
        assert private not in rendered
        assert private not in repr(result)
        assert private not in result.user_guidance
    assert "total_frames" not in rendered
    assert "marker_ids" not in rendered
    fixed = {
        "protocol_delivery",
        "acknowledgement_correlation",
        "batch_acknowledgement_observed",
        "batch_success_established",
        "batch_terminal_observed",
        "callback_marker_coverage_means_success",
        "planner_state_committed",
        "runtime_batch_atomic",
        "automatic_retry",
        "ring_contacted",
        "ring_display_changed",
        "host_notification_changed",
        "input_emitted",
        "simulation_only",
        "live_available",
        "owner_authorized",
        "hardware_eligible",
        "hardware_verified",
        "input_eligible",
        "result_retains_private_notification_data",
    }
    by_name = {item.name: item for item in fields(type(result))}
    assert fixed <= set(by_name)
    assert all(not by_name[name].init for name in fixed)


def test_deduplicated_plan_performs_zero_transport_io_and_commits_nothing():
    state = _state(last_notification_id="same")
    request = _request(notification_id="same")
    transport = ScriptedVendorFakeTransport.vendor_route()

    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(state, request))

    assert result.disposition is NotifyDisposition.DEDUPLICATED
    assert result.reason is NotifyBatchSimulationReason.DEDUPLICATED
    assert result.completeness is NotifyBatchCompleteness.NOT_DISPATCHED
    assert result.write_invoked is False
    assert result.protocol_delivery == "not_attempted"
    assert result.acknowledgement_correlation == "not_applicable"
    assert result.fake_write_plan == "none_deduplicated"
    assert result.scripted_transport_contains_private_test_frames is False
    assert result.planner_state_committed is False
    assert result.cleanup_succeeded is True
    assert transport.connect_count == 0
    assert transport.subscribe_count == 0
    assert transport.write_count == 0
    assert transport.close_count == 0


def test_future_marker_is_unowned_diagnostic_and_never_acknowledges_a_later_frame():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, call: (
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _success(2))
        if call.data_for_test()[2] == 1
        else None
    )
    simulator = FakeVendorNotifyBatchSimulator(transport)

    result = run(simulator.simulate(_state(), _request()))

    assert result.reason is NotifyBatchSimulationReason.LOCAL_QUIET
    assert result.completeness is NotifyBatchCompleteness.UNKNOWN
    assert result.unmatched_marker_callback_observed is True
    assert result.marker_matched_callback_observed is False
    assert result.all_planned_fake_write_calls_returned is True
    assert result.tainted is False
    assert transport.targeted_write_count == 4


def test_retained_frame_warning_reflects_transport_storage_across_attempts():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorNotifyBatchSimulator(transport)
    run(simulator.simulate(_state(), _request(), quiet_timeout=0.01))

    retained = run(simulator.simulate(
        _state(last_notification_id="same"),
        _request(notification_id="same"),
    ))

    assert retained.write_invoked is False
    assert retained.scripted_transport_contains_private_test_frames is True
    assert "clear_sensitive_test_state()" in retained.user_guidance
    assert "simulator and transport" in retained.user_guidance

    transport.clear_sensitive_test_state()
    cleared = run(simulator.simulate(
        _state(last_notification_id="same"),
        _request(notification_id="same"),
    ))
    assert cleared.scripted_transport_contains_private_test_frames is False
    assert "clear_sensitive_test_state()" not in cleared.user_guidance


def test_future_marker_ownership_is_fixed_at_arrival_not_when_queue_is_drained():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_between_drains(fake, call):
        if call.data_for_test()[2] != 1:
            return

        async def delayed():
            for _ in range(7):
                await asyncio.sleep(0)
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _success(2))

        asyncio.create_task(delayed())

    transport.before_write = emit_between_drains
    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))

    assert result.reason is NotifyBatchSimulationReason.LOCAL_QUIET
    assert result.unmatched_marker_callback_observed is True
    assert result.marker_matched_callback_observed is False
    assert result.all_planned_fake_write_calls_returned is True
    assert result.tainted is False


def test_prewrite_success_and_failure_callbacks_are_unowned():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_early(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _success(1))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _failure())

    transport.before_subscribe = emit_early
    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))

    assert result.reason is NotifyBatchSimulationReason.LOCAL_QUIET
    assert result.marker_matched_callback_observed is False
    assert result.unmarked_failure_callback_observed is False
    assert result.all_planned_fake_write_calls_returned is True


@pytest.mark.parametrize(
    "metadata",
    (
        (
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F3,
                properties=("write",),
                descriptor_uuids=(),
            ),
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F4,
                properties=("notify",),
                descriptor_uuids=(),
            ),
        ),
        (
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F3,
                properties=("write",),
                descriptor_uuids=(),
            ),
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F4,
                properties=("notify",),
                descriptor_uuids=(uuid16(0x2902),),
            ),
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F4,
                properties=("notify",),
                descriptor_uuids=(uuid16(0x2902),),
            ),
        ),
    ),
)
def test_structurally_ambiguous_or_missing_cccd_route_never_subscribes_or_writes(
    metadata,
):
    transport = ScriptedVendorFakeTransport(
        services={VENDOR_SERVICE_56FF}, metadata=metadata
    )

    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request()
    ))

    assert result.reason is NotifyBatchSimulationReason.PREFLIGHT_FAILURE
    assert result.write_invoked is False
    assert result.protocol_delivery == "not_attempted"
    assert result.acknowledgement_correlation == "not_applicable"
    assert transport.subscribe_count == 0
    assert transport.write_count == 0
    assert transport.close_count == 1


def test_targeted_subscription_is_confirmed_before_writes_and_identity_is_reused():
    events = []
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda _fake, call: events.append(
        ("subscribe", call.target_instance_id)
    )
    transport.before_write = lambda _fake, call: events.append(
        ("write", call.target_instance_id)
    )
    transport.before_unsubscribe = lambda _fake, call: events.append(
        ("unsubscribe", call.target_instance_id)
    )

    run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))

    assert events[0][0] == "subscribe"
    assert events[-1][0] == "unsubscribe"
    assert all(kind != "write" for kind, _identity in events[:1])
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.generic_write_count == 0
    assert transport.subscription_calls[0].target_instance_id == events[-1][1]


def test_stale_callback_from_prior_connection_generation_is_ignored():
    transport = ScriptedVendorFakeTransport.vendor_route()
    first = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))
    assert first.marker_matched_callback_observed is False

    transport.before_write = lambda fake, call: (
        fake.emit_stale(0, _success(call.data_for_test()[2]))
    )
    second = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))

    assert second.marker_matched_callback_observed is False
    assert second.unmatched_marker_callback_observed is False
    assert transport.connection_generation == 2


def test_duplicate_owned_marker_is_diagnostic_not_batch_completion():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_duplicate(fake, call):
        marker = call.data_for_test()[2]
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _success(marker))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _success(marker))

    transport.before_write = emit_duplicate
    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))

    assert result.marker_matched_callback_observed is True
    assert result.duplicate_marker_callback_observed is True
    assert result.batch_success_established is False
    assert result.completeness is NotifyBatchCompleteness.UNKNOWN


def test_quiet_without_callbacks_and_complete_marker_limit_both_stay_unknown():
    quiet_transport = ScriptedVendorFakeTransport.vendor_route()
    quiet_result = run(FakeVendorNotifyBatchSimulator(quiet_transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))
    assert quiet_result.reason is NotifyBatchSimulationReason.LOCAL_QUIET
    assert quiet_result.completeness is NotifyBatchCompleteness.UNKNOWN
    assert quiet_result.batch_success_established is False

    limit_transport = ScriptedVendorFakeTransport.vendor_route()
    limit_transport.before_write = lambda fake, call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _success(call.data_for_test()[2])
    )
    limit_result = run(FakeVendorNotifyBatchSimulator(limit_transport).simulate(
        _state(), _request(), observation_limit=4
    ))
    assert limit_result.reason is NotifyBatchSimulationReason.OBSERVATION_LIMIT
    assert limit_result.completeness is NotifyBatchCompleteness.UNKNOWN
    assert limit_result.all_planned_fake_write_calls_returned is True
    assert limit_result.tainted is False


def test_mid_plan_observation_limit_aborts_and_blocks_reuse_without_call_uncertainty():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _success(call.data_for_test()[2])
    )
    simulator = FakeVendorNotifyBatchSimulator(transport)

    result = run(simulator.simulate(
        _state(), _request(), observation_limit=1
    ))

    assert result.reason is NotifyBatchSimulationReason.OBSERVATION_LIMIT
    assert result.completeness is NotifyBatchCompleteness.ABORTED
    assert result.all_planned_fake_write_calls_returned is False
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.tainted is True
    with pytest.raises(NotifyBatchSimulationTaintedError, match="tainted"):
        run(simulator.simulate(_state(), _request()))


def test_unmarked_failure_stops_only_not_yet_invoked_fake_writes():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _failure()
    )
    simulator = FakeVendorNotifyBatchSimulator(transport)

    result = run(simulator.simulate(_state(), _request()))

    assert result.reason is NotifyBatchSimulationReason.UNMARKED_FAILURE_OBSERVED
    assert result.completeness is NotifyBatchCompleteness.UNKNOWN
    assert result.unmarked_failure_callback_observed is True
    assert result.future_writes_stopped_after_failure is True
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False
    assert result.batch_terminal_observed is False
    assert result.tainted is True
    assert transport.targeted_write_count == 1


def test_multiple_unmarked_failures_are_reported_without_an_exact_count():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_failures(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _failure())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _failure())

    transport.before_write = emit_failures
    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request()
    ))

    assert result.unmarked_failure_callback_observed is True
    assert result.multiple_unmarked_failure_callbacks_observed is True
    assert result.future_writes_stopped_after_failure is True
    assert result.batch_terminal_observed is False


def test_failure_remains_primary_at_limit_with_a_future_marker_also_observed():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_mixed(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _failure())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _success(2))

    transport.before_write = emit_mixed
    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), observation_limit=2
    ))

    assert result.reason is NotifyBatchSimulationReason.UNMARKED_FAILURE_OBSERVED
    assert result.unmarked_failure_callback_observed is True
    assert result.unmatched_marker_callback_observed is True
    assert result.future_writes_stopped_after_failure is True


def test_late_unmarked_failure_does_not_claim_that_writes_were_stopped():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def fail_on_final(fake, call):
        frame = call.data_for_test()
        if frame[2] == frame[1]:
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _failure())

    transport.before_write = fail_on_final
    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request()
    ))

    assert result.reason is NotifyBatchSimulationReason.UNMARKED_FAILURE_OBSERVED
    assert result.all_planned_fake_write_calls_returned is True
    assert result.future_writes_stopped_after_failure is False
    assert "after every planned fake write call returned" in result.user_guidance
    assert "not-yet-invoked synthetic writes were stopped" not in result.user_guidance


@pytest.mark.parametrize("opcode", (0x12, 0x92))
def test_malformed_matching_callback_after_dispatch_is_uncertain(opcode):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((opcode,)) + bytes(18)
    )
    simulator = FakeVendorNotifyBatchSimulator(transport)

    result = run(simulator.simulate(_state(), _request()))

    assert result.reason is NotifyBatchSimulationReason.MALFORMED_MATCHING_CALLBACK
    assert result.completeness is NotifyBatchCompleteness.UNCERTAIN
    assert result.tainted is True
    assert result.batch_success_established is False


def test_callback_burst_is_bounded_and_classified_as_overflow():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def overflow(fake, _call):
        for _ in range(300):
            fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x45,)) + bytes(19))

    transport.before_write = overflow
    simulator = FakeVendorNotifyBatchSimulator(transport)
    result = run(simulator.simulate(_state(), _request()))

    assert result.reason is NotifyBatchSimulationReason.QUEUE_OVERFLOW
    assert result.completeness is NotifyBatchCompleteness.UNCERTAIN
    assert result.tainted is True


def test_write_error_preserves_owned_failure_without_false_stop_causality():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=RuntimeError("private backend detail")
    )
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _failure()
    )
    simulator = FakeVendorNotifyBatchSimulator(transport)

    result = run(simulator.simulate(_state(), _request()))

    assert result.reason is NotifyBatchSimulationReason.WRITE_FAILURE
    assert result.completeness is NotifyBatchCompleteness.UNCERTAIN
    assert result.unmarked_failure_callback_observed is True
    assert result.future_writes_stopped_after_failure is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert transport.targeted_write_count == 1
    assert "private backend detail" not in repr(result)


def test_blocked_write_timeout_preserves_owned_failure_and_primary_reason():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _failure()
    )

    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), stage_timeout=0.01
    ))

    assert result.reason is NotifyBatchSimulationReason.WRITE_TIMEOUT
    assert result.unmarked_failure_callback_observed is True
    assert result.future_writes_stopped_after_failure is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert "attempt ended before the planned fake calls returned" in result.user_guidance


def test_successful_write_return_is_preserved_when_disconnect_finishes_together():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: (
        asyncio.get_running_loop().call_soon(fake.emit_disconnect)
    )

    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request()
    ))

    assert result.reason is NotifyBatchSimulationReason.DISCONNECTED
    assert result.all_invoked_fake_write_calls_returned is True
    assert result.transport_call_uncertain is False


def test_disconnect_caused_write_exception_is_classified_as_disconnect():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit_disconnect()

    result = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request()
    ))

    assert result.reason is NotifyBatchSimulationReason.DISCONNECTED
    assert result.all_invoked_fake_write_calls_returned is False
    assert result.transport_call_uncertain is True


def test_exact_types_preconnected_and_forged_inputs_fail_before_fake_io():
    class UnsafeFakeSubclass(ScriptedVendorFakeTransport):
        pass

    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorNotifyBatchSimulator(UnsafeFakeSubclass(services=set(), metadata=()))

    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorNotifyBatchSimulator(transport)
    with pytest.raises(TypeError, match="exact NotifyPlannerState"):
        run(simulator.simulate(object(), _request()))
    with pytest.raises(TypeError, match="exact NotifyRequest"):
        run(simulator.simulate(_state(), object()))
    assert transport.connect_count == 0

    forged_state = _state()
    object.__setattr__(forged_state, "_next_uid", 10000)
    forged_transport = ScriptedVendorFakeTransport.vendor_route()
    with pytest.raises(ValueError, match="next UID"):
        run(FakeVendorNotifyBatchSimulator(forged_transport).simulate(
            forged_state, _request()
        ))
    assert forged_transport.connect_count == 0

    for attribute, label in (
        ("_notification_id", "notification id"),
        ("_title", "title"),
        ("_content", "content"),
    ):
        forged_request = _request()
        private = b"private-prefix-\xff-secret"
        object.__setattr__(forged_request, attribute, private)
        request_transport = ScriptedVendorFakeTransport.vendor_route()
        with pytest.raises(ValueError, match=label) as exc_info:
            run(FakeVendorNotifyBatchSimulator(request_transport).simulate(
                _state(), forged_request
            ))
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert "private-prefix" not in str(exc_info.value)
        assert "private-prefix" not in repr(exc_info.value)
        assert request_transport.connect_count == 0
        assert request_transport.response_write_calls == []

    preconnected = ScriptedVendorFakeTransport.vendor_route()
    run(preconnected.connect())
    with pytest.raises(RuntimeError, match="already connected or in use"):
        run(FakeVendorNotifyBatchSimulator(preconnected).simulate(_state(), _request()))
    assert preconnected.write_count == 0


def test_cancellation_during_invoked_write_taints_and_finishes_cleanup():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorNotifyBatchSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.simulate(
            _state(), _request(), stage_timeout=0.1
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        gate.release()
        with pytest.raises(NotifyBatchSimulationTaintedError, match="tainted"):
            await simulator.simulate(_state(), _request())

    run(scenario())
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1


def test_cleanup_failure_uses_pre_and_post_write_uncertainty_boundary():
    post = ScriptedVendorFakeTransport.vendor_route(
        close_error=RuntimeError("private close detail")
    )
    post_result = run(FakeVendorNotifyBatchSimulator(post).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))
    assert post_result.reason is NotifyBatchSimulationReason.CLEANUP_FAILURE
    assert post_result.completeness is NotifyBatchCompleteness.UNCERTAIN
    assert post_result.tainted is True

    pre = ScriptedVendorFakeTransport.vendor_route(
        subscribe_error=RuntimeError("private subscribe detail"),
        close_error=RuntimeError("private close detail"),
    )
    pre_result = run(FakeVendorNotifyBatchSimulator(pre).simulate(_state(), _request()))
    assert pre_result.reason is NotifyBatchSimulationReason.CLEANUP_FAILURE
    assert pre_result.completeness is NotifyBatchCompleteness.ABORTED
    assert pre_result.write_invoked is False
    assert pre_result.protocol_delivery == "not_attempted"
    assert pre_result.acknowledgement_correlation == "not_applicable"
    assert pre_result.scripted_transport_contains_private_test_frames is False
    assert pre_result.tainted is True


@pytest.mark.parametrize(
    ("reason", "expected"),
    (
        (NotifyBatchSimulationReason.CONNECT_FAILURE, "connection failed"),
        (NotifyBatchSimulationReason.PREFLIGHT_FAILURE, "preflight failed"),
        (NotifyBatchSimulationReason.SUBSCRIPTION_FAILURE, "subscription failed"),
        (NotifyBatchSimulationReason.WRITE_FAILURE, "write failed"),
        (NotifyBatchSimulationReason.WRITE_TIMEOUT, "write timed out"),
        (NotifyBatchSimulationReason.MALFORMED_MATCHING_CALLBACK, "malformed"),
        (NotifyBatchSimulationReason.QUEUE_OVERFLOW, "queue overflowed"),
        (NotifyBatchSimulationReason.STAGE_TIMEOUT, "stage timed out"),
        (NotifyBatchSimulationReason.OVERALL_TIMEOUT, "overall deadline expired"),
        (NotifyBatchSimulationReason.DISCONNECTED, "disconnected"),
        (NotifyBatchSimulationReason.CLEANUP_FAILURE, "cleanup failed"),
        (NotifyBatchSimulationReason.OBSERVATION_LIMIT, "observation limit"),
    ),
)
def test_guidance_leads_with_primary_reason(reason, expected):
    transport = ScriptedVendorFakeTransport.vendor_route()
    base = run(FakeVendorNotifyBatchSimulator(transport).simulate(
        _state(), _request(), quiet_timeout=0.01
    ))

    guidance = replace(base, reason=reason).user_guidance.lower()

    assert expected in guidance
    assert "private-id" not in guidance
    assert "private title" not in guidance
