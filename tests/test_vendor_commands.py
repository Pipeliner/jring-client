import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_commands import (
    StaticVendorCommandOperation,
    StaticVendorCommandRequest,
    WeatherSnapshot,
    encode_ai_chat_state,
    encode_ai_connection_method,
    encode_ai_language,
    encode_app_state,
    encode_binding_info,
    encode_blood_oxygen_mode,
    encode_device_time,
    encode_ecg_mode,
    encode_eq_info,
    encode_factory_test_mode,
    encode_g_sensor_indicator,
    encode_heart_rate_session_start,
    encode_heart_rate_session_stop,
    encode_offline_speech_recognition,
    encode_phone_call_state,
    encode_temperature_mode,
    encode_touch_mode,
    encode_weather,
)


def _assert_request(request, operation, expected, *, priority=False):
    assert request.operation is operation
    assert request.synthetic_bytes_for_test() == expected
    assert len(request.synthetic_bytes_for_test()) == 20
    assert request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert request.maturity == "static_apk_only"
    assert request.hardware_eligible is False
    assert request.hardware_verified is False
    assert request.queue_priority_observed_in_sdk is priority


def test_phone_call_state_preserves_four_neutral_bytes():
    request = encode_phone_call_state(
        first_value=1,
        second_value=2,
        third_value=3,
        fourth_value=4,
    )
    _assert_request(
        request,
        StaticVendorCommandOperation.PHONE_CALL_STATE,
        bytes((0x43, 1, 2, 3, 4)) + bytes(15),
    )
    assert request.privacy_class == "phone_state"


def test_weather_frame_preserves_signed_temperatures_and_little_endian_fields():
    snapshot = WeatherSnapshot(
        device_epoch_seconds=0x04030201,
        daytime_code=0x0605,
        evening_code=0x0807,
        lowest_temperature=-10,
        highest_temperature=35,
        air_quality_code=9,
        pm25=0x0B0A,
        uv_index=12,
        aqi=0x0E0D,
        current_temperature=-2,
    )
    request = encode_weather(record_index=3, snapshot=snapshot)
    _assert_request(
        request,
        StaticVendorCommandOperation.WEATHER,
        bytes(
            (
                0x22,
                3,
                1,
                2,
                3,
                4,
                5,
                6,
                7,
                8,
                246,
                35,
                9,
                10,
                11,
                12,
                13,
                14,
                254,
                0,
            )
        ),
    )
    assert "04030201" not in repr(snapshot)
    assert request.privacy_class == "environment"


@pytest.mark.parametrize(
    "field,value",
    [
        ("device_epoch_seconds", -1),
        ("device_epoch_seconds", 0x1_0000_0000),
        ("daytime_code", 0x10000),
        ("lowest_temperature", -129),
        ("highest_temperature", 128),
        ("air_quality_code", True),
        ("pm25", -1),
        ("uv_index", 256),
        ("aqi", 65536),
    ],
)
def test_weather_fields_are_strictly_bounded(field, value):
    values = dict(
        device_epoch_seconds=1,
        daytime_code=2,
        evening_code=3,
        lowest_temperature=-1,
        highest_temperature=1,
        air_quality_code=4,
        pm25=5,
        uv_index=6,
        aqi=7,
        current_temperature=0,
    )
    values[field] = value
    with pytest.raises((TypeError, ValueError)):
        WeatherSnapshot(**values)


def test_weather_requires_a_real_snapshot_and_bounded_index():
    snapshot = WeatherSnapshot(1, 2, 3, -1, 1, 4, 5, 6, 7, 0)
    for index in (-1, 256, True):
        with pytest.raises((TypeError, ValueError)):
            encode_weather(record_index=index, snapshot=snapshot)
    with pytest.raises(TypeError):
        encode_weather(record_index=0, snapshot=None)


def test_ai_language_is_opaque_explicit_utf8_and_never_uses_host_locale():
    request = encode_ai_language("zh-Hant")
    _assert_request(
        request,
        StaticVendorCommandOperation.AI_LANGUAGE,
        bytes((0x54, 0x10)) + b"zh-Hant" + bytes(11),
    )
    assert "sdk_used_implicit_charset_and_silent_truncation" in request.corrected_sdk_quirks
    assert "language_value_vocabulary_is_unknown" in request.corrected_sdk_quirks


@pytest.mark.parametrize("tag", ["", "en\n", "\x00", "x" * 19, "\ud800", b"en"])
def test_ai_language_rejects_unsafe_or_oversized_input(tag):
    with pytest.raises((TypeError, ValueError)):
        encode_ai_language(tag)


