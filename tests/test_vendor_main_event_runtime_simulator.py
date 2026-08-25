import asyncio
from dataclasses import replace

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F4
from jring.vendor_history_runtime_simulator import FakeVendorHistorySimulator
from jring.vendor_main_event_runtime_simulator import (
    FakeVendorMainEventSimulator,
    MainEventCollectionCompleteness,
    MainEventKind,
    MainEventSimulationReason,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport
from jring.vendor_protocol import StaticQuery, encode_day_query


def run(coro):
    return asyncio.run(coro)


def _frame(opcode: int, body: bytes = b"") -> bytes:
    return bytes((opcode,)) + body.ljust(19, b"\x00")


def test_collects_only_closed_passive_main_events_without_any_write():
    transport = ScriptedVendorFakeTransport.vendor_route()
    frames = (
        _frame(0x06, bytes((68,))),
        _frame(0x22, bytes((99,))),
        _frame(0x51, (123_456).to_bytes(4, "little")),
        _frame(0x49),
    )

    def emit(fake, _call):
        for frame in frames:
            fake.emit(VENDOR_CHARACTERISTIC_33F4, frame)

    transport.before_subscribe = emit
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=4,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.LIMIT_REACHED
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 4
    assert result.unrelated_frame_count == 0
    assert result.event_kinds == (
        MainEventKind.DEVICE_ACTION,
        MainEventKind.DEVICE_ACTION,
        MainEventKind.CUMULATIVE_STEP,
        MainEventKind.PHONE_VOLUME_REQUEST,
    )
    events = result.events_for_test()
    assert events[0].value_for_test().label == "volume_up"
    assert events[1].value_for_test().label == "weather_location_refresh"
    assert events[2].value_for_test().cumulative_steps == 123_456
    assert events[3].value_for_test().requests_host_volume_state is True
    assert all(event.simulation_only is True for event in events)
    assert all(event.hardware_eligible is False for event in events)
    assert all(event.input_eligible is False for event in events)
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert result.input_eligible is False
    assert result.hardware_verified is False
    assert result.wire_terminal_observed is False
    assert result.quiet_means_success is False
    assert transport.subscribe_count == 1
    assert transport.targeted_subscribe_count == 1
    assert transport.subscription_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F4
    assert transport.subscription_calls[0].target_instance_id is not None
    assert (
        transport.subscription_calls[0].target_instance_id
        == transport.unsubscribe_calls[0].target_instance_id
    )
    assert transport.unsubscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    assert transport.generic_write_count == 0
    assert transport.write_with_response_count == 0
    assert transport.close_count == 1
    rendered = repr(result)
    assert "123456" not in rendered
    assert "volume_up" not in rendered
    assert "weather" not in rendered
    assert "events=<redacted>" in rendered
    assert "123456" not in repr(events[2])
    assert "volume_up" not in repr(events[0])


def test_78_motion_collision_is_unrelated_and_local_quiet_remains_unknown():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x78, bytes((0x09, 7))),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        quiet_timeout=0.01,
    ))

    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert result.completeness is MainEventCollectionCompleteness.UNKNOWN
    assert result.event_count == 0
    assert result.unrelated_frame_count == 1
    assert result.events_for_test() == ()
    assert transport.write_count == 0


@pytest.mark.parametrize("opcode", (0x06, 0x22, 0x51, 0x49))
def test_malformed_matching_event_aborts_without_exposing_a_value(opcode):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((opcode,)) + bytes(18),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_queue_overflow_aborts_and_discards_partial_projection():
    transport = ScriptedVendorFakeTransport.vendor_route()
    event = _frame(0x06, bytes((16,)))

    def overflow(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, event)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, event)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, event)

    transport.before_subscribe = overflow
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.QUEUE_OVERFLOW
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_late_malformed_event_discards_an_earlier_decoded_event():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_valid_then_malformed(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((68,))))
        asyncio.get_running_loop().call_later(
            0.001,
            fake.emit,
            VENDOR_CHARACTERISTIC_33F4,
            bytes((0x51,)) + bytes(18),
        )

    transport.before_subscribe = emit_valid_then_malformed
    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=3,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.MALFORMED_EVENT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()


