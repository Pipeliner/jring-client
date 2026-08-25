"""Offline-only typed encoders for statically recovered vendor settings.

These objects are synthetic protocol vectors.  They cannot connect, subscribe, or
write, and static APK evidence does not establish owner authorization, firmware
support, response timing, or safe hardware behavior.  The public encoders deliberately
correct permissive SDK behavior by rejecting truncation, implicit encodings, and
untyped integer modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
import unicodedata

from .uuids import VENDOR_CHARACTERISTIC_33F3


class StaticVendorSettingOperation(str, Enum):
    DEVICE_SETTINGS = "device_settings"
    HOUR_FORMAT = "hour_format"
    DEVICE_CODE = "device_code"
    LANGUAGE = "language"
    SENSOR_SESSION_START = "sensor_session_start"
    SENSOR_SESSION_STOP = "sensor_session_stop"
    HEART_RATE_AREA = "heart_rate_area"
    DEVICE_NAME = "device_name"


class HourFormat(Enum):
    TWENTY_FOUR = 0
    TWELVE = 1


class WearMode(Enum):
    """Neutral wire values; the app presented these as two wearing sides."""

    SIDE_0 = 0
    SIDE_1 = 1


class BrightnessLevel(Enum):
    LEVEL_1 = 20
    LEVEL_2 = 40
    LEVEL_3 = 60
    LEVEL_4 = 80
    LEVEL_5 = 100


class SensorSessionMode(Enum):
    """Neutral selectors for the shared 0x23 sensor session."""

    MODE_1 = 1
    MODE_2 = 2
    MODE_3 = 3
    MODE_4 = 4


@dataclass(frozen=True, repr=False)
class VendorClockTime:
    hour: int
    minute: int

    def __post_init__(self) -> None:
        _bounded_int(self.hour, "hour", maximum=23)
        _bounded_int(self.minute, "minute", maximum=59)

    def __repr__(self) -> str:
        return "VendorClockTime(<redacted>)"


_RESPONSE_OPCODES = {
    StaticVendorSettingOperation.DEVICE_SETTINGS: (0x1B, 0x9B),
    StaticVendorSettingOperation.HOUR_FORMAT: (0x1D, 0x9D),
    StaticVendorSettingOperation.DEVICE_CODE: (0x1E, 0x9E),
    StaticVendorSettingOperation.LANGUAGE: (0x21, 0xA1),
    StaticVendorSettingOperation.SENSOR_SESSION_START: (0x23, 0xA3),
    StaticVendorSettingOperation.SENSOR_SESSION_STOP: (0x23, 0xA3),
    StaticVendorSettingOperation.HEART_RATE_AREA: (0x26, 0xA6),
    StaticVendorSettingOperation.DEVICE_NAME: (0x30, None),
}


@dataclass(frozen=True, init=False, repr=False)
class StaticVendorSettingRequest:
    """A hidden-byte, hardware-ineligible synthetic request vector."""

    operation: StaticVendorSettingOperation
    corrected_sdk_quirks: tuple[str, ...]
    _encoded: bytes = field(repr=False)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor setting requests must use a typed offline encoder")

    def __repr__(self) -> str:
        return (
            "StaticVendorSettingRequest("
            f"operation={self.operation.value!r}, maturity='static_apk_only')"
        )

    @classmethod
    def _from_parts(
        cls,
        operation: StaticVendorSettingOperation,
        encoded: bytes,
        corrected_sdk_quirks: tuple[str, ...],
    ) -> "StaticVendorSettingRequest":
        request = object.__new__(cls)
        object.__setattr__(request, "operation", operation)
        object.__setattr__(request, "corrected_sdk_quirks", corrected_sdk_quirks)
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
    def response_success_opcode(self) -> int:
        return _RESPONSE_OPCODES[self.operation][0]

    @property
    def response_failure_opcode(self) -> int | None:
        return _RESPONSE_OPCODES[self.operation][1]

    @property
    def queue_priority_observed_in_sdk(self) -> bool:
        return self.operation in {
            StaticVendorSettingOperation.SENSOR_SESSION_START,
            StaticVendorSettingOperation.SENSOR_SESSION_STOP,
        }

    def synthetic_bytes_for_test(self) -> bytes:
        """Return a synthetic vector for offline verification only."""

        return bytes(self._encoded)


def _bounded_int(value: int, label: str, *, maximum: int = 0xFF) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    if not 0 <= value <= maximum:
        raise ValueError(f"{label} must be between 0 and {maximum}")
    return value


def _boolean(value: bool, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a boolean")
    return value


def _typed_enum(value: object, enum_type: type[Enum], label: str) -> Enum:
    if not isinstance(value, enum_type):
        raise TypeError(f"{label} must be a {enum_type.__name__}")
    return value


def _request(
    operation: StaticVendorSettingOperation,
    opcode: int,
    payload: bytes = b"",
    *,
    quirks: tuple[str, ...] = (),
) -> StaticVendorSettingRequest:
    if len(payload) > 19:
        raise ValueError("vendor settings payload exceeds the fixed 20-byte frame")
    encoded = bytes((opcode,)) + bytes(payload) + bytes(19 - len(payload))
    return StaticVendorSettingRequest._from_parts(operation, encoded, quirks)


def encode_device_settings(
    *,
    enable_light: bool,
    enable_vibrate: bool,
    quiet_enabled: bool,
    quiet_start: VendorClockTime,
    quiet_end: VendorClockTime,
    calling_enabled: bool,
    short_video_enabled: bool,
    wear_mode: WearMode,
    brightness: BrightnessLevel,
) -> StaticVendorSettingRequest:
    """Encode the broad SDK profile mutation formerly called ``setDeviceInfo``."""

    flags = (
        _boolean(enable_light, "enable_light"),
        _boolean(enable_vibrate, "enable_vibrate"),
        _boolean(quiet_enabled, "quiet_enabled"),
        _boolean(calling_enabled, "calling_enabled"),
        _boolean(short_video_enabled, "short_video_enabled"),
    )
    if not isinstance(quiet_start, VendorClockTime):
        raise TypeError("quiet_start must be a VendorClockTime")
    if not isinstance(quiet_end, VendorClockTime):
        raise TypeError("quiet_end must be a VendorClockTime")
    typed_wear = _typed_enum(wear_mode, WearMode, "wear_mode")
    typed_brightness = _typed_enum(brightness, BrightnessLevel, "brightness")
    light, vibrate, quiet, calling, short_video = flags
    payload = bytes(
        (
            int(light),
            int(vibrate),
            0,
            0,
            int(quiet),
            quiet_start.hour,
            quiet_start.minute,
            quiet_end.hour,
            quiet_end.minute,
            int(not calling),
            int(short_video),
            typed_wear.value,
            typed_brightness.value,
        )
    )
    return _request(
        StaticVendorSettingOperation.DEVICE_SETTINGS,
        0x1B,
        payload,
        quirks=(
            "sdk_name_implied_read_only_device_info",
            "calling_bit_is_inverted",
            "invalid_brightness_fell_back_to_80",
            "sdk_low_byte_truncation_replaced_by_strict_types",
        ),
    )


def encode_hour_format(value: HourFormat) -> StaticVendorSettingRequest:
    typed = _typed_enum(value, HourFormat, "hour format")
    return _request(
        StaticVendorSettingOperation.HOUR_FORMAT,
        0x1D,
        bytes((typed.value,)),
        quirks=("sdk_accepted_any_integer_and_kept_only_the_low_byte",),
    )


def encode_device_code(code: bytes) -> StaticVendorSettingRequest:
    if not isinstance(code, bytes):
        raise TypeError("device code must be bytes")
    if not 1 <= len(code) <= 19:
        raise ValueError("device code must contain between 1 and 19 bytes")
    return _request(
        StaticVendorSettingOperation.DEVICE_CODE,
        0x1E,
        code,
        quirks=(
            "sdk_silently_truncated_after_19_bytes",
            "app_call_site_appended_a_zero_byte_after_hex_decoding",
            "identifier_bytes_are_private",
        ),
    )


_LANGUAGE_TAG = re.compile(r"[a-z]{2,3}-[A-Z]{2}")


def encode_language(tag: str) -> StaticVendorSettingRequest:
    if type(tag) is not str:
        raise TypeError("language tag must be text")
    if _LANGUAGE_TAG.fullmatch(tag) is None:
        raise ValueError("language tag must use canonical language-REGION form")
    encoded = tag.encode("utf-8")
    if len(encoded) > 19:
        raise ValueError("language tag exceeds the 19-byte wire field")
    return _request(
        StaticVendorSettingOperation.LANGUAGE,
        0x21,
        encoded,
        quirks=(
            "sdk_inferred_and_logged_host_locale",
            "sdk_overlength_branch_copied_only_18_bytes",
            "sdk_overlength_copy_could_split_utf8",
        ),
    )


def encode_sensor_session_start(mode: SensorSessionMode) -> StaticVendorSettingRequest:
    typed = _typed_enum(mode, SensorSessionMode, "sensor session mode")
    return _request(
        StaticVendorSettingOperation.SENSOR_SESSION_START,
        0x23,
        bytes((typed.value,)),
        quirks=(
            "sdk_callbacks_named_every_mode_as_blood_pressure",
            "sdk_exposed_four_wrappers_for_one_shared_session",
        ),
    )


def encode_sensor_session_stop() -> StaticVendorSettingRequest:
    return _request(
        StaticVendorSettingOperation.SENSOR_SESSION_STOP,
        0x23,
        b"\x00",
        quirks=(
            "all_sdk_stop_wrappers_collapsed_to_mode_zero",
            "stop_frame_has_no_per_mode_identity",
        ),
    )


def encode_heart_rate_area(
    enabled: bool, *, first_value: int, second_value: int
) -> StaticVendorSettingRequest:
    active = _boolean(enabled, "enabled")
    first = _bounded_int(first_value, "first_value")
    second = _bounded_int(second_value, "second_value")
    return _request(
        StaticVendorSettingOperation.HEART_RATE_AREA,
        0x26,
        bytes((int(active), first, second)),
        quirks=(
            "sdk_did_not_validate_or_name_field_order",
            "sdk_low_byte_truncation_replaced_by_bounded_neutral_fields",
        ),
    )


def encode_device_name(name: str) -> StaticVendorSettingRequest:
    if type(name) is not str:
        raise TypeError("device name must be text")
    if not name:
        raise ValueError("device name cannot be empty")
    if unicodedata.normalize("NFC", name) != name:
        raise ValueError("device name must be NFC-normalized")
    if not name.isprintable():
        raise ValueError("device name cannot contain control characters")
    encoded = name.encode("utf-8")
    if len(encoded) > 11:
        raise ValueError("device name must fit in 11 UTF-8 bytes")
    return _request(
        StaticVendorSettingOperation.DEVICE_NAME,
        0x30,
        encoded,
        quirks=(
            "sdk_used_implicit_charset_and_silently_truncated_to_11_bytes",
            "sdk_truncation_could_split_a_multibyte_character",
            "sdk_parser_had_no_failure_opcode_branch",
        ),
    )


__all__ = [
    "BrightnessLevel",
    "HourFormat",
    "SensorSessionMode",
    "StaticVendorSettingOperation",
    "StaticVendorSettingRequest",
    "VendorClockTime",
    "WearMode",
    "encode_device_code",
    "encode_device_name",
    "encode_device_settings",
    "encode_heart_rate_area",
    "encode_hour_format",
    "encode_language",
    "encode_sensor_session_start",
    "encode_sensor_session_stop",
]
