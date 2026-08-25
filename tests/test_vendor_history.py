import math

import pytest

from jring.protocol import ProtocolError
from jring.vendor_history import (
    HistoryCloseReason,
    HistoryCompleteness,
    HistoryFamily,
    HistoryPhase,
    HistoryStreamKind,
    VendorHistoryStream,
    decode_vendor_history_frame,
)


def _frame(opcode: int, base: int, payload: bytes) -> bytes:
    return bytes((opcode,)) + base.to_bytes(4, "little") + payload


def _detail_frame(marker: int, fields: dict[int, int]) -> bytes:
    data = bytearray(20)
    data[0] = 0x16
    data[1] = marker
    for offset, value in fields.items():
        data[offset] = value
    return bytes(data)


def test_day_type_frames_decode_fifteen_raw_minute_samples():
    base = 1_700_000_000

    first = decode_vendor_history_frame(
        _frame(0x10, base, bytes(range(15)))
    )
    second = decode_vendor_history_frame(
        _frame(0x11, base, bytes(range(15, 30)))
    )

    assert [sample.family for sample in first.samples] == [
        HistoryFamily.DAY_TYPE_1
    ] * 15
    assert [sample.device_epoch_seconds for sample in first.samples] == [
        base + index * 60 for index in range(15)
    ]
    assert [sample.values for sample in first.samples] == [
        (value, 0) for value in range(15)
    ]
    assert second.samples[0].family is HistoryFamily.DAY_TYPE_2
    assert second.samples[-1].values == (29, 0)


def test_daily_stream_has_one_rescheduled_idle_close_not_a_wire_terminal():
    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=4.0,
        idle_timeout=2.0,
        overall_timeout=20.0,
    )
    first = stream.feed(_frame(0x10, 100, bytes(15)), now=0.5)
    second = stream.feed(_frame(0x11, 1_000, bytes(15)), now=1.75)

    assert first.closure is None
    assert second.closure is None
    assert stream.poll(now=2.5).closure is None  # old timer was invalidated
    closed = stream.poll(now=3.75).closure

    assert closed is not None
    assert closed.reason is HistoryCloseReason.IDLE_TIMEOUT
    assert closed.completeness is HistoryCompleteness.UNKNOWN
    assert closed.wire_terminal is False
    assert closed.families == (
        HistoryFamily.DAY_TYPE_1,
        HistoryFamily.DAY_TYPE_2,
    )
    assert closed.last_device_epoch_seconds == 1_840
    assert closed.last_timestamp_by_family == (
        (HistoryFamily.DAY_TYPE_1, 940),
        (HistoryFamily.DAY_TYPE_2, 1_840),
    )
    assert stream.poll(now=10.0).closure is None


def test_detail_metadata_and_a0_emit_two_samples_then_close_once():
    stream = VendorHistoryStream(
        HistoryStreamKind.DETAIL,
        started_at=0.0,
        overall_timeout=20.0,
    )
    stream.feed(_detail_frame(0xF0, {6: 5, 7: 0}), now=0.1)
    stream.feed(_detail_frame(0xAA, {2: 5, 7: 8, 8: 0}), now=0.2)
    data = bytearray(20)
    data[0:2] = bytes((0x16, 0xA0))
    data[2:6] = (1_000).to_bytes(4, "little")
    data[6:8] = (7).to_bytes(2, "little")
    data[8:14] = bytes((3, 0, 0, 0, 0, 0))  # Java round(0.5) == 1
    data[14:20] = bytes((9, 0, 0, 0, 0, 0))  # Java round(1.5) == 2

    update = stream.feed(bytes(data), now=0.3)

    assert [(sample.device_epoch_seconds, sample.values) for sample in update.samples] == [
        (1_000, (0, 1)),
        (1_060, (0, 2)),
    ]
    assert update.closure is not None
    assert update.closure.reason is HistoryCloseReason.DEVICE_METADATA
    assert update.closure.completeness is HistoryCompleteness.CONFIRMED
    assert update.closure.wire_terminal is False
    assert update.closure.last_device_epoch_seconds == 1_060
    assert stream.phase is HistoryPhase.CLOSED
    assert stream.poll(now=20.0).closure is None


