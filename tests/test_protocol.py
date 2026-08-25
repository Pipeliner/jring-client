from datetime import datetime, timezone

import pytest

from jring.protocol import (
    HistoryRecord,
    MAX_HEART_RATE_MEASUREMENT_LENGTH,
    ProtocolError,
    SimEnvelope,
    parse_battery,
    parse_device_text,
    parse_heart_rate,
)


def test_standard_gatt_golden_vectors():
    assert parse_battery(b"\x57") == 87
    assert parse_device_text(b"JR-1\x00") == "JR-1"
    assert parse_heart_rate(bytes.fromhex("0062")).bpm == 98
    assert parse_heart_rate(bytes.fromhex("014b00")).bpm == 75


def test_heart_rate_accepts_contact_energy_and_rr_fields_without_exposing_them():
    unsupported = parse_heart_rate(bytes.fromhex("0048"))
    not_detected = parse_heart_rate(bytes.fromhex("0448"))
    detected = parse_heart_rate(bytes.fromhex("0648"))
    optional_fields = parse_heart_rate(bytes.fromhex("1848341200040005"))

    assert unsupported.contact_detected is None
    assert not_detected.contact_detected is False
    assert detected.contact_detected is True
    assert optional_fields.bpm == 72
    assert optional_fields.contact_detected is None
    assert parse_heart_rate(bytes.fromhex("08483412")).bpm == 72
    assert parse_heart_rate(bytes.fromhex("104800040005")).bpm == 72
    assert parse_heart_rate(bytes.fromhex("192c0134120004")).bpm == 300


@pytest.mark.parametrize(
    "value, message",
    (
        (bytes.fromhex("2048"), "reserved flags"),
        (bytes.fromhex("4048"), "reserved flags"),
        (bytes.fromhex("8048"), "reserved flags"),
        (bytes.fromhex("0248"), "contact flags"),
        (bytes.fromhex("0848"), "energy-expended"),
        (bytes.fromhex("084801"), "energy-expended"),
        (bytes.fromhex("1048"), "RR interval"),
        (bytes.fromhex("104801"), "RR interval length"),
        (bytes.fromhex("00480000"), "trailing"),
    ),
)
def test_heart_rate_rejects_malformed_optional_fields(value, message):
    with pytest.raises(ProtocolError, match=message):
        parse_heart_rate(value)


def test_heart_rate_rejects_frames_over_the_documented_bound_without_echoing_data():
    marker = b"private-health-data"
    value = b"\x10\x48" + marker * (
        MAX_HEART_RATE_MEASUREMENT_LENGTH // len(marker) + 1
    )

    with pytest.raises(ProtocolError) as caught:
        parse_heart_rate(value)

    assert "private" not in str(caught.value)


def test_heart_rate_documented_frame_bound_is_inclusive():
    value = b"\x10\x48" + b"\x00\x04" * (
        (MAX_HEART_RATE_MEASUREMENT_LENGTH - 2) // 2
    )

    assert len(value) == MAX_HEART_RATE_MEASUREMENT_LENGTH
    assert parse_heart_rate(value).bpm == 72


@pytest.mark.parametrize("value", [b"", b"\x65", b"\xff"])
def test_battery_rejects_invalid(value):
    with pytest.raises(ProtocolError):
        parse_battery(value)


def test_simulator_envelope_golden_and_checksum():
    encoded = SimEnvelope(2, b"abc").encode()
    assert encoded.hex() == "4a5202030061626361"
    assert SimEnvelope.decode(encoded) == SimEnvelope(2, b"abc")
    with pytest.raises(ProtocolError):
        SimEnvelope.decode(encoded[:-1] + b"\x00")


def test_history_record_is_typed():
    record = HistoryRecord(datetime(2026, 1, 2, tzinfo=timezone.utc), "heart_rate", 72)
    assert record.to_dict()["kind"] == "heart_rate"
