import asyncio

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F4
from jring.vendor_ecg_history_runtime_simulator import (
    EcgHistoryCollectionCompleteness,
    EcgHistorySimulationReason,
    FakeVendorEcgHistorySimulator,
)
from jring.vendor_main_commands import EcgHistoryRequest
from jring.vendor_runtime_fake import ScriptedVendorFakeTransport


def run(coro):
    return asyncio.run(coro)


def _metadata(timestamp: int = 123_456_789, value: int = 77) -> bytes:
    return bytes((0x2C,)) + timestamp.to_bytes(4, "little") + bytes((value,)) + bytes(14)


def _event(
    first: int = 91,
    second: int = 92,
    timestamp: int = 987_654_321,
) -> bytes:
    return (
        bytes((0x2D, first, second))
        + timestamp.to_bytes(4, "little")
        + bytes(13)
    )


def _samples(discriminator: int = 9) -> bytes:
    return bytes((0x2E, discriminator)) + bytes((0x23, 0x61, 0x45)) * 6


def _collect(transport, **options):
    return run(FakeVendorEcgHistorySimulator(transport).collect(
        request=EcgHistoryRequest(1_700_000_000, 19_800),
        quiet_timeout=0.01,
        **options,
    ))


def test_metadata_events_and_samples_preserve_wire_order_but_never_confirm_end():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _event())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _samples())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _event(93, 94, 987_654_322))

    transport.before_write = emit
    result = _collect(transport, frame_limit=5)

    assert result.reason is EcgHistorySimulationReason.LOCAL_QUIET
    assert result.completeness is EcgHistoryCollectionCompleteness.UNKNOWN
    assert result.projections == (
        ("onGetEcgHistory", 1, "wire_frame"),
        ("onGetEcgStartEnd", 1, "wire_frame"),
        ("onGetEcgHistoryData", 1, "wire_frame"),
        ("onGetEcgStartEnd", 1, "wire_frame"),
    )
    assert result.accepted_frame_count == 4
    assert result.sample_count == 12
    assert result.metadata_received is True
    assert result.wire_terminal_observed is False
    assert result.quiet_means_success is False


@pytest.mark.parametrize("frame", [_event(), _samples()])
def test_history_before_metadata_aborts_without_projecting_a_callback(frame):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, frame
    )

    result = _collect(transport)

    assert result.reason is EcgHistorySimulationReason.ORDERING_VIOLATION
    assert result.completeness is EcgHistoryCollectionCompleteness.ABORTED
    assert result.accepted_frame_count == 0
    assert result.projections == ()


def test_duplicate_metadata_aborts_after_only_the_first_projection():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata(123_456_790, 78))

    transport.before_write = emit
    result = _collect(transport)

    assert result.reason is EcgHistorySimulationReason.ORDERING_VIOLATION
    assert result.completeness is EcgHistoryCollectionCompleteness.ABORTED
    assert result.accepted_frame_count == 1
    assert result.projections == (("onGetEcgHistory", 1, "wire_frame"),)


def test_no_start_end_value_or_pattern_is_promoted_to_a_terminal():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        for values in ((0, 0, 0), (0xFF, 0xFF, 0xFFFFFFFF), (1, 0, 1)):
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _event(*values))

    transport.before_write = emit
    result = _collect(transport, frame_limit=4)

    assert result.reason is EcgHistorySimulationReason.LIMIT_REACHED
    assert result.completeness is EcgHistoryCollectionCompleteness.UNKNOWN
    assert result.wire_terminal_observed is False
    assert result.projections.count(("onGetEcgStartEnd", 1, "wire_frame")) == 3


@pytest.mark.parametrize(
    "frame",
    [bytes((0x2C, 77)), bytes((0x2D, 77)), bytes((0x2E, 77))],
)
def test_matching_malformed_frame_aborts_without_retaining_raw_bytes(frame):
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, frame
    )

    result = _collect(transport)

    assert result.reason is EcgHistorySimulationReason.MALFORMED_FRAME
    assert result.completeness is EcgHistoryCollectionCompleteness.ABORTED
    assert "77" not in repr(result)
    assert "parsed_frames=<redacted>" in repr(result)


def test_abort_after_metadata_explicitly_requires_discarding_partial_results():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x2E, 77)))

    transport.before_write = emit
    result = _collect(transport)

    assert result.completeness is EcgHistoryCollectionCompleteness.ABORTED
    assert result.accepted_frame_count == 1
    assert result.partial_data_requires_discard is True
    assert "discard" in result.user_guidance.lower()