def test_detail_metadata_is_transaction_local_and_never_invents_completion():
    stream = VendorHistoryStream(
        HistoryStreamKind.DETAIL,
        started_at=10.0,
        idle_timeout=2.0,
        overall_timeout=20.0,
    )
    data = bytearray(20)
    data[0:2] = bytes((0x16, 0xA0))
    data[2:6] = (2_000).to_bytes(4, "little")
    data[6:8] = (7).to_bytes(2, "little")

    update = stream.feed(bytes(data), now=10.1)

    assert len(update.samples) == 2
    assert update.closure is None
    closed = stream.poll(now=12.1).closure
    assert closed is not None
    assert closed.reason is HistoryCloseReason.IDLE_TIMEOUT
    assert closed.completeness is HistoryCompleteness.UNKNOWN


def test_detail_ff_is_the_only_direct_wire_terminal_and_never_fakes_epoch_zero():
    stream = VendorHistoryStream(HistoryStreamKind.DETAIL, started_at=0.0)

    update = stream.feed(_detail_frame(0xFF, {}), now=0.1)

    assert update.closure is not None
    assert update.closure.reason is HistoryCloseReason.WIRE_TERMINAL
    assert update.closure.completeness is HistoryCompleteness.CONFIRMED
    assert update.closure.wire_terminal is True
    assert update.closure.last_device_epoch_seconds is None


def test_temperature_history_uses_little_endian_pairs_and_last_sample_for_close():
    base = 10_000
    payload = b"".join(
        first.to_bytes(2, "little") + second.to_bytes(2, "little")
        for first, second in ((1, 2), (0x1234, 0x5678), (500, 600))
    ) + bytes(3)
    stream = VendorHistoryStream(
        HistoryStreamKind.TEMPERATURE,
        started_at=0.0,
        idle_timeout=2.0,
    )

    update = stream.feed(_frame(0x39, base, payload), now=0.1)

    assert [(sample.device_epoch_seconds, sample.values) for sample in update.samples] == [
        (base, (1, 2)),
        (base + 300, (0x1234, 0x5678)),
        (base + 600, (500, 600)),
    ]
    closed = stream.poll(now=2.1).closure
    assert closed is not None
    assert closed.last_device_epoch_seconds == base + 600


def test_existing_oxygen_and_advanced_frames_project_to_one_canonical_shape():
    oxygen_base = 20_000
    oxygen = decode_vendor_history_frame(
        _frame(0x40, oxygen_base, bytes(range(15)))
    )
    advanced_base = 30_000
    advanced = decode_vendor_history_frame(
        _frame(0x55, advanced_base, bytes(range(1, 16)))
    )

    assert oxygen.samples[-1].device_epoch_seconds == oxygen_base + 840
    assert oxygen.samples[-1].values == (14,)
    assert oxygen.samples[-1].data_by_day_type == 13
    assert oxygen.samples[-1].data_by_day_values == (14, 0)
    assert [sample.device_epoch_seconds for sample in advanced.samples] == [
        advanced_base,
        advanced_base + 900,
        advanced_base + 1_800,
    ]
    assert [sample.values for sample in advanced.samples] == [
        (1, 2, 3, 4, 5),
        (6, 7, 8, 9, 10),
        (11, 12, 13, 14, 15),
    ]
    # The generic type-14 projection uses record starts 5/10/15, not the APK's
    # accidental adjacent positions 5/6/7.
    assert [sample.data_by_day_values for sample in advanced.samples] == [
        (1, 0),
        (6, 0),
        (11, 0),
    ]


