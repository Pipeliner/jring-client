import asyncio
from dataclasses import replace

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F6
from jring.vendor_raw_protocol import encode_raw_ai_state
from jring.vendor_raw_runtime_simulator import (
    FakeRawEventSimulator,
    RawCollectionCompleteness,
    RawSimulationReason,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport


def run(coro):
    return asyncio.run(coro)


def test_raw_fake_collects_typed_event_without_claiming_command_acknowledgement():
    transport = ScriptedVendorFakeTransport.raw_vendor_route()
    notification = bytes((0x06, 0x00)) + bytes(6) + bytes((7, 8))
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F6, notification
    )
    simulator = FakeRawEventSimulator(transport)

    result = run(simulator.collect(
        command=encode_raw_ai_state(True), event_limit=1, quiet_timeout=0.1
    ))

    assert result.reason is RawSimulationReason.LIMIT_REACHED
    assert result.completeness is RawCollectionCompleteness.UNKNOWN
    assert result.event_count == 1
    assert result.command_written is True
    assert result.events_for_test()[0].first_value == 7
    assert result.events_for_test()[0].second_value == 8
    assert result.command_acknowledged is False
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    assert transport.write_count == 1
    assert transport.subscribe_count == 1
    assert transport.unsubscribe_count == 1
    assert transport.targeted_write_count == 1
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.response_write_calls[0].target_instance_id is not None
    assert (
        transport.subscription_calls[0].target_instance_id
        == transport.unsubscribe_calls[0].target_instance_id
    )
    assert transport.close_count == 1
    assert notification.hex() not in repr(result)


def test_missing_connection_scoped_raw_target_fails_before_subscription_or_write():
    transport = ScriptedVendorFakeTransport.raw_vendor_route()
    real_inventory = transport.gatt_characteristics

    async def inventory_without_response_target():
        records = await real_inventory()
        return tuple(
            replace(record, target=None)
            if record.uuid == VENDOR_CHARACTERISTIC_33F6
            else record
            for record in records
        )

    transport.gatt_characteristics = inventory_without_response_target

    result = run(FakeRawEventSimulator(transport).collect(
        command=encode_raw_ai_state(True), event_limit=1, quiet_timeout=0.01
    ))

    assert result.reason is RawSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert transport.targeted_subscribe_count == 0
    assert transport.targeted_write_count == 0

    setup_failed = ScriptedVendorFakeTransport.raw_vendor_route(
        connect_error=RuntimeError("unexpected connect failure")
    )
    result = run(FakeRawEventSimulator(setup_failed).collect())
    assert result.reason is RawSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert setup_failed.targeted_subscribe_count == 0
    assert setup_failed.targeted_write_count == 0
    assert setup_failed.close_count == 1


def test_revoked_raw_target_after_structural_preflight_fails_closed():
    transport = ScriptedVendorFakeTransport.raw_vendor_route()
    transport.owns_target = lambda _target: False

    result = run(FakeRawEventSimulator(transport).collect(
        command=encode_raw_ai_state(True), event_limit=1, quiet_timeout=0.01
    ))

    assert result.reason is RawSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert result.command_written is False
    assert result.delivery_uncertain is False
    assert result.event_count == 0
    assert transport.targeted_subscribe_count == 0
    assert transport.targeted_write_count == 0
    assert transport.close_count == 1


def test_raw_local_quiet_is_unknown_not_success_or_terminal():
    transport = ScriptedVendorFakeTransport.raw_vendor_route()
    simulator = FakeRawEventSimulator(transport)

    result = run(simulator.collect(event_limit=1, quiet_timeout=0.01))

    assert result.reason is RawSimulationReason.LOCAL_QUIET
    assert result.completeness is RawCollectionCompleteness.UNKNOWN
    assert result.event_count == 0
    assert result.command_written is False
    assert result.command_acknowledged is False
    assert result.quiet_means_success is False


def test_main_route_cannot_be_reused_for_raw_collection():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeRawEventSimulator(transport)

    result = run(simulator.collect(event_limit=1, quiet_timeout=0.01))

    assert result.reason is RawSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert result.command_written is False
    assert transport.write_count == 0
    assert transport.subscribe_count == 0
    assert transport.close_count == 1


