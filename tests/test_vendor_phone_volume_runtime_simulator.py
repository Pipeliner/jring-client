import asyncio
from dataclasses import asdict

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4
from jring.vendor_main_commands import PhoneVolumeRequest
from jring.vendor_phone_volume_runtime_simulator import (
    FakeVendorPhoneVolumeSimulator,
    PhoneVolumeProjectionCompleteness,
    PhoneVolumeProjectionReason,
    PhoneVolumeSimulationTaintedError,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport


def run(coro):
    return asyncio.run(coro)


def _frame(opcode: int, body: bytes = b"") -> bytes:
    return bytes((opcode,)) + body.ljust(19, b"\x00")


def _request() -> PhoneVolumeRequest:
    return PhoneVolumeRequest(7, 15, 3, 5)


def test_exact_device_request_projects_one_closed_response_without_claiming_ack():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
    )

    result = run(FakeVendorPhoneVolumeSimulator(transport).project_once(_request()))

    assert result.reason is PhoneVolumeProjectionReason.FAKE_WRITE_CALL_RETURNED
    assert result.completeness is PhoneVolumeProjectionCompleteness.UNKNOWN
    assert result.request_observed is True
    assert result.write_invoked is True
    assert result.fake_write_call_completed is True
    assert result.transport_call_uncertain is False
    assert result.protocol_delivery == "unknown"
    assert result.application_acknowledgement_observed is False
    assert result.protocol_terminal_observed is False
    assert result.quiet_means_success is False
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    assert result.host_audio_accessed is False
    assert result.host_audio_modified is False
    assert result.host_state_source == "caller_supplied_offline_values"
    assert result.live_available is False
    assert result.owner_authorized is False
    assert result.input_eligible is False
    assert result.cleanup_succeeded is True
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_write_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.response_write_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F3
    assert (
        transport.response_write_calls[0].data_for_test()
        == _request().frames()[0].synthetic_bytes_for_test()
    )
    assert (
        transport.response_write_calls[0].connection_generation
        == transport.subscription_calls[0].connection_generation
    )
    assert transport.close_count == 1
    rendered = repr(result)
    assert "7" not in rendered
    assert "15" not in rendered
    assert "3" not in rendered
    assert "5" not in rendered
    assert "payload" not in rendered
    assert set(asdict(result)) == {
        "reason",
        "completeness",
        "request_observed",
        "unrelated_frame_count",
        "write_invoked",
        "fake_write_call_completed",
        "transport_call_uncertain",
        "cleanup_succeeded",
        "tainted",
        "protocol_delivery",
        "application_acknowledgement_observed",
        "protocol_terminal_observed",
        "quiet_means_success",
        "simulation_only",
        "live_available",
        "owner_authorized",
        "hardware_eligible",
        "hardware_verified",
        "host_state_source",
        "host_audio_accessed",
        "host_audio_modified",
        "input_eligible",
    }


@pytest.mark.parametrize("frame", (_frame(0x51), bytes((0x49,)) + bytes(18)))
def test_unrelated_or_malformed_frames_never_project(frame):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, frame
    )

    result = run(FakeVendorPhoneVolumeSimulator(transport).project_once(
        _request(), quiet_timeout=0.01
    ))

    expected = (
        PhoneVolumeProjectionReason.MALFORMED_REQUEST
        if frame[0] == 0x49
        else PhoneVolumeProjectionReason.LOCAL_QUIET
    )
    assert result.reason is expected
    assert result.write_invoked is False
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is False
    assert transport.write_count == 0


def test_write_failure_is_uncertain_and_never_retried():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=RuntimeError("private audio values")
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
    )

    simulator = FakeVendorPhoneVolumeSimulator(transport)
    result = run(simulator.project_once(_request()))

    assert result.reason is PhoneVolumeProjectionReason.WRITE_FAILURE
    assert result.completeness is PhoneVolumeProjectionCompleteness.UNCERTAIN
    assert result.request_observed is True
    assert result.write_invoked is True
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert transport.write_count == 1
    assert "private" not in repr(result)
    with pytest.raises(PhoneVolumeSimulationTaintedError):
        run(simulator.project_once(_request()))
    assert transport.write_count == 1


def test_write_timeout_is_uncertain_and_never_retried():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_gate=ScriptGate.blocked()
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
    )

    result = run(FakeVendorPhoneVolumeSimulator(transport).project_once(
        _request(), stage_timeout=0.01
    ))

    assert result.reason is PhoneVolumeProjectionReason.WRITE_TIMEOUT
    assert result.write_invoked is True
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is True
    assert result.completeness is PhoneVolumeProjectionCompleteness.UNCERTAIN
    assert result.tainted is True
    assert transport.write_count == 1


