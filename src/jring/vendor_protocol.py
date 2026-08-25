"""Offline-only clean-room codecs derived from static APK evidence.

Nothing in this module transmits to a ring. Static evidence establishes candidate
request bytes, not firmware support, response semantics, side effects, legitimate
session state, or hardware eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import zlib

from .protocol import ProtocolError
from .uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4


class StaticQuery(str, Enum):
    CURRENT_SPORT = "current_sport"
    BATTERY = "battery"
    DEVICE_INFO = "device_info"
    BAND_FUNCTIONS = "band_functions"
    MULTI_SPORT_DAY = "multi_sport_day"
    OXYGEN_DAY = "oxygen_day"
    ADVANCED_SENSOR_DAY = "advanced_sensor_day"


_ZERO_ARGUMENT_OPCODES = {
    StaticQuery.CURRENT_SPORT: 0x03,
    StaticQuery.BATTERY: 0x0B,
    StaticQuery.DEVICE_INFO: 0x0C,
    StaticQuery.BAND_FUNCTIONS: 0x20,
}
_DAY_OPCODES = {
    StaticQuery.MULTI_SPORT_DAY: 0x25,
    StaticQuery.OXYGEN_DAY: 0x40,
    StaticQuery.ADVANCED_SENSOR_DAY: 0x55,
}


@dataclass(frozen=True)
class StaticVendorRequest:
    operation: StaticQuery
    _encoded: bytes = field(default=b"", repr=False)

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F3

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def synthetic_bytes_for_test(self) -> bytes:
        """Return the public synthetic vector for offline verification only."""

        return bytes(self._encoded)


@dataclass(frozen=True)
class StaticProtocolCoverage:
    operation: StaticQuery
    request_opcode: int
    success_opcodes: tuple[int, ...]
    failure_opcodes: tuple[int, ...]

    @property
    def request_endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F3

    @property
    def response_endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F4

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False


@dataclass(frozen=True)
class VendorBattery:
    percent: int
    state_code: int

    @property
    def state_meaning(self) -> str:
        return "unknown"


@dataclass(frozen=True)
class VendorCurrentSport:
    variant: str
    device_epoch_seconds: int
    steps: int | None = None
    distance: int | None = None
    calories: int | None = None
    unknown_value: int | None = None
    primary: int | None = None
    secondary: int | None = None
    tertiary: int | None = None


@dataclass(frozen=True)
class VendorDeviceInfo:
    device_type: int
    hardware_revision: int
    software_revision: int
    integrity_valid: bool
    identifier_redacted: bool = True


_STATIC_APP_FEATURE_INDEX = {
    0: "social_notifications",
    2: "weather",
    3: "time",
    4: "anti_lost",
    18: "automatic_interval",
    19: "notifications",
    20: "reminders",
    24: "sport",
    25: "dial",
    26: "wallpaper",
    31: "custom_dial",
    32: "female_reminder",
    34: "classic_bluetooth",
    35: "vibration",
    42: "custom_alarm",
    44: "sms_auto_response",
    45: "electronic_card",
    48: "chat_assistant",
    56: "sport_from_app",
    63: "short_video",
    68: "wifi",
    69: "wear_mode",
    70: "brightness",
    78: "connect_watch",
    79: "connect_bracelet",
    80: "automatic_screen_wake",
    82: "ai_transfer",
    85: "device_serial",
}


@dataclass(frozen=True)
class VendorBandFunctions:
    flags: tuple[bool, ...]

    def enabled(self, index: int) -> bool:
        if type(index) is not int:
            raise TypeError("feature index must be an integer")
        if not 0 <= index < len(self.flags):
            raise ValueError("feature index is outside the static flag set")
        return self.flags[index]

    def static_app_mapping(self, index: int) -> str | None:
        self.enabled(index)
        return _STATIC_APP_FEATURE_INDEX.get(index)


@dataclass(frozen=True)
class VendorMultiSportSample:
    device_epoch_seconds: int
    sport_type_code: int
    value: int


@dataclass(frozen=True)
class VendorMultiSportDay:
    device_epoch_seconds: int
    samples: tuple[VendorMultiSportSample, ...]
    end_of_history: bool = False


@dataclass(frozen=True)
class VendorOxygenSample:
    device_epoch_seconds: int
    value: int


@dataclass(frozen=True)
class VendorOxygenDay:
    device_epoch_seconds: int
    samples: tuple[VendorOxygenSample, ...]
    end_of_history: bool = False


@dataclass(frozen=True)
class VendorAdvancedSensorSample:
    device_epoch_seconds: int
    fields: tuple[int, int, int, int, int]


@dataclass(frozen=True)
class VendorAdvancedSensorDay:
    device_epoch_seconds: int
    samples: tuple[VendorAdvancedSensorSample, ...]
    end_of_history: bool = False


_DEVICE_ACTIONS = {
    1: ("find_phone_alarm", False, "host_alarm"),
    2: ("camera_shutter", True, "host_camera"),
    4: ("call_hangup", False, "phone_call"),
    5: ("weather_location_refresh", False, "location_access"),
    8: ("call_answer", False, "phone_call"),
    16: ("media_play_pause", True, "host_media"),
    32: ("media_next", True, "host_media"),
    64: ("media_previous", True, "host_media"),
    65: ("camera_open", False, "host_camera_lifecycle"),
    66: ("camera_close", False, "host_camera_lifecycle"),
    67: ("time_sync_request", False, "device_write_request"),
    68: ("volume_up", True, "host_audio"),
    69: ("volume_down", True, "host_audio"),
}


@dataclass(frozen=True)
class VendorDeviceAction:
    code: int
    label: str
    input_candidate: bool
    side_effect_class: str
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorStepCounter:
    cumulative_steps: int
    event_semantics: str = "experimental_counter_only"
    hardware_verified: bool = False
    input_eligible: bool = False


@dataclass(frozen=True)
class VendorDeviceState:
    flag_0: bool
    flag_1: bool
    flag_2: bool
    unused_bits_present: bool


@dataclass(frozen=True)
class VendorDeviceDialCustom:
    values: tuple[int, int, int, int]
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorReadCurrentSport:
    discriminator: int
    device_epoch_seconds: int
    first_value: int
    second_value: int


@dataclass(frozen=True)
class VendorPhoneVolumeRequest:
    requests_host_volume_state: bool = True
    input_candidate: bool = False


@dataclass(frozen=True)
class VendorSingleValueState:
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorWorshipInfo:
    values: tuple[int, int]
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorWorshipTimes:
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorMotionFrame:
    subcommand: int
    channels: tuple[int, int, int, int, int, int, int, int]
    channel_meaning: str = "unknown"
    trailing_bytes_ignored_by_sdk: bool = True
    hardware_verified: bool = False


def _request(operation: StaticQuery, *fields: int) -> StaticVendorRequest:
    encoded = bytes((operation_opcode(operation), *fields)) + bytes(19 - len(fields))
    return StaticVendorRequest(operation=operation, _encoded=encoded)


def operation_opcode(operation: StaticQuery) -> int:
    try:
        return (_ZERO_ARGUMENT_OPCODES | _DAY_OPCODES)[operation]
    except (KeyError, TypeError) as exc:
        raise ValueError("unsupported static query") from exc


def static_protocol_coverage() -> tuple[StaticProtocolCoverage, ...]:
    response_opcodes = {
        StaticQuery.CURRENT_SPORT: ((0x03, 0x13), (0x83,)),
        StaticQuery.BATTERY: ((0x0B,), (0x8B,)),
        StaticQuery.DEVICE_INFO: ((0x0C,), (0x8C,)),
        StaticQuery.BAND_FUNCTIONS: ((0x20,), (0xA0,)),
        StaticQuery.MULTI_SPORT_DAY: ((0x25,), (0xA5,)),
        StaticQuery.OXYGEN_DAY: ((0x40,), ()),
        StaticQuery.ADVANCED_SENSOR_DAY: ((0x55,), ()),
    }
    return tuple(
        StaticProtocolCoverage(
            operation=operation,
            request_opcode=operation_opcode(operation),
            success_opcodes=response_opcodes[operation][0],
            failure_opcodes=response_opcodes[operation][1],
        )
        for operation in StaticQuery
    )


def encode_static_query(operation: StaticQuery) -> StaticVendorRequest:
    if operation not in _ZERO_ARGUMENT_OPCODES:
        raise ValueError("query requires typed arguments or is unsupported")
    return _request(operation)


def encode_day_query(
    operation: StaticQuery, *, day_offset: int
) -> StaticVendorRequest:
    if operation not in _DAY_OPCODES:
        raise ValueError("query does not accept a day offset or is unsupported")
    if type(day_offset) is not int:
        raise TypeError("day offset must be an integer")
    if not 0 <= day_offset <= 0xFF:
        raise ValueError("day offset must fit one unsigned byte")
    return _request(operation, day_offset)


def _response(data: bytes, *opcodes: int) -> bytes:
    if not isinstance(data, bytes) or len(data) != 20:
        raise ProtocolError("vendor response must be exactly 20 bytes")
    if data[0] not in opcodes:
        raise ProtocolError("unexpected or failed vendor response opcode")
    return data


def parse_vendor_battery(data: bytes) -> VendorBattery:
    response = _response(data, 0x0B)
    if response[1] > 100:
        raise ProtocolError("invalid vendor battery percentage")
    return VendorBattery(percent=response[1], state_code=response[2])


def parse_vendor_current_sport(data: bytes) -> VendorCurrentSport:
    response = _response(data, 0x03, 0x13)
    timestamp = int.from_bytes(response[1:5], "little")
    first = int.from_bytes(response[5:9], "little")
    second = int.from_bytes(response[9:13], "little")
    third = int.from_bytes(response[13:17], "little")
    if response[0] == 0x03:
        return VendorCurrentSport(
            variant="activity_summary",
            device_epoch_seconds=timestamp,
            steps=first,
            distance=second,
            calories=third,
            unknown_value=int.from_bytes(response[17:20], "little"),
        )
    return VendorCurrentSport(
        variant="secondary_summary",
        device_epoch_seconds=timestamp,
        primary=first,
        secondary=second,
        tertiary=third,
    )


def parse_vendor_device_info(data: bytes) -> VendorDeviceInfo:
    response = _response(data, 0x0C)
    expected_crc = int.from_bytes(response[16:20], "little")
    actual_crc = zlib.crc32(response[1:16], 1_247_391_573) & 0xFFFFFFFF
    return VendorDeviceInfo(
        device_type=int.from_bytes(response[1:3], "little"),
        hardware_revision=int.from_bytes(response[9:11], "little"),
        software_revision=int.from_bytes(response[11:13], "little"),
        integrity_valid=actual_crc == expected_crc,
    )


def parse_vendor_band_functions(data: bytes) -> VendorBandFunctions:
    response = _response(data, 0x20)
    flags = tuple(
        bool(value & (1 << bit))
        for value in response[1:13]
        for bit in range(8)
    )
    return VendorBandFunctions(flags=flags)


def parse_vendor_multi_sport_day(data: bytes) -> VendorMultiSportDay:
    response = _response(data, 0x25)
    base = int.from_bytes(response[1:5], "little")
    samples: list[VendorMultiSportSample] = []
    for index in range(6):
        first = response[5 + (index * 2)]
        second = response[6 + (index * 2)]
        packed = response[17 + (index // 2)]
        type_high = packed & 0xF0 if index % 2 == 0 else (packed & 0x0F) << 4
        samples.append(
            VendorMultiSportSample(
                device_epoch_seconds=base + (index * 60),
                sport_type_code=(first & 0x0F) | type_high,
                value=(second << 4) | (first >> 4),
            )
        )
    return VendorMultiSportDay(device_epoch_seconds=base, samples=tuple(samples))


def parse_vendor_oxygen_day(data: bytes) -> VendorOxygenDay:
    response = _response(data, 0x40)
    base = int.from_bytes(response[1:5], "little")
    samples = tuple(
        VendorOxygenSample(
            device_epoch_seconds=base + (index * 60),
            value=value,
        )
        for index, value in enumerate(response[5:20])
    )
    return VendorOxygenDay(device_epoch_seconds=base, samples=samples)


def parse_vendor_advanced_sensor_day(data: bytes) -> VendorAdvancedSensorDay:
    response = _response(data, 0x55)
    base = int.from_bytes(response[1:5], "little")
    samples = tuple(
        VendorAdvancedSensorSample(
            device_epoch_seconds=base + (index * 900),
            fields=tuple(response[5 + index * 5 : 10 + index * 5]),
        )
        for index in range(3)
    )
    return VendorAdvancedSensorDay(device_epoch_seconds=base, samples=samples)


def parse_vendor_device_action(data: bytes) -> VendorDeviceAction:
    response = _response(data, 0x06, 0x22)
    code = response[1] if response[0] == 0x06 else 5
    label, input_candidate, side_effect = _DEVICE_ACTIONS.get(
        code, ("unknown", False, "unknown")
    )
    return VendorDeviceAction(
        code=code,
        label=label,
        input_candidate=input_candidate,
        side_effect_class=side_effect,
    )


def parse_vendor_step_counter(data: bytes) -> VendorStepCounter:
    response = _response(data, 0x51)
    return VendorStepCounter(
        cumulative_steps=int.from_bytes(response[1:5], "little")
    )


def parse_vendor_device_state(data: bytes) -> VendorDeviceState:
    response = _response(data, 0x3D)
    flags = response[1]
    return VendorDeviceState(
        flag_0=bool(flags & 0x01),
        flag_1=bool(flags & 0x02),
        flag_2=bool(flags & 0x04),
        unused_bits_present=bool(flags & 0xF8),
    )


def parse_vendor_device_dial_custom(data: bytes) -> VendorDeviceDialCustom:
    response = _response(data, 0x42)
    return VendorDeviceDialCustom(values=tuple(response[1:5]))


def parse_vendor_read_current_sport(data: bytes) -> VendorReadCurrentSport:
    response = _response(data, 0x29)
    return VendorReadCurrentSport(
        discriminator=response[1],
        device_epoch_seconds=int.from_bytes(response[2:6], "little"),
        first_value=int.from_bytes(response[6:10], "little"),
        second_value=int.from_bytes(response[10:14], "little"),
    )


def parse_vendor_phone_volume_request(data: bytes) -> VendorPhoneVolumeRequest:
    _response(data, 0x49)
    return VendorPhoneVolumeRequest()


def _subresponse(data: bytes, subcommand: int) -> bytes:
    response = _response(data, 0x78)
    if response[1] != subcommand:
        raise ProtocolError("unexpected vendor response subcommand")
    return response


def parse_vendor_screen_light_time(data: bytes) -> VendorSingleValueState:
    response = _subresponse(data, 0x0B)
    return VendorSingleValueState(value=response[2])


def parse_vendor_touch_mode(data: bytes) -> VendorSingleValueState:
    response = _subresponse(data, 0x09)
    return VendorSingleValueState(value=response[2])


def parse_vendor_worship_info(data: bytes) -> VendorWorshipInfo:
    response = _subresponse(data, 0x07)
    return VendorWorshipInfo(values=(response[2], response[3]))


def parse_vendor_worship_times(data: bytes) -> VendorWorshipTimes:
    response = _subresponse(data, 0x08)
    return VendorWorshipTimes(value=int.from_bytes(response[2:6], "little"))


_KNOWN_78_SUBCOMMANDS = frozenset({0x03, 0x07, 0x08, 0x09, 0x0B, 0x0C})


def parse_vendor_motion_frame(
    data: bytes, *, expected_subcommand: int
) -> VendorMotionFrame:
    if type(expected_subcommand) is not int:
        raise TypeError("expected motion subcommand must be an integer")
    if not 0 <= expected_subcommand <= 0xFF:
        raise ValueError("expected motion subcommand must fit one unsigned byte")
    if expected_subcommand in _KNOWN_78_SUBCOMMANDS:
        raise ProtocolError("known non-motion vendor subcommand")
    response = _subresponse(data, expected_subcommand)
    channels = tuple(
        int.from_bytes(response[offset : offset + 2], "little", signed=True)
        for offset in range(2, 18, 2)
    )
    return VendorMotionFrame(
        subcommand=expected_subcommand,
        channels=channels,
    )
