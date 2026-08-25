import asyncio

import pytest

from jring.transport import GattCharacteristicMetadata
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from jring.vendor_protocol import StaticQuery, encode_static_query
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport
from jring.vendor_runtime_simulator import (
    FakeVendorRuntimeSimulator,
    SimulationBusyError,
    SimulationReason,
    SimulationTaintedError,
)
from jring.vendor_transport import OfflineVendorOperation, TransactionCompleteness
from jring.vendor_settings import HourFormat, encode_hour_format


CCCD = uuid16(0x2902)
GOOD_BATTERY = bytes((0x0B, 64, 7)) + bytes(17)


def operation():
    return OfflineVendorOperation.from_static_request(
        encode_static_query(StaticQuery.BATTERY)
    )


def run(coro):
    return asyncio.run(coro)


def test_success_discards_early_frames_and_processes_write_hook_frame_after_ack():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def before_subscribe(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)
        asyncio.get_running_loop().call_soon(
            fake.emit, VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY
        )

    def before_write(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)

    transport.before_subscribe = before_subscribe
    transport.before_write = before_write
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert result.write_invoked is True
    assert result.parsed_value_for_test().percent == 64
    assert transport.write_count == 1
    assert transport.write_with_response_count == 1
    assert transport.generic_write_count == 0
    assert transport.subscribe_count == 1
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert simulator.discarded_frame_count == 2
    assert simulator.tainted is False
    assert GOOD_BATTERY.hex() not in repr(result)
    assert "parsed_value=<redacted>" in repr(result)
    assert result.user_guidance == (
        "A synthetic response matched; real hardware remains unverified."
    )


def test_fake_runtime_reproduces_typed_mutation_ack_without_live_authority():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x1D,)) + bytes(19)
    )
    simulator = FakeVendorRuntimeSimulator(transport)
    mutation = OfflineVendorOperation.from_setting_request(
        encode_hour_format(HourFormat.TWENTY_FOUR)
    )

    result = run(simulator.execute(mutation, timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert result.parsed_value_for_test().success is True
    assert result.parsed_value_for_test().operation.value == "hour_format"
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert result.hardware_verified is False


@pytest.mark.parametrize(
    "transport",
    [
        ScriptedVendorFakeTransport.vendor_route(services=set()),
        ScriptedVendorFakeTransport.vendor_route(
            write_properties=("write-without-response",)
        ),
        ScriptedVendorFakeTransport.vendor_route(notify_properties=("indicate",)),
        ScriptedVendorFakeTransport.vendor_route(response_descriptors=()),
        ScriptedVendorFakeTransport(
            services={VENDOR_SERVICE_56FF},
            metadata=(
                GattCharacteristicMetadata(
                    VENDOR_SERVICE_56FF,
                    VENDOR_CHARACTERISTIC_33F3,
                    ("write",),
                    (),
                ),
                GattCharacteristicMetadata(
                    VENDOR_SERVICE_56FF,
                    VENDOR_CHARACTERISTIC_33F3,
                    ("write",),
                    (),
                ),
                GattCharacteristicMetadata(
                    VENDOR_SERVICE_56FF,
                    VENDOR_CHARACTERISTIC_33F4,
                    ("notify",),
                    (CCCD,),
                ),
            ),
        ),
    ],
)
def test_preflight_requires_one_unambiguous_response_write_and_notify_cccd(transport):
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert transport.subscribe_count == 0
    assert transport.write_count == 0
    assert transport.close_count == 1
    assert simulator.tainted is False


def test_exact_scripted_fake_type_is_required():
    class UnsafeSubclass(ScriptedVendorFakeTransport):
        pass

    transport = ScriptedVendorFakeTransport.vendor_route()
    subclass = UnsafeSubclass(
        services={VENDOR_SERVICE_56FF},
        metadata=transport.metadata_snapshot_for_test(),
    )

    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorRuntimeSimulator(subclass)


def test_subscribe_timeout_is_aborted_and_never_attempts_a_write():
    transport = ScriptedVendorFakeTransport.vendor_route(
        subscribe_gate=ScriptGate.blocked()
    )
    simulator = FakeVendorRuntimeSimulator(transport, cleanup_timeout=0.01)

    result = run(simulator.execute(operation(), timeout=0.02))

    assert result.reason is SimulationReason.TIMEOUT
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert transport.write_count == 0
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert simulator.tainted is False


def test_write_error_after_invocation_is_uncertain_tainted_and_never_retried():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=OSError("response write failed")
    )
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.WRITE_FAILURE
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert transport.write_count == 1
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert simulator.tainted is True
    assert "may have received" in result.user_guidance
    assert "not repeated" in result.user_guidance
    with pytest.raises(SimulationTaintedError):
        run(simulator.execute(operation(), timeout=0.2))


def test_disconnect_while_write_is_blocked_is_uncertain_and_closes_once():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorRuntimeSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.execute(operation(), timeout=0.2))
        await gate.wait_until_entered()
        transport.emit_disconnect(ConnectionError("link lost"))
        return await task

    result = run(scenario())
    assert result.reason is SimulationReason.DISCONNECTED
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert transport.write_count == 1
    assert transport.close_count == 1
    assert simulator.tainted is True
    assert result.cleanup_succeeded is False


