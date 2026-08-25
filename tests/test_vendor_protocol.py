import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4
from jring.vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    encode_day_query,
    encode_static_query,
    parse_vendor_advanced_sensor_day,
    parse_vendor_battery,
    parse_vendor_band_functions,
    parse_vendor_current_sport,
    parse_vendor_device_info,
    parse_vendor_multi_sport_day,
    parse_vendor_oxygen_day,
    static_protocol_coverage,
)
from jring.protocol import ProtocolError


@pytest.mark.parametrize(
    "operation,opcode",
    [
        (StaticQuery.CURRENT_SPORT, 0x03),
        (StaticQuery.BATTERY, 0x0B),
        (StaticQuery.DEVICE_INFO, 0x0C),
        (StaticQuery.BAND_FUNCTIONS, 0x20),
    ],
)
def test_static_zero_argument_query_vectors(operation, opcode):
    request = encode_static_query(operation)

    assert request.synthetic_bytes_for_test() == bytes((opcode,)) + bytes(19)
    assert request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert request.maturity == "static_apk_only"
    assert request.hardware_eligible is False


@pytest.mark.parametrize(
    "operation,opcode",
    [
        (StaticQuery.MULTI_SPORT_DAY, 0x25),
        (StaticQuery.OXYGEN_DAY, 0x40),
        (StaticQuery.ADVANCED_SENSOR_DAY, 0x55),
    ],
)
def test_static_day_query_vectors(operation, opcode):
    request = encode_day_query(operation, day_offset=7)

    assert request.synthetic_bytes_for_test() == bytes((opcode, 7)) + bytes(18)
    assert request.hardware_eligible is False


@pytest.mark.parametrize("day_offset", [-1, 256, True, 1.5])
def test_day_query_rejects_values_not_representable_as_one_unsigned_byte(day_offset):
    with pytest.raises((TypeError, ValueError)):
        encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=day_offset)


def test_query_kinds_cannot_be_used_with_the_wrong_encoder():
    with pytest.raises(ValueError):
        encode_static_query(StaticQuery.OXYGEN_DAY)
    with pytest.raises(ValueError):
        encode_day_query(StaticQuery.BATTERY, day_offset=1)


def test_static_request_repr_never_contains_frame_bytes():
    request = encode_static_query(StaticQuery.BATTERY)

    assert "0b00" not in repr(request).lower()
    assert "frame" not in repr(request).lower()


def test_static_request_cannot_be_constructed_as_hardware_eligible():
    with pytest.raises(TypeError):
        StaticVendorRequest(
            StaticQuery.BATTERY,
            b"",
            hardware_eligible=True,
        )


def test_client_has_no_vendor_transmission_api():
    from jring.client import JRingClient

    assert not hasattr(JRingClient, "send_vendor_request")
    assert not hasattr(JRingClient, "write_vendor_frame")


def test_vendor_battery_response_is_typed_without_guessing_state_meaning():
    response = parse_vendor_battery(bytes((0x0B, 84, 1)) + bytes(17))

    assert response.percent == 84
    assert response.state_code == 1
    assert response.state_meaning == "unknown"


@pytest.mark.parametrize(
    "data",
    [
        bytes((0x8B,)) + bytes(19),
        bytes((0x0B, 101)) + bytes(18),
        bytes((0x0B, 50)),
        bytes((0x0C,)) + bytes(19),
    ],
)
def test_vendor_battery_response_fails_closed(data):
    with pytest.raises(ProtocolError):
        parse_vendor_battery(data)


def test_current_sport_activity_summary_uses_little_endian_fields():
    data = (
        bytes((0x03,))
        + (1_700_000_000).to_bytes(4, "little")
        + (12_345).to_bytes(4, "little")
        + (6_789).to_bytes(4, "little")
        + (321).to_bytes(4, "little")
        + (0x030201).to_bytes(3, "little")
    )

    result = parse_vendor_current_sport(data)

    assert result.variant == "activity_summary"
    assert result.device_epoch_seconds == 1_700_000_000
    assert result.steps == 12_345
    assert result.distance == 6_789
    assert result.calories == 321
    assert result.unknown_value == 0x030201


def test_current_sport_secondary_variant_preserves_neutral_field_names():
    data = (
        bytes((0x13,))
        + (100).to_bytes(4, "little")
        + (200).to_bytes(4, "little")
        + (300).to_bytes(4, "little")
        + (400).to_bytes(4, "little")
        + bytes(3)
    )

    result = parse_vendor_current_sport(data)

    assert result.variant == "secondary_summary"
    assert (result.primary, result.secondary, result.tertiary) == (200, 300, 400)
    assert result.steps is None


@pytest.mark.parametrize("opcode", [0x83, 0x04, 0x14])
def test_current_sport_rejects_failure_and_unrelated_opcodes(opcode):
    with pytest.raises(ProtocolError):
        parse_vendor_current_sport(bytes((opcode,)) + bytes(19))


def test_device_info_redacts_unique_identifier_and_verifies_seeded_crc32():
    body = bytes(range(1, 16))
    data = bytes((0x0C,)) + body + bytes.fromhex("47b17004")

    result = parse_vendor_device_info(data)

    assert result.device_type == 0x0201
    assert result.hardware_revision == 0x0A09
    assert result.software_revision == 0x0C0B
    assert result.integrity_valid is True
    assert result.identifier_redacted is True
    assert not hasattr(result, "identifier")
    assert not hasattr(result, "mac_address")
    assert "030405060708" not in repr(result)


