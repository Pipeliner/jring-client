"""Strict offline plans for a statically recovered vendor command family.

Every object is a redacted test artifact.  This module cannot connect, subscribe,
write, retry, or otherwise interact with a Bluetooth device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .uuids import VENDOR_CHARACTERISTIC_33F3


_FRAME_LENGTH = 20


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _bounded(value: object, label: str, minimum: int, maximum: int) -> int:
    result = _integer(value, label)
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def _exact_type(value: object, expected: type, label: str) -> None:
    if type(value) is not expected:
        raise TypeError(f"{label} must be a {expected.__name__}")


def _payload(prefix: bytes) -> bytes:
    if type(prefix) is not bytes:
        raise TypeError("vendor command prefix must be bytes")
    if not prefix or len(prefix) > _FRAME_LENGTH:
        raise ValueError("vendor command prefix must fit one 20-byte frame")
    return prefix + bytes(_FRAME_LENGTH - len(prefix))


class CommandRole(str, Enum):
    SETTING = "setting"
    NO_ARGUMENT_QUERY = "no_argument_query"
    NO_ARGUMENT_ACTION = "no_argument_action"
    PARAMETERIZED_QUERY = "parameterized_query"
    HOST_STATE_PROJECTION = "host_state_projection"


class MainCommandOperation(str, Enum):
    SET_SCREEN_LIGHT_TIME = "set_screen_light_time"
    GET_DATA_BY_DAY = "get_data_by_day"
    GET_DEVICE_CODE = "get_device_code"
    GET_DEVICE_DIAL = "get_device_dial"
    GET_DEVICE_DIAL_CUSTOM = "get_device_dial_custom"
    GET_DEVICE_SYSTEM_STATE = "get_device_system_state"
    GET_ECG_HISTORY = "get_ecg_history"
    GET_EQ_INFO = "get_eq_info"
    GET_MEDIA_FILE_STATE = "get_media_file_state"
    QUERY_OFFLINE_SPEECH_STATE = "query_offline_speech_state"
    SCAN_WIFI = "scan_wifi"
    SEND_PHONE_VOLUME = "send_phone_volume"


_OPERATION_METADATA = {
    MainCommandOperation.SET_SCREEN_LIGHT_TIME: (
        "device_setting",
        "device_mutation",
    ),
    MainCommandOperation.GET_DATA_BY_DAY: ("health_history", "health_history_query"),
    MainCommandOperation.GET_DEVICE_CODE: ("device_identifier", "device_query"),
    MainCommandOperation.GET_DEVICE_DIAL: ("device_personalization", "device_query"),
    MainCommandOperation.GET_DEVICE_DIAL_CUSTOM: (
        "device_personalization",
        "device_query",
    ),
    MainCommandOperation.GET_DEVICE_SYSTEM_STATE: ("device_state", "device_query"),
    MainCommandOperation.GET_ECG_HISTORY: ("health_history", "health_history_query"),
    MainCommandOperation.GET_EQ_INFO: ("audio_profile", "device_query"),
    MainCommandOperation.GET_MEDIA_FILE_STATE: ("media_state", "device_query"),
    MainCommandOperation.QUERY_OFFLINE_SPEECH_STATE: (
        "speech_setting",
        "device_query",
    ),
    MainCommandOperation.SCAN_WIFI: ("network_discovery", "network_scan_action"),
    MainCommandOperation.SEND_PHONE_VOLUME: ("host_audio_state", "host_state_projection"),
}


class _StaticPlan:
    @property
    def operation(self) -> MainCommandOperation:
        raise NotImplementedError

    @property
    def privacy_class(self) -> str:
        return _OPERATION_METADATA[self.operation][0]

    @property
    def risk_class(self) -> str:
        return _OPERATION_METADATA[self.operation][1]

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>, hardware_eligible=False)"


@dataclass(frozen=True, repr=False, init=False)
class VendorMainCommandFrame(_StaticPlan):
    endpoint_uuid: str
    _payload: bytes = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("vendor main-command frames require a closed typed request")

    @classmethod
    def _create(cls, payload: bytes) -> "VendorMainCommandFrame":
        if type(payload) is not bytes or len(payload) != _FRAME_LENGTH:
            raise ValueError("vendor main-command payload must be exactly 20 bytes")
        instance = object.__new__(cls)
        object.__setattr__(instance, "endpoint_uuid", VENDOR_CHARACTERISTIC_33F3)
        object.__setattr__(instance, "_payload", payload)
        return instance

    def synthetic_bytes_for_test(self) -> bytes:
        return bytes(self._payload)

    def __repr__(self) -> str:
        return (
            "VendorMainCommandFrame("
            f"endpoint_uuid={self.endpoint_uuid!r}, payload=<redacted>, "
            "hardware_eligible=False)"
        )


def _single_frame(payload: bytes) -> tuple[VendorMainCommandFrame, ...]:
    return (VendorMainCommandFrame._create(payload),)


@dataclass(frozen=True, repr=False)
class ScreenLightTimeRequest(_StaticPlan):
    raw_value: int = field(repr=False)

    def __post_init__(self) -> None:
        _bounded(self.raw_value, "screen light time raw value", 0, 0xFF)

    @property
    def operation(self) -> MainCommandOperation:
        return MainCommandOperation.SET_SCREEN_LIGHT_TIME

    @property
    def role(self) -> CommandRole:
        return CommandRole.SETTING

    def frames(self) -> tuple[VendorMainCommandFrame, ...]:
        return _single_frame(_payload(bytes((0x78, 0x0A, self.raw_value))))


class DayDataKind(Enum):
    SDK_TYPE_1 = 1
    SDK_TYPE_2 = 2
    SDK_TYPE_12 = 12
    SDK_TYPE_13 = 13


_DAY_DATA_OPCODES = {
    DayDataKind.SDK_TYPE_1: 0x10,
    DayDataKind.SDK_TYPE_2: 0x16,
    DayDataKind.SDK_TYPE_12: 0x39,
    DayDataKind.SDK_TYPE_13: 0x40,
}


@dataclass(frozen=True, repr=False)
class DayDataRequest(_StaticPlan):
    kind: DayDataKind
    day_offset: int = field(repr=False)

    def __post_init__(self) -> None:
        _exact_type(self.kind, DayDataKind, "day-data kind")
        _bounded(self.day_offset, "day offset", 0, 0xFF)

    @property
    def operation(self) -> MainCommandOperation:
        return MainCommandOperation.GET_DATA_BY_DAY

    @property
    def role(self) -> CommandRole:
        return CommandRole.PARAMETERIZED_QUERY

    def frames(self) -> tuple[VendorMainCommandFrame, ...]:
        return _single_frame(
            _payload(bytes((_DAY_DATA_OPCODES[self.kind], self.day_offset)))
        )


class NoArgumentMainCommand(Enum):
    DEVICE_CODE = (MainCommandOperation.GET_DEVICE_CODE, bytes((0x1F,)))
    DEVICE_DIAL = (MainCommandOperation.GET_DEVICE_DIAL, bytes((0x34,)))
    DEVICE_DIAL_CUSTOM = (MainCommandOperation.GET_DEVICE_DIAL_CUSTOM, bytes((0x42,)))
    DEVICE_SYSTEM_STATE = (
        MainCommandOperation.GET_DEVICE_SYSTEM_STATE,
        bytes((0x54, 0x11)),
    )
    EQ_INFO = (MainCommandOperation.GET_EQ_INFO, bytes((0x53, 0x01)))
    MEDIA_FILE_STATE = (MainCommandOperation.GET_MEDIA_FILE_STATE, bytes((0x54, 0x05)))
    OFFLINE_SPEECH_STATE = (
        MainCommandOperation.QUERY_OFFLINE_SPEECH_STATE,
        bytes((0x78, 0x0C)),
    )
    SCAN_WIFI = (MainCommandOperation.SCAN_WIFI, bytes((0x54, 0x08)))

    @property
    def operation(self) -> MainCommandOperation:
        return self.value[0]

    @property
    def prefix(self) -> bytes:
        return self.value[1]


@dataclass(frozen=True, repr=False)
class NoArgumentMainCommandRequest(_StaticPlan):
    command: NoArgumentMainCommand

    def __post_init__(self) -> None:
        _exact_type(self.command, NoArgumentMainCommand, "no-argument main command")

    @property
    def operation(self) -> MainCommandOperation:
        return self.command.operation

    @property
    def role(self) -> CommandRole:
        if self.operation is MainCommandOperation.SCAN_WIFI:
            return CommandRole.NO_ARGUMENT_ACTION
        return CommandRole.NO_ARGUMENT_QUERY

    def frames(self) -> tuple[VendorMainCommandFrame, ...]:
        return _single_frame(_payload(self.command.prefix))


@dataclass(frozen=True, repr=False)
class EcgHistoryRequest(_StaticPlan):
    epoch_seconds: int = field(repr=False)
    raw_utc_offset_seconds: int = field(repr=False)

    def __post_init__(self) -> None:
        epoch = _bounded(self.epoch_seconds, "ECG history epoch", 0, 0xFFFFFFFF)
        offset = _bounded(
            self.raw_utc_offset_seconds,
            "raw UTC offset seconds",
            -86_400,
            86_400,
        )
        device_epoch = epoch + offset
        if not 0 <= device_epoch <= 0xFFFFFFFF:
            raise ValueError("ECG device epoch must fit one unsigned 32-bit value")

    @property
    def device_epoch_seconds(self) -> int:
        return self.epoch_seconds + self.raw_utc_offset_seconds

    @property
    def operation(self) -> MainCommandOperation:
        return MainCommandOperation.GET_ECG_HISTORY

    @property
    def role(self) -> CommandRole:
        return CommandRole.PARAMETERIZED_QUERY

    def frames(self) -> tuple[VendorMainCommandFrame, ...]:
        encoded = self.device_epoch_seconds.to_bytes(4, "little")
        return _single_frame(_payload(bytes((0x2C,)) + encoded))


@dataclass(frozen=True, repr=False)
class PhoneVolumeRequest(_StaticPlan):
    current_music: int = field(repr=False)
    maximum_music: int = field(repr=False)
    current_call: int = field(repr=False)
    maximum_call: int = field(repr=False)

    def __post_init__(self) -> None:
        current_music = _bounded(self.current_music, "current music volume", 0, 0xFF)
        maximum_music = _bounded(self.maximum_music, "maximum music volume", 1, 0xFF)
        current_call = _bounded(self.current_call, "current call volume", 0, 0xFF)
        maximum_call = _bounded(self.maximum_call, "maximum call volume", 1, 0xFF)
        if current_music > maximum_music:
            raise ValueError("current music volume cannot exceed maximum music volume")
        if current_call > maximum_call:
            raise ValueError("current call volume cannot exceed maximum call volume")

    @property
    def role(self) -> CommandRole:
        return CommandRole.HOST_STATE_PROJECTION

    @property
    def operation(self) -> MainCommandOperation:
        return MainCommandOperation.SEND_PHONE_VOLUME

    def frames(self) -> tuple[VendorMainCommandFrame, ...]:
        values = bytes(
            (
                self.current_music,
                self.maximum_music,
                self.current_call,
                self.maximum_call,
            )
        )
        return _single_frame(_payload(bytes((0x49,)) + values))
