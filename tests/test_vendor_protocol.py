import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4
from jring.vendor_protocol import (
    StaticQuery,
    StaticAckOperation,
    StaticValueEvent,
    Static54ValueEvent,
    Static45Notification,
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
    parse_vendor_54_value_event,
    parse_vendor_binding_info,
    parse_vendor_chat_action,
    parse_vendor_device_code,
    parse_vendor_device_dial,
    parse_vendor_device_file_state,
    parse_vendor_device_test_event,
    parse_vendor_eq_info,
    parse_vendor_factory_test_data,
    parse_vendor_offline_speech_mode,
    parse_vendor_45_notification,
    parse_vendor_contact_crc,
    parse_vendor_e_card_need_update,
    parse_vendor_sms_need_update,
    parse_vendor_sms_send,
    parse_vendor_wifi_ssid_count,
    parse_vendor_wifi_state,
    VendorWifiSsidAssembler,
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
    assert response.app_requests_full_notification is False
    assert response.app_requests_low_notification is False
    assert response.app_projection_scope == "reviewed_app_condition_not_wire_semantics"


@pytest.mark.parametrize(
    "percent,state,full,low",
    [
        (100, 1, True, False),
        (99, 1, False, False),
        (10, 0, False, True),
        (0, 0, False, True),
        (11, 0, False, False),
        (100, 0, False, False),
    ],
)
def test_vendor_battery_exposes_exact_app_notification_conditions_only(
    percent, state, full, low
):
    result = parse_vendor_battery(bytes((0x0B, percent, state)) + bytes(17))

    assert result.app_requests_full_notification is full
    assert result.app_requests_low_notification is low
    assert result.state_meaning == "unknown"


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


@pytest.mark.parametrize(
    "parser,data",
    [
        (parse_vendor_current_sport, bytes((0x03,)) + bytes.fromhex("00000080") + bytes(15)),
        (parse_vendor_current_sport, bytes((0x03,)) + bytes(4) + bytes.fromhex("00000080") + bytes(11)),
        (parse_vendor_multi_sport_day, bytes((0x25,)) + bytes.fromhex("00000080") + bytes(15)),
        (parse_vendor_oxygen_day, bytes((0x40,)) + bytes.fromhex("00000080") + bytes(15)),
        (parse_vendor_advanced_sensor_day, bytes((0x55,)) + bytes.fromhex("00000080") + bytes(15)),
        (parse_vendor_step_counter, bytes((0x51,)) + bytes.fromhex("00000080") + bytes(15)),
        (parse_vendor_read_current_sport, bytes((0x29, 0)) + bytes.fromhex("00000080") + bytes(14)),
        (parse_vendor_worship_times, bytes((0x78, 0x08)) + bytes.fromhex("00000080") + bytes(14)),
        (parse_vendor_sensor_measurement, bytes((0x14,)) + bytes.fromhex("00000080") + bytes(15)),
    ],
)
def test_sdk_integer_parse_fields_reject_values_above_signed_ceiling(parser, data):
    with pytest.raises(ProtocolError, match="APK signed range"):
        parser(data)


def test_sdk_integer_parse_ceiling_is_inclusive_but_ecg_long_path_stays_unsigned():
    maximum = (0x7FFFFFFF).to_bytes(4, "little")
    sport = parse_vendor_current_sport(bytes((0x03,)) + maximum * 4 + bytes(3))
    ecg = parse_vendor_ecg_history_info(
        bytes((0x2C,)) + bytes.fromhex("ffffffff") + bytes(15)
    )

    assert sport.device_epoch_seconds == 0x7FFFFFFF
    assert sport.steps == 0x7FFFFFFF
    assert ecg.device_epoch_seconds == 0xFFFFFFFF


def test_device_info_redacts_unique_identifier_and_verifies_seeded_crc32():
    body = bytes(range(1, 16))
    data = bytes((0x0C,)) + body + bytes.fromhex("47b17004")

    result = parse_vendor_device_info(data)

    assert result.device_type == 0x0201
    assert result.hardware_revision_hex == "0A09"
    assert result.software_revision_hex == "0C0B"
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


def test_band_function_app_projection_covers_every_reviewed_direct_index():
    result = parse_vendor_band_functions(bytes((0x20,)) + bytes(19))
    expected = {
        0: "social_notifications", 2: "weather", 3: "time", 4: "anti_lost",
        5: "blood_pressure", 6: "heart_rate", 9: "ecg", 10: "temperature",
        18: "automatic_interval", 19: "notifications", 20: "reminders",
        21: "ecg_xt", 22: "blood_pressure_adjustment", 24: "sport",
        25: "dial", 26: "wallpaper", 28: "blood_pressure_only",
        29: "blood_oxygen", 30: "blood_pressure_and_oxygen",
        31: "custom_dial", 32: "female_reminder", 34: "classic_bluetooth",
        35: "vibration", 41: "distance_algorithm_v2", 42: "custom_alarm",
        43: "distance_algorithm_v3", 44: "sms_auto_response",
        45: "electronic_card", 47: "extended_notifications", 48: "chat_assistant",
        49: "hide_call", 50: "hide_sms", 51: "hide_notifications",
        52: "hide_alarm", 53: "hide_sedentary", 54: "hide_find_device",
        55: "hide_quiet_mode", 56: "sport_from_app",
        57: "hide_more_settings", 59: "battery_low_full_indicator",
        60: "battery_data", 61: "sport_step", 62: "measurement",
        63: "short_video", 65: "blood_pressure_oxygen_separate_mode",
        68: "wifi", 69: "wear_mode", 70: "brightness", 78: "connect_watch",
        79: "connect_bracelet", 80: "automatic_screen_wake",
        81: "offline_oxygen", 82: "ai_transfer", 83: "advanced_sensor_offline",
        84: "blood_sugar", 85: "device_serial", 86: "hrv",
    }

    assert len(expected) == 57
    assert result.static_app_direct_projections == tuple(expected.items())
    assert {
        index: result.static_app_mapping(index) for index in range(96)
        if result.static_app_mapping(index) is not None
    } == expected


def test_band_function_composites_preserve_surprising_reviewed_app_predicates():
    enabled = bytearray(20)
    enabled[0] = 0x20
    for index in (20, 30, 33, 34, 40):
        enabled[1 + (index // 8)] |= 1 << (index % 8)

    result = parse_vendor_band_functions(bytes(enabled))

    assert result.static_app_composite_projections == (
        ("nateon_notifications", (30, 20), True),
        ("viber_telegram_notifications", (20, 33), True),
        ("multiple_contacts", (34, 40), True),
    )
    assert result.static_app_mapping(33) is None
    assert result.static_app_mapping(40) is None
    assert result.app_projection_scope == "reviewed_app_behavior_not_firmware_semantics"


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
    assert result.generic_sensor_mode_success is True
    assert result.callback_projection_order == (
        "generic_sensor_mode_success",
        "multi_sport_sample",
        "multi_sport_sample",
        "multi_sport_sample",
        "multi_sport_sample",
        "multi_sport_sample",
        "multi_sport_sample",
    )
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
    assert [
        (row.opcode, row.predicate, row.direct_callback)
        for row in coverage[0].failure_dispatches
    ] == [(0x83, "always", False)]
    assert [
        (row.opcode, row.predicate, row.direct_callback)
        for row in coverage[1].failure_dispatches
    ] == [(0x8B, "always", False)]
    assert [
        (row.opcode, row.predicate, row.direct_callback)
        for row in coverage[2].failure_dispatches
    ] == [(0x8C, "always", False)]
    assert [
        (row.opcode, row.predicate, row.direct_callback)
        for row in coverage[4].failure_dispatches
    ] == [
        (0xA5, "byte_1_equals_ff", True),
        (0xA5, "byte_1_not_ff", False),
    ]
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
    assert result.app_snooze_repeat_state is True
    assert result.app_snooze_state is False
    assert result.app_alarm_enabled_state is True
    assert result.app_projection_scope == "reviewed_app_storage_not_wire_semantics"


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


def test_motion_frame_requires_an_explicit_unknown_subcommand_and_decodes_nine_i16():
    channels = (-32768, -2, -1, 0, 1, 2, 300, 32767, -12345)
    encoded = b"".join(value.to_bytes(2, "little", signed=True) for value in channels)
    data = bytes((0x78, 0x22)) + encoded

    result = parse_vendor_motion_frame(data, expected_subcommand=0x22)

    assert result.subcommand == 0x22
    assert result.channels == channels
    assert result.channel_meaning == "unknown"
    assert result.trailing_bytes_ignored_by_sdk is False
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


def test_multi_sport_frame_also_reports_generic_sensor_mode_success():
    result = parse_vendor_ack(
        bytes((0x25,)) + bytes(19),
        StaticAckOperation.GENERIC_SENSOR_MODE,
    )

    assert result.success is True
    assert result.operation is StaticAckOperation.GENERIC_SENSOR_MODE


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
    "opcode,success,requested_active,active",
    [
        (0x14, True, True, True),
        (0x15, True, False, False),
        (0x94, False, True, None),
        (0x95, False, False, None),
    ],
)
def test_sensor_measurement_state_distinguishes_open_close_and_failure(
    opcode, success, requested_active, active
):
    data = (
        bytes((opcode,))
        + (123).to_bytes(4, "little")
        + bytes((7, 8))
        + bytes(13)
    )

    result = parse_vendor_sensor_measurement(data)

    assert result.success is success
    assert result.requested_active is requested_active
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


def test_ecg_result_representations_redact_samples_fields_and_timestamps():
    values = parse_vendor_ecg_values(
        bytes((0x2E, 9)) + bytes((0x23, 0x61, 0x45)) * 6,
        kind="history",
    )
    history = parse_vendor_ecg_history_info(
        bytes((0x2C,)) + (123_456_789).to_bytes(4, "little") + bytes((77,)) + bytes(14)
    )
    start_end = parse_vendor_ecg_start_end(
        bytes((0x2D, 91, 92)) + (987_654_321).to_bytes(4, "little") + bytes(13)
    )

    assert "291" not in repr(values)
    assert "1110" not in repr(values)
    assert "123456789" not in repr(history)
    assert "77" not in repr(history)
    assert "987654321" not in repr(start_end)
    assert "91" not in repr(start_end)
    assert "92" not in repr(start_end)
    assert "sample_count=12" in repr(values)
    assert "<redacted>" in repr(history)
    assert "<redacted>" in repr(start_end)


def test_device_test_and_chat_action_events_are_strictly_distinct():
    device_test = parse_vendor_device_test_event(bytes((0x3A,)) + bytes(19))
    chat = parse_vendor_chat_action(bytes((0x4E, 7)) + bytes(18))

    assert device_test.kind == "device_test_command"
    assert device_test.hardware_verified is False
    assert chat.value == 7
    with pytest.raises(ProtocolError):
        parse_vendor_device_test_event(bytes((0x4E,)) + bytes(19))


def test_device_code_discards_all_identifier_bytes():
    result = parse_vendor_device_code(bytes((0x1F,)) + bytes(range(1, 20)))

    assert result.identifier_redacted is True
    assert result.success is True
    assert result.consumed_identifier_bytes == 18
    assert result.trailing_byte_ignored_by_sdk is True
    assert not hasattr(result, "identifier")
    assert "0102030405" not in repr(result)

    failure = parse_vendor_device_code(bytes((0x9F,)) + bytes(19))
    assert failure.success is False
    assert failure.consumed_identifier_bytes == 0


def test_device_dial_decodes_every_field_in_the_twenty_byte_layout():
    data = (
        bytes((0x34,))
        + (1).to_bytes(2, "little")
        + (0xABCD).to_bytes(2, "little")
        + (240).to_bytes(2, "little")
        + (280).to_bytes(2, "little")
        + (16).to_bytes(2, "little")
        + bytes((3, 1))
        + (9).to_bytes(2, "little")
        + (120).to_bytes(2, "little")
        + (140).to_bytes(2, "little")
        + bytes((4,))
    )

    result = parse_vendor_device_dial(data)

    assert result.code_hex == ("0001", "ABCD")
    assert result.codes == (1, 0xABCD)
    assert result.dimensions == (240, 280)
    assert result.unit_width == 16
    assert (result.color_mode, result.custom_flag, result.dial_id) == (3, 1, 9)
    assert result.preview_dimensions == (120, 140)
    assert result.shape_code == 4


def test_device_file_state_decodes_54_06_u32_only():
    result = parse_vendor_device_file_state(
        bytes((0x54, 0x06)) + (123_456).to_bytes(4, "little") + bytes(14)
    )

    assert result.value == 123_456
    with pytest.raises(ProtocolError):
        parse_vendor_device_file_state(bytes((0x54, 0x05)) + bytes(18))
    with pytest.raises(ProtocolError):
        parse_vendor_device_file_state(
            bytes((0x54, 0x06)) + (0x80000000).to_bytes(4, "little") + bytes(14)
        )


@pytest.mark.parametrize("kind,selector", [("set", 0), ("get", 1)])
def test_eq_info_decodes_signed_values_and_requires_expected_kind(kind, selector):
    signed = (-2, -1, 0, 1, 2)
    encoded = bytes(value & 0xFF for value in signed)
    data = bytes((0x53, selector, 7, 8, len(signed))) + encoded + bytes(10)

    result = parse_vendor_eq_info(data, expected_kind=kind)

    assert result.kind == kind
    assert result.metadata == (7, 8)
    assert result.values == signed
    with pytest.raises(ProtocolError):
        parse_vendor_eq_info(data, expected_kind="get" if kind == "set" else "set")


def test_eq_info_preserves_fifteen_wire_values_despite_apk_callback_bug():
    values = tuple(range(-7, 8))
    result = parse_vendor_eq_info(
        bytes((0x53, 1, 0, 0, 15))
        + bytes(value & 0xFF for value in values),
        expected_kind="get",
    )

    assert result.values == values
    assert result.apk_callback_drops_last_value is True


def test_eq_info_rejects_count_beyond_wire_capacity():
    with pytest.raises(ProtocolError):
        parse_vendor_eq_info(
            bytes((0x53, 1, 0, 0, 16)) + bytes(15),
            expected_kind="get",
        )


def test_factory_test_bytes_are_hidden_and_byte_19_is_not_claimed():
    result = parse_vendor_factory_test_data(bytes((0x50,)) + bytes(range(1, 20)))

    assert result.consumed_bytes == 19
    assert result.trailing_byte_ignored_by_sdk is True
    assert result.synthetic_bytes_for_explicit_local_use() == bytes((0x50,)) + bytes(range(1, 19))
    assert "0102030405" not in repr(result)


@pytest.mark.parametrize("subcommand", [0x03, 0x0C])
def test_offline_speech_mode_accepts_only_two_static_subcommands(subcommand):
    result = parse_vendor_offline_speech_mode(
        bytes((0x78, subcommand, 4)) + bytes(17)
    )

    assert result.subcommand == subcommand
    assert result.value == 4


@pytest.mark.parametrize(
    "event,subcommand",
    [
        (Static54ValueEvent.DEVICE_SYSTEM_STATE, 0x12),
        (Static54ValueEvent.WIFI_AP_STATE, 0x13),
        (Static54ValueEvent.AI_CONNECTION_METHOD, 0x14),
    ],
)
def test_54_value_events_are_subcommand_specific(event, subcommand):
    result = parse_vendor_54_value_event(
        bytes((0x54, subcommand, 9)) + bytes(17), event
    )

    assert result.event is event
    assert result.value == 9


def test_binding_info_preserves_neutral_fields_without_claiming_owner_state():
    result = parse_vendor_binding_info(bytes((0x4B, 2, 3)) + bytes(17))

    assert result.values == (2, 3)
    assert result.meaning == "unknown"
    assert result.hardware_verified is False


@pytest.mark.parametrize(
    "kind,selector",
    [
        (Static45Notification.CLASSIC_NAME, 1),
        (Static45Notification.APP_ID, 2),
    ],
)
def test_45_text_notifications_discard_sensitive_text_and_byte_19(kind, selector):
    result = parse_vendor_45_notification(
        bytes((0x45, selector)) + bytes(range(2, 20)), expected_kind=kind
    )

    assert result.kind is kind
    assert result.content_redacted is True
    assert result.consumed_content_bytes == 17
    assert result.trailing_byte_ignored_by_sdk is True
    assert not hasattr(result, "content")


def test_classic_bt_info_preserves_only_two_non_identifier_values():
    result = parse_vendor_45_notification(
        bytes((0x45, 0, 7, 8)) + bytes(range(4, 20)),
        expected_kind=Static45Notification.CLASSIC_INFO,
    )

    assert result.values == (7, 8)
    assert result.identifiers_redacted is True
    assert not hasattr(result, "first_identifier")


def test_contact_and_update_fingerprints_are_redacted():
    contact = parse_vendor_contact_crc(bytes((0x46,)) + bytes(range(1, 20)))
    e_card = parse_vendor_e_card_need_update(
        bytes((0x4C, 3)) + bytes(range(2, 20))
    )
    sms = parse_vendor_sms_need_update(bytes((0x4D, 3)) + bytes(range(2, 20)))

    assert contact.content_redacted is True
    assert contact.consumed_content_bytes == 4
    assert e_card.consumed_content_bytes == 17
    assert sms.consumed_content_bytes == 17
    assert e_card.callback_zero_fills_last_byte is True
    assert "02030405" not in repr(e_card)


def test_sms_send_discards_text_and_reports_apk_off_by_one_projection():
    result = parse_vendor_sms_send(
        bytes((0x4D, 6, 9, 3)) + b"ABCD" + bytes(12)
    )

    assert result.value == 9
    assert result.declared_text_length == 3
    assert result.apk_consumed_text_bytes == 4
    assert result.text_redacted is True
    assert not hasattr(result, "text")

    with pytest.raises(ProtocolError):
        parse_vendor_sms_send(bytes((0x4D, 6, 9, 16)) + bytes(16))


def test_wifi_state_discards_address_material_and_never_starts_networking():
    result = parse_vendor_wifi_state(
        bytes((0x54, 4, 2, 192, 168, 1, 1)) + bytes(13)
    )

    assert result.state_code == 2
    assert result.address_redacted is True
    assert result.host_network_action == "not_performed"
    assert not hasattr(result, "address")


def test_wifi_ssid_count_is_a_single_bounded_value():
    assert parse_vendor_wifi_ssid_count(
        bytes((0x54, 9, 6)) + bytes(17)
    ).count == 6


def test_wifi_ssid_assembler_hides_fragments_and_returns_only_on_end():
    assembler = VendorWifiSsidAssembler(max_encoded_bytes=32)
    first = bytes((0x54, 0x0A, 0x01, 0xD8)) + b"Private" + bytes(9)
    final = bytes((0x54, 0x0A, 0xC1, 0xD8)) + b"%20Net" + bytes(10)

    assert assembler.feed(first) is None
    result = assembler.feed(final)

    assert result is not None
    assert result.end_flag is True
    assert result.part_id == 1
    assert result.current_id == 1
    assert result.signal == -40
    assert result.ssid_for_explicit_local_use() == "Private%20Net"
    assert "Private" not in repr(result)


def test_wifi_ssid_assembler_is_bounded_and_resettable():
    assembler = VendorWifiSsidAssembler(max_encoded_bytes=3)
    frame = bytes((0x54, 0x0A, 0x80, 0)) + b"four" + bytes(12)

    with pytest.raises(ProtocolError):
        assembler.feed(frame)
    assembler.reset()
    assert assembler.buffered_bytes == 0


def test_wifi_ssid_continuation_requires_matching_started_entry():
    assembler = VendorWifiSsidAssembler()
    continuation = bytes((0x54, 0x0A, 0xC2, 0)) + b"private" + bytes(9)

    with pytest.raises(ProtocolError):
        assembler.feed(continuation)
    assert assembler.buffered_bytes == 0