@pytest.mark.parametrize(
    "kind,failure_opcode",
    [
        (HistoryStreamKind.DAILY, 0x90),
        (HistoryStreamKind.DETAIL, 0x96),
        (HistoryStreamKind.TEMPERATURE, 0xB9),
    ],
)
def test_proven_failure_opcodes_close_failed_without_normal_end(kind, failure_opcode):
    stream = VendorHistoryStream(kind, started_at=0.0)

    update = stream.feed(bytes((failure_opcode,)) + bytes(19), now=0.1)

    assert update.samples == ()
    assert update.closure is not None
    assert update.closure.reason is HistoryCloseReason.DEVICE_FAILURE
    assert update.closure.completeness is HistoryCompleteness.FAILED
    assert update.closure.wire_terminal is False


@pytest.mark.parametrize(
    "kind,opcode,last_offset",
    [
        (HistoryStreamKind.OXYGEN, 0x40, 840),
        (HistoryStreamKind.ADVANCED_SENSOR, 0x55, 1_800),
    ],
)
def test_no_host_clock_heuristic_or_duplicate_end(kind, opcode, last_offset):
    # This raw number's rendering is deliberately irrelevant: the decoder never
    # converts it through the host timezone or recognizes a local 23:45 marker.
    base = 86_400 - last_offset
    payload = bytes(15)
    stream = VendorHistoryStream(kind, started_at=0.0, idle_timeout=2.0)

    update = stream.feed(_frame(opcode, base, payload), now=0.1)

    assert update.closure is None
    assert stream.poll(now=2.099).closure is None
    closed = stream.poll(now=2.1).closure
    assert closed is not None
    assert closed.reason is HistoryCloseReason.IDLE_TIMEOUT
    assert closed.last_device_epoch_seconds == base + last_offset
    assert stream.poll(now=99.0).closure is None


def test_timeouts_are_finite_monotonic_and_timeout_wins_at_exact_deadline():
    with pytest.raises(ValueError):
        VendorHistoryStream(
            HistoryStreamKind.DAILY,
            started_at=0.0,
            idle_timeout=math.inf,
        )

    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=5.0,
        first_frame_timeout=3.0,
        overall_timeout=10.0,
    )
    update = stream.feed(_frame(0x10, 100, bytes(15)), now=8.0)

    assert update.samples == ()
    assert update.closure is not None
    assert update.closure.reason is HistoryCloseReason.FIRST_FRAME_TIMEOUT
    assert update.closure.completeness is HistoryCompleteness.ABORTED


def test_stale_deadline_token_cannot_close_a_rescheduled_stream():
    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=1.0,
        idle_timeout=2.0,
    )
    stale = stream.deadline_token()
    stream.feed(_frame(0x10, 100, bytes(15)), now=0.5)
    current = stream.deadline_token()

    assert stale is not None
    assert current is not None
    assert stale != current
    assert stream.poll(now=1.0, token=stale).closure is None
    assert stream.phase is HistoryPhase.RECEIVING
    assert stream.poll(now=2.5, token=current).closure.reason is HistoryCloseReason.IDLE_TIMEOUT


def test_deadline_token_from_an_old_session_cannot_close_a_new_session():
    old_stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=1.0,
    )
    stale = old_stream.deadline_token()
    new_stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=1.0,
    )

    assert stale is not None
    assert new_stream.poll(now=1.0, token=stale).closure is None
    assert new_stream.phase is HistoryPhase.WAITING_FIRST_FRAME
    assert new_stream.poll(
        now=1.0, token=new_stream.deadline_token()
    ).closure.reason is HistoryCloseReason.FIRST_FRAME_TIMEOUT


def test_monotonic_time_cannot_regress_or_move_a_deadline_backwards():
    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=20.0,
        idle_timeout=2.0,
        overall_timeout=30.0,
    )
    stream.feed(_frame(0x10, 1_000, bytes(15)), now=10.0)
    expected_token = stream.deadline_token()

    with pytest.raises(ValueError, match="monotonic"):
        stream.feed(_frame(0x10, 100, bytes(15)), now=9.999)

    assert stream.deadline_token() == expected_token


def test_stream_identity_and_phase_are_read_only():
    stream = VendorHistoryStream(HistoryStreamKind.DAILY, started_at=0.0)

    with pytest.raises(AttributeError):
        stream.kind = HistoryStreamKind.OXYGEN
    with pytest.raises(AttributeError):
        stream.phase = HistoryPhase.CLOSED
    with pytest.raises(ProtocolError):
        stream.feed(_frame(0x40, 100, bytes(15)), now=0.1)


