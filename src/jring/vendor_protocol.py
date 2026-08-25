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


class StaticAckOperation(str, Enum):
    DEVICE_TIME = "device_time"
    USER_INFO = "user_info"
    VIBRATION = "vibration"
    ANTI_LOST = "anti_lost"
    PHONE_MODE = "phone_mode"
    IDLE_TIME = "idle_time"
    SLEEP_TIME = "sleep_time"
    ALARM = "alarm"
    DEVICE_MODE = "device_mode"
    AUTO_HEART = "auto_heart"
    GOAL = "goal"
    DEVICE_INFO_SET = "device_info_set"
    HOUR_FORMAT = "hour_format"
    DEVICE_CODE_SET = "device_code_set"
    LANGUAGE = "language"
    GENERIC_SENSOR_MODE = "generic_sensor_mode"
    HEART_RATE_AREA = "heart_rate_area"
    DEVICE_NAME = "device_name"
    REMINDER = "reminder"
    REMINDER_TEXT = "reminder_text"
    BP_ADJUST = "bp_adjust"
    DEVICE_DIAL_STATE = "device_dial_state"
    WALLPAPER_STATE = "wallpaper_state"
    EDIT_DIAL_CUSTOM = "edit_dial_custom"
    FEMALE_REMINDER = "female_reminder"


class StaticValueEvent(str, Enum):
    TEMPERATURE_MODE = "temperature_mode"
    TEMPERATURE_MODE_CHANGE = "temperature_mode_change"
    BLOOD_OXYGEN_MODE = "blood_oxygen_mode"
    SENSOR_OXYGEN_DATA = "sensor_oxygen_data"


class Static54ValueEvent(str, Enum):
    DEVICE_SYSTEM_STATE = "device_system_state"
    WIFI_AP_STATE = "wifi_ap_state"
    AI_CONNECTION_METHOD = "ai_connection_method"


class Static45Notification(str, Enum):
    CLASSIC_INFO = "classic_info"
    CLASSIC_NAME = "classic_name"
    APP_ID = "app_id"


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

