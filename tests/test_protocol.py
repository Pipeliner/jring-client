from datetime import datetime, timezone

import pytest

from jring.protocol import (
    HistoryRecord,
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
