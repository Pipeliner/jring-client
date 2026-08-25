import asyncio

import pytest

import jring.vendor_generic_history_runtime_simulator as generic_runtime
from jring.uuids import VENDOR_CHARACTERISTIC_33F4
from jring.vendor_generic_history_runtime_simulator import (
    FakeVendorGenericHistorySimulator,
    GenericHistorySimulationReason,
)
from jring.vendor_history import (
    HistoryCloseReason,
    HistoryClosure,
    HistoryCompleteness,
    HistoryStreamKind,
    VendorHistoryUpdate,
)
from jring.vendor_main_commands import DayDataKind, DayDataRequest
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport


def run(coro):
    return asyncio.run(coro)


def _frame(opcode: int, base: int = 100, payload: bytes = bytes(15)) -> bytes:
    return bytes((opcode,)) + base.to_bytes(4, "little") + payload


def _detail(marker: int, fields: dict[int, int] | None = None) -> bytes:
    data = bytearray(20)
    data[0:2] = bytes((0x16, marker))
    for offset, value in (fields or {}).items():
        data[offset] = value
    return bytes(data)


def test_daily_frames_project_samples_then_local_unknown_end():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x10))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x11, 1_000))

    transport.before_write = emit
    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        frame_limit=3,
        quiet_timeout=0.01,
    ))

    assert result.reason is GenericHistorySimulationReason.LOCAL_QUIET
    assert result.completeness is HistoryCompleteness.UNKNOWN
    assert result.projections == (
        ("onGetDataByDay", 15, "wire_frame"),
        ("onGetDataByDay", 15, "wire_frame"),
        ("onGetDataByDayEnd", 1, "local_quiet_projection"),
    )
    assert result.local_end_projected is True
    assert result.wire_terminal_observed is False
    assert result.accepted_frame_count == 2
    assert result.local_end_arguments_for_explicit_test_use() == (2, 1_840)
    assert "1840" not in repr(result)
    assert transport.targeted_write_count == 1
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.response_write_calls[0].target_instance_id is not None


def test_detail_ff_is_confirmed_wire_terminal_without_invented_samples():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _detail(0xFF)
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_2, 7),
        frame_limit=4,
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.WIRE_TERMINAL
    assert result.completeness is HistoryCompleteness.CONFIRMED
    assert result.projections == (("onGetDataByDayEnd", 1, "wire_terminal"),)
    assert result.wire_terminal_observed is True
    assert result.sample_count == 0


def test_detail_metadata_predicate_closes_confirmed_but_not_wire_terminal():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _detail(0xF0, {6: 5}))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _detail(0xAA, {2: 5, 7: 8}))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _detail(0xA0, {6: 7}))

    transport.before_write = emit
    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_2, 0),
        frame_limit=5,
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.DEVICE_METADATA
    assert result.completeness is HistoryCompleteness.CONFIRMED
    assert result.projections == (
        ("onGetDataByDay", 2, "wire_frame"),
        ("onGetDataByDayEnd", 1, "device_metadata"),
    )
    assert result.wire_terminal_observed is False


def test_detail_metadata_only_quiet_does_not_fabricate_local_end():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _detail(0xF0, {6: 5})
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_2, 0),
        frame_limit=2,
        quiet_timeout=0.01,
    ))

    assert result.reason is GenericHistorySimulationReason.LOCAL_QUIET
    assert result.sample_count == 0
    assert result.local_end_projected is False
    assert result.projections == ()


@pytest.mark.parametrize(
    "kind,failure_opcode",
    [
        (DayDataKind.SDK_TYPE_1, 0x90),
        (DayDataKind.SDK_TYPE_2, 0x96),
        (DayDataKind.SDK_TYPE_12, 0xB9),
    ],
)
def test_proven_failure_frames_project_failed_end(kind, failure_opcode):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((failure_opcode,)) + bytes(19)
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(kind, 0),
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.DEVICE_FAILURE
    assert result.completeness is HistoryCompleteness.FAILED
    assert result.projections == (("onGetDataByDayEnd", 1, "wire_failure_frame"),)


def test_other_family_does_not_refresh_quiet_or_become_success():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x40)
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_12, 0),
        quiet_timeout=0.01,
    ))

    assert result.reason is GenericHistorySimulationReason.LOCAL_QUIET
    assert result.completeness is HistoryCompleteness.UNKNOWN
    assert result.unrelated_frame_count == 1
    assert result.accepted_frame_count == 0
    assert result.projections == ()


def test_type_13_preserves_generic_then_specialized_oxygen_multiplicity():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x40)
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_13, 0),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.LIMIT_REACHED
    assert result.projections == (
        ("onGetDataByDay", 15, "wire_frame"),
        ("onGetOxygenOfflineData", 15, "wire_frame"),
    )


def test_matching_malformed_frame_aborts_and_result_repr_redacts_data():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x39, 77))
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_12, 0),
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.MALFORMED_FRAME
    assert result.completeness is HistoryCompleteness.ABORTED
    assert "77" not in repr(result)
    assert "parsed_updates=<redacted>" in repr(result)
    assert result.partial_data is False
    assert "no real device was contacted" in result.user_guidance
    assert "without a completion claim" in result.user_guidance


def test_limit_is_unknown_and_does_not_fabricate_end_projection():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x39, payload=bytes(15))
    )

    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_12, 0),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.LIMIT_REACHED
    assert result.completeness is HistoryCompleteness.UNKNOWN
    assert result.projections == (("onGetDataByDay", 3, "wire_frame"),)
    assert result.local_end_projected is False