def test_disconnect_after_write_invocation_is_uncertain_without_retry():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
    )
    transport.before_write = lambda fake, _call: fake.emit_disconnect(
        ConnectionError("private adapter detail")
    )

    result = run(FakeVendorPhoneVolumeSimulator(transport).project_once(_request()))

    assert result.reason is PhoneVolumeProjectionReason.DISCONNECTED
    assert result.completeness is PhoneVolumeProjectionCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert transport.write_count == 1
    assert "private" not in repr(result)


def test_preflight_and_cleanup_fail_closed_without_false_success():
    preflight = ScriptedVendorFakeTransport.vendor_route(write_properties=("read",))
    result = run(FakeVendorPhoneVolumeSimulator(preflight).project_once(
        _request(), quiet_timeout=0.01
    ))
    assert result.reason is PhoneVolumeProjectionReason.PREFLIGHT_FAILURE
    assert result.completeness is PhoneVolumeProjectionCompleteness.ABORTED
    assert preflight.subscribe_count == 0
    assert preflight.write_count == 0

    cleanup = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_error=RuntimeError("private cleanup")
    )
    cleanup.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
    )
    result = run(FakeVendorPhoneVolumeSimulator(cleanup).project_once(_request()))
    assert result.reason is PhoneVolumeProjectionReason.CLEANUP_FAILURE
    assert result.completeness is PhoneVolumeProjectionCompleteness.UNCERTAIN
    assert result.application_acknowledgement_observed is False
    assert result.cleanup_succeeded is False
    assert result.tainted is True

    prewrite_cleanup = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_error=RuntimeError("private cleanup")
    )
    simulator = FakeVendorPhoneVolumeSimulator(prewrite_cleanup)
    result = run(simulator.project_once(_request(), quiet_timeout=0.01))
    assert result.reason is PhoneVolumeProjectionReason.CLEANUP_FAILURE
    assert result.completeness is PhoneVolumeProjectionCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.transport_call_uncertain is False
    assert result.tainted is True
    assert prewrite_cleanup.write_count == 0
    with pytest.raises(PhoneVolumeSimulationTaintedError):
        run(simulator.project_once(_request()))


def test_inbound_body_is_discarded_and_duplicate_request_cannot_change_projection():
    transport = ScriptedVendorFakeTransport.vendor_route()
    private_body = b"private-looking-body"[:19]

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x49, private_body))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x49, bytes((99,)) * 19))

    transport.before_subscribe = emit
    result = run(FakeVendorPhoneVolumeSimulator(transport).project_once(_request()))

    assert result.reason is PhoneVolumeProjectionReason.FAKE_WRITE_CALL_RETURNED
    assert transport.write_count == 1
    assert transport.response_write_calls[0].data_for_test() == (
        _request().frames()[0].synthetic_bytes_for_test()
    )
    assert private_body not in transport.response_write_calls[0].data_for_test()
    assert private_body.decode() not in repr(result)


def test_early_request_is_discarded_if_subscription_never_confirms():
    transport = ScriptedVendorFakeTransport.vendor_route(
        subscribe_error=RuntimeError("private subscription error")
    )
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
    )

    result = run(FakeVendorPhoneVolumeSimulator(transport).project_once(_request()))

    assert result.reason is PhoneVolumeProjectionReason.PREFLIGHT_FAILURE
    assert result.request_observed is False
    assert result.write_invoked is False
    assert transport.write_count == 0


def test_cancellation_after_write_invocation_taints_and_cleans_up():
    async def scenario():
        gate = ScriptGate.blocked()
        transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
        transport.before_subscribe = lambda fake, _call: fake.emit(
            VENDOR_CHARACTERISTIC_33F4, _frame(0x49)
        )
        simulator = FakeVendorPhoneVolumeSimulator(transport)
        task = asyncio.create_task(simulator.project_once(_request()))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert simulator.tainted is True
        assert transport.write_count == 1
        assert transport.unsubscribe_count == 1
        assert transport.close_count == 1
        with pytest.raises(PhoneVolumeSimulationTaintedError):
            await simulator.project_once(_request())

    run(scenario())


def test_stale_callback_and_busy_or_wrong_types_cannot_project():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorPhoneVolumeSimulator(transport)
    first = run(simulator.project_once(_request(), quiet_timeout=0.01))
    assert first.reason is PhoneVolumeProjectionReason.LOCAL_QUIET
    transport.emit_stale(0, _frame(0x49))
    assert transport.write_count == 0

    run(transport.connect())
    with pytest.raises(RuntimeError, match="already connected or in use"):
        run(simulator.project_once(_request()))
    run(transport.close())

    with pytest.raises(TypeError, match="PhoneVolumeRequest"):
        run(simulator.project_once(object()))
    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorPhoneVolumeSimulator(object())


@pytest.mark.parametrize("value", (0, -1, float("inf"), True, "1"))
def test_time_bounds_are_strict(value):
    with pytest.raises((TypeError, ValueError)):
        run(FakeVendorPhoneVolumeSimulator(
            ScriptedVendorFakeTransport.vendor_route()
        ).project_once(_request(), quiet_timeout=value))
