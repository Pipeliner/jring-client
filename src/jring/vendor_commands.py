"""Strict offline vectors for a statically recovered vendor command family.

This module has no transport integration.  Its immutable request objects describe
synthetic 20-byte vectors only; they do not establish firmware support, owner consent,
safe side effects, or hardware verification.  Host time, locale, weather acquisition,
phone state, and binding flows remain outside the codec boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .uuids import VENDOR_CHARACTERISTIC_33F3


class StaticVendorCommandOperation(str, Enum):
    PHONE_CALL_STATE = "phone_call_state"
    WEATHER = "weather"
    AI_LANGUAGE = "ai_language"
    AI_CHAT_STATE = "ai_chat_state"
    AI_CONNECTION_METHOD = "ai_connection_method"
    APP_STATE = "app_state"
    BINDING_INFO = "binding_info"
    BLOOD_OXYGEN_MODE = "blood_oxygen_mode"
    DEVICE_TIME = "device_time"
    ECG_MODE = "ecg_mode"
    EQ_INFO = "eq_info"
    G_SENSOR_INDICATOR = "g_sensor_indicator"
    HEART_RATE_SESSION_START = "heart_rate_session_start"
    HEART_RATE_SESSION_STOP = "heart_rate_session_stop"
    OFFLINE_SPEECH_RECOGNITION = "offline_speech_recognition"
    TEMPERATURE_MODE = "temperature_mode"
    TOUCH_MODE = "touch_mode"
    FACTORY_TEST_MODE = "factory_test_mode"


_PRIVACY_CLASSES = {
    StaticVendorCommandOperation.PHONE_CALL_STATE: "phone_state",
    StaticVendorCommandOperation.WEATHER: "environment",
    StaticVendorCommandOperation.AI_LANGUAGE: "locale",
    StaticVendorCommandOperation.AI_CHAT_STATE: "ai_setting",
    StaticVendorCommandOperation.AI_CONNECTION_METHOD: "ai_setting",
    StaticVendorCommandOperation.APP_STATE: "device_state",
    StaticVendorCommandOperation.BINDING_INFO: "owner_binding",
    StaticVendorCommandOperation.BLOOD_OXYGEN_MODE: "health_sensor",
    StaticVendorCommandOperation.DEVICE_TIME: "device_time",
    StaticVendorCommandOperation.ECG_MODE: "health_sensor",
    StaticVendorCommandOperation.EQ_INFO: "audio_profile",
    StaticVendorCommandOperation.G_SENSOR_INDICATOR: "motion_sensor",
    StaticVendorCommandOperation.HEART_RATE_SESSION_START: "health_sensor",
    StaticVendorCommandOperation.HEART_RATE_SESSION_STOP: "health_sensor",
    StaticVendorCommandOperation.OFFLINE_SPEECH_RECOGNITION: "speech_setting",
    StaticVendorCommandOperation.TEMPERATURE_MODE: "health_sensor",
    StaticVendorCommandOperation.TOUCH_MODE: "touch_setting",
    StaticVendorCommandOperation.FACTORY_TEST_MODE: "factory_state",
}

_PRIORITY_OPERATIONS = frozenset(
    {
        StaticVendorCommandOperation.AI_CHAT_STATE,
        StaticVendorCommandOperation.AI_CONNECTION_METHOD,
        StaticVendorCommandOperation.BLOOD_OXYGEN_MODE,
        StaticVendorCommandOperation.G_SENSOR_INDICATOR,
        StaticVendorCommandOperation.HEART_RATE_SESSION_START,
        StaticVendorCommandOperation.HEART_RATE_SESSION_STOP,
        StaticVendorCommandOperation.OFFLINE_SPEECH_RECOGNITION,
        StaticVendorCommandOperation.TOUCH_MODE,
    }
)


@dataclass(frozen=True, init=False, repr=False)
class StaticVendorCommandRequest:
    operation: StaticVendorCommandOperation
    corrected_sdk_quirks: tuple[str, ...]
    _encoded: bytes = field(repr=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor command requests must use a typed offline encoder")

    def __repr__(self) -> str:
        return (
            "StaticVendorCommandRequest("
            f"operation={self.operation.value!r}, maturity='static_apk_only')"
        )

    @classmethod
    def _from_parts(
        cls,
        operation: StaticVendorCommandOperation,
        encoded: bytes,
        quirks: tuple[str, ...],
    ) -> "StaticVendorCommandRequest":
        request = object.__new__(cls)
        object.__setattr__(request, "operation", operation)
        object.__setattr__(request, "corrected_sdk_quirks", quirks)
        object.__setattr__(request, "_encoded", encoded)
        return request

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F3

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def queue_priority_observed_in_sdk(self) -> bool:
        return self.operation in _PRIORITY_OPERATIONS

    @property
    def privacy_class(self) -> str:
        return _PRIVACY_CLASSES[self.operation]

    @property
    def risk_class(self) -> str:
        if self.operation is StaticVendorCommandOperation.FACTORY_TEST_MODE:
            return "factory_mutation"
        if self.operation in {
            StaticVendorCommandOperation.BLOOD_OXYGEN_MODE,
            StaticVendorCommandOperation.ECG_MODE,
            StaticVendorCommandOperation.HEART_RATE_SESSION_START,
            StaticVendorCommandOperation.HEART_RATE_SESSION_STOP,
            StaticVendorCommandOperation.TEMPERATURE_MODE,
        }:
            return "health_sensor_mutation"
        if self.operation is StaticVendorCommandOperation.BINDING_INFO:
            return "owner_binding_mutation"
        return "device_mutation"

    def synthetic_bytes_for_test(self) -> bytes:
        """Return the hidden synthetic bytes for offline verification only."""

        return bytes(self._encoded)


def _int(value: int, label: str, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def _u8(value: int, label: str) -> int:
    return _int(value, label, 0, 0xFF)


def _u16(value: int, label: str) -> int:
    return _int(value, label, 0, 0xFFFF)


def _u32(value: int, label: str) -> int:
    return _int(value, label, 0, 0xFFFFFFFF)


def _i8(value: int, label: str) -> int:
    return _int(value, label, -128, 127)


def _i32(value: int, label: str) -> int:
    return _int(value, label, -(2**31), 2**31 - 1)


def _bool(value: bool, label: str = "enabled") -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a boolean")
    return value


def _request(
    operation: StaticVendorCommandOperation,
    opcode: int,
    payload: bytes = b"",
    *,
    quirks: tuple[str, ...] = (),
) -> StaticVendorCommandRequest:
    if len(payload) > 19:
        raise ValueError("vendor command payload exceeds the fixed 20-byte frame")
    encoded = bytes((opcode,)) + bytes(payload) + bytes(19 - len(payload))
    return StaticVendorCommandRequest._from_parts(operation, encoded, quirks)


def encode_phone_call_state(
    *, first_value: int, second_value: int, third_value: int, fourth_value: int
) -> StaticVendorCommandRequest:
    values = (
        _u8(first_value, "first_value"),
        _u8(second_value, "second_value"),
        _u8(third_value, "third_value"),
        _u8(fourth_value, "fourth_value"),
    )
    return _request(
        StaticVendorCommandOperation.PHONE_CALL_STATE,
        0x43,
        bytes(values),
        quirks=("sdk_exposed_four_unvalidated_unnamed_bytes",),
    )


@dataclass(frozen=True, repr=False)
class WeatherSnapshot:
    device_epoch_seconds: int
    daytime_code: int
    evening_code: int
    lowest_temperature: int
    highest_temperature: int
    air_quality_code: int
    pm25: int
    uv_index: int
    aqi: int
    current_temperature: int

    def __post_init__(self) -> None:
        _u32(self.device_epoch_seconds, "device_epoch_seconds")
        _u16(self.daytime_code, "daytime_code")
        _u16(self.evening_code, "evening_code")
        _i8(self.lowest_temperature, "lowest_temperature")
        _i8(self.highest_temperature, "highest_temperature")
        _u8(self.air_quality_code, "air_quality_code")
        _u16(self.pm25, "pm25")
        _u8(self.uv_index, "uv_index")
        _u16(self.aqi, "aqi")
        _i8(self.current_temperature, "current_temperature")

    def __repr__(self) -> str:
        return "WeatherSnapshot(<redacted>)"


def encode_weather(
    *, record_index: int, snapshot: WeatherSnapshot
) -> StaticVendorCommandRequest:
    index = _u8(record_index, "record_index")
    if not isinstance(snapshot, WeatherSnapshot):
        raise TypeError("snapshot must be a WeatherSnapshot")
    payload = (
        bytes((index,))
        + snapshot.device_epoch_seconds.to_bytes(4, "little")
        + snapshot.daytime_code.to_bytes(2, "little")
        + snapshot.evening_code.to_bytes(2, "little")
        + bytes(
            (
                snapshot.lowest_temperature & 0xFF,
                snapshot.highest_temperature & 0xFF,
                snapshot.air_quality_code,
            )
        )
        + snapshot.pm25.to_bytes(2, "little")
        + bytes((snapshot.uv_index,))
        + snapshot.aqi.to_bytes(2, "little")
        + bytes((snapshot.current_temperature & 0xFF,))
    )
    return _request(
        StaticVendorCommandOperation.WEATHER,
        0x22,
        payload,
        quirks=(
            "sdk_read_a_cached_platform_weather_list",
            "sdk_queued_an_all_zero_frame_for_a_null_record",
            "sdk_silently_truncated_integer_fields",
        ),
    )


def encode_ai_language(language_value: str) -> StaticVendorCommandRequest:
    if type(language_value) is not str:
        raise TypeError("AI language value must be text")
    if not language_value or not language_value.isprintable():
        raise ValueError("AI language value must be non-empty printable text")
    try:
        encoded = language_value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("AI language value must be valid Unicode text") from exc
    if len(encoded) > 18:
        raise ValueError("AI language value must fit in 18 UTF-8 bytes")
    return _request(
        StaticVendorCommandOperation.AI_LANGUAGE,
        0x54,
        b"\x10" + encoded,
        quirks=(
            "sdk_used_implicit_charset_and_silent_truncation",
            "host_locale_inference_is_outside_the_offline_codec",
            "language_value_vocabulary_is_unknown",
        ),
    )


def encode_ai_chat_state(enabled: bool) -> StaticVendorCommandRequest:
    return _request(
        StaticVendorCommandOperation.AI_CHAT_STATE,
        0x54,
        bytes((0x0F, int(_bool(enabled)))),
    )


def encode_ai_connection_method(method_code: int) -> StaticVendorCommandRequest:
    code = _u8(method_code, "method_code")
    return _request(
        StaticVendorCommandOperation.AI_CONNECTION_METHOD,
        0x54,
        bytes((0x14, code)),
        quirks=("connection_method_meaning_is_not_hardware_verified",),
    )


def encode_app_state(*, first_state: int, second_state: int) -> StaticVendorCommandRequest:
    first = _i32(first_state, "first_state")
    second = _i32(second_state, "second_state")
    return _request(
        StaticVendorCommandOperation.APP_STATE,
        0x52,
        first.to_bytes(4, "little", signed=True)
        + second.to_bytes(4, "little", signed=True),
        quirks=("state_field_meanings_are_not_hardware_verified",),
    )


def encode_binding_info(
    *, first_value: int, second_value: int, third_value: int
) -> StaticVendorCommandRequest:
    payload = bytes(
        (
            _u8(first_value, "first_value"),
            _u8(second_value, "second_value"),
            _u8(third_value, "third_value"),
        )
    )
    return _request(
        StaticVendorCommandOperation.BINDING_INFO,
        0x4B,
        payload,
        quirks=(
            "sdk_gate_mislabeled_this_binding_command_as_device_code",
            "binding_field_meanings_remain_neutral",
        ),
    )


def encode_blood_oxygen_mode(enabled: bool) -> StaticVendorCommandRequest:
    return _request(
        StaticVendorCommandOperation.BLOOD_OXYGEN_MODE,
        0x3E,
        bytes((int(_bool(enabled)),)),
        quirks=("this_is_distinct_from_shared_sensor_session_mode_2",),
    )


def encode_device_time(
    *, local_epoch_seconds: int, raw_utc_offset_hours: int
) -> StaticVendorCommandRequest:
    epoch = _u32(local_epoch_seconds, "local_epoch_seconds")
    offset = _int(raw_utc_offset_hours, "raw_utc_offset_hours", -12, 14)
    return _request(
        StaticVendorCommandOperation.DEVICE_TIME,
        0x01,
        epoch.to_bytes(4, "little") + bytes((offset & 0xFF,)),
        quirks=(
            "sdk_derived_timestamp_and_offset_from_current_host_time",
            "sdk_shifted_epoch_by_current_timezone_offset",
            "sdk_timestamp_used_dst_offset_but_offset_byte_used_raw_offset",
            "wire_offset_supports_whole_hours_only",
        ),
    )


def encode_ecg_mode(enabled: bool, *, mode_code: int) -> StaticVendorCommandRequest:
    active = _bool(enabled)
    mode = _u8(mode_code, "mode_code")
    return _request(
        StaticVendorCommandOperation.ECG_MODE,
        0x2A,
        bytes((int(active), mode)),
        quirks=("mode_code_meaning_is_not_hardware_verified",),
    )


def encode_eq_info(
    *, first_metadata: int, second_metadata: int, values: tuple[int, ...]
) -> StaticVendorCommandRequest:
    first = _u8(first_metadata, "first_metadata")
    second = _u8(second_metadata, "second_metadata")
    if not isinstance(values, tuple):
        raise TypeError("EQ values must be an immutable tuple")
    if not 10 <= len(values) <= 15:
        raise ValueError("EQ values must contain between 10 and 15 entries")
    encoded_values = bytes(_i8(value, "EQ value") & 0xFF for value in values)
    return _request(
        StaticVendorCommandOperation.EQ_INFO,
        0x53,
        bytes((0, first, second, len(values))) + encoded_values,
        quirks=(
            "sdk_only_copied_values_for_counts_10_through_15",
            "sdk_silently_truncated_metadata_and_signed_values",
        ),
    )


def encode_g_sensor_indicator(enabled: bool) -> StaticVendorCommandRequest:
    return _request(
        StaticVendorCommandOperation.G_SENSOR_INDICATOR,
        0x78,
        bytes((int(_bool(enabled)),)),
        quirks=("boolean_is_the_subcommand_not_a_payload_value",),
    )


def encode_heart_rate_session_start(
    *, reference_value: int, mode_code: int
) -> StaticVendorCommandRequest:
    reference = _u32(reference_value, "reference_value")
    mode = _u8(mode_code, "mode_code")
    return _request(
        StaticVendorCommandOperation.HEART_RATE_SESSION_START,
        0x14,
        reference.to_bytes(4, "little") + bytes((mode,)),
        quirks=("reference_and_mode_meanings_are_not_hardware_verified",),
    )


def encode_heart_rate_session_stop(*, mode_code: int) -> StaticVendorCommandRequest:
    mode = _u8(mode_code, "mode_code")
    return _request(
        StaticVendorCommandOperation.HEART_RATE_SESSION_STOP,
        0x15,
        bytes(4) + bytes((mode,)),
        quirks=(
            "sdk_stop_ignored_the_reference_value",
            "start_and_stop_use_distinct_opcodes",
        ),
    )


def encode_offline_speech_recognition(enabled: bool) -> StaticVendorCommandRequest:
    return _request(
        StaticVendorCommandOperation.OFFLINE_SPEECH_RECOGNITION,
        0x78,
        bytes((0x03, int(_bool(enabled)))),
    )


def encode_temperature_mode(enabled: bool) -> StaticVendorCommandRequest:
    return _request(
        StaticVendorCommandOperation.TEMPERATURE_MODE,
        0x37,
        bytes((int(_bool(enabled)),)),
    )


def encode_touch_mode(mode_code: int) -> StaticVendorCommandRequest:
    mode = _u8(mode_code, "mode_code")
    return _request(
        StaticVendorCommandOperation.TOUCH_MODE,
        0x78,
        bytes((0x09, mode)),
        quirks=("touch_mode_meaning_is_not_hardware_verified",),
    )


def encode_factory_test_mode(enabled: bool) -> StaticVendorCommandRequest:
    return _request(
        StaticVendorCommandOperation.FACTORY_TEST_MODE,
        0x50,
        bytes((int(_bool(enabled)),)),
        quirks=("factory_mode_has_high_risk_unverified_side_effects",),
    )


__all__ = [
    "StaticVendorCommandOperation",
    "StaticVendorCommandRequest",
    "WeatherSnapshot",
    "encode_ai_chat_state",
    "encode_ai_connection_method",
    "encode_ai_language",
    "encode_app_state",
    "encode_binding_info",
    "encode_blood_oxygen_mode",
    "encode_device_time",
    "encode_ecg_mode",
    "encode_eq_info",
    "encode_factory_test_mode",
    "encode_g_sensor_indicator",
    "encode_heart_rate_session_start",
    "encode_heart_rate_session_stop",
    "encode_offline_speech_recognition",
    "encode_phone_call_state",
    "encode_temperature_mode",
    "encode_touch_mode",
    "encode_weather",
]
