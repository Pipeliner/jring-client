import asyncio

import pytest

from jring.transport import GattCharacteristicMetadata
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from jring.vendor_history_runtime_simulator import (
    FakeVendorHistorySimulator,
    HistoryCollectionCompleteness,
    HistorySimulationReason,
)
from jring.vendor_protocol import StaticQuery, encode_day_query
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport


def run(coro):
    return asyncio.run(coro)


def test_oxygen_history_preserves_shared_projection_multiplicity_without_terminal():
    transport = ScriptedVendorFakeTransport.vendor_route()
    response = (
        bytes((0x40,))
        + (1_700_000_000).to_bytes(4, "little")
        + bytes(range(15))
    )
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, response
    )
    simulator = FakeVendorHistorySimulator(transport)

    result = run(simulator.collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is HistorySimulationReason.LIMIT_REACHED
    assert result.completeness is HistoryCollectionCompleteness.UNKNOWN
    assert result.accepted_frame_count == 1
    assert result.projections == (
        ("onGetDataByDay", 15, "wire_frame"),
        ("onGetOxygenOfflineData", 15, "wire_frame"),
    )
    assert len(result.parsed_frames_for_test()[0].samples) == 15
    assert result.wire_terminal_observed is False
    assert result.quiet_means_success is False
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert transport.write_count == 1
    assert transport.unsubscribe_count == 1
    assert transport.targeted_write_count == 1
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.response_write_calls[0].target_instance_id is not None
    assert (
        transport.subscription_calls[0].target_instance_id
        == transport.unsubscribe_calls[0].target_instance_id
    )
    assert (
        transport.response_write_calls[0].target_instance_id
        != transport.subscription_calls[0].target_instance_id
    )
    assert transport.close_count == 1
    assert response.hex() not in repr(result)


def test_cross_service_request_uuid_duplicate_fails_before_subscription_or_write():
    exact = ScriptedVendorFakeTransport.vendor_route()
    transport = ScriptedVendorFakeTransport(
        services={VENDOR_SERVICE_56FF, uuid16(0x180A)},
        metadata=exact.metadata_snapshot_for_test() + (
            GattCharacteristicMetadata(
                uuid16(0x180A),
                VENDOR_CHARACTERISTIC_33F3,
                ("write",),
                (),
            ),
        ),
    )

    result = run(FakeVendorHistorySimulator(transport).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        quiet_timeout=0.01,
    ))

    assert result.reason is HistorySimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert transport.targeted_subscribe_count == 0
    assert transport.targeted_write_count == 0

    setup_failed = ScriptedVendorFakeTransport.vendor_route(
        connect_error=RuntimeError("unexpected connect failure")
    )
    result = run(FakeVendorHistorySimulator(setup_failed).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
    ))
    assert result.reason is HistorySimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert setup_failed.targeted_subscribe_count == 0
    assert setup_failed.targeted_write_count == 0
    assert setup_failed.close_count == 1


def test_revoked_history_target_after_structural_preflight_fails_closed():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.owns_target = lambda _target: False

    result = run(FakeVendorHistorySimulator(transport).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        quiet_timeout=0.01,
    ))

    assert result.reason is HistorySimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert result.command_written is False
    assert result.delivery_uncertain is False
    assert result.accepted_frame_count == 0
    assert transport.targeted_subscribe_count == 0
    assert transport.targeted_write_count == 0
    assert transport.close_count == 1


def test_unrelated_main_event_does_not_become_history_or_success():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x0B, 50)) + bytes(18)
    )
    simulator = FakeVendorHistorySimulator(transport)

    result = run(simulator.collect(
        request=encode_day_query(StaticQuery.ADVANCED_SENSOR_DAY, day_offset=1),
        frame_limit=1,
        quiet_timeout=0.01,
    ))

    assert result.reason is HistorySimulationReason.LOCAL_QUIET
    assert result.completeness is HistoryCollectionCompleteness.UNKNOWN
    assert result.accepted_frame_count == 0
    assert result.unrelated_frame_count == 1
    assert result.projections == ()
    assert result.quiet_means_success is False


def test_multi_sport_conditional_failure_is_failed_not_unknown_success():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0xA5, 0xFF)) + bytes(18)
    )
    simulator = FakeVendorHistorySimulator(transport)

    result = run(simulator.collect(
        request=encode_day_query(StaticQuery.MULTI_SPORT_DAY, day_offset=2),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is HistorySimulationReason.DEVICE_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.FAILED
    assert result.projections == (
        ("onGetMultipleSportData", 1, "wire_failure_frame"),
    )
    assert result.accepted_frame_count == 0


def test_oxygen_local_end_is_projected_only_after_data_then_quiet():
    transport = ScriptedVendorFakeTransport.vendor_route()
    response = bytes((0x40,)) + (100).to_bytes(4, "little") + bytes(range(15))
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, response
    )
    simulator = FakeVendorHistorySimulator(transport)

    result = run(simulator.collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        frame_limit=2,
        quiet_timeout=0.01,
    ))

    assert result.reason is HistorySimulationReason.LOCAL_QUIET
    assert result.completeness is HistoryCollectionCompleteness.UNKNOWN
    assert result.local_end_projected is True
    assert result.projections[-1] == (
        "onGetOxygenOfflineDataEnd", 1, "local_quiet_projection"
    )
    assert result.local_end_device_epoch_seconds_for_test() == 100 + (14 * 60)
    assert result.wire_terminal_observed is False


