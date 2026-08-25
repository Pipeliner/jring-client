import asyncio

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F4
from jring.vendor_generic_history_runtime_simulator import (
    FakeVendorGenericHistorySimulator,
    GenericHistorySimulationReason,
)
from jring.vendor_history import HistoryCompleteness
from jring.vendor_main_commands import DayDataKind, DayDataRequest
from jring.vendor_runtime_fake import ScriptedVendorFakeTransport


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


def test_collector_accepts_only_exact_closed_fake_and_request_types():
    with pytest.raises(TypeError):
        FakeVendorGenericHistorySimulator(object())

    simulator = FakeVendorGenericHistorySimulator(
        ScriptedVendorFakeTransport.vendor_route()
    )
    with pytest.raises(TypeError):
        run(simulator.collect(request=object()))