def test_timeout_while_write_is_blocked_is_uncertain():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.02))

    assert result.reason is SimulationReason.TIMEOUT
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert transport.write_count == 1
    assert simulator.tainted is True


def test_bounded_during_write_queue_overflow_fails_uncertain():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def before_write(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x0C,)) + bytes(19))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)

    transport.before_write = before_write
    simulator = FakeVendorRuntimeSimulator(transport, max_buffered_frames=1)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.FRAME_QUEUE_OVERFLOW
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert simulator.tainted is True


def test_malformed_current_frame_is_uncertain_but_unrelated_frame_is_ignored():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def before_write(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x0C,)) + bytes(19))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, b"bad")

    transport.before_write = before_write
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.MALFORMED_RESPONSE
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert simulator.unrelated_frame_count == 1
    assert simulator.tainted is True


def test_single_flight_rejects_a_second_attempt_without_waiting():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(connect_gate=gate)
    simulator = FakeVendorRuntimeSimulator(transport)

    async def scenario():
        first = asyncio.create_task(simulator.execute(operation(), timeout=0.2))
        await gate.wait_until_entered()
        with pytest.raises(SimulationBusyError):
            await simulator.execute(operation(), timeout=0.2)
        first.cancel()
        return await first

    result = run(scenario())
    assert result.reason is SimulationReason.CANCELLED
    assert result.completeness is TransactionCompleteness.ABORTED
    assert transport.connect_count == 1
    assert transport.write_count == 0


def test_task_cancellation_after_write_invocation_returns_uncertain_cleanup_result():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorRuntimeSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.execute(operation(), timeout=0.2))
        await gate.wait_until_entered()
        task.cancel()
        return await task

    result = run(scenario())
    assert result.reason is SimulationReason.CANCELLED
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1


def test_retained_callback_from_old_generation_is_ignored():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def before_write(fake, _call):
        if fake.write_count == 1:
            fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)
        else:
            fake.emit_stale(0, b"malformed-old-generation")
            fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)

    transport.before_write = before_write
    simulator = FakeVendorRuntimeSimulator(transport)

    first = run(simulator.execute(operation(), timeout=0.2))
    second = run(simulator.execute(operation(), timeout=0.2))

    assert first.reason is SimulationReason.SUCCESS
    assert second.reason is SimulationReason.SUCCESS
    assert simulator.stale_frame_count == 1
    assert transport.write_count == 2
    assert transport.unsubscribe_count == 2
    assert transport.close_count == 2


def test_disconnect_listener_registration_is_removed_exactly_once_on_cleanup():
    transport = ScriptedVendorFakeTransport.vendor_route()
    real_add_listener = transport.add_disconnect_listener
    removals = []

    def tracked_add_listener(listener):
        remove = real_add_listener(listener)

        def tracked_remove():
            removals.append(True)
            remove()

        return tracked_remove

    transport.add_disconnect_listener = tracked_add_listener
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY
    )
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.cleanup_succeeded is True
    assert removals == [True]


def test_cleanup_time_notification_is_stale_and_cannot_change_success():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def before_write(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)

    def before_unsubscribe(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, b"late-cleanup-frame")

    transport.before_write = before_write
    transport.before_unsubscribe = before_unsubscribe
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert simulator.stale_frame_count == 1


def test_unsubscribe_failure_after_write_makes_cleanup_uncertain_and_taints():
    transport = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_error=OSError("stop notify failed")
    )
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY
    )
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.CLEANUP_FAILURE
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.cleanup_succeeded is False
    assert result.tainted is True
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    with pytest.raises(SimulationTaintedError):
        run(simulator.execute(operation(), timeout=0.2))


def test_close_failure_before_write_remains_aborted_but_poisons_reuse():
    transport = ScriptedVendorFakeTransport.vendor_route(
        services=set(), close_error=OSError("close failed")
    )
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.CLEANUP_FAILURE
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.cleanup_succeeded is False
    assert result.tainted is True
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 0
    assert transport.close_count == 1
    with pytest.raises(SimulationTaintedError):
        run(simulator.execute(operation(), timeout=0.2))