def test_bounded_raw_queue_overflow_aborts_without_projecting_partial_events():
    transport = ScriptedVendorFakeTransport.raw_vendor_route()
    notification = bytes((0x06, 0x00)) + bytes(6) + bytes((7, 8))

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F6, notification)
        fake.emit(VENDOR_CHARACTERISTIC_33F6, notification)
        fake.emit(VENDOR_CHARACTERISTIC_33F6, notification)

    transport.before_write = emit
    result = run(FakeRawEventSimulator(transport).collect(
        command=encode_raw_ai_state(True),
        event_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is RawSimulationReason.QUEUE_OVERFLOW
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert result.event_count == 0
    assert result.delivery_uncertain is False


def test_raw_setup_overall_and_cleanup_deadlines_are_bounded():
    stage_blocked = ScriptedVendorFakeTransport.raw_vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeRawEventSimulator(stage_blocked).collect(
        stage_timeout=0.01,
        overall_timeout=1.0,
    ))
    assert result.reason is RawSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED

    overall_blocked = ScriptedVendorFakeTransport.raw_vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeRawEventSimulator(overall_blocked).collect(
        stage_timeout=1.0,
        overall_timeout=0.01,
    ))
    assert result.reason is RawSimulationReason.OVERALL_TIMEOUT
    assert result.completeness is RawCollectionCompleteness.ABORTED

    cleanup_blocked = ScriptedVendorFakeTransport.raw_vendor_route(
        unsubscribe_gate=ScriptGate.blocked()
    )
    result = run(FakeRawEventSimulator(cleanup_blocked).collect(
        event_limit=1,
        quiet_timeout=0.01,
        cleanup_timeout=0.01,
    ))
    assert result.reason is RawSimulationReason.CLEANUP_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert result.cleanup_succeeded is False

    close_failed = ScriptedVendorFakeTransport.raw_vendor_route(
        close_error=RuntimeError("unexpected close failure")
    )
    result = run(FakeRawEventSimulator(close_failed).collect(
        quiet_timeout=0.01,
    ))
    assert result.reason is RawSimulationReason.CLEANUP_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert result.cleanup_succeeded is False


def test_raw_write_timeout_reports_uncertain_delivery():
    transport = ScriptedVendorFakeTransport.raw_vendor_route(
        write_gate=ScriptGate.blocked()
    )

    result = run(FakeRawEventSimulator(transport).collect(
        command=encode_raw_ai_state(True),
        stage_timeout=0.01,
        overall_timeout=1.0,
    ))

    assert result.reason is RawSimulationReason.WRITE_FAILURE
    assert result.completeness is RawCollectionCompleteness.ABORTED
    assert result.command_written is False
    assert result.delivery_uncertain is True


def test_raw_backend_timeout_errors_are_not_relabelled_as_overall_deadline():
    connect_failed = ScriptedVendorFakeTransport.raw_vendor_route(
        connect_error=TimeoutError("backend connect timeout")
    )
    connect_result = run(FakeRawEventSimulator(connect_failed).collect())

    assert connect_result.reason is RawSimulationReason.PREFLIGHT_FAILURE
    assert connect_result.delivery_uncertain is False

    write_failed = ScriptedVendorFakeTransport.raw_vendor_route(
        write_error=TimeoutError("backend write timeout")
    )
    write_result = run(FakeRawEventSimulator(write_failed).collect(
        command=encode_raw_ai_state(True),
    ))

    assert write_result.reason is RawSimulationReason.WRITE_FAILURE
    assert write_result.delivery_uncertain is True


def test_raw_concurrent_collection_is_rejected_without_second_transport_io():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.raw_vendor_route(connect_gate=gate)
    simulator = FakeRawEventSimulator(transport)

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
    assert result.reason is RawSimulationReason.LOCAL_QUIET


def test_raw_cancellation_cleans_up_releases_single_flight_and_stales_callback():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.raw_vendor_route(write_gate=gate)
    simulator = FakeRawEventSimulator(transport)
    command = encode_raw_ai_state(True)

    async def scenario():
        task = asyncio.create_task(simulator.collect(
            command=command,
            stage_timeout=0.1,
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        gate.release()
        reused = await simulator.collect(
            command=command,
            quiet_timeout=0.01,
        )
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
    assert result.reason is RawSimulationReason.LOCAL_QUIET
    assert len(retained_queues) == 1
    assert retained_queues[0].qsize() == 0
    transport.emit_stale(0, bytes((0x06, 0x00)) + bytes(8))
    assert retained_queues[0].qsize() == 0