def test_bounded_queue_overflow_aborts_instead_of_silently_dropping_history():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        for base in (100, 200, 300):
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x10, base))

    transport.before_write = emit
    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.QUEUE_OVERFLOW
    assert result.completeness is HistoryCompleteness.ABORTED
    assert result.accepted_frame_count == 0
    assert result.projections == ()
    assert result.delivery_uncertain is True


def test_setup_delay_does_not_turn_a_valid_frame_into_device_failure():
    transport = ScriptedVendorFakeTransport.vendor_route()

    async def delayed_emit(fake, _call):
        await asyncio.sleep(0.02)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x10))

    transport.before_write = delayed_emit
    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        frame_limit=1,
        quiet_timeout=0.1,
        overall_timeout=0.01,
        stage_timeout=0.1,
    ))

    assert result.reason is GenericHistorySimulationReason.LIMIT_REACHED
    assert result.completeness is HistoryCompleteness.UNKNOWN
    assert result.sample_count == 15


def test_expired_stream_closure_never_projects_a_device_failure(monkeypatch):
    class ExpiredStream:
        def __init__(self, *_args, **_kwargs):
            pass

        def feed(self, _data, *, now):
            return VendorHistoryUpdate(closure=HistoryClosure(
                stream_kind=HistoryStreamKind.DAILY,
                reason=HistoryCloseReason.OVERALL_TIMEOUT,
                completeness=HistoryCompleteness.ABORTED,
                families=(),
            ))

    monkeypatch.setattr(generic_runtime, "VendorHistoryStream", ExpiredStream)
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x10)
    )
    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
    ))

    assert result.reason is GenericHistorySimulationReason.OVERALL_TIMEOUT
    assert result.completeness is HistoryCompleteness.ABORTED
    assert result.projections == ()


def test_blocked_setup_and_cleanup_stages_are_bounded_and_aborted():
    connect_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorGenericHistorySimulator(connect_blocked).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        stage_timeout=0.01,
    ))
    assert result.reason is GenericHistorySimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is HistoryCompleteness.ABORTED

    cleanup_blocked = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_gate=ScriptGate.blocked()
    )
    cleanup_blocked.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _frame(0x10)
    )
    result = run(FakeVendorGenericHistorySimulator(cleanup_blocked).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        frame_limit=1,
        stage_timeout=0.01,
    ))
    assert result.reason is GenericHistorySimulationReason.CLEANUP_FAILURE
    assert result.completeness is HistoryCompleteness.ABORTED
    assert result.cleanup_succeeded is False


def test_collector_rejects_concurrent_use_and_allows_sequential_reuse():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(connect_gate=gate)
    simulator = FakeVendorGenericHistorySimulator(transport)
    request = DayDataRequest(DayDataKind.SDK_TYPE_1, 0)

    async def scenario():
        first = asyncio.create_task(simulator.collect(
            request=request,
            quiet_timeout=0.01,
            stage_timeout=0.1,
        ))
        await gate.wait_until_entered()
        with pytest.raises(RuntimeError, match="already in progress"):
            await simulator.collect(request=request)
        gate.release()
        first_result = await first
        second_result = await simulator.collect(
            request=request,
            quiet_timeout=0.01,
        )
        return first_result, second_result

    first_result, second_result = run(scenario())
    assert first_result.reason is GenericHistorySimulationReason.LOCAL_QUIET
    assert second_result.reason is GenericHistorySimulationReason.LOCAL_QUIET


def test_old_retained_callback_cannot_inject_into_reused_collector():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorGenericHistorySimulator(transport)
    request = DayDataRequest(DayDataKind.SDK_TYPE_1, 0)

    def first_emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x10, 100))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x11, 200))

    def second_emit(fake, _call):
        fake.emit_stale(0, bytes((0x90,)) + bytes(19))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _frame(0x10, 300))

    async def scenario():
        transport.before_write = first_emit
        first = await simulator.collect(request=request, frame_limit=1)
        transport.before_write = second_emit
        second = await simulator.collect(request=request, frame_limit=1)
        return first, second

    first, second = run(scenario())
    assert first.sample_count == 15
    assert second.reason is GenericHistorySimulationReason.LIMIT_REACHED
    assert second.completeness is HistoryCompleteness.UNKNOWN
    assert second.sample_count == 15
    assert second.projections == (("onGetDataByDay", 15, "wire_frame"),)


def test_frame_limit_is_capped_before_connecting():
    transport = ScriptedVendorFakeTransport.vendor_route()
    simulator = FakeVendorGenericHistorySimulator(transport)

    with pytest.raises(ValueError, match="cannot exceed"):
        run(simulator.collect(
            request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
            frame_limit=4_097,
        ))
    assert transport.connect_count == 0


def test_unknown_result_guidance_calls_out_local_incompleteness():
    transport = ScriptedVendorFakeTransport.vendor_route()
    result = run(FakeVendorGenericHistorySimulator(transport).collect(
        request=DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        quiet_timeout=0.01,
    ))

    assert "Synthetic history only" in result.user_guidance
    assert "stopped locally" in result.user_guidance
    assert "may be incomplete" in result.user_guidance


def test_collector_accepts_only_exact_closed_fake_and_request_types():
    with pytest.raises(TypeError):
        FakeVendorGenericHistorySimulator(object())

    simulator = FakeVendorGenericHistorySimulator(
        ScriptedVendorFakeTransport.vendor_route()
    )
    with pytest.raises(TypeError):
        run(simulator.collect(request=object()))
