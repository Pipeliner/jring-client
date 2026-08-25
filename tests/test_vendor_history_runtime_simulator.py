import asyncio

from jring.uuids import VENDOR_CHARACTERISTIC_33F4
from jring.vendor_history_runtime_simulator import (
    FakeVendorHistorySimulator,
    HistoryCollectionCompleteness,
    HistorySimulationReason,
)
from jring.vendor_protocol import StaticQuery, encode_day_query
from jring.vendor_runtime_fake import ScriptedVendorFakeTransport


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
    assert transport.close_count == 1
    assert response.hex() not in repr(result)


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