def test_cleanup_failure_discards_an_earlier_decoded_event():
    transport = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_error=RuntimeError("private cleanup detail")
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        _frame(0x06, bytes((68,))),
    )

    result = run(FakeVendorMainEventSimulator(transport).collect(
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is MainEventSimulationReason.CLEANUP_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert "private" not in repr(result)


def test_exact_fake_main_response_target_and_route_are_required():
    class UnsafeFakeSubclass(ScriptedVendorFakeTransport):
        pass

    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorMainEventSimulator(UnsafeFakeSubclass(services=set(), metadata=()))

    wrong_route = ScriptedVendorFakeTransport.raw_vendor_route()
    result = run(FakeVendorMainEventSimulator(wrong_route).collect(quiet_timeout=0.01))
    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert wrong_route.targeted_subscribe_count == 0
    assert wrong_route.write_count == 0

    missing_target = ScriptedVendorFakeTransport.vendor_route()
    real_inventory = missing_target.gatt_characteristics

    async def inventory_without_response_target():
        records = await real_inventory()
        return tuple(
            replace(record, target=None)
            if record.uuid == VENDOR_CHARACTERISTIC_33F4
            else record
            for record in records
        )

    missing_target.gatt_characteristics = inventory_without_response_target
    result = run(FakeVendorMainEventSimulator(missing_target).collect())
    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert missing_target.targeted_subscribe_count == 0
    assert missing_target.write_count == 0


def test_revoked_response_target_after_structural_preflight_fails_closed():
    transport = ScriptedVendorFakeTransport.vendor_route()
    real_owns_target = transport.owns_target
    transport.owns_target = lambda target: (
        target.uuid != VENDOR_CHARACTERISTIC_33F4 and real_owns_target(target)
    )

    result = run(FakeVendorMainEventSimulator(transport).collect())

    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert transport.targeted_subscribe_count == 0
    assert transport.write_count == 0
    assert transport.close_count == 1


def test_stage_overall_and_cleanup_deadlines_abort_with_stable_reasons():
    stage_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorMainEventSimulator(stage_blocked).collect(
        stage_timeout=0.01,
        overall_timeout=1.0,
    ))
    assert result.reason is MainEventSimulationReason.STAGE_TIMEOUT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED

    overall_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorMainEventSimulator(overall_blocked).collect(
        stage_timeout=1.0,
        overall_timeout=0.01,
    ))
    assert result.reason is MainEventSimulationReason.OVERALL_TIMEOUT
    assert result.completeness is MainEventCollectionCompleteness.ABORTED

    cleanup_blocked = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorMainEventSimulator(cleanup_blocked).collect(
        quiet_timeout=0.01,
        cleanup_timeout=0.01,
    ))
    assert result.reason is MainEventSimulationReason.CLEANUP_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.cleanup_succeeded is False


@pytest.mark.parametrize(
    "controls",
    (
        {"connect_error": RuntimeError("private connect detail")},
        {"service_inventory_error": RuntimeError("private inventory detail")},
        {"metadata_error": RuntimeError("private metadata detail")},
        {"subscribe_error": RuntimeError("private subscribe detail")},
    ),
)
def test_ordinary_transport_errors_map_to_redacted_preflight_failure(controls):
    transport = ScriptedVendorFakeTransport.vendor_route(**controls)

    result = run(FakeVendorMainEventSimulator(transport).collect())

    assert result.reason is MainEventSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert "private" not in repr(result)
    assert transport.write_count == 0


def test_disconnect_aborts_without_consuming_an_already_queued_event():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_then_disconnect(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x06, bytes((2,))))
        asyncio.get_running_loop().call_soon(fake.emit_disconnect)

    transport.before_subscribe = emit_then_disconnect
    result = run(FakeVendorMainEventSimulator(transport).collect(quiet_timeout=0.1))

    assert result.reason is MainEventSimulationReason.DISCONNECTED
    assert result.completeness is MainEventCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.events_for_test() == ()
    assert transport.write_count == 0


