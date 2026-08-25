import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4
from jring.vendor_protocol import (
    StaticQuery,
    StaticAckOperation,
    StaticValueEvent,
    StaticVendorRequest,
    encode_day_query,
    encode_static_query,
    parse_vendor_advanced_sensor_day,
    parse_vendor_battery,
    parse_vendor_band_functions,
    parse_vendor_current_sport,
    parse_vendor_device_info,
    parse_vendor_device_action,
    parse_vendor_device_dial_custom,
    parse_vendor_device_state,
    parse_vendor_motion_frame,
    parse_vendor_multi_sport_day,
    parse_vendor_oxygen_day,
    parse_vendor_ack,
    parse_vendor_ecg_mode_ack,
    parse_vendor_notify_ack,
    parse_vendor_phone_volume_request,
    parse_vendor_read_current_sport,
    parse_vendor_screen_light_time,
    parse_vendor_step_counter,
    parse_vendor_touch_mode,
    parse_vendor_worship_info,
    parse_vendor_worship_times,
    parse_vendor_ecg_history_info,
    parse_vendor_ecg_start_end,
    parse_vendor_ecg_values,
    parse_vendor_sensor_measurement,
    parse_vendor_sensor_state_change,
    parse_vendor_sensor_values,
    parse_vendor_temperature_data,
    parse_vendor_value_event,
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


@pytest.mark.parametrize(
    "code,label,input_candidate,side_effect",
    [
        (2, "camera_shutter", True, "host_camera"),
        (4, "call_hangup", False, "phone_call"),
        (16, "media_play_pause", True, "host_media"),
        (32, "media_next", True, "host_media"),
        (64, "media_previous", True, "host_media"),
        (68, "volume_up", True, "host_audio"),
        (69, "volume_down", True, "host_audio"),
        (255, "unknown", False, "unknown"),
    ],
)
def test_device_action_decoder_classifies_input_candidates_and_side_effects(
    code, label, input_candidate, side_effect
):
    result = parse_vendor_device_action(bytes((0x06, code)) + bytes(18))

    assert result.code == code
    assert result.label == label
    assert result.input_candidate is input_candidate
    assert result.side_effect_class == side_effect
    assert result.hardware_verified is False


def test_weather_action_opcode_uses_its_static_action_without_payload_guessing():
    result = parse_vendor_device_action(bytes((0x22, 99)) + bytes(18))

    assert result.code == 5
    assert result.label == "weather_location_refresh"
    assert result.input_candidate is False


def test_step_counter_is_cumulative_and_not_a_verified_button_event():
    result = parse_vendor_step_counter(
        bytes((0x51,)) + (123_456).to_bytes(4, "little") + bytes(15)
    )

    assert result.cumulative_steps == 123_456
    assert result.event_semantics == "experimental_counter_only"
    assert result.hardware_verified is False
    assert result.input_eligible is False


@pytest.mark.parametrize(
    "parser,data",
    [
        (parse_vendor_device_action, bytes((0x86,)) + bytes(19)),
        (parse_vendor_device_action, bytes(19)),
        (parse_vendor_step_counter, bytes((0xD1,)) + bytes(19)),
        (parse_vendor_step_counter, bytes(21)),
    ],
)
def test_non_health_event_decoders_fail_closed(parser, data):
    with pytest.raises(ProtocolError):
        parser(data)


def test_device_state_decodes_only_the_three_statically_used_bits():
    result = parse_vendor_device_state(bytes((0x3D, 0b10000101)) + bytes(18))

    assert result.flag_0 is True
    assert result.flag_1 is False
    assert result.flag_2 is True
    assert result.unused_bits_present is True


def test_device_dial_custom_preserves_four_neutral_values():
    result = parse_vendor_device_dial_custom(bytes((0x42, 1, 2, 3, 4)) + bytes(15))

    assert result.values == (1, 2, 3, 4)
    assert result.hardware_verified is False


def test_read_current_sport_keeps_unverified_values_neutral():
    base = 1_700_000_000
    result = parse_vendor_read_current_sport(
        bytes((0x29, 7))
        + base.to_bytes(4, "little")
        + (123).to_bytes(4, "little")
        + (456).to_bytes(4, "little")
        + bytes(6)
    )

    assert result.discriminator == 7
    assert result.device_epoch_seconds == base
    assert result.first_value == 123
    assert result.second_value == 456


def test_phone_volume_request_is_an_event_not_volume_data():
    result = parse_vendor_phone_volume_request(bytes((0x49,)) + bytes(19))

    assert result.requests_host_volume_state is True
    assert result.input_candidate is False


@pytest.mark.parametrize(
    "parser,subcommand,value",
    [
        (parse_vendor_screen_light_time, 0x0B, 17),
        (parse_vendor_touch_mode, 0x09, 3),
    ],
)
def test_vendor_78_single_value_subcommands_require_exact_subcommand(
    parser, subcommand, value
):
    data = bytes((0x78, subcommand, value)) + bytes(17)

    assert parser(data).value == value
    with pytest.raises(ProtocolError):
        parser(bytes((0x78, subcommand ^ 1, value)) + bytes(17))


def test_worship_subcommands_decode_only_their_statically_used_fields():
    info = parse_vendor_worship_info(bytes((0x78, 0x07, 3, 4)) + bytes(16))
    times = parse_vendor_worship_times(
        bytes((0x78, 0x08)) + (123_456).to_bytes(4, "little") + bytes(14)
    )

    assert info.values == (3, 4)
    assert times.value == 123_456


def test_motion_frame_requires_an_explicit_unknown_subcommand_and_decodes_eight_i16():
    channels = (-32768, -2, -1, 0, 1, 2, 300, 32767)
    encoded = b"".join(value.to_bytes(2, "little", signed=True) for value in channels)
    data = bytes((0x78, 0x22)) + encoded + bytes((0xAA, 0xBB))

    result = parse_vendor_motion_frame(data, expected_subcommand=0x22)

    assert result.subcommand == 0x22
    assert result.channels == channels
    assert result.channel_meaning == "unknown"
    assert result.trailing_bytes_ignored_by_sdk is True
    assert result.hardware_verified is False


@pytest.mark.parametrize("subcommand", [0x03, 0x07, 0x08, 0x09, 0x0B, 0x0C])
def test_motion_frame_rejects_known_non_motion_subcommands(subcommand):
    data = bytes((0x78, subcommand)) + bytes(18)

    with pytest.raises(ProtocolError):
        parse_vendor_motion_frame(data, expected_subcommand=subcommand)


def test_motion_frame_rejects_subcommand_mismatch():
    with pytest.raises(ProtocolError):
        parse_vendor_motion_frame(
            bytes((0x78, 0x22)) + bytes(18),
            expected_subcommand=0x23,
        )


@pytest.mark.parametrize(
    "operation,success_opcode,failure_opcode",
    [
        (StaticAckOperation.DEVICE_TIME, 0x01, 0x81),
        (StaticAckOperation.USER_INFO, 0x02, 0x82),
        (StaticAckOperation.VIBRATION, 0x04, 0x84),
        (StaticAckOperation.ANTI_LOST, 0x05, 0x85),
        (StaticAckOperation.PHONE_MODE, 0x07, 0x87),
        (StaticAckOperation.IDLE_TIME, 0x08, 0x88),
        (StaticAckOperation.SLEEP_TIME, 0x09, 0x89),
        (StaticAckOperation.ALARM, 0x0D, 0x8D),
        (StaticAckOperation.DEVICE_MODE, 0x0E, 0x8E),
        (StaticAckOperation.AUTO_HEART, 0x19, 0x99),
        (StaticAckOperation.GOAL, 0x1A, 0x9A),
        (StaticAckOperation.DEVICE_INFO_SET, 0x1B, 0x9B),
        (StaticAckOperation.HOUR_FORMAT, 0x1D, 0x9D),
        (StaticAckOperation.DEVICE_CODE_SET, 0x1E, 0x9E),
        (StaticAckOperation.LANGUAGE, 0x21, 0xA1),
        (StaticAckOperation.GENERIC_SENSOR_MODE, 0x23, 0xA3),
        (StaticAckOperation.HEART_RATE_AREA, 0x26, 0xA6),
    ],
)
def test_vendor_ack_decodes_operation_specific_success_and_failure(
    operation, success_opcode, failure_opcode
):
    success = parse_vendor_ack(bytes((success_opcode,)) + bytes(19), operation)
    failure = parse_vendor_ack(bytes((failure_opcode,)) + bytes(19), operation)

    assert success.operation is operation
    assert success.success is True
    assert failure.operation is operation
    assert failure.success is False
    assert success.hardware_verified is False


@pytest.mark.parametrize(
    "operation,success_opcode",
    [
        (StaticAckOperation.DEVICE_NAME, 0x30),
        (StaticAckOperation.REMINDER, 0x31),
        (StaticAckOperation.REMINDER_TEXT, 0x32),
        (StaticAckOperation.BP_ADJUST, 0x33),
        (StaticAckOperation.DEVICE_DIAL_STATE, 0x35),
        (StaticAckOperation.WALLPAPER_STATE, 0x36),
        (StaticAckOperation.EDIT_DIAL_CUSTOM, 0x41),
        (StaticAckOperation.FEMALE_REMINDER, 0x44),
    ],
)
def test_vendor_success_only_ack_rejects_guessed_failure_branch(operation, success_opcode):
    assert parse_vendor_ack(
        bytes((success_opcode,)) + bytes(19), operation
    ).success is True
    with pytest.raises(ProtocolError):
        parse_vendor_ack(bytes((success_opcode | 0x80,)) + bytes(19), operation)


def test_vendor_ack_requires_the_expected_operation_not_just_any_known_opcode():
    with pytest.raises(ProtocolError):
        parse_vendor_ack(
            bytes((0x01,)) + bytes(19),
            StaticAckOperation.USER_INFO,
        )


def test_notify_ack_requires_the_outbound_marker_for_success():
    success = parse_vendor_notify_ack(
        bytes((0x12, 0, 7)) + bytes(17), expected_marker=7
    )
    failure = parse_vendor_notify_ack(
        bytes((0x92,)) + bytes(19), expected_marker=7
    )

    assert success.success is True
    assert failure.success is False
    with pytest.raises(ProtocolError):
        parse_vendor_notify_ack(
            bytes((0x12, 0, 8)) + bytes(17), expected_marker=7
        )


@pytest.mark.parametrize("marker", [-1, 256, True, 1.5])
def test_notify_ack_rejects_invalid_expected_marker(marker):
    with pytest.raises((TypeError, ValueError)):
        parse_vendor_notify_ack(bytes((0x12,)) + bytes(19), expected_marker=marker)


def test_ecg_mode_ack_keeps_response_mode_without_inventing_failure_opcode():
    result = parse_vendor_ecg_mode_ack(bytes((0x2A, 3)) + bytes(18))

    assert result.success is True
    assert result.response_mode == 3
    assert result.hardware_verified is False
    with pytest.raises(ProtocolError):
        parse_vendor_ecg_mode_ack(bytes((0x9A,)) + bytes(19))


@pytest.mark.parametrize(
    "opcode,success,active",
    [(0x14, True, True), (0x15, True, False), (0x94, False, True), (0x95, False, False)],
)
def test_sensor_measurement_state_distinguishes_open_close_and_failure(
    opcode, success, active
):
    data = (
        bytes((opcode,))
        + (123).to_bytes(4, "little")
        + bytes((7, 8))
        + bytes(13)
    )

    result = parse_vendor_sensor_measurement(data)

    assert result.success is success
    assert result.active is active
    if opcode == 0x14:
        assert (result.device_epoch_seconds, result.first_value, result.second_value) == (
            123, 7, 8
        )
    else:
        assert result.device_epoch_seconds == 0


def test_live_sensor_values_preserve_eight_neutral_bytes():
    result = parse_vendor_sensor_values(bytes((0x24,)) + bytes(range(1, 9)) + bytes(11))

    assert result.values == tuple(range(1, 9))
    assert result.meaning == "unknown"


@pytest.mark.parametrize("opcode,family", [(0x27, 1), (0x28, 2)])
def test_sensor_state_change_uses_static_family_without_guessing_sensor(opcode, family):
    result = parse_vendor_sensor_state_change(bytes((opcode,)) + bytes(19))

    assert result.family == family
    assert result.state_code == 0
    assert result.meaning == "unknown"


@pytest.mark.parametrize(
    "event,opcode",
    [
        (StaticValueEvent.TEMPERATURE_MODE, 0x37),
        (StaticValueEvent.TEMPERATURE_MODE_CHANGE, 0x3B),
        (StaticValueEvent.BLOOD_OXYGEN_MODE, 0x3E),
        (StaticValueEvent.SENSOR_OXYGEN_DATA, 0x3F),
    ],
)
def test_single_value_sensor_events_are_operation_specific(event, opcode):
    result = parse_vendor_value_event(bytes((opcode, 77)) + bytes(18), event)

    assert result.event is event
    assert result.value == 77
    assert result.hardware_verified is False


def test_temperature_data_decodes_two_little_endian_values():
    result = parse_vendor_temperature_data(
        bytes((0x38,))
        + (0x1234).to_bytes(2, "little")
        + (0x5678).to_bytes(2, "little")
        + bytes(15)
    )

    assert result.values == (0x1234, 0x5678)


@pytest.mark.parametrize("opcode,kind", [(0x2B, "live"), (0x2E, "history")])
def test_ecg_values_unpack_six_groups_into_twelve_unsigned_values(opcode, kind):
    groups = bytes((0x23, 0x61, 0x45)) * 6
    result = parse_vendor_ecg_values(bytes((opcode, 9)) + groups, kind=kind)

    assert result.discriminator == 9
    assert result.values == (0x123, 0x456) * 6
    assert result.kind == kind


def test_ecg_history_info_and_start_end_use_exact_little_endian_fields():
    history = parse_vendor_ecg_history_info(
        bytes((0x2C,)) + (123).to_bytes(4, "little") + bytes((7,)) + bytes(14)
    )
    start_end = parse_vendor_ecg_start_end(
        bytes((0x2D, 1, 2)) + (456).to_bytes(4, "little") + bytes(13)
    )

    assert (history.device_epoch_seconds, history.value) == (123, 7)
    assert (start_end.first_value, start_end.second_value) == (1, 2)
    assert start_end.device_epoch_seconds == 456
