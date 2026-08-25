"""Pure offline encoders for statically recovered personal-setting requests.

This module cannot subscribe, write, retry, or clear a command queue.  Its request
objects remain hardware-ineligible and expose encoded bytes only through an explicitly
test-scoped accessor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from .uuids import VENDOR_CHARACTERISTIC_33F3
from .vendor_request_integrity import seal_vendor_request, validate_vendor_request


class PersonalSettingOperation(str, Enum):
    REMINDER = "reminder"
    REMINDER_TEXT = "reminder_text"
    BP_ADJUST = "bp_adjust"
    DEVICE_DIAL_STATE = "device_dial_state"
    DEVICE_WALLPAPER_STATE = "device_wallpaper_state"
    EDIT_DEVICE_DIAL_CUSTOM = "edit_device_dial_custom"
    FEMALE_REMINDER = "female_reminder"


@dataclass(frozen=True)
class OfflinePersonalSettingSafety:
    transport_integration: bool = False
    apk_queue_clearing_reproduced: bool = False
    apk_write_retry_reproduced: bool = False


_OFFLINE_SAFETY = OfflinePersonalSettingSafety()


@dataclass(frozen=True, init=False, repr=False)
class OfflinePersonalSettingRequest:
    operation: PersonalSettingOperation
    privacy_class: str
    _encoded: bytes = field(repr=False)

    def __init__(self) -> None:
        raise TypeError("offline personal-setting requests use closed encoder functions")

    @classmethod
    def _create(
        cls,
        operation: PersonalSettingOperation,
        privacy_class: str,
        encoded: bytes,
    ) -> "OfflinePersonalSettingRequest":
        if type(operation) is not PersonalSettingOperation:
            raise TypeError("operation must be a PersonalSettingOperation")
        if not isinstance(encoded, bytes) or len(encoded) != 20:
            raise ValueError("offline personal-setting request must be exactly 20 bytes")
        request = object.__new__(cls)
        object.__setattr__(request, "operation", operation)
        object.__setattr__(request, "privacy_class", privacy_class)
        object.__setattr__(request, "_encoded", bytes(encoded))
        seal_vendor_request(request, operation=operation, frames=(bytes(encoded),))
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
    def safety(self) -> OfflinePersonalSettingSafety:
        return _OFFLINE_SAFETY

    def synthetic_bytes_for_test(self) -> bytes:
        return bytes(self._encoded)

    def validate_for_fake_execution(self) -> None:
        validate_vendor_request(
            self,
            operation=self.operation,
            frames=(self._encoded,),
        )

    def __repr__(self) -> str:
        return (
            "OfflinePersonalSettingRequest("
            f"operation={self.operation.value!r}, privacy_class={self.privacy_class!r}, "
            "frame=<redacted>, hardware_eligible=False)"
        )


def _integer(value: int, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    return value


def _u8(value: int, label: str) -> int:
    result = _integer(value, label)
    if not 0 <= result <= 0xFF:
        raise ValueError(f"{label} must fit one unsigned byte")
    return result


def _u16(value: int, label: str) -> int:
    result = _integer(value, label)
    if not 0 <= result <= 0xFFFF:
        raise ValueError(f"{label} must fit one unsigned 16-bit value")
    return result


def _u32(value: int, label: str) -> int:
    result = _integer(value, label)
    if not 0 <= result <= 0xFFFFFFFF:
        raise ValueError(f"{label} must fit one unsigned 32-bit value")
    return result


def _hour(value: int, label: str) -> int:
    result = _u8(value, label)
    if result > 23:
        raise ValueError(f"{label} must be between 0 and 23")
    return result


def _minute(value: int, label: str) -> int:
    result = _u8(value, label)
    if result > 59:
        raise ValueError(f"{label} must be between 0 and 59")
    return result


def _request(
    operation: PersonalSettingOperation,
    privacy_class: str,
    *fields: int,
) -> OfflinePersonalSettingRequest:
    encoded = bytes(fields) + bytes(20 - len(fields))
    return OfflinePersonalSettingRequest._create(operation, privacy_class, encoded)


def encode_reminder(
    *,
    interval_seconds: int,
    start_hour: int,
    start_minute: int,
    end_hour: int,
    end_minute: int,
    neutral_1: int,
    neutral_2: int,
) -> OfflinePersonalSettingRequest:
    interval = _u32(interval_seconds, "interval seconds")
    if interval != 0 and not (60 <= interval <= 14_400 and interval % 60 == 0):
        raise ValueError(
            "interval seconds must be zero or an observed 1..240 minute interval"
        )
    encoded = (
        bytes((0x31,))
        + interval.to_bytes(4, "little")
        + bytes((
            _hour(start_hour, "start hour"),
            _minute(start_minute, "start minute"),
            _hour(end_hour, "end hour"),
            _minute(end_minute, "end minute"),
            _u8(neutral_1, "first neutral reminder field"),
            _u8(neutral_2, "second neutral reminder field"),
        ))
        + bytes(9)
    )
    return OfflinePersonalSettingRequest._create(
        PersonalSettingOperation.REMINDER,
        "personal_schedule",
        encoded,
    )


def encode_reminder_text(*, index: int, text: str) -> OfflinePersonalSettingRequest:
    item = _u8(index, "reminder text index")
    if not isinstance(text, str):
        raise TypeError("reminder text must be a string")
    if "\x00" in text:
        raise ValueError("reminder text cannot contain a NUL byte")
    encoded_text = text.encode("utf-8")
    if len(encoded_text) > 18:
        raise ValueError("UTF-8 reminder text must fit 18 bytes without truncation")
    encoded = bytes((0x32, item)) + encoded_text + bytes(18 - len(encoded_text))
    return OfflinePersonalSettingRequest._create(
        PersonalSettingOperation.REMINDER_TEXT,
        "private_text",
        encoded,
    )


def encode_bp_adjust(
    *, systolic: int, diastolic: int
) -> OfflinePersonalSettingRequest:
    first = _u16(systolic, "systolic adjustment")
    second = _u16(diastolic, "diastolic adjustment")
    if not 60 <= first <= 249:
        raise ValueError("systolic adjustment must be between 60 and 249")
    if not 30 <= second <= 199:
        raise ValueError("diastolic adjustment must be between 30 and 199")
    if first < second:
        raise ValueError("systolic adjustment cannot be below diastolic adjustment")
    encoded = (
        bytes((0x33,))
        + first.to_bytes(2, "little")
        + second.to_bytes(2, "little")
        + bytes(15)
    )
    return OfflinePersonalSettingRequest._create(
        PersonalSettingOperation.BP_ADJUST,
        "sensitive_health_calibration",
        encoded,
    )


def encode_device_dial_state(*, state: int) -> OfflinePersonalSettingRequest:
    return _request(
        PersonalSettingOperation.DEVICE_DIAL_STATE,
        "device_personalization",
        0x35,
        _u8(state, "neutral dial state"),
    )


def encode_device_wallpaper_state(*, state: int) -> OfflinePersonalSettingRequest:
    return _request(
        PersonalSettingOperation.DEVICE_WALLPAPER_STATE,
        "device_personalization",
        0x36,
        _u8(state, "neutral wallpaper state"),
    )


def encode_edit_device_dial_custom(
    *,
    neutral_1: int,
    neutral_2: int,
    neutral_3: int,
    neutral_4: int,
) -> OfflinePersonalSettingRequest:
    return _request(
        PersonalSettingOperation.EDIT_DEVICE_DIAL_CUSTOM,
        "device_personalization",
        0x41,
        _u8(neutral_1, "first neutral custom-dial field"),
        _u8(neutral_2, "second neutral custom-dial field"),
        _u8(neutral_3, "third neutral custom-dial field"),
        _u8(neutral_4, "fourth neutral custom-dial field"),
    )


def encode_female_reminder(
    *,
    enabled: bool,
    year: int,
    month: int,
    day: int,
    length: int,
    period: int,
    as_of: date,
) -> OfflinePersonalSettingRequest:
    if type(enabled) is not bool:
        raise TypeError("female-reminder enabled state must be a boolean")
    if type(as_of) is not date:
        raise TypeError("as_of must be a date")
    validated_year = _u16(year, "female-reminder year")
    validated_month = _u8(month, "female-reminder month")
    validated_day = _u8(day, "female-reminder day")
    if not 2000 <= validated_year <= as_of.year:
        raise ValueError("female-reminder year must be between 2000 and as_of.year")
    try:
        date(validated_year, validated_month, validated_day)
    except ValueError as exc:
        raise ValueError("female-reminder date must be calendar-valid") from exc
    validated_length = _u8(length, "female-reminder length")
    validated_period = _u8(period, "female-reminder period")
    if not 3 <= validated_length <= 15:
        raise ValueError("female-reminder length must be between 3 and 15")
    if not 17 <= validated_period <= 60:
        raise ValueError("female-reminder period must be between 17 and 60")
    encoded = (
        bytes((0x44,))
        + validated_year.to_bytes(2, "little")
        + bytes((
            validated_month,
            validated_day,
            validated_length,
            validated_period,
            int(enabled),
        ))
        + bytes(12)
    )
    return OfflinePersonalSettingRequest._create(
        PersonalSettingOperation.FEMALE_REMINDER,
        "sensitive_reproductive_calendar",
        encoded,
    )