@pytest.mark.parametrize(
    "encoder,operation,prefix",
    [
        (encode_ai_chat_state, StaticVendorCommandOperation.AI_CHAT_STATE, (0x54, 0x0F)),
        (
            encode_blood_oxygen_mode,
            StaticVendorCommandOperation.BLOOD_OXYGEN_MODE,
            (0x3E,),
        ),
        (
            encode_offline_speech_recognition,
            StaticVendorCommandOperation.OFFLINE_SPEECH_RECOGNITION,
            (0x78, 0x03),
        ),
        (encode_temperature_mode, StaticVendorCommandOperation.TEMPERATURE_MODE, (0x37,)),
        (encode_factory_test_mode, StaticVendorCommandOperation.FACTORY_TEST_MODE, (0x50,)),
    ],
)
def test_boolean_mode_frames_are_exact(encoder, operation, prefix):
    for enabled in (False, True):
        expected = bytes(prefix + (int(enabled),))
        expected += bytes(20 - len(expected))
        request = encoder(enabled)
        _assert_request(
            request,
            operation,
            expected,
            priority=operation
            in {
                StaticVendorCommandOperation.AI_CHAT_STATE,
                StaticVendorCommandOperation.BLOOD_OXYGEN_MODE,
                StaticVendorCommandOperation.OFFLINE_SPEECH_RECOGNITION,
            },
        )


@pytest.mark.parametrize(
    "encoder",
    [
        encode_ai_chat_state,
        encode_blood_oxygen_mode,
        encode_offline_speech_recognition,
        encode_temperature_mode,
        encode_factory_test_mode,
        encode_g_sensor_indicator,
    ],
)
def test_boolean_commands_reject_integer_truthiness(encoder):
    with pytest.raises(TypeError):
        encoder(1)


def test_ai_connection_method_is_a_neutral_bounded_code():
    request = encode_ai_connection_method(7)
    _assert_request(
        request,
        StaticVendorCommandOperation.AI_CONNECTION_METHOD,
        bytes((0x54, 0x14, 7)) + bytes(17),
        priority=True,
    )


def test_app_state_uses_two_signed_little_endian_i32_values():
    request = encode_app_state(first_state=0x01020304, second_state=-1)
    _assert_request(
        request,
        StaticVendorCommandOperation.APP_STATE,
        bytes((0x52, 4, 3, 2, 1, 0xFF, 0xFF, 0xFF, 0xFF)) + bytes(11),
    )


@pytest.mark.parametrize("value", [-(2**31) - 1, 2**31, True, 1.5])
def test_app_state_rejects_values_outside_signed_i32(value):
    with pytest.raises((TypeError, ValueError)):
        encode_app_state(first_state=value, second_state=0)


def test_binding_info_preserves_three_neutral_bytes_but_is_identifier_sensitive():
    request = encode_binding_info(first_value=4, second_value=0, third_value=1)
    _assert_request(
        request,
        StaticVendorCommandOperation.BINDING_INFO,
        bytes((0x4B, 4, 0, 1)) + bytes(16),
    )
    assert request.privacy_class == "owner_binding"


def test_device_time_requires_explicit_local_epoch_and_whole_hour_raw_offset():
    request = encode_device_time(
        local_epoch_seconds=0x04030201,
        raw_utc_offset_hours=-5,
    )
    _assert_request(
        request,
        StaticVendorCommandOperation.DEVICE_TIME,
        bytes((0x01, 1, 2, 3, 4, 0xFB)) + bytes(14),
    )
    assert (
        "sdk_derived_timestamp_and_offset_from_current_host_time"
        in request.corrected_sdk_quirks
    )


@pytest.mark.parametrize(
    "epoch,offset",
    [(-1, 0), (0x1_0000_0000, 0), (0, -13), (0, 15), (True, 0), (0, 5.5)],
)
def test_device_time_rejects_wrapping_or_non_timezone_values(epoch, offset):
    with pytest.raises((TypeError, ValueError)):
        encode_device_time(local_epoch_seconds=epoch, raw_utc_offset_hours=offset)


@pytest.mark.parametrize("enabled", [False, True])
def test_ecg_mode_has_boolean_state_and_neutral_mode_byte(enabled):
    request = encode_ecg_mode(enabled, mode_code=3)
    _assert_request(
        request,
        StaticVendorCommandOperation.ECG_MODE,
        bytes((0x2A, int(enabled), 3)) + bytes(17),
    )