def test_bounded_history_queue_overflow_aborts_without_projecting_partial_data():
    transport = ScriptedVendorFakeTransport.vendor_route()
    response = bytes((0x40,)) + (100).to_bytes(4, "little") + bytes(range(15))

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, response)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, response)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, response)

    transport.before_write = emit
    result = run(FakeVendorHistorySimulator(transport).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is HistorySimulationReason.QUEUE_OVERFLOW
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert result.accepted_frame_count == 0
    assert result.projections == ()
    assert result.local_end_projected is False
    assert result.delivery_uncertain is False


def test_oversized_matching_history_frame_is_bounded_then_aborts_malformed():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x40,)) + bytes(100_000)
    )

    result = run(FakeVendorHistorySimulator(transport).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        quiet_timeout=0.01,
    ))

    assert result.reason is HistorySimulationReason.MALFORMED_FRAME
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    callback = transport.subscription_calls[0].callback
    retained_queues = [
        cell.cell_contents
        for cell in (callback.__closure__ or ())
        if isinstance(cell.cell_contents, asyncio.Queue)
    ]
    assert retained_queues[0].qsize() == 0


def test_history_setup_overall_and_cleanup_deadlines_are_bounded():
    stage_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorHistorySimulator(stage_blocked).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        stage_timeout=0.01,
        overall_timeout=1.0,
    ))
    assert result.reason is HistorySimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED

    overall_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorHistorySimulator(overall_blocked).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        stage_timeout=1.0,
        overall_timeout=0.01,
    ))
    assert result.reason is HistorySimulationReason.OVERALL_TIMEOUT
    assert result.completeness is HistoryCollectionCompleteness.ABORTED

    cleanup_blocked = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_gate=ScriptGate.blocked()
    )
    cleanup_blocked.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((0x40,)) + (100).to_bytes(4, "little") + bytes(range(15)),
    )
    result = run(FakeVendorHistorySimulator(cleanup_blocked).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        frame_limit=1,
        cleanup_timeout=0.01,
    ))
    assert result.reason is HistorySimulationReason.CLEANUP_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert result.cleanup_succeeded is False

    close_failed = ScriptedVendorFakeTransport.vendor_route(
        close_error=RuntimeError("unexpected close failure")
    )
    result = run(FakeVendorHistorySimulator(close_failed).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        quiet_timeout=0.01,
    ))
    assert result.reason is HistorySimulationReason.CLEANUP_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert result.cleanup_succeeded is False


def test_history_write_timeout_reports_uncertain_delivery():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_gate=ScriptGate.blocked()
    )

    result = run(FakeVendorHistorySimulator(transport).collect(
        request=encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0),
        stage_timeout=0.01,
        overall_timeout=1.0,
    ))

    assert result.reason is HistorySimulationReason.WRITE_FAILURE
    assert result.completeness is HistoryCollectionCompleteness.ABORTED
    assert result.command_written is False
    assert result.delivery_uncertain is True


def test_history_backend_timeout_errors_are_not_relabelled_as_overall_deadline():
    request = encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0)
    connect_failed = ScriptedVendorFakeTransport.vendor_route(
        connect_error=TimeoutError("backend connect timeout")
    )
    connect_result = run(FakeVendorHistorySimulator(connect_failed).collect(
        request=request,
    ))

    assert connect_result.reason is HistorySimulationReason.PREFLIGHT_FAILURE
    assert connect_result.delivery_uncertain is False

    write_failed = ScriptedVendorFakeTransport.vendor_route(
        write_error=TimeoutError("backend write timeout")
    )
    write_result = run(FakeVendorHistorySimulator(write_failed).collect(
        request=request,
    ))

    assert write_result.reason is HistorySimulationReason.WRITE_FAILURE
    assert write_result.delivery_uncertain is True


def test_history_concurrent_collection_is_rejected_without_second_transport_io():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(connect_gate=gate)
    simulator = FakeVendorHistorySimulator(transport)
    request = encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0)

    async def scenario():
        first = asyncio.create_task(simulator.collect(
            request=request,
            quiet_timeout=0.01,
            stage_timeout=0.1,
        ))
        await gate.wait_until_entered()
        with pytest.raises(RuntimeError, match="already in progress"):
            await simulator.collect(request=request)
        assert transport.connect_count == 1
        gate.release()
        return await first

    result = run(scenario())
    assert result.reason is HistorySimulationReason.LOCAL_QUIET


def test_history_cancellation_cleans_up_releases_single_flight_and_stales_callback():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorHistorySimulator(transport)
    request = encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=0)

    async def scenario():
        task = asyncio.create_task(simulator.collect(
            request=request,
            stage_timeout=0.1,
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        gate.release()
        reused = await simulator.collect(request=request, quiet_timeout=0.01)
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
    assert result.reason is HistorySimulationReason.LOCAL_QUIET
    assert len(retained_queues) == 1
    assert retained_queues[0].qsize() == 0
    transport.emit_stale(0, bytes((0x40,)) + bytes(19))
    assert retained_queues[0].qsize() == 0
