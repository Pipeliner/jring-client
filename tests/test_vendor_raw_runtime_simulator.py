import asyncio

from jring.uuids import VENDOR_CHARACTERISTIC_33F6
from jring.vendor_raw_protocol import encode_raw_ai_state
from jring.vendor_raw_runtime_simulator import (
    FakeRawEventSimulator,
    RawCollectionCompleteness,
    RawSimulationReason,
)
from jring.vendor_runtime_fake import ScriptedVendorFakeTransport


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
    assert transport.close_count == 1
    assert notification.hex() not in repr(result)


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
