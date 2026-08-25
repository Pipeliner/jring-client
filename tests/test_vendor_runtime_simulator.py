import asyncio
from copy import copy, deepcopy
from dataclasses import asdict, replace
import json
import time

import pytest

from jring import vendor_runtime_simulator
from jring.transport import GattCharacteristicMetadata, GattCharacteristicTarget
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from jring.vendor_protocol import StaticQuery, encode_static_query
from jring.vendor_commands import (
    encode_heart_rate_session_start,
    encode_heart_rate_session_stop,
)
from jring.vendor_main_commands import (
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
)
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


def device_system_operation():
    return OfflineVendorOperation.from_main_command_request(
        NoArgumentMainCommandRequest(NoArgumentMainCommand.DEVICE_SYSTEM_STATE)
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
    assert transport.targeted_write_count == 1
    assert transport.write_with_response_count == 0
    assert transport.generic_write_count == 0
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.response_write_calls[0].target_instance_id is not None
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


def test_success_result_keeps_parsed_value_out_of_structured_serialization():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY
    )
    result = run(FakeVendorRuntimeSimulator(transport).execute(
        operation(), timeout=0.2
    ))

    parsed = result.parsed_value_for_test()
    assert parsed.percent == 64
    payload = asdict(result)
    rendered = json.dumps(payload, default=str, sort_keys=True)
    assert "_parsed_value" not in payload
    assert '"percent"' not in rendered
    assert '"voltage"' not in rendered
    assert result.parsed_value_redacted is True
    assert result.parsed_value_serialized is False
    for cloned in (copy(result), deepcopy(result)):
        assert cloned.parsed_value_for_test().percent == 64
        assert "_parsed_value" not in asdict(cloned)
    with pytest.raises((TypeError, ValueError), match="_decoded_value"):
        replace(result)
    replaced = replace(result, _decoded_value=parsed)
    assert replaced.parsed_value_for_test().percent == 64
    assert "_parsed_value" not in asdict(replaced)