_ACK_OPCODES = {
    StaticAckOperation.DEVICE_TIME: (0x01, 0x81),
    StaticAckOperation.USER_INFO: (0x02, 0x82),
    StaticAckOperation.VIBRATION: (0x04, 0x84),
    StaticAckOperation.ANTI_LOST: (0x05, 0x85),
    StaticAckOperation.PHONE_MODE: (0x07, 0x87),
    StaticAckOperation.IDLE_TIME: (0x08, 0x88),
    StaticAckOperation.SLEEP_TIME: (0x09, 0x89),
    StaticAckOperation.ALARM: (0x0D, 0x8D),
    StaticAckOperation.DEVICE_MODE: (0x0E, 0x8E),
    StaticAckOperation.AUTO_HEART: (0x19, 0x99),
    StaticAckOperation.GOAL: (0x1A, 0x9A),
    StaticAckOperation.DEVICE_INFO_SET: (0x1B, 0x9B),
    StaticAckOperation.HOUR_FORMAT: (0x1D, 0x9D),
    StaticAckOperation.DEVICE_CODE_SET: (0x1E, 0x9E),
    StaticAckOperation.LANGUAGE: (0x21, 0xA1),
    StaticAckOperation.GENERIC_SENSOR_MODE: (0x23, 0xA3),
    StaticAckOperation.HEART_RATE_AREA: (0x26, 0xA6),
    StaticAckOperation.DEVICE_NAME: (0x30, None),
    StaticAckOperation.REMINDER: (0x31, None),
    StaticAckOperation.REMINDER_TEXT: (0x32, None),
    StaticAckOperation.BP_ADJUST: (0x33, None),
    StaticAckOperation.DEVICE_DIAL_STATE: (0x35, None),
    StaticAckOperation.WALLPAPER_STATE: (0x36, None),
    StaticAckOperation.EDIT_DIAL_CUSTOM: (0x41, None),
    StaticAckOperation.FEMALE_REMINDER: (0x44, None),
}
_VALUE_EVENT_OPCODES = {
    StaticValueEvent.TEMPERATURE_MODE: 0x37,
    StaticValueEvent.TEMPERATURE_MODE_CHANGE: 0x3B,
    StaticValueEvent.BLOOD_OXYGEN_MODE: 0x3E,
    StaticValueEvent.SENSOR_OXYGEN_DATA: 0x3F,
}
_54_VALUE_EVENT_SUBCOMMANDS = {
    Static54ValueEvent.DEVICE_SYSTEM_STATE: 0x12,
    Static54ValueEvent.WIFI_AP_STATE: 0x13,
    Static54ValueEvent.AI_CONNECTION_METHOD: 0x14,
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


@dataclass(frozen=True)
class VendorAcknowledgement:
    operation: StaticAckOperation
    success: bool
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorNotifyAcknowledgement:
    success: bool
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorEcgModeAcknowledgement:
    success: bool
    response_mode: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorSensorMeasurement:
    success: bool
    active: bool
    device_epoch_seconds: int
    first_value: int
    second_value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorSensorValues:
    values: tuple[int, int, int, int, int, int, int, int]
    meaning: str = "unknown"
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorSensorStateChange:
    family: int
    state_code: int = 0
    meaning: str = "unknown"
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorValueEvent:
    event: StaticValueEvent
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorTemperatureData:
    values: tuple[int, int]
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorEcgValues:
    kind: str
    discriminator: int
    values: tuple[int, ...]
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorEcgHistoryInfo:
    device_epoch_seconds: int
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorEcgStartEnd:
    first_value: int
    second_value: int
    device_epoch_seconds: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorVoidEvent:
    kind: str
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorDeviceCode:
    success: bool = True
    identifier_redacted: bool = True
    consumed_identifier_bytes: int = 18
    trailing_byte_ignored_by_sdk: bool = True
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorDeviceDial:
    codes: tuple[int, int]
    dimensions: tuple[int, int]
    unit_width: int
    color_mode: int
    custom_flag: int
    dial_id: int
    preview_dimensions: tuple[int, int]
    shape_code: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorDeviceFileState:
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorEqInfo:
    kind: str
    metadata: tuple[int, int]
    values: tuple[int, ...]
    apk_callback_drops_last_value: bool = False
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorFactoryTestData:
    _data: bytes = field(repr=False)
    consumed_bytes: int = 19
    trailing_byte_ignored_by_sdk: bool = True
    hardware_verified: bool = False

    def synthetic_bytes_for_explicit_local_use(self) -> bytes:
        return bytes(self._data)


@dataclass(frozen=True)
class VendorOfflineSpeechMode:
    subcommand: int
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class Vendor54ValueEvent:
    event: Static54ValueEvent
    value: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorBindingInfo:
    values: tuple[int, int]
    meaning: str = "unknown"
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorRedactedTextNotification:
    kind: Static45Notification
    consumed_content_bytes: int = 17
    content_redacted: bool = True
    trailing_byte_ignored_by_sdk: bool = True
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorClassicInfo:
    values: tuple[int, int]
    identifiers_redacted: bool = True
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorRedactedBlob:
    kind: str
    consumed_content_bytes: int
    content_redacted: bool = True
    callback_zero_fills_last_byte: bool = False
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorSmsSend:
    value: int
    declared_text_length: int
    apk_consumed_text_bytes: int
    text_redacted: bool = True
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorWifiState:
    state_code: int
    address_redacted: bool = True
    host_network_action: str = "not_performed"
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorWifiSsidCount:
    count: int
    hardware_verified: bool = False


@dataclass(frozen=True)
class VendorWifiSsid:
    end_flag: bool
    part_id: int
    current_id: int
    signal: int
    _ssid: bytes = field(repr=False)
    hardware_verified: bool = False

    def ssid_for_explicit_local_use(self) -> str:
        return self._ssid.decode("utf-8", errors="strict")


class VendorWifiSsidAssembler:
    def __init__(self, *, max_encoded_bytes: int = 256):
        if type(max_encoded_bytes) is not int:
            raise TypeError("maximum SSID bytes must be an integer")
        if not 1 <= max_encoded_bytes <= 4096:
            raise ValueError("maximum SSID bytes must be between 1 and 4096")
        self._maximum = max_encoded_bytes
        self._buffer = bytearray()
        self._current_id: int | None = None

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def reset(self) -> None:
        self._buffer.clear()
        self._current_id = None

    def feed(self, data: bytes) -> VendorWifiSsid | None:
        response = _response(data, 0x54)
        if response[1] != 0x0A:
            raise ProtocolError("unexpected vendor Wi-Fi SSID subcommand")
        flags = response[2]
        part_id = (flags >> 6) & 0x01
        current_id = flags & 0x3F
        if part_id == 0:
            self.reset()
            self._current_id = current_id
        elif self._current_id != current_id:
            self.reset()
            raise ProtocolError("vendor Wi-Fi SSID fragment sequence mismatch")
        content = response[4:20].split(b"\x00", 1)[0]
        if len(self._buffer) + len(content) > self._maximum:
            self.reset()
            raise ProtocolError("vendor Wi-Fi SSID exceeds configured bound")
        self._buffer.extend(content)
        if not flags & 0x80:
            return None
        result = VendorWifiSsid(
            end_flag=True,
            part_id=part_id,
            current_id=current_id,
            signal=response[3] - 256 if response[3] >= 128 else response[3],
            _ssid=bytes(self._buffer),
        )
        self.reset()
        return result


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


def parse_vendor_ack(
    data: bytes, operation: StaticAckOperation
) -> VendorAcknowledgement:
    if not isinstance(operation, StaticAckOperation):
        raise TypeError("acknowledgement operation must be a StaticAckOperation")
    success_opcode, failure_opcode = _ACK_OPCODES[operation]
    allowed = (
        (success_opcode,)
        if failure_opcode is None
        else (success_opcode, failure_opcode)
    )
    response = _response(data, *allowed)
    return VendorAcknowledgement(
        operation=operation,
        success=response[0] == success_opcode,
    )


def parse_vendor_notify_ack(
    data: bytes, *, expected_marker: int
) -> VendorNotifyAcknowledgement:
    if type(expected_marker) is not int:
        raise TypeError("expected notification marker must be an integer")
    if not 0 <= expected_marker <= 0xFF:
        raise ValueError("expected notification marker must fit one unsigned byte")
    response = _response(data, 0x12, 0x92)
    if response[0] == 0x12 and response[2] != expected_marker:
        raise ProtocolError("vendor notification acknowledgement marker mismatch")
    return VendorNotifyAcknowledgement(success=response[0] == 0x12)


def parse_vendor_ecg_mode_ack(data: bytes) -> VendorEcgModeAcknowledgement:
    response = _response(data, 0x2A)
    return VendorEcgModeAcknowledgement(
        success=True,
        response_mode=response[1],
    )


def parse_vendor_sensor_measurement(data: bytes) -> VendorSensorMeasurement:
    response = _response(data, 0x14, 0x15, 0x94, 0x95)
    if response[0] == 0x14:
        return VendorSensorMeasurement(
            success=True,
            active=True,
            device_epoch_seconds=int.from_bytes(response[1:5], "little"),
            first_value=response[5],
            second_value=response[6],
        )
    return VendorSensorMeasurement(
        success=response[0] == 0x15,
        active=response[0] in {0x14, 0x94},
        device_epoch_seconds=0,
        first_value=0,
        second_value=0,
    )


def parse_vendor_sensor_values(data: bytes) -> VendorSensorValues:
    response = _response(data, 0x24)
    return VendorSensorValues(values=tuple(response[1:9]))


def parse_vendor_sensor_state_change(data: bytes) -> VendorSensorStateChange:
    response = _response(data, 0x27, 0x28)
    return VendorSensorStateChange(family=1 if response[0] == 0x27 else 2)


def parse_vendor_value_event(
    data: bytes, event: StaticValueEvent
) -> VendorValueEvent:
    if not isinstance(event, StaticValueEvent):
        raise TypeError("value event must be a StaticValueEvent")
    response = _response(data, _VALUE_EVENT_OPCODES[event])
    return VendorValueEvent(event=event, value=response[1])


def parse_vendor_temperature_data(data: bytes) -> VendorTemperatureData:
    response = _response(data, 0x38)
    return VendorTemperatureData(
        values=(
            int.from_bytes(response[1:3], "little"),
            int.from_bytes(response[3:5], "little"),
        )
    )


def parse_vendor_ecg_values(data: bytes, *, kind: str) -> VendorEcgValues:
    if kind not in {"live", "history"}:
        raise ValueError("ECG value kind must be live or history")
    response = _response(data, 0x2B if kind == "live" else 0x2E)
    values = []
    for offset in range(2, 20, 3):
        first, middle, third = response[offset : offset + 3]
        values.extend((first | ((middle & 0x0F) << 8), (middle >> 4) | (third << 4)))
    return VendorEcgValues(
        kind=kind,
        discriminator=response[1],
        values=tuple(values),
    )


def parse_vendor_ecg_history_info(data: bytes) -> VendorEcgHistoryInfo:
    response = _response(data, 0x2C)
    return VendorEcgHistoryInfo(
        device_epoch_seconds=int.from_bytes(response[1:5], "little"),
        value=response[5],
    )


def parse_vendor_ecg_start_end(data: bytes) -> VendorEcgStartEnd:
    response = _response(data, 0x2D)
    return VendorEcgStartEnd(
        first_value=response[1],
        second_value=response[2],
        device_epoch_seconds=int.from_bytes(response[3:7], "little"),
    )


def parse_vendor_device_test_event(data: bytes) -> VendorVoidEvent:
    _response(data, 0x3A)
    return VendorVoidEvent(kind="device_test_command")


def parse_vendor_chat_action(data: bytes) -> VendorSingleValueState:
    response = _response(data, 0x4E)
    return VendorSingleValueState(value=response[1])


def parse_vendor_device_code(data: bytes) -> VendorDeviceCode:
    response = _response(data, 0x1F, 0x9F)
    return VendorDeviceCode(
        success=response[0] == 0x1F,
        consumed_identifier_bytes=18 if response[0] == 0x1F else 0,
    )


def parse_vendor_device_dial(data: bytes) -> VendorDeviceDial:
    response = _response(data, 0x34)
    return VendorDeviceDial(
        codes=(
            int.from_bytes(response[1:3], "little"),
            int.from_bytes(response[3:5], "little"),
        ),
        dimensions=(
            int.from_bytes(response[5:7], "little"),
            int.from_bytes(response[7:9], "little"),
        ),
        unit_width=int.from_bytes(response[9:11], "little"),
        color_mode=response[11],
        custom_flag=response[12],
        dial_id=int.from_bytes(response[13:15], "little"),
        preview_dimensions=(
            int.from_bytes(response[15:17], "little"),
            int.from_bytes(response[17:19], "little"),
        ),
        shape_code=response[19],
    )


def parse_vendor_device_file_state(data: bytes) -> VendorDeviceFileState:
    response = _response(data, 0x54)
    if response[1] != 0x06:
        raise ProtocolError("unexpected vendor file-state subcommand")
    value = int.from_bytes(response[2:6], "little")
    if value > 0x7FFFFFFF:
        raise ProtocolError("vendor file-state value exceeds APK signed range")
    return VendorDeviceFileState(value=value)


def parse_vendor_eq_info(data: bytes, *, expected_kind: str) -> VendorEqInfo:
    if expected_kind not in {"set", "get"}:
        raise ValueError("EQ response kind must be set or get")
    response = _response(data, 0x53)
    actual_kind = "set" if response[1] == 0 else "get"
    if actual_kind != expected_kind:
        raise ProtocolError("unexpected vendor EQ response kind")
    count = response[4]
    if count > 15:
        raise ProtocolError("vendor EQ value count exceeds wire capacity")
    values = tuple(
        value - 256 if value >= 128 else value
        for value in response[5 : 5 + count]
    )
    return VendorEqInfo(
        kind=actual_kind,
        metadata=(response[2], response[3]),
        values=values,
        apk_callback_drops_last_value=count == 15,
    )


def parse_vendor_factory_test_data(data: bytes) -> VendorFactoryTestData:
    response = _response(data, 0x50)
    return VendorFactoryTestData(_data=bytes(response[:19]))


def parse_vendor_offline_speech_mode(data: bytes) -> VendorOfflineSpeechMode:
    response = _response(data, 0x78)
    if response[1] not in {0x03, 0x0C}:
        raise ProtocolError("unexpected offline speech response subcommand")
    return VendorOfflineSpeechMode(subcommand=response[1], value=response[2])


def parse_vendor_54_value_event(
    data: bytes, event: Static54ValueEvent
) -> Vendor54ValueEvent:
    if not isinstance(event, Static54ValueEvent):
        raise TypeError("54 value event must be a Static54ValueEvent")
    response = _response(data, 0x54)
    if response[1] != _54_VALUE_EVENT_SUBCOMMANDS[event]:
        raise ProtocolError("unexpected vendor 54 response subcommand")
    return Vendor54ValueEvent(event=event, value=response[2])


def parse_vendor_binding_info(data: bytes) -> VendorBindingInfo:
    response = _response(data, 0x4B)
    return VendorBindingInfo(values=(response[1], response[2]))


_45_SELECTORS = {
    Static45Notification.CLASSIC_INFO: 0,
    Static45Notification.CLASSIC_NAME: 1,
    Static45Notification.APP_ID: 2,
}


def parse_vendor_45_notification(
    data: bytes, *, expected_kind: Static45Notification
) -> VendorClassicInfo | VendorRedactedTextNotification:
    if not isinstance(expected_kind, Static45Notification):
        raise TypeError("45 notification kind must be a Static45Notification")
    response = _response(data, 0x45)
    if response[1] != _45_SELECTORS[expected_kind]:
        raise ProtocolError("unexpected vendor 45 notification selector")
    if expected_kind is Static45Notification.CLASSIC_INFO:
        return VendorClassicInfo(values=(response[2], response[3]))
    return VendorRedactedTextNotification(kind=expected_kind)


def parse_vendor_contact_crc(data: bytes) -> VendorRedactedBlob:
    _response(data, 0x46)
    return VendorRedactedBlob(kind="contact_crc", consumed_content_bytes=4)


def _private_update_blob(data: bytes, *, opcode: int, kind: str) -> VendorRedactedBlob:
    response = _response(data, opcode)
    if response[1] != 0x03:
        raise ProtocolError("unexpected private update notification selector")
    return VendorRedactedBlob(
        kind=kind,
        consumed_content_bytes=17,
        callback_zero_fills_last_byte=True,
    )


def parse_vendor_e_card_need_update(data: bytes) -> VendorRedactedBlob:
    return _private_update_blob(data, opcode=0x4C, kind="e_card_need_update")


def parse_vendor_sms_need_update(data: bytes) -> VendorRedactedBlob:
    return _private_update_blob(data, opcode=0x4D, kind="sms_need_update")


def parse_vendor_sms_send(data: bytes) -> VendorSmsSend:
    response = _response(data, 0x4D)
    if response[1] != 0x06:
        raise ProtocolError("unexpected SMS send notification selector")
    declared = response[3]
    if declared > 15:
        raise ProtocolError("vendor SMS text length exceeds wire capacity")
    return VendorSmsSend(
        value=response[2],
        declared_text_length=declared,
        apk_consumed_text_bytes=min(15, declared + 1),
    )


def parse_vendor_wifi_state(data: bytes) -> VendorWifiState:
    response = _response(data, 0x54)
    if response[1] != 0x04:
        raise ProtocolError("unexpected vendor Wi-Fi state subcommand")
    return VendorWifiState(state_code=response[2])


def parse_vendor_wifi_ssid_count(data: bytes) -> VendorWifiSsidCount:
    response = _response(data, 0x54)
    if response[1] != 0x09:
        raise ProtocolError("unexpected vendor Wi-Fi count subcommand")
    return VendorWifiSsidCount(count=response[2])