@pytest.mark.parametrize("kind", list(HistoryStreamKind))
def test_empty_stream_closure_preserves_operation_identity_and_static_maturity(kind):
    stream = VendorHistoryStream(
        kind,
        started_at=0.0,
        first_frame_timeout=1.0,
    )

    closure = stream.poll(now=1.0).closure

    assert closure is not None
    assert closure.stream_kind is kind
    assert closure.families == ()
    assert closure.maturity == "static_apk_only"
    assert closure.hardware_verified is False


def test_last_timestamp_means_last_emitted_not_largest_seen():
    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=10.0,
    )
    stream.feed(_frame(0x10, 1_000, bytes(15)), now=0.1)
    stream.feed(_frame(0x10, 100, bytes(15)), now=0.2)

    closure = stream.poll(now=2.2).closure

    assert closure is not None
    assert closure.last_device_epoch_seconds == 940
    assert closure.last_timestamp_by_family == (
        (HistoryFamily.DAY_TYPE_1, 940),
    )


def test_calculated_deadlines_must_remain_finite():
    with pytest.raises(ValueError, match="deadline"):
        VendorHistoryStream(
            HistoryStreamKind.DAILY,
            started_at=1e308,
            first_frame_timeout=1e308,
            overall_timeout=1e308,
        )


def test_poll_rejects_a_non_token_instead_of_silently_disabling_timeout():
    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=1.0,
    )

    with pytest.raises(TypeError, match="token"):
        stream.poll(now=1.0, token="not-a-token")


@pytest.mark.parametrize(
    "family,timestamp,values,error",
    [
        ("oxygen", 0, (1,), TypeError),
        (HistoryFamily.OXYGEN, True, (1,), TypeError),
        (HistoryFamily.OXYGEN, -1, (1,), ValueError),
        (HistoryFamily.OXYGEN, 0, [], TypeError),
        (HistoryFamily.OXYGEN, 0, (), ValueError),
        (HistoryFamily.OXYGEN, 0, (True,), TypeError),
        (HistoryFamily.OXYGEN, 0, (256,), ValueError),
        (HistoryFamily.ADVANCED_SENSOR, 0, (1, 2, 3), ValueError),
        (HistoryFamily.DAY_TYPE_1, 0, (1, 1), ValueError),
        (HistoryFamily.DAY_TYPE_3, 0, (1, 2), ValueError),
    ],
)
def test_public_history_sample_rejects_invalid_shapes(
    family, timestamp, values, error
):
    from jring.vendor_history import VendorHistorySample

    with pytest.raises(error):
        VendorHistorySample(family, timestamp, values)


def test_unrelated_or_malformed_frames_do_not_refresh_the_stream():
    stream = VendorHistoryStream(
        HistoryStreamKind.DAILY,
        started_at=0.0,
        first_frame_timeout=1.0,
    )

    with pytest.raises(ProtocolError):
        stream.feed(bytes((0x40,)) + bytes(19), now=0.5)
    with pytest.raises(ProtocolError):
        decode_vendor_history_frame(bytes((0x10,)) + bytes(18))

    assert stream.poll(now=1.0).closure.reason is HistoryCloseReason.FIRST_FRAME_TIMEOUT


def test_disconnect_closes_once_and_repr_redacts_measurements_and_timestamps():
    stream = VendorHistoryStream(HistoryStreamKind.OXYGEN, started_at=0.0)
    update = stream.feed(_frame(0x40, 12_345, bytes((77,)) + bytes(14)), now=0.1)

    assert "12345" not in repr(update)
    assert "77" not in repr(update)
    closed = stream.disconnect().closure
    assert closed is not None
    assert closed.reason is HistoryCloseReason.DISCONNECTED
    assert closed.completeness is HistoryCompleteness.ABORTED
    assert stream.disconnect().closure is None