def test_concurrent_collection_is_rejected_without_second_transport_io():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(connect_gate=gate)
    simulator = FakeVendorMainEventSimulator(transport)

    async def scenario():
        first = asyncio.create_task(simulator.collect(
            quiet_timeout=0.01,
            stage_timeout=0.1,
        ))
        await gate.wait_until_entered()
        with pytest.raises(RuntimeError, match="already in progress"):
            await simulator.collect()
        assert transport.connect_count == 1
        gate.release()
        return await first

    result = run(scenario())
    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert transport.write_count == 0


def test_two_simulators_cannot_share_one_transport_concurrently():
    transport = ScriptedVendorFakeTransport.vendor_route()
    first_simulator = FakeVendorMainEventSimulator(transport)
    second_simulator = FakeVendorMainEventSimulator(transport)

    async def scenario():
        first = asyncio.create_task(first_simulator.collect(quiet_timeout=1.0))
        while transport.subscribe_count == 0:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="already connected or in use"):
            await second_simulator.collect()
        assert transport.connect_count == 1
        assert transport.close_count == 0
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

    run(scenario())
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1


def test_preconnected_transport_is_rejected_without_closing_caller_connection():
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def scenario():
        await transport.connect()
        with pytest.raises(RuntimeError, match="already connected or in use"):
            await FakeVendorMainEventSimulator(transport).collect()

    run(scenario())
    assert transport.connected is True
    assert transport.connect_count == 1
    assert transport.close_count == 0
    assert transport.subscribe_count == 0


def test_transport_lease_blocks_a_different_fake_coordinator_without_interference():
    transport = ScriptedVendorFakeTransport.vendor_route()
    passive = FakeVendorMainEventSimulator(transport)
    history = FakeVendorHistorySimulator(transport)

    async def scenario():
        first = asyncio.create_task(passive.collect(quiet_timeout=1.0))
        while transport.subscribe_count == 0:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="already connected or in use"):
            await history.collect(
                request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0)
            )
        assert transport.connect_count == 1
        assert transport.close_count == 0
        assert transport.write_count == 0
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

    run(scenario())
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert transport.write_count == 0


def test_cancellation_cleans_up_releases_single_flight_and_stales_callback():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorMainEventSimulator(transport)
    original_subscribe = transport.subscribe_target

    async def scenario():
        subscribed = asyncio.Event()

        async def observed_subscribe(target, callback):
            await original_subscribe(target, callback)
            subscribed.set()

        transport.subscribe_target = observed_subscribe
        task = asyncio.create_task(simulator.collect(quiet_timeout=1.0))
        await subscribed.wait()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        reused = await simulator.collect(quiet_timeout=0.01)
        return reused

    result = run(scenario())
    callback = transport.subscription_calls[0].callback
    retained_queues = [
        cell.cell_contents
        for cell in (callback.__closure__ or ())
        if isinstance(cell.cell_contents, asyncio.Queue)
    ]

    assert transport.unsubscribe_count == 2
    assert transport.close_count == 2
    assert result.reason is MainEventSimulationReason.LOCAL_QUIET
    assert len(retained_queues) == 1
    assert retained_queues[0].qsize() == 0
    transport.emit_stale(0, _frame(0x06, bytes((68,))))
    assert retained_queues[0].qsize() == 0
    assert transport.write_count == 0


@pytest.mark.parametrize(
    "kwargs,error",
    (
        ({"event_limit": True}, TypeError),
        ({"event_limit": 0}, ValueError),
        ({"event_limit": 4097}, ValueError),
        ({"quiet_timeout": float("nan")}, ValueError),
        ({"overall_timeout": 0}, ValueError),
        ({"stage_timeout": "soon"}, TypeError),
        ({"cleanup_timeout": -1}, ValueError),
    ),
)
def test_collection_bounds_are_validated_before_transport_io(kwargs, error):
    transport = ScriptedVendorFakeTransport.vendor_route()

    with pytest.raises(error):
        run(FakeVendorMainEventSimulator(transport).collect(**kwargs))

    assert transport.connect_count == 0
    assert transport.subscribe_count == 0
    assert transport.write_count == 0