def test_device_system_query_owns_only_exact_postwrite_54_12_response():
    transport = ScriptedVendorFakeTransport.vendor_route()
    private_state_code = 0xA7
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((0x54, 0x12, private_state_code)) + bytes(17),
    )

    def after_write_entry(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x54, 0x04, 9)) + bytes(17))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x54, 0x13, 8)) + bytes(17))
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            bytes((0x54, 0x12, private_state_code)) + bytes(17),
        )

    transport.before_write = after_write_entry
    simulator = FakeVendorRuntimeSimulator(transport)
    result = run(simulator.execute(device_system_operation(), timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert result.write_invoked is True
    assert transport.write_count == 1
    assert transport.targeted_write_count == 1
    assert transport.response_write_calls[0].data_for_test() == (
        bytes((0x54, 0x11)) + bytes(18)
    )
    assert simulator.discarded_frame_count == 1
    assert simulator.unrelated_frame_count == 2
    parsed = result.parsed_value_for_test()
    assert parsed.event.value == "device_system_state"
    assert parsed.value == private_state_code
    rendered = json.dumps(asdict(result), default=str, sort_keys=True)
    assert str(private_state_code) not in rendered
    assert "_parsed_value" not in rendered
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    payload = asdict(result)
    assert payload["simulation_only"] is True
    assert payload["scripted_transport"] is True
    assert payload["matching_fake_response_observed"] is True
    assert payload["fake_transaction_completed"] is True
    assert payload["state_freshness"] == "synthetic_fixture_only"
    for denied in (
        "current_device_state_observed",
        "bluetooth_readiness_observed",
        "bluetooth_connection_state_observed",
        "battery_or_power_state_observed",
        "firmware_health_observed",
        "owner_binding_observed",
        "live_wire_terminal_verified",
        "ring_contacted",
        "live_available",
        "hardware_eligible",
        "hardware_verified",
        "input_eligible",
        "host_input_emitted",
    ):
        assert payload[denied] is False
    assert result.user_guidance.startswith(
        "Matched one scripted fake device-system query response."
    )
    assert "does not report current device state" in result.user_guidance


def test_eq_query_ignores_set_kind_before_matching_get_kind():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def after_write_entry(fake, _call):
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            bytes((0x53, 0x00, 1, 2, 0)) + bytes(15),
        )
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            bytes((0x53, 0x01, 3, 4, 0)) + bytes(15),
        )

    transport.before_write = after_write_entry
    simulator = FakeVendorRuntimeSimulator(transport)
    operation_value = OfflineVendorOperation.from_main_command_request(
        NoArgumentMainCommandRequest(NoArgumentMainCommand.EQ_INFO)
    )

    result = run(simulator.execute(operation_value, timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert simulator.unrelated_frame_count == 1
    assert result.parsed_value_for_test().kind == "get"


def test_truncated_unrelated_opcode_does_not_poison_matching_query():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def after_write_entry(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, b"\x4e")
        fake.emit(VENDOR_CHARACTERISTIC_33F4, GOOD_BATTERY)

    transport.before_write = after_write_entry
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert simulator.unrelated_frame_count == 1


@pytest.mark.parametrize(
    "command,valid_response",
    (
        (
            NoArgumentMainCommand.DEVICE_SYSTEM_STATE,
            bytes((0x54, 0x12, 7)) + bytes(17),
        ),
        (
            NoArgumentMainCommand.EQ_INFO,
            bytes((0x53, 0x01, 3, 4, 0)) + bytes(15),
        ),
    ),
)
def test_selectorless_shared_opcode_is_unrelated_before_exact_branch(
    command, valid_response
):
    transport = ScriptedVendorFakeTransport.vendor_route()

    def after_write_entry(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, valid_response[:1])
        fake.emit(VENDOR_CHARACTERISTIC_33F4, valid_response)

    transport.before_write = after_write_entry
    simulator = FakeVendorRuntimeSimulator(transport)
    operation_value = OfflineVendorOperation.from_main_command_request(
        NoArgumentMainCommandRequest(command)
    )

    result = run(simulator.execute(operation_value, timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert simulator.unrelated_frame_count == 1


@pytest.mark.parametrize(
    "request_value,other_response,own_response",
    (
        (
            encode_heart_rate_session_start(reference_value=1, mode_code=2),
            bytes((0x15,)) + bytes(19),
            bytes((0x14, 7)) + bytes(18),
        ),
        (
            encode_heart_rate_session_stop(mode_code=2),
            bytes((0x14,)) + bytes(19),
            bytes((0x15,)) + bytes(19),
        ),
    ),
)
def test_heart_rate_start_stop_runtime_owns_only_its_exact_branch(
    request_value, other_response, own_response
):
    transport = ScriptedVendorFakeTransport.vendor_route()

    def after_write_entry(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, other_response)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, own_response)

    transport.before_write = after_write_entry
    simulator = FakeVendorRuntimeSimulator(transport)
    operation_value = OfflineVendorOperation.from_command_request(request_value)

    result = run(simulator.execute(operation_value, timeout=0.2))

    assert result.reason is SimulationReason.SUCCESS
    assert result.completeness is TransactionCompleteness.SUCCEEDED
    assert simulator.unrelated_frame_count == 1
    assert transport.write_count == 1


@pytest.mark.parametrize(
    "request_value,failure_opcode",
    (
        (encode_heart_rate_session_start(reference_value=1, mode_code=2), 0x94),
        (encode_heart_rate_session_stop(mode_code=2), 0x95),
    ),
)
def test_heart_rate_start_stop_runtime_preserves_distinct_failure_branch(
    request_value, failure_opcode
):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4,
        bytes((failure_opcode,)) + bytes(19),
    )
    operation_value = OfflineVendorOperation.from_command_request(request_value)

    result = run(
        FakeVendorRuntimeSimulator(transport).execute(operation_value, timeout=0.2)
    )

    assert result.reason is SimulationReason.DEVICE_FAILURE
    assert result.completeness is TransactionCompleteness.FAILED
    assert result.write_invoked is True
    assert transport.write_count == 1


def test_mutated_closed_operation_is_rejected_before_fake_io():
    operation_value = device_system_operation()
    object.__setattr__(operation_value, "_request_frame", bytes.fromhex("dead") + bytes(18))
    transport = ScriptedVendorFakeTransport.vendor_route()

    with pytest.raises(ValueError, match="execution shape was mutated"):
        run(FakeVendorRuntimeSimulator(transport).execute(operation_value, timeout=0.2))

    assert transport.connect_count == 0
    assert transport.subscribe_count == 0
    assert transport.write_count == 0


@pytest.mark.parametrize(
    "field,value",
    (
        ("success_opcodes", (0x55,)),
        ("failure_opcodes", (0xD4,)),
        ("expected_subcommand", 0x04),
        ("excluded_subcommands", (0x12,)),
        ("name", "forged_device_state"),
        ("_parser", lambda _data: object()),
    ),
)
def test_mutated_response_discriminator_or_parser_is_rejected_before_io(field, value):
    operation_value = device_system_operation()
    object.__setattr__(operation_value, field, value)
    transport = ScriptedVendorFakeTransport.vendor_route()

    with pytest.raises(ValueError, match="execution shape was mutated"):
        run(FakeVendorRuntimeSimulator(transport).execute(operation_value, timeout=0.2))

    assert transport.connect_count == 0
    assert transport.write_count == 0


def test_deadline_before_actual_write_entry_is_aborted_and_owns_no_response(monkeypatch):
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorRuntimeSimulator(transport)
    original = simulator._await_boundary

    async def expire_before_write_entry(awaitable, attempt):
        if attempt.stage is vendor_runtime_simulator._Stage.WRITE:
            attempt.deadline = time.monotonic() - 1
        return await original(awaitable, attempt)

    monkeypatch.setattr(simulator, "_await_boundary", expire_before_write_entry)
    result = run(simulator.execute(device_system_operation(), timeout=0.2))

    assert result.reason is SimulationReason.TIMEOUT
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.tainted is False
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0
    payload = asdict(result)
    assert payload["matching_fake_response_observed"] is False
    assert payload["fake_transaction_completed"] is False
    assert payload["simulation_only"] is True
    assert result.user_guidance.startswith(
        "The scripted fake device-system query was aborted"
    )


def test_disconnect_before_actual_write_entry_is_aborted_without_dispatch(monkeypatch):
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorRuntimeSimulator(transport)
    original = simulator._await_boundary

    async def disconnect_before_write_entry(awaitable, attempt):
        if attempt.stage is vendor_runtime_simulator._Stage.WRITE:
            attempt.disconnect_event.set()
        return await original(awaitable, attempt)

    monkeypatch.setattr(simulator, "_await_boundary", disconnect_before_write_entry)
    result = run(simulator.execute(device_system_operation(), timeout=0.2))

    assert result.reason is SimulationReason.DISCONNECTED
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.tainted is False
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0


def test_cancellation_before_actual_write_entry_is_aborted_without_dispatch(monkeypatch):
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorRuntimeSimulator(transport)
    original = simulator._await_boundary

    async def cancel_before_write_entry(awaitable, attempt):
        if attempt.stage is vendor_runtime_simulator._Stage.WRITE:
            asyncio.current_task().cancel()
        return await original(awaitable, attempt)

    monkeypatch.setattr(simulator, "_await_boundary", cancel_before_write_entry)
    result = run(simulator.execute(device_system_operation(), timeout=0.2))

    assert result.reason is SimulationReason.CANCELLED
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.tainted is False
    assert transport.write_count == 0
    assert transport.targeted_write_count == 0


@pytest.mark.parametrize("length", (19, 21))
def test_malformed_exact_device_system_response_is_uncertain_and_redacted(length):
    transport = ScriptedVendorFakeTransport.vendor_route()
    candidate = bytes((0x54, 0x12, 0xA7)) + bytes(18)
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, candidate[:length]
    )
    simulator = FakeVendorRuntimeSimulator(transport)
    result = run(simulator.execute(device_system_operation(), timeout=0.2))

    assert result.reason is SimulationReason.MALFORMED_RESPONSE
    assert result.completeness is TransactionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.tainted is True
    assert result.parsed_value_for_test() is None
    assert "167" not in json.dumps(asdict(result), default=str)
    assert transport.write_count == 1
    payload = asdict(result)
    assert payload["matching_fake_response_observed"] is False
    assert payload["fake_transaction_completed"] is False
    assert payload["live_available"] is False
    assert result.user_guidance.startswith(
        "The scripted fake device-system query is uncertain."
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


def test_structurally_consistent_but_unowned_targets_fail_before_fake_io():
    transport = ScriptedVendorFakeTransport.vendor_route()
    original_inventory = transport.gatt_characteristics

    async def forged_inventory():
        records = await original_inventory()
        return tuple(
            replace(
                record,
                target=GattCharacteristicTarget(
                    record.target.connection_generation,
                    record.target.service_uuid,
                    record.target.uuid,
                    record.target.instance_id,
                ),
            )
            for record in records
        )

    transport.gatt_characteristics = forged_inventory
    simulator = FakeVendorRuntimeSimulator(transport)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is TransactionCompleteness.ABORTED
    assert transport.subscribe_count == 0
    assert transport.write_count == 0


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


def test_disconnect_at_pre_write_boundary_is_aborted_before_dispatch(monkeypatch):
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorRuntimeSimulator(transport)

    async def disconnect_at_boundary(_delay):
        for listener in tuple(transport._disconnect_listeners):
            listener(ConnectionError("link lost before dispatch"))

    monkeypatch.setattr(vendor_runtime_simulator.asyncio, "sleep", disconnect_at_boundary)

    result = run(simulator.execute(operation(), timeout=0.2))

    assert result.reason is SimulationReason.DISCONNECTED
    assert result.completeness is TransactionCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.tainted is False
    assert transport.write_count == 0


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
        fake.emit(VENDOR_CHARACTERISTIC_33F4, b"\x0b")

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