def test_eq_set_frame_keeps_ten_to_fifteen_signed_values():
    values = tuple(range(-7, 8))
    request = encode_eq_info(first_metadata=7, second_metadata=8, values=values)
    _assert_request(
        request,
        StaticVendorCommandOperation.EQ_INFO,
        bytes((0x53, 0, 7, 8, 15)) + bytes(value & 0xFF for value in values),
    )
    assert "sdk_only_copied_values_for_counts_10_through_15" in request.corrected_sdk_quirks


@pytest.mark.parametrize(
    "values",
    [
        tuple(range(9)),
        tuple(range(16)),
        tuple([-129] + [0] * 9),
        tuple([128] + [0] * 9),
        list(range(10)),
    ],
)
def test_eq_values_are_immutable_signed_bytes_with_valid_sdk_count(values):
    with pytest.raises((TypeError, ValueError)):
        encode_eq_info(first_metadata=0, second_metadata=0, values=values)


def test_g_sensor_indicator_uses_boolean_as_the_0x78_subcommand():
    off = encode_g_sensor_indicator(False)
    on = encode_g_sensor_indicator(True)
    _assert_request(
        off,
        StaticVendorCommandOperation.G_SENSOR_INDICATOR,
        bytes((0x78, 0)) + bytes(18),
        priority=True,
    )
    _assert_request(
        on,
        StaticVendorCommandOperation.G_SENSOR_INDICATOR,
        bytes((0x78, 1)) + bytes(18),
        priority=True,
    )
    assert "boolean_is_the_subcommand_not_a_payload_value" in on.corrected_sdk_quirks


def test_heart_rate_start_and_stop_are_distinct_opcodes():
    start = encode_heart_rate_session_start(reference_value=0x04030201, mode_code=5)
    stop = encode_heart_rate_session_stop(mode_code=5)
    _assert_request(
        start,
        StaticVendorCommandOperation.HEART_RATE_SESSION_START,
        bytes((0x14, 1, 2, 3, 4, 5)) + bytes(14),
        priority=True,
    )
    _assert_request(
        stop,
        StaticVendorCommandOperation.HEART_RATE_SESSION_STOP,
        bytes((0x15, 0, 0, 0, 0, 5)) + bytes(14),
        priority=True,
    )
    assert "sdk_stop_ignored_the_reference_value" in stop.corrected_sdk_quirks


def test_touch_mode_is_a_neutral_bounded_code():
    request = encode_touch_mode(9)
    _assert_request(
        request,
        StaticVendorCommandOperation.TOUCH_MODE,
        bytes((0x78, 0x09, 9)) + bytes(17),
        priority=True,
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda: encode_phone_call_state(
            first_value=-1,
            second_value=0,
            third_value=0,
            fourth_value=0,
        ),
        lambda: encode_ai_connection_method(256),
        lambda: encode_binding_info(first_value=0, second_value=True, third_value=0),
        lambda: encode_ecg_mode(True, mode_code=-1),
        lambda: encode_eq_info(first_metadata=256, second_metadata=0, values=tuple(range(10))),
        lambda: encode_heart_rate_session_start(reference_value=-1, mode_code=0),
        lambda: encode_heart_rate_session_stop(mode_code=256),
        lambda: encode_touch_mode(True),
    ],
)
def test_neutral_integer_fields_never_wrap_or_accept_booleans(call):
    with pytest.raises((TypeError, ValueError)):
        call()


def test_factory_mode_is_marked_high_risk_despite_offline_only_encoding():
    request = encode_factory_test_mode(True)
    assert request.risk_class == "factory_mutation"
    assert request.hardware_eligible is False


def test_request_repr_hides_frames_private_state_weather_and_time():
    requests = (
        encode_binding_info(first_value=4, second_value=0, third_value=1),
        encode_device_time(local_epoch_seconds=0x04030201, raw_utc_offset_hours=1),
        encode_phone_call_state(first_value=1, second_value=2, third_value=3, fourth_value=4),
    )
    joined = " ".join(repr(value).lower() for value in requests)
    assert "04030201" not in joined
    assert "4b040001" not in joined
    assert "_encoded" not in joined


def test_request_cannot_be_directly_constructed_or_promoted():
    with pytest.raises(TypeError):
        StaticVendorCommandRequest(
            StaticVendorCommandOperation.APP_STATE,
            bytes(20),
        )
    request = encode_app_state(first_state=0, second_state=0)
    with pytest.raises((AttributeError, TypeError)):
        request.hardware_eligible = True
