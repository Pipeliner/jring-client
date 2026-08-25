import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_settings import (
    BrightnessLevel,
    HourFormat,
    SensorSessionMode,
    StaticVendorSettingOperation,
    StaticVendorSettingRequest,
    VendorClockTime,
    WearMode,
    encode_device_code,
    encode_device_name,
    encode_device_settings,
    encode_heart_rate_area,
    encode_hour_format,
    encode_language,
    encode_sensor_session_start,
    encode_sensor_session_stop,
)


def _assert_static_request(request, operation, expected):
    assert request.operation is operation
    assert request.synthetic_bytes_for_test() == expected
    assert len(request.synthetic_bytes_for_test()) == 20
    assert request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert request.maturity == "static_apk_only"
    assert request.hardware_eligible is False


def test_device_settings_preserve_the_exact_profile_layout_and_inverted_calling_bit():
    request = encode_device_settings(
        enable_light=True,
        enable_vibrate=False,
        quiet_enabled=True,
        quiet_start=VendorClockTime(22, 15),
        quiet_end=VendorClockTime(7, 45),
        calling_enabled=True,
        short_video_enabled=True,
        wear_mode=WearMode.SIDE_1,
        brightness=BrightnessLevel.LEVEL_5,
    )

    _assert_static_request(
        request,
        StaticVendorSettingOperation.DEVICE_SETTINGS,
        bytes((0x1B, 1, 0, 0, 0, 1, 22, 15, 7, 45, 0, 1, 1, 100))
        + bytes(6),
    )
    assert "calling_bit_is_inverted" in request.corrected_sdk_quirks
    assert "invalid_brightness_fell_back_to_80" in request.corrected_sdk_quirks


def test_device_settings_false_calling_uses_one_on_the_wire():
    request = encode_device_settings(
        enable_light=False,
        enable_vibrate=True,
        quiet_enabled=False,
        quiet_start=VendorClockTime(0, 0),
        quiet_end=VendorClockTime(23, 59),
        calling_enabled=False,
        short_video_enabled=False,
        wear_mode=WearMode.SIDE_0,
        brightness=BrightnessLevel.LEVEL_1,
    )

    assert request.synthetic_bytes_for_test()[1:14] == bytes(
        (0, 1, 0, 0, 0, 0, 0, 23, 59, 1, 0, 0, 20)
    )


@pytest.mark.parametrize(
    "args",
    [
        (-1, 0),
        (24, 0),
        (0, -1),
        (0, 60),
        (True, 0),
        (0, False),
    ],
)
def test_clock_time_is_strict_and_bounded(args):
    with pytest.raises((TypeError, ValueError)):
        VendorClockTime(*args)


@pytest.mark.parametrize("field", ["enable_light", "calling_enabled", "short_video_enabled"])
def test_device_setting_flags_require_real_booleans(field):
    values = dict(
        enable_light=False,
        enable_vibrate=False,
        quiet_enabled=False,
        quiet_start=VendorClockTime(0, 0),
        quiet_end=VendorClockTime(0, 0),
        calling_enabled=False,
        short_video_enabled=False,
        wear_mode=WearMode.SIDE_0,
        brightness=BrightnessLevel.LEVEL_1,
    )
    values[field] = 1

    with pytest.raises(TypeError):
        encode_device_settings(**values)


def test_device_setting_enums_cannot_be_replaced_by_raw_integers():
    common = dict(
        enable_light=False,
        enable_vibrate=False,
        quiet_enabled=False,
        quiet_start=VendorClockTime(0, 0),
        quiet_end=VendorClockTime(0, 0),
        calling_enabled=False,
        short_video_enabled=False,
    )
    with pytest.raises(TypeError):
        encode_device_settings(**common, wear_mode=0, brightness=BrightnessLevel.LEVEL_1)
    with pytest.raises(TypeError):
        encode_device_settings(**common, wear_mode=WearMode.SIDE_0, brightness=1)


@pytest.mark.parametrize(
    "setting,wire",
    [(HourFormat.TWENTY_FOUR, 0), (HourFormat.TWELVE, 1)],
)
def test_hour_format_is_a_closed_enum(setting, wire):
    request = encode_hour_format(setting)
    _assert_static_request(
        request,
        StaticVendorSettingOperation.HOUR_FORMAT,
        bytes((0x1D, wire)) + bytes(18),
    )


def test_hour_format_rejects_untyped_sdk_integer():
    with pytest.raises(TypeError):
        encode_hour_format(1)


def test_device_code_is_private_bounded_and_not_in_repr():
    private_code = bytes(range(1, 20))
    request = encode_device_code(private_code)

    _assert_static_request(
        request,
        StaticVendorSettingOperation.DEVICE_CODE,
        bytes((0x1E,)) + private_code,
    )
    assert private_code.hex() not in repr(request)
    assert "sdk_silently_truncated_after_19_bytes" in request.corrected_sdk_quirks