def test_unknown_completion_guidance_never_calls_quiet_or_limit_success():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _metadata()
    )

    result = _collect(transport, frame_limit=1)

    assert result.completeness is EcgHistoryCollectionCompleteness.UNKNOWN
    assert result.partial_data_requires_discard is False
    assert "incomplete" in result.user_guidance.lower()
    assert "success" not in result.user_guidance.lower()


def test_unrelated_live_ecg_does_not_refresh_the_accepted_frame_deadline():
    transport = ScriptedVendorFakeTransport.vendor_route()
    delayed = []

    async def emit_later(fake):
        await asyncio.sleep(0.006)
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x2B, 1)) + bytes(18))
        await asyncio.sleep(0.006)
        try:
            fake.emit(VENDOR_CHARACTERISTIC_33F4, _samples())
        except KeyError:
            pass

    def start(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        delayed.append(asyncio.create_task(emit_later(fake)))

    transport.before_write = start

    async def scenario():
        result = await FakeVendorEcgHistorySimulator(transport).collect(
            request=EcgHistoryRequest(1_700_000_000, 19_800),
            frame_limit=4,
            quiet_timeout=0.01,
        )
        await asyncio.gather(*delayed)
        return result

    result = run(scenario())

    assert result.reason is EcgHistorySimulationReason.LOCAL_QUIET
    assert result.accepted_frame_count == 1
    assert result.unrelated_frame_count == 1
    assert result.sample_count == 0


def test_bounded_queue_overflow_aborts_instead_of_dropping_ecg_history():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _event())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _samples())

    transport.before_write = emit
    result = _collect(transport, frame_limit=1)

    assert result.reason is EcgHistorySimulationReason.QUEUE_OVERFLOW
    assert result.completeness is EcgHistoryCollectionCompleteness.ABORTED
    assert result.accepted_frame_count == 0
    assert result.projections == ()
    assert result.delivery_uncertain is True


def test_cleanup_drains_orphan_queue_and_stale_callback_retains_no_ecg_bytes():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _samples())

    transport.before_write = emit
    result = _collect(transport, frame_limit=1)
    callback = transport.subscription_calls[0].callback
    retained_queues = [
        cell.cell_contents
        for cell in (callback.__closure__ or ())
        if isinstance(cell.cell_contents, asyncio.Queue)
    ]

    assert result.reason is EcgHistorySimulationReason.LIMIT_REACHED
    assert len(retained_queues) == 1
    assert retained_queues[0].qsize() == 0
    transport.emit_stale(0, _samples(17))
    assert retained_queues[0].qsize() == 0


def test_oversized_matching_notification_is_bounded_then_aborts_malformed():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x2C,)) + bytes(100_000)
    )

    result = _collect(transport)

    assert result.reason is EcgHistorySimulationReason.MALFORMED_FRAME
    callback = transport.subscription_calls[0].callback
    retained_queues = [
        cell.cell_contents
        for cell in (callback.__closure__ or ())
        if isinstance(cell.cell_contents, asyncio.Queue)
    ]
    assert retained_queues[0].qsize() == 0


def test_result_repr_hides_samples_timestamps_metadata_and_parsed_frames():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _event())
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _samples())

    transport.before_write = emit
    result = _collect(transport, frame_limit=3)
    rendered = repr(result)

    for sensitive in ("123456789", "987654321", "291", "1110"):
        assert sensitive not in rendered
    assert "parsed_frames=<redacted>" in rendered
    assert "sample_count=12" in rendered
    assert len(result.parsed_frames_for_test()) == 3


def test_collector_subscribes_before_exact_request_write_and_cleans_up():
    transport = ScriptedVendorFakeTransport.vendor_route()
    observed = []

    def inspect_write(fake, call):
        observed.append(fake.active_callback_count)
        assert call.data_for_test() == (
            bytes((0x2C,))
            + (1_700_019_800).to_bytes(4, "little")
            + bytes(15)
        )
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _metadata())

    transport.before_write = inspect_write
    result = _collect(transport, frame_limit=1)

    assert observed == [1]
    assert result.reason is EcgHistorySimulationReason.LIMIT_REACHED
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert transport.active_callback_count == 0


def test_collector_accepts_only_exact_closed_fake_and_request_types():
    with pytest.raises(TypeError):
        FakeVendorEcgHistorySimulator(object())

    simulator = FakeVendorEcgHistorySimulator(
        ScriptedVendorFakeTransport.vendor_route()
    )
    with pytest.raises(TypeError):
        run(simulator.collect(request=object()))
    with pytest.raises(ValueError, match="at most"):
        run(simulator.collect(
            request=EcgHistoryRequest(0, 0),
            frame_limit=4_097,
        ))