def test_device_info_reports_bad_integrity_without_exposing_private_bytes():
    data = bytes((0x0C,)) + bytes(range(1, 16)) + bytes(4)

    result = parse_vendor_device_info(data)

    assert result.integrity_valid is False
    assert "030405060708" not in repr(result)


@pytest.mark.parametrize("data", [bytes(19), bytes((0x8C,)) + bytes(19)])
def test_device_info_rejects_wrong_length_and_failure_opcode(data):
    with pytest.raises(ProtocolError):
        parse_vendor_device_info(data)


def test_band_functions_expand_twelve_bytes_lsb_first():
    data = bytes((0x20, 0b10000001, 0b00000010)) + bytes(17)

    result = parse_vendor_band_functions(data)

    assert len(result.flags) == 96
    assert result.enabled(0) is True
    assert result.enabled(7) is True
    assert result.enabled(9) is True
    assert result.enabled(8) is False
    assert result.static_app_mapping(0) == "social_notifications"
    assert result.static_app_mapping(1) is None


@pytest.mark.parametrize("index", [-1, 96, True, 1.5])
def test_band_functions_reject_invalid_flag_indexes(index):
    result = parse_vendor_band_functions(bytes((0x20,)) + bytes(19))

    with pytest.raises((TypeError, ValueError)):
        result.enabled(index)


@pytest.mark.parametrize("data", [bytes(19), bytes((0xA0,)) + bytes(19)])
def test_band_functions_reject_wrong_length_and_failure_opcode(data):
    with pytest.raises(ProtocolError):
        parse_vendor_band_functions(data)


def test_multi_sport_day_decodes_six_packed_records():
    base = 1_700_000_000
    record_bytes = bytes(
        (
            0x31, 0x12,
            0x42, 0x23,
            0x53, 0x34,
            0x64, 0x45,
            0x75, 0x56,
            0x86, 0x67,
        )
    )
    packed_type_nibbles = bytes((0xA9, 0xB8, 0xC7))
    data = bytes((0x25,)) + base.to_bytes(4, "little") + record_bytes + packed_type_nibbles

    result = parse_vendor_multi_sport_day(data)

    assert result.device_epoch_seconds == base
    assert [sample.device_epoch_seconds for sample in result.samples] == [
        base + offset for offset in range(0, 360, 60)
    ]
    assert [sample.sport_type_code for sample in result.samples] == [
        0xA1, 0x92, 0xB3, 0x84, 0xC5, 0x76
    ]
    assert [sample.value for sample in result.samples] == [
        0x123, 0x234, 0x345, 0x456, 0x567, 0x678
    ]
    assert result.end_of_history is False


def test_oxygen_day_decodes_fifteen_one_minute_samples_without_guessing_end():
    base = 1_700_000_000
    values = bytes(range(80, 95))

    result = parse_vendor_oxygen_day(
        bytes((0x40,)) + base.to_bytes(4, "little") + values
    )

    assert result.device_epoch_seconds == base
    assert [sample.device_epoch_seconds for sample in result.samples] == [
        base + offset for offset in range(0, 900, 60)
    ]
    assert [sample.value for sample in result.samples] == list(range(80, 95))
    assert result.end_of_history is False


def test_advanced_sensor_day_preserves_three_neutral_five_byte_records():
    base = 1_700_000_000
    fields = bytes(range(1, 16))

    result = parse_vendor_advanced_sensor_day(
        bytes((0x55,)) + base.to_bytes(4, "little") + fields
    )

    assert result.device_epoch_seconds == base
    assert [sample.device_epoch_seconds for sample in result.samples] == [
        base,
        base + 900,
        base + 1800,
    ]
    assert result.samples[0].fields == (1, 2, 3, 4, 5)
    assert result.samples[2].fields == (11, 12, 13, 14, 15)
    assert result.end_of_history is False


@pytest.mark.parametrize(
    "parser,opcode",
    [
        (parse_vendor_multi_sport_day, 0xA5),
        (parse_vendor_oxygen_day, 0xC0),
        (parse_vendor_advanced_sensor_day, 0xD5),
    ],
)
def test_day_decoders_reject_failure_or_unrelated_opcodes(parser, opcode):
    with pytest.raises(ProtocolError):
        parser(bytes((opcode,)) + bytes(19))


def test_static_protocol_coverage_is_complete_and_cannot_claim_hardware_support():
    coverage = static_protocol_coverage()

    assert [entry.operation for entry in coverage] == list(StaticQuery)
    assert [entry.request_opcode for entry in coverage] == [
        0x03,
        0x0B,
        0x0C,
        0x20,
        0x25,
        0x40,
        0x55,
    ]
    assert coverage[0].success_opcodes == (0x03, 0x13)
    assert coverage[0].failure_opcodes == (0x83,)
    assert coverage[4].failure_opcodes == (0xA5,)
    assert coverage[5].failure_opcodes == ()
    assert all(entry.request_endpoint_uuid == VENDOR_CHARACTERISTIC_33F3 for entry in coverage)
    assert all(entry.response_endpoint_uuid == VENDOR_CHARACTERISTIC_33F4 for entry in coverage)
    assert all(entry.maturity == "static_apk_only" for entry in coverage)
    assert all(entry.hardware_eligible is False for entry in coverage)