@pytest.mark.parametrize("code", [b"", bytes(20), bytearray(b"abc"), "abc", None])
def test_device_code_rejects_empty_oversized_or_non_bytes(code):
    with pytest.raises((TypeError, ValueError)):
        encode_device_code(code)


def test_language_is_explicit_canonical_and_deterministic_utf8():
    request = encode_language("pt-BR")

    _assert_static_request(
        request,
        StaticVendorSettingOperation.LANGUAGE,
        bytes((0x21,)) + b"pt-BR" + bytes(14),
    )
    assert "sdk_inferred_and_logged_host_locale" in request.corrected_sdk_quirks
    assert "sdk_overlength_branch_copied_only_18_bytes" in request.corrected_sdk_quirks


@pytest.mark.parametrize(
    "tag", ["PT-br", "en", "en-us", "zh-Hant", "english-US", "en-US\x00", b"en-US"]
)
def test_language_rejects_noncanonical_or_ambiguous_tags(tag):
    with pytest.raises((TypeError, ValueError)):
        encode_language(tag)


@pytest.mark.parametrize(
    "mode,wire",
    [
        (SensorSessionMode.MODE_1, 1),
        (SensorSessionMode.MODE_2, 2),
        (SensorSessionMode.MODE_3, 3),
        (SensorSessionMode.MODE_4, 4),
    ],
)
def test_shared_sensor_session_uses_neutral_typed_mode(mode, wire):
    request = encode_sensor_session_start(mode)
    _assert_static_request(
        request,
        StaticVendorSettingOperation.SENSOR_SESSION_START,
        bytes((0x23, wire)) + bytes(18),
    )
    assert "sdk_callbacks_named_every_mode_as_blood_pressure" in request.corrected_sdk_quirks


def test_shared_sensor_stop_has_no_false_per_mode_identity():
    request = encode_sensor_session_stop()
    _assert_static_request(
        request,
        StaticVendorSettingOperation.SENSOR_SESSION_STOP,
        bytes((0x23, 0)) + bytes(18),
    )
    assert "all_sdk_stop_wrappers_collapsed_to_mode_zero" in request.corrected_sdk_quirks
    assert request.queue_priority_observed_in_sdk is True
    assert request.response_success_opcode == 0x23
    assert request.response_failure_opcode == 0xA3


def test_sensor_start_rejects_integer_or_boolean_mode():
    with pytest.raises(TypeError):
        encode_sensor_session_start(1)
    with pytest.raises(TypeError):
        encode_sensor_session_start(True)


def test_heart_rate_area_preserves_neutral_one_byte_fields():
    request = encode_heart_rate_area(True, first_value=60, second_value=180)
    _assert_static_request(
        request,
        StaticVendorSettingOperation.HEART_RATE_AREA,
        bytes((0x26, 1, 60, 180)) + bytes(16),
    )
    assert "sdk_did_not_validate_or_name_field_order" in request.corrected_sdk_quirks


@pytest.mark.parametrize(
    "enabled,first,second",
    [(1, 0, 0), (True, -1, 0), (True, 256, 0), (True, 0, True), (True, 0, 1.5)],
)
def test_heart_rate_area_rejects_truncation_and_non_boolean_flags(enabled, first, second):
    with pytest.raises((TypeError, ValueError)):
        encode_heart_rate_area(enabled, first_value=first, second_value=second)


def test_device_name_uses_explicit_utf8_without_truncating_a_code_point():
    request = encode_device_name("Ríng")
    encoded = "Ríng".encode("utf-8")
    _assert_static_request(
        request,
        StaticVendorSettingOperation.DEVICE_NAME,
        bytes((0x30,)) + encoded + bytes(19 - len(encoded)),
    )
    assert "Ríng" not in repr(request)
    assert (
        "sdk_used_implicit_charset_and_silently_truncated_to_11_bytes"
        in request.corrected_sdk_quirks
    )
    assert request.queue_priority_observed_in_sdk is False
    assert request.response_success_opcode == 0x30
    assert request.response_failure_opcode is None


@pytest.mark.parametrize(
    "name",
    ["", "abcdefghijkl", "ring\n", "e\u0301", b"ring", None],
)
def test_device_name_rejects_empty_oversized_control_non_nfc_or_non_text(name):
    with pytest.raises((TypeError, ValueError)):
        encode_device_name(name)


def test_request_bytes_and_sensitive_inputs_are_structurally_hidden():
    request = encode_device_code(b"private-code")

    assert "private" not in repr(request).lower()
    assert "1e70" not in repr(request).lower()
    assert "_encoded" not in repr(request)


def test_request_cannot_be_directly_constructed_or_promoted_to_hardware():
    with pytest.raises(TypeError):
        StaticVendorSettingRequest(
            StaticVendorSettingOperation.HOUR_FORMAT,
            bytes(20),
            (),
        )
    request = encode_hour_format(HourFormat.TWENTY_FOUR)
    with pytest.raises((AttributeError, TypeError)):
        request.hardware_eligible = True
