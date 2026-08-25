"""Bounded offline model of a future vendor GATT transaction engine.

The objects in this module describe and simulate ordering; they cannot access a radio,
subscribe, unsubscribe, or write.  In particular, a returned write intent is test data
rather than authorization to send its bytes to hardware.  Planning and confirming a
live notification-unsubscribe operation remains a live-adapter blocker outside this
offline slice.  Notification readiness is intentionally modeled at the subscription
API level: this module never claims that a client observed a CCCD write or
acknowledgement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from functools import partial
import itertools
from weakref import WeakKeyDictionary
import math
from typing import Callable
from uuid import UUID

from .protocol import ProtocolError
from .uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4
from .vendor_protocol import (
    StaticAckOperation,
    Static54ValueEvent,
    StaticQuery,
    StaticVendorRequest,
    encode_static_query,
    operation_opcode,
    parse_vendor_ack,
    parse_vendor_band_functions,
    parse_vendor_battery,
    parse_vendor_current_sport,
    parse_vendor_device_info,
    parse_vendor_device_code,
    parse_vendor_device_dial,
    parse_vendor_device_dial_custom,
    parse_vendor_device_file_state,
    parse_vendor_eq_info,
    parse_vendor_offline_speech_mode,
    parse_vendor_screen_light_time,
    parse_vendor_sensor_measurement,
    parse_vendor_54_value_event,
    static_protocol_coverage,
)
from .vendor_settings import (
    StaticVendorSettingOperation,
    StaticVendorSettingRequest,
)
from .vendor_personal_settings import (
    OfflinePersonalSettingRequest,
    PersonalSettingOperation,
)
from .vendor_behavior_settings import (
    AlarmBatchRequest,
    AntiLostRequest,
    AutoHeartScheduleRequest,
    CameraModeRequest,
    ClockTime,
    DeviceMode,
    DeviceModeRequest,
    GoalStepRequest,
    IdleReminderRequest,
    SleepScheduleRequest,
    VibrationRequest,
)
from .vendor_main_commands import (
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
    ScreenLightTimeRequest,
)
from .vendor_commands import (
    StaticVendorCommandOperation,
    StaticVendorCommandRequest,
)
from .vendor_phone_integration import OfflinePhoneOperation, OfflinePhoneRequest
from .vendor_runtime_eligibility import (
    fake_singleton_terminal_request_names,
    require_fake_singleton_terminal,
)

_ENGINE_IDS = itertools.count()


class EnginePhase(str, Enum):
    DISCONNECTED = "disconnected"
    SUBSCRIPTION_REQUIRED = "subscription_required"
    READY = "ready"
    RECONNECT_REQUIRED = "reconnect_required"


class NotificationSubscriptionOutcome(str, Enum):
    """Result of the transport's high-level subscription call only."""

    TRANSPORT_CALL_COMPLETED = "transport_call_completed"
    FAILED = "failed"


class WriteOutcome(str, Enum):
    ACKNOWLEDGED = "acknowledged"
    DEFINITELY_NOT_DISPATCHED = "definitely_not_dispatched"
    OUTCOME_UNKNOWN = "outcome_unknown"


class NotificationDisposition(str, Enum):
    MATCHED_SUCCESS = "matched_success"
    MATCHED_FAILURE = "matched_failure"
    UNRELATED = "unrelated"
    STALE = "stale"
    NOT_IN_FLIGHT = "not_in_flight"
    TIMED_OUT = "timed_out"
    MALFORMED = "malformed"


class TransactionCloseReason(str, Enum):
    SUCCESS = "success"
    DEVICE_FAILURE = "device_failure"
    TIMEOUT = "timeout"
    WRITE_FAILURE = "write_failure"
    SUBSCRIPTION_FAILURE = "subscription_failure"
    MALFORMED_RESPONSE = "malformed_response"
    CANCELLED = "cancelled"
    DISCONNECTED = "disconnected"


class TransactionCompleteness(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"
    UNCERTAIN = "uncertain"


class _Match(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNRELATED = "unrelated"


def _normalize_uuid(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a UUID string")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ValueError(f"{label} must be a valid UUID") from exc


_STATIC_RESPONSE_PARSERS: dict[StaticQuery, Callable[[bytes], object]] = {
    StaticQuery.CURRENT_SPORT: parse_vendor_current_sport,
    StaticQuery.BATTERY: parse_vendor_battery,
    StaticQuery.DEVICE_INFO: parse_vendor_device_info,
    StaticQuery.BAND_FUNCTIONS: parse_vendor_band_functions,
}
_ZERO_ARGUMENT_QUERIES = frozenset(
    {
        StaticQuery.CURRENT_SPORT,
        StaticQuery.BATTERY,
        StaticQuery.DEVICE_INFO,
        StaticQuery.BAND_FUNCTIONS,
    }
)
_STATIC_QUERY_REQUEST_NAMES = {
    StaticQuery.CURRENT_SPORT: "getCurSportData",
    StaticQuery.BATTERY: "getDeviceBatery",
    StaticQuery.DEVICE_INFO: "getDeviceInfo",
    StaticQuery.BAND_FUNCTIONS: "getBandFunction",
}

_SETTING_ACKS = {
    StaticVendorSettingOperation.DEVICE_SETTINGS: StaticAckOperation.DEVICE_INFO_SET,
    StaticVendorSettingOperation.HOUR_FORMAT: StaticAckOperation.HOUR_FORMAT,
    StaticVendorSettingOperation.DEVICE_CODE: StaticAckOperation.DEVICE_CODE_SET,
    StaticVendorSettingOperation.LANGUAGE: StaticAckOperation.LANGUAGE,
    StaticVendorSettingOperation.HEART_RATE_AREA: StaticAckOperation.HEART_RATE_AREA,
    StaticVendorSettingOperation.DEVICE_NAME: StaticAckOperation.DEVICE_NAME,
}
_SETTING_REQUEST_OPCODES = {
    StaticVendorSettingOperation.DEVICE_SETTINGS: 0x1B,
    StaticVendorSettingOperation.HOUR_FORMAT: 0x1D,
    StaticVendorSettingOperation.DEVICE_CODE: 0x1E,
    StaticVendorSettingOperation.LANGUAGE: 0x21,
    StaticVendorSettingOperation.SENSOR_SESSION_START: 0x23,
    StaticVendorSettingOperation.SENSOR_SESSION_STOP: 0x23,
    StaticVendorSettingOperation.HEART_RATE_AREA: 0x26,
    StaticVendorSettingOperation.DEVICE_NAME: 0x30,
}
_SETTING_REQUEST_NAMES = {
    StaticVendorSettingOperation.DEVICE_SETTINGS: "setDeviceInfo",
    StaticVendorSettingOperation.HOUR_FORMAT: "setHourFormat",
    StaticVendorSettingOperation.DEVICE_CODE: "setDeviceCode",
    StaticVendorSettingOperation.LANGUAGE: "setLanguage",
    StaticVendorSettingOperation.SENSOR_SESSION_START: "setBloodPressureMode",
    StaticVendorSettingOperation.SENSOR_SESSION_STOP: "setBloodPressureMode",
    StaticVendorSettingOperation.HEART_RATE_AREA: "setDeviceHeartRateArea",
    StaticVendorSettingOperation.DEVICE_NAME: "setDeviceName",
}
_PERSONAL_ACKS = {
    PersonalSettingOperation.REMINDER: StaticAckOperation.REMINDER,
    PersonalSettingOperation.REMINDER_TEXT: StaticAckOperation.REMINDER_TEXT,
    PersonalSettingOperation.BP_ADJUST: StaticAckOperation.BP_ADJUST,
    PersonalSettingOperation.DEVICE_DIAL_STATE: StaticAckOperation.DEVICE_DIAL_STATE,
    PersonalSettingOperation.DEVICE_WALLPAPER_STATE: StaticAckOperation.WALLPAPER_STATE,
    PersonalSettingOperation.EDIT_DEVICE_DIAL_CUSTOM: StaticAckOperation.EDIT_DIAL_CUSTOM,
    PersonalSettingOperation.FEMALE_REMINDER: StaticAckOperation.FEMALE_REMINDER,
}
_PERSONAL_REQUEST_OPCODES = {
    PersonalSettingOperation.REMINDER: 0x31,
    PersonalSettingOperation.REMINDER_TEXT: 0x32,
    PersonalSettingOperation.BP_ADJUST: 0x33,
    PersonalSettingOperation.DEVICE_DIAL_STATE: 0x35,
    PersonalSettingOperation.DEVICE_WALLPAPER_STATE: 0x36,
    PersonalSettingOperation.EDIT_DEVICE_DIAL_CUSTOM: 0x41,
    PersonalSettingOperation.FEMALE_REMINDER: 0x44,
}
_PERSONAL_REQUEST_NAMES = {
    PersonalSettingOperation.REMINDER: "setReminder",
    PersonalSettingOperation.REMINDER_TEXT: "setReminderText",
    PersonalSettingOperation.BP_ADJUST: "setBPAdjust",
    PersonalSettingOperation.DEVICE_DIAL_STATE: "setDeviceDialState",
    PersonalSettingOperation.DEVICE_WALLPAPER_STATE: "setDeviceWallpaperState",
    PersonalSettingOperation.EDIT_DEVICE_DIAL_CUSTOM: "editDeviceDialCustom",
    PersonalSettingOperation.FEMALE_REMINDER: "setFemaleReminder",
}
_BEHAVIOR_ACKS = {
    VibrationRequest: ("vibration", 0x04, StaticAckOperation.VIBRATION),
    AntiLostRequest: ("anti_lost", 0x05, StaticAckOperation.ANTI_LOST),
    CameraModeRequest: ("camera_mode", 0x07, StaticAckOperation.PHONE_MODE),
    IdleReminderRequest: ("idle_reminder", 0x08, StaticAckOperation.IDLE_TIME),
    SleepScheduleRequest: ("sleep_schedule", 0x09, StaticAckOperation.SLEEP_TIME),
    DeviceModeRequest: ("device_mode", 0x0E, StaticAckOperation.DEVICE_MODE),
    AutoHeartScheduleRequest: (
        "auto_heart_schedule", 0x19, StaticAckOperation.AUTO_HEART,
    ),
    GoalStepRequest: ("goal_step", 0x1A, StaticAckOperation.GOAL),
}
_BEHAVIOR_REQUEST_NAMES = {
    VibrationRequest: "sendVibrationSignal",
    AntiLostRequest: "setAntiLost",
    CameraModeRequest: "setPhontMode",
    IdleReminderRequest: "setIdleTime",
    SleepScheduleRequest: "setSleepTime",
    DeviceModeRequest: "setDeviceMode",
    AutoHeartScheduleRequest: "setAutoHeartMode",
    GoalStepRequest: "setGoalStep",
}


def _canonical_behavior_frame(request: object) -> bytes:
    """Rebuild one accepted behavior request through its validating constructor."""

    def clock(value: object, label: str) -> ClockTime:
        if type(value) is not ClockTime:
            raise TypeError(f"{label} must be a ClockTime")
        return ClockTime(value.hour, value.minute)

    if type(request) is VibrationRequest:
        canonical = VibrationRequest(request.count)
    elif type(request) is AntiLostRequest:
        canonical = AntiLostRequest(request.enabled)
    elif type(request) is CameraModeRequest:
        canonical = CameraModeRequest(request.enabled)
    elif type(request) is IdleReminderRequest:
        start = clock(request._start, "idle start")
        end = clock(request._end, "idle end")
        if request._interval_seconds == 0:
            canonical = IdleReminderRequest.disabled(start=start, end=end)
        else:
            if request._interval_seconds % 60:
                raise ValueError("idle interval seconds must preserve whole minutes")
            canonical = IdleReminderRequest.enabled(
                interval_minutes=request._interval_seconds // 60,
                start=start,
                end=end,
            )
    elif type(request) is SleepScheduleRequest:
        canonical = SleepScheduleRequest(
            clock(request.noon_start, "noon start"),
            clock(request.noon_end, "noon end"),
            clock(request.night_start, "night start"),
            clock(request.night_end, "night end"),
        )
    elif type(request) is DeviceModeRequest:
        if type(request.mode) is not DeviceMode:
            raise TypeError("device mode must be a DeviceMode")
        canonical = DeviceModeRequest(request.mode)
    elif type(request) is AutoHeartScheduleRequest:
        canonical = AutoHeartScheduleRequest(
            request.enabled,
            clock(request.start, "automatic heart start"),
            clock(request.end, "automatic heart end"),
            request.interval_minutes,
        )
    elif type(request) is GoalStepRequest:
        canonical = GoalStepRequest(request.steps)
    else:
        raise TypeError("request must be a closed single-frame behavior request")
    frames = canonical.frames()
    if len(frames) != 1:
        raise ValueError("single-frame behavior request produced an invalid batch")
    return frames[0].synthetic_bytes_for_test()


_NO_ARGUMENT_MAIN_RESPONSES = {
    NoArgumentMainCommand.DEVICE_CODE: (
        (0x1F,), (0x9F,), None, parse_vendor_device_code,
    ),
    NoArgumentMainCommand.DEVICE_DIAL: (
        (0x34,), (), None, parse_vendor_device_dial,
    ),
    NoArgumentMainCommand.DEVICE_DIAL_CUSTOM: (
        (0x42,), (), None, parse_vendor_device_dial_custom,
    ),
    NoArgumentMainCommand.DEVICE_SYSTEM_STATE: (
        (0x54,), (), 0x12,
        partial(parse_vendor_54_value_event, event=Static54ValueEvent.DEVICE_SYSTEM_STATE),
    ),
    NoArgumentMainCommand.EQ_INFO: (
        (0x53,), (), None, partial(parse_vendor_eq_info, expected_kind="get"),
    ),
    NoArgumentMainCommand.MEDIA_FILE_STATE: (
        (0x54,), (), 0x06, parse_vendor_device_file_state,
    ),
    NoArgumentMainCommand.OFFLINE_SPEECH_STATE: (
        (0x78,), (), 0x0C, parse_vendor_offline_speech_mode,
    ),
}
_NO_ARGUMENT_REQUEST_NAMES = {
    NoArgumentMainCommand.DEVICE_CODE: "getDeviceCode",
    NoArgumentMainCommand.DEVICE_DIAL: "getDeviceDial",
    NoArgumentMainCommand.DEVICE_DIAL_CUSTOM: "getDeviceDialCustom",
    NoArgumentMainCommand.DEVICE_SYSTEM_STATE: "getDeviceSystemStateInfo",
    NoArgumentMainCommand.EQ_INFO: "getEqInfo",
    NoArgumentMainCommand.MEDIA_FILE_STATE: "getMediaFileState",
    NoArgumentMainCommand.OFFLINE_SPEECH_STATE: (
        "queryOfflineSpeechRecognitionState"
    ),
}
_COMMAND_RESPONSES = {
    StaticVendorCommandOperation.DEVICE_TIME: (
        0x01, (0x01,), (0x81,), None,
        partial(parse_vendor_ack, operation=StaticAckOperation.DEVICE_TIME),
    ),
    StaticVendorCommandOperation.HEART_RATE_SESSION_START: (
        0x14, (0x14,), (0x94,), None, parse_vendor_sensor_measurement,
    ),
    StaticVendorCommandOperation.HEART_RATE_SESSION_STOP: (
        0x15, (0x15,), (0x95,), None, parse_vendor_sensor_measurement,
    ),
}
_COMMAND_REQUEST_NAMES = {
    StaticVendorCommandOperation.DEVICE_TIME: "setDeviceTime",
    StaticVendorCommandOperation.ECG_MODE: "setEcgMode",
    StaticVendorCommandOperation.EQ_INFO: "setEqInfo2",
    StaticVendorCommandOperation.HEART_RATE_SESSION_START: "setHeartRateMode",
    StaticVendorCommandOperation.HEART_RATE_SESSION_STOP: "setHeartRateMode",
    StaticVendorCommandOperation.OFFLINE_SPEECH_RECOGNITION: (
        "setOfflineSpeechRecognitionState"
    ),
    StaticVendorCommandOperation.TEMPERATURE_MODE: "setTemperatureMode",
    StaticVendorCommandOperation.TOUCH_MODE: "setTouchMode",
    StaticVendorCommandOperation.FACTORY_TEST_MODE: "startFactoryTestMode",
    StaticVendorCommandOperation.AI_CONNECTION_METHOD: "setAiConnectionMethod",
    StaticVendorCommandOperation.BINDING_INFO: "setBindedInfo",
    StaticVendorCommandOperation.BLOOD_OXYGEN_MODE: "setBloodOxygenMode",
}
_PHONE_RESPONSES = {
    OfflinePhoneOperation.USER_INFO: (
        0x02, (0x02,), (0x82,), None,
        partial(parse_vendor_ack, operation=StaticAckOperation.USER_INFO),
    ),
}
_PHONE_REQUEST_NAMES = {
    OfflinePhoneOperation.USER_INFO: "setUserInfo",
    OfflinePhoneOperation.OPEN_WIFI_AP_MODE: "openWifiApMode",
    OfflinePhoneOperation.WORSHIP_INFO: "setWorshipInfo",
}


def fake_singleton_factory_request_names() -> frozenset[str]:
    """Return the public request rows bound by singleton operation factories."""

    return frozenset(
        {
            *(_STATIC_QUERY_REQUEST_NAMES[item] for item in _ZERO_ARGUMENT_QUERIES),
            *(_SETTING_REQUEST_NAMES[item] for item in _SETTING_ACKS),
            *(_PERSONAL_REQUEST_NAMES[item] for item in _PERSONAL_ACKS),
            *(_BEHAVIOR_REQUEST_NAMES[item] for item in _BEHAVIOR_ACKS),
            *(
                _NO_ARGUMENT_REQUEST_NAMES[item]
                for item in _NO_ARGUMENT_MAIN_RESPONSES
            ),
            *(_COMMAND_REQUEST_NAMES[item] for item in _COMMAND_RESPONSES),
            *(_PHONE_REQUEST_NAMES[item] for item in _PHONE_RESPONSES),
            "SetScreenLightTime",
        }
    )


if fake_singleton_factory_request_names() != fake_singleton_terminal_request_names():
    raise RuntimeError(
        "fake singleton factories do not match the closed terminal eligibility ledger"
    )


class _OperationIntegrityToken:
    pass


@dataclass(frozen=True)
class _OperationExecutionShape:
    name: str
    request_endpoint_uuid: str
    response_endpoint_uuid: str
    request_frame: bytes
    success_opcodes: tuple[int, ...]
    failure_opcodes: tuple[int, ...]
    expected_subcommand: int | None
    excluded_subcommands: tuple[int, ...]
    parser: Callable[[bytes], object] = field(compare=False, repr=False)


_OPERATION_EXECUTION_SHAPES: WeakKeyDictionary[
    _OperationIntegrityToken, _OperationExecutionShape
] = WeakKeyDictionary()


@dataclass(frozen=True, init=False, repr=False)
class OfflineVendorOperation:
    name: str
    request_endpoint_uuid: str
    response_endpoint_uuid: str
    _request_frame: bytes = field(repr=False)
    _execution_token: _OperationIntegrityToken = field(repr=False, compare=False)
    success_opcodes: tuple[int, ...]
    failure_opcodes: tuple[int, ...]
    expected_subcommand: int | None
    excluded_subcommands: tuple[int, ...]
    _parser: Callable[[bytes], object] = field(repr=False, compare=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("use a closed OfflineVendorOperation factory")

    @classmethod
    def _create(
        cls,
        *,
        name: str,
        request_frame: bytes,
        success_opcodes: tuple[int, ...],
        failure_opcodes: tuple[int, ...],
        expected_subcommand: int | None,
        parser: Callable[[bytes], object],
        excluded_subcommands: tuple[int, ...] = (),
    ) -> "OfflineVendorOperation":
        instance = object.__new__(cls)
        object.__setattr__(instance, "name", name)
        object.__setattr__(instance, "request_endpoint_uuid", VENDOR_CHARACTERISTIC_33F3)
        object.__setattr__(instance, "response_endpoint_uuid", VENDOR_CHARACTERISTIC_33F4)
        object.__setattr__(instance, "_request_frame", bytes(request_frame))
        object.__setattr__(instance, "success_opcodes", tuple(success_opcodes))
        object.__setattr__(instance, "failure_opcodes", tuple(failure_opcodes))
        object.__setattr__(instance, "expected_subcommand", expected_subcommand)
        object.__setattr__(
            instance, "excluded_subcommands", tuple(excluded_subcommands)
        )
        object.__setattr__(instance, "_parser", parser)
        token = _OperationIntegrityToken()
        object.__setattr__(instance, "_execution_token", token)
        _OPERATION_EXECUTION_SHAPES[token] = _OperationExecutionShape(
            name=name,
            request_endpoint_uuid=VENDOR_CHARACTERISTIC_33F3,
            response_endpoint_uuid=VENDOR_CHARACTERISTIC_33F4,
            request_frame=bytes(request_frame),
            success_opcodes=tuple(success_opcodes),
            failure_opcodes=tuple(failure_opcodes),
            expected_subcommand=expected_subcommand,
            excluded_subcommands=tuple(excluded_subcommands),
            parser=parser,
        )
        return instance

    def validate_for_fake_execution(self) -> None:
        """Reject a closed operation whose executable request shape was mutated."""

        if type(self._execution_token) is not _OperationIntegrityToken:
            raise ValueError("offline operation execution identity was mutated")
        expected = _OPERATION_EXECUTION_SHAPES.get(self._execution_token)
        if expected is None:
            raise ValueError("offline operation execution identity is unavailable")
        if (
            self.name != expected.name
            or self.request_endpoint_uuid != expected.request_endpoint_uuid
            or self.response_endpoint_uuid != expected.response_endpoint_uuid
            or type(self._request_frame) is not bytes
            or self._request_frame != expected.request_frame
            or self.success_opcodes != expected.success_opcodes
            or self.failure_opcodes != expected.failure_opcodes
            or self.expected_subcommand != expected.expected_subcommand
            or self.excluded_subcommands != expected.excluded_subcommands
            or self._parser is not expected.parser
        ):
            raise ValueError("offline operation execution shape was mutated")

    @classmethod
    def from_static_request(
        cls, request: StaticVendorRequest
    ) -> "OfflineVendorOperation":
        """Build only from one of the closed, offline static-query encoders."""

        if type(request) is not StaticVendorRequest:
            raise TypeError("request must be a StaticVendorRequest")
        if not isinstance(request.operation, StaticQuery):
            raise TypeError("request operation must be a StaticQuery")
        if request.operation not in _ZERO_ARGUMENT_QUERIES:
            raise TypeError(
                "streaming day query requires a separate collection state machine"
            )
        require_fake_singleton_terminal(_STATIC_QUERY_REQUEST_NAMES[request.operation])
        frame = request.synthetic_bytes_for_test()
        if len(frame) != 20 or frame[0] != operation_opcode(request.operation):
            raise ValueError("static request does not match its operation opcode")
        expected = encode_static_query(request.operation).synthetic_bytes_for_test()
        if frame != expected:
            raise ValueError("static zero-argument request has an invalid shape")

        coverage = next(
            item
            for item in static_protocol_coverage()
            if item.operation is request.operation
        )
        return cls._create(
            name=request.operation.value,
            request_frame=frame,
            success_opcodes=coverage.success_opcodes,
            failure_opcodes=coverage.failure_opcodes,
            expected_subcommand=None,
            parser=_STATIC_RESPONSE_PARSERS[request.operation],
        )

    @classmethod
    def from_setting_request(
        cls, request: StaticVendorSettingRequest
    ) -> "OfflineVendorOperation":
        """Compose a fake-only matcher from a closed typed settings encoder."""

        if type(request) is not StaticVendorSettingRequest:
            raise TypeError("request must be a StaticVendorSettingRequest")
        StaticVendorSettingRequest.validate_for_fake_execution(request)
        if not isinstance(request.operation, StaticVendorSettingOperation):
            raise TypeError("request operation must be a StaticVendorSettingOperation")
        require_fake_singleton_terminal(_SETTING_REQUEST_NAMES[request.operation])
        frame = StaticVendorSettingRequest.synthetic_bytes_for_test(request)
        expected_opcode = _SETTING_REQUEST_OPCODES[request.operation]
        if len(frame) != 20 or frame[0] != expected_opcode:
            raise ValueError("setting request does not match its closed operation")
        success = (request.response_success_opcode,)
        if request.operation in {
            StaticVendorSettingOperation.SENSOR_SESSION_START,
            StaticVendorSettingOperation.SENSOR_SESSION_STOP,
        }:
            success += (0x25,)
        failure = (
            ()
            if request.response_failure_opcode is None
            else (request.response_failure_opcode,)
        )
        ack_operation = _SETTING_ACKS[request.operation]
        return cls._create(
            name=request.operation.value,
            request_frame=frame,
            success_opcodes=success,
            failure_opcodes=failure,
            expected_subcommand=None,
            parser=partial(parse_vendor_ack, operation=ack_operation),
        )

    @classmethod
    def from_personal_setting_request(
        cls, request: OfflinePersonalSettingRequest
    ) -> "OfflineVendorOperation":
        """Compose a success-only fake matcher from a closed personal encoder."""

        if type(request) is not OfflinePersonalSettingRequest:
            raise TypeError("request must be an OfflinePersonalSettingRequest")
        OfflinePersonalSettingRequest.validate_for_fake_execution(request)
        if not isinstance(request.operation, PersonalSettingOperation):
            raise TypeError("request operation must be a PersonalSettingOperation")
        require_fake_singleton_terminal(_PERSONAL_REQUEST_NAMES[request.operation])
        frame = OfflinePersonalSettingRequest.synthetic_bytes_for_test(request)
        expected_opcode = _PERSONAL_REQUEST_OPCODES[request.operation]
        if len(frame) != 20 or frame[0] != expected_opcode:
            raise ValueError("personal-setting request does not match its operation")
        ack_operation = _PERSONAL_ACKS[request.operation]
        return cls._create(
            name=request.operation.value,
            request_frame=frame,
            success_opcodes=(expected_opcode,),
            failure_opcodes=(),
            expected_subcommand=None,
            parser=partial(parse_vendor_ack, operation=ack_operation),
        )

    @classmethod
    def from_behavior_request(cls, request: object) -> "OfflineVendorOperation":
        """Compose one closed single-frame behavior mutation for the fake runtime."""

        if type(request) is AlarmBatchRequest:
            raise TypeError("multi-frame alarm batches require a separate state machine")
        binding = _BEHAVIOR_ACKS.get(type(request))
        if binding is None:
            raise TypeError("request must be a closed single-frame behavior request")
        require_fake_singleton_terminal(_BEHAVIOR_REQUEST_NAMES[type(request)])
        name, expected_opcode, ack_operation = binding
        frame = _canonical_behavior_frame(request)
        type(request).validate_for_fake_execution(request)
        if len(frame) != 20 or frame[0] != expected_opcode:
            raise ValueError("behavior request does not match its closed operation")
        success_opcode = expected_opcode
        failure_opcode = expected_opcode | 0x80
        return cls._create(
            name=name,
            request_frame=frame,
            success_opcodes=(success_opcode,),
            failure_opcodes=(failure_opcode,),
            expected_subcommand=None,
            parser=partial(parse_vendor_ack, operation=ack_operation),
        )

    @classmethod
    def from_main_command_request(cls, request: object) -> "OfflineVendorOperation":
        """Compose a proven single-response main-command route for the fake runtime."""

        if type(request) is ScreenLightTimeRequest:
            require_fake_singleton_terminal("SetScreenLightTime")
            frames = request.frames()
            frame = frames[0].synthetic_bytes_for_test()
            canonical = ScreenLightTimeRequest(request.raw_value)
            expected = canonical.frames()[0].synthetic_bytes_for_test()
            if frame != expected:
                raise ValueError("screen-light request has an invalid shape")
            return cls._create(
                name=request.operation.value,
                request_frame=frame,
                success_opcodes=(0x78,),
                failure_opcodes=(),
                expected_subcommand=0x0B,
                parser=parse_vendor_screen_light_time,
            )
        if type(request) is not NoArgumentMainCommandRequest:
            raise TypeError("request is not a proven single-response main command")
        if request.command is NoArgumentMainCommand.SCAN_WIFI:
            raise TypeError("streaming Wi-Fi scan requires a separate state machine")
        binding = _NO_ARGUMENT_MAIN_RESPONSES.get(request.command)
        if binding is None:
            raise TypeError("main command has no proven single-response binding")
        require_fake_singleton_terminal(_NO_ARGUMENT_REQUEST_NAMES[request.command])
        success, failure, expected_subcommand, parser = binding
        frames = request.frames()
        if len(frames) != 1:
            raise ValueError("single-response main command produced an invalid batch")
        frame = frames[0].synthetic_bytes_for_test()
        if len(frame) != 20:
            raise ValueError("main command request must be exactly 20 bytes")
        canonical = NoArgumentMainCommandRequest(request.command)
        expected = canonical.frames()[0].synthetic_bytes_for_test()
        if frame != expected:
            raise ValueError("main command request has an invalid shape")
        return cls._create(
            name=request.operation.value,
            request_frame=frame,
            success_opcodes=success,
            failure_opcodes=failure,
            expected_subcommand=expected_subcommand,
            parser=parser,
            excluded_subcommands=(0x00,)
            if request.command is NoArgumentMainCommand.EQ_INFO
            else (),
        )

    @classmethod
    def from_command_request(
        cls, request: StaticVendorCommandRequest
    ) -> "OfflineVendorOperation":
        """Compose only command families with an exact static response correlation."""

        if type(request) is not StaticVendorCommandRequest:
            raise TypeError("request must be a StaticVendorCommandRequest")
        StaticVendorCommandRequest.validate_for_fake_execution(request)
        request_name = _COMMAND_REQUEST_NAMES.get(request.operation)
        if request_name is not None:
            require_fake_singleton_terminal(request_name)
        binding = _COMMAND_RESPONSES.get(request.operation)
        if binding is None:
            raise TypeError("command has no exact response correlation")
        request_opcode, success, failure, expected_subcommand, parser = binding
        frame = StaticVendorCommandRequest.synthetic_bytes_for_test(request)
        if len(frame) != 20 or frame[0] != request_opcode:
            raise ValueError("vendor command does not match its closed operation")
        return cls._create(
            name=request.operation.value,
            request_frame=frame,
            success_opcodes=success,
            failure_opcodes=failure,
            expected_subcommand=expected_subcommand,
            parser=parser,
        )

    @classmethod
    def from_phone_request(
        cls, request: OfflinePhoneRequest
    ) -> "OfflineVendorOperation":
        """Compose only single-frame phone integrations with a closed response."""

        if type(request) is not OfflinePhoneRequest:
            raise TypeError("request must be an OfflinePhoneRequest")
        OfflinePhoneRequest.validate_for_fake_execution(request)
        request_name = _PHONE_REQUEST_NAMES.get(request.operation)
        if request_name is not None:
            require_fake_singleton_terminal(request_name)
        binding = _PHONE_RESPONSES.get(request.operation)
        if binding is None:
            raise TypeError("phone integration has no exact singleton correlation")
        request_opcode, success, failure, expected_subcommand, parser = binding
        frames = OfflinePhoneRequest.synthetic_frames_for_test(request)
        if len(frames) != 1:
            raise TypeError("multi-frame phone integration requires a separate state machine")
        frame = frames[0]
        if len(frame) != 20 or frame[0] != request_opcode:
            raise ValueError("phone integration does not match its closed operation")
        return cls._create(
            name=request.operation.value,
            request_frame=frame,
            success_opcodes=success,
            failure_opcodes=failure,
            expected_subcommand=expected_subcommand,
            parser=parser,
        )

    @classmethod
    def screen_light_time(cls) -> "OfflineVendorOperation":
        """Closed static subcommand route used by offline matcher simulations."""

        require_fake_singleton_terminal("SetScreenLightTime")
        return cls._create(
            name="screen_light_time",
            request_frame=bytes((0x78, 0x0A)) + bytes(18),
            success_opcodes=(0x78,),
            failure_opcodes=(),
            expected_subcommand=0x0B,
            parser=parse_vendor_screen_light_time,
        )

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def synthetic_request_for_test(self) -> bytes:
        return bytes(self._request_frame)

    def _match(self, endpoint_uuid: str, data: bytes) -> tuple[_Match, object | None]:
        endpoint = _normalize_uuid(endpoint_uuid, "notification endpoint")
        if endpoint != self.response_endpoint_uuid:
            return _Match.UNRELATED, None
        if not isinstance(data, bytes):
            raise ProtocolError("vendor response must be exactly 20 bytes")
        expected_opcodes = self.success_opcodes + self.failure_opcodes
        if not data or data[0] not in expected_opcodes:
            return _Match.UNRELATED, None
        if self.expected_subcommand is not None:
            if len(data) < 2:
                return _Match.UNRELATED, None
            if data[1] != self.expected_subcommand:
                return _Match.UNRELATED, None
        if self.excluded_subcommands:
            if len(data) < 2:
                return _Match.UNRELATED, None
            if data[1] in self.excluded_subcommands:
                return _Match.UNRELATED, None
        if len(data) != 20:
            raise ProtocolError("vendor response must be exactly 20 bytes")
        opcode = data[0]
        if opcode in self.failure_opcodes:
            return _Match.FAILURE, None
        return _Match.SUCCESS, self._parser(data)

    def __repr__(self) -> str:
        return (
            "OfflineVendorOperation("
            f"name={self.name!r}, request_endpoint_uuid={self.request_endpoint_uuid!r}, "
            f"response_endpoint_uuid={self.response_endpoint_uuid!r}, "
            "request_frame=<redacted>, hardware_eligible=False)"
        )


@dataclass(frozen=True, repr=False)
class VendorOperationToken:
    generation: int
    _engine_id: int = field(repr=False)

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"VendorOperationToken(generation={self.generation})"


@dataclass(frozen=True, repr=False)
class NotificationSubscriptionToken:
    generation: int
    _engine_id: int = field(repr=False)

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"NotificationSubscriptionToken(generation={self.generation})"


@dataclass(frozen=True, repr=False)
class NotificationSubscriptionIntent:
    token: NotificationSubscriptionToken
    characteristic_uuid: str

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "NotificationSubscriptionIntent("
            f"token={self.token!r}, characteristic_uuid={self.characteristic_uuid!r}, "
            "hardware_eligible=False)"
        )


@dataclass(frozen=True, repr=False)
class OfflineWriteIntent:
    operation_name: str
    token: VendorOperationToken
    endpoint_uuid: str
    deadline: float
    _frame: bytes = field(repr=False)

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    def synthetic_bytes_for_test(self) -> bytes:
        return bytes(self._frame)

    def __repr__(self) -> str:
        return (
            "OfflineWriteIntent("
            f"operation_name={self.operation_name!r}, token={self.token!r}, "
            f"endpoint_uuid={self.endpoint_uuid!r}, deadline={self.deadline!r}, "
            "frame=<redacted>, hardware_eligible=False)"
        )


@dataclass(frozen=True, repr=False)
class TransactionClosure:
    operation_name: str
    token: VendorOperationToken
    reason: TransactionCloseReason
    completeness: TransactionCompleteness

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_verified(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "TransactionClosure("
            f"operation_name={self.operation_name!r}, token={self.token!r}, "
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            "hardware_verified=False)"
        )


@dataclass(frozen=True)
class VendorEngineUpdate:
    write_intent: OfflineWriteIntent | None = None
    closure: TransactionClosure | None = None


@dataclass(frozen=True, repr=False)
class VendorNotificationResult:
    disposition: NotificationDisposition
    closure: TransactionClosure | None = None
    parsed_value: object | None = field(default=None, repr=False)

    def __repr__(self) -> str:
        reason = None if self.closure is None else self.closure.reason.value
        return (
            "VendorNotificationResult("
            f"disposition={self.disposition.value!r}, closure_reason={reason!r}, "
            f"has_parsed_value={self.parsed_value is not None})"
        )


@dataclass(frozen=True)
class _Pending:
    token: VendorOperationToken
    operation: OfflineVendorOperation
    deadline: float


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("operation timeout must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("operation timeout must be finite and positive")
    return result


class OfflineVendorTransactionEngine:
    """Single-flight simulator with one deadline starting when work is queued."""

    def __init__(self, *, operation_timeout: float = 8.0) -> None:
        self._operation_timeout = _timeout(operation_timeout)
        self._engine_id = next(_ENGINE_IDS)
        self._generation = 0
        self._connection_generation = 0
        self._phase = EnginePhase.DISCONNECTED
        self._expected_subscription_token: NotificationSubscriptionToken | None = None
        self._last_now: float | None = None
        self._queued: _Pending | None = None
        self._write_pending: _Pending | None = None
        self._in_flight: _Pending | None = None

    @property
    def phase(self) -> EnginePhase:
        return self._phase

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def requires_reconnect(self) -> bool:
        return self._phase is EnginePhase.RECONNECT_REQUIRED

    @property
    def active_token(self) -> VendorOperationToken | None:
        pending = self._in_flight or self._write_pending or self._queued
        return None if pending is None else pending.token

    @property
    def deadline(self) -> float | None:
        pending = self._in_flight or self._write_pending or self._queued
        return None if pending is None else pending.deadline

    def __repr__(self) -> str:
        return (
            "OfflineVendorTransactionEngine("
            f"phase={self._phase.value!r}, has_queued={self._queued is not None}, "
            f"write_confirmation_pending={self._write_pending is not None}, "
            f"has_in_flight={self._in_flight is not None}, "
            f"requires_reconnect={self.requires_reconnect}, hardware_eligible=False)"
        )

    def _reject_reconnect_required(self) -> None:
        if self._phase is EnginePhase.RECONNECT_REQUIRED:
            raise ProtocolError(
                "vendor session outcome is uncertain; record observed disconnect "
                "before new work"
            )

    def _observe_now(self, now: float) -> float:
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise TypeError("now must be a monotonic number")
        current = float(now)
        if not math.isfinite(current):
            raise ValueError("monotonic time must be finite")
        if self._last_now is not None and current < self._last_now:
            raise ValueError("monotonic time cannot move backwards")
        self._last_now = current
        return current

    def mark_connected(self, *, now: float) -> NotificationSubscriptionIntent:
        self._observe_now(now)
        self._reject_reconnect_required()
        if self._phase is not EnginePhase.DISCONNECTED:
            raise ProtocolError("offline vendor engine is already connected")
        self._connection_generation += 1
        token = NotificationSubscriptionToken(
            self._connection_generation, self._engine_id
        )
        self._expected_subscription_token = token
        self._phase = EnginePhase.SUBSCRIPTION_REQUIRED
        return NotificationSubscriptionIntent(
            token=token,
            characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
        )

    def confirm_subscription(
        self,
        *,
        token: NotificationSubscriptionToken,
        characteristic_uuid: str,
        outcome: NotificationSubscriptionOutcome,
        now: float,
    ) -> VendorEngineUpdate:
        self._observe_now(now)
        self._reject_reconnect_required()
        if self._phase is not EnginePhase.SUBSCRIPTION_REQUIRED:
            raise ProtocolError("subscription confirmation is not currently expected")
        if not isinstance(token, NotificationSubscriptionToken):
            raise TypeError(
                "subscription token must be a NotificationSubscriptionToken"
            )
        if token != self._expected_subscription_token:
            raise ProtocolError("stale notification subscription confirmation token")
        if type(outcome) is not NotificationSubscriptionOutcome:
            raise TypeError("outcome must be a NotificationSubscriptionOutcome")
        characteristic = _normalize_uuid(
            characteristic_uuid, "notification subscription characteristic"
        )
        if characteristic != VENDOR_CHARACTERISTIC_33F4:
            raise ProtocolError(
                "subscription confirmation does not match notification readiness"
            )
        self._expected_subscription_token = None
        if outcome is NotificationSubscriptionOutcome.FAILED:
            self._phase = EnginePhase.RECONNECT_REQUIRED
            return VendorEngineUpdate(
                closure=self._close(
                    TransactionCloseReason.SUBSCRIPTION_FAILURE,
                    TransactionCompleteness.ABORTED,
                )
            )
        self._phase = EnginePhase.READY
        return VendorEngineUpdate()

    def enqueue(
        self, operation: OfflineVendorOperation, *, now: float
    ) -> VendorOperationToken:
        current = self._observe_now(now)
        if type(operation) is not OfflineVendorOperation:
            raise TypeError("operation must be an OfflineVendorOperation")
        self._reject_reconnect_required()
        if self._phase is EnginePhase.DISCONNECTED:
            raise ProtocolError("cannot queue a vendor operation while disconnected")
        if (
            self._queued is not None
            or self._write_pending is not None
            or self._in_flight is not None
        ):
            raise ProtocolError("a vendor operation is already queued or in flight")
        deadline = current + self._operation_timeout
        if not math.isfinite(deadline):
            raise ValueError("calculated response deadline must be finite")
        self._generation += 1
        token = VendorOperationToken(self._generation, self._engine_id)
        self._queued = _Pending(token, operation, deadline)
        return token

    def _close(
        self,
        reason: TransactionCloseReason,
        completeness: TransactionCompleteness,
    ) -> TransactionClosure | None:
        pending = self._in_flight or self._write_pending or self._queued
        self._in_flight = None
        self._write_pending = None
        self._queued = None
        if pending is None:
            return None
        if completeness is TransactionCompleteness.UNCERTAIN:
            self._phase = EnginePhase.RECONNECT_REQUIRED
        return TransactionClosure(
            operation_name=pending.operation.name,
            token=pending.token,
            reason=reason,
            completeness=completeness,
        )

    def _interrupted_completeness(self) -> TransactionCompleteness:
        if self._write_pending is not None or self._in_flight is not None:
            return TransactionCompleteness.UNCERTAIN
        return TransactionCompleteness.ABORTED

    def _expire(self, now: float) -> TransactionClosure | None:
        deadline = self.deadline
        if deadline is None or now < deadline:
            return None
        completeness = self._interrupted_completeness()
        return self._close(
            TransactionCloseReason.TIMEOUT,
            completeness,
        )

    def take_write(self, *, now: float) -> VendorEngineUpdate:
        current = self._observe_now(now)
        expired = self._expire(current)
        if expired is not None:
            return VendorEngineUpdate(closure=expired)
        if self._phase is not EnginePhase.READY or self._queued is None:
            return VendorEngineUpdate()
        pending = self._queued
        self._queued = None
        self._write_pending = pending
        return VendorEngineUpdate(
            write_intent=OfflineWriteIntent(
                operation_name=pending.operation.name,
                token=pending.token,
                endpoint_uuid=pending.operation.request_endpoint_uuid,
                deadline=pending.deadline,
                _frame=pending.operation.synthetic_request_for_test(),
            )
        )

    def confirm_write(
        self,
        token: VendorOperationToken,
        *,
        outcome: WriteOutcome,
        now: float,
    ) -> VendorEngineUpdate:
        if not isinstance(token, VendorOperationToken):
            raise TypeError("operation token must be a VendorOperationToken")
        if type(outcome) is not WriteOutcome:
            raise TypeError("outcome must be a WriteOutcome")
        current = self._observe_now(now)
        if token != self.active_token:
            return VendorEngineUpdate()
        expired = self._expire(current)
        if expired is not None:
            return VendorEngineUpdate(closure=expired)
        if self._write_pending is None:
            raise ProtocolError("characteristic write confirmation was not expected")
        if outcome is WriteOutcome.DEFINITELY_NOT_DISPATCHED:
            return VendorEngineUpdate(
                closure=self._close(
                    TransactionCloseReason.WRITE_FAILURE,
                    TransactionCompleteness.ABORTED,
                )
            )
        if outcome is WriteOutcome.OUTCOME_UNKNOWN:
            return VendorEngineUpdate(
                closure=self._close(
                    TransactionCloseReason.WRITE_FAILURE,
                    TransactionCompleteness.UNCERTAIN,
                )
            )
        self._in_flight = self._write_pending
        self._write_pending = None
        return VendorEngineUpdate()

    def receive(
        self,
        token: VendorOperationToken,
        *,
        endpoint_uuid: str,
        data: bytes,
        now: float,
    ) -> VendorNotificationResult:
        if not isinstance(token, VendorOperationToken):
            raise TypeError("operation token must be a VendorOperationToken")
        current = self._observe_now(now)
        if token != self.active_token:
            return VendorNotificationResult(NotificationDisposition.STALE)
        expired = self._expire(current)
        if expired is not None:
            return VendorNotificationResult(
                NotificationDisposition.TIMED_OUT,
                closure=expired,
            )
        if self._in_flight is None:
            return VendorNotificationResult(NotificationDisposition.NOT_IN_FLIGHT)
        try:
            match, parsed = self._in_flight.operation._match(endpoint_uuid, data)
        except ProtocolError:
            return VendorNotificationResult(
                NotificationDisposition.MALFORMED,
                closure=self._close(
                    TransactionCloseReason.MALFORMED_RESPONSE,
                    TransactionCompleteness.UNCERTAIN,
                ),
            )
        if match is _Match.UNRELATED:
            return VendorNotificationResult(NotificationDisposition.UNRELATED)
        if match is _Match.SUCCESS:
            return VendorNotificationResult(
                NotificationDisposition.MATCHED_SUCCESS,
                closure=self._close(
                    TransactionCloseReason.SUCCESS,
                    TransactionCompleteness.SUCCEEDED,
                ),
                parsed_value=parsed,
            )
        return VendorNotificationResult(
            NotificationDisposition.MATCHED_FAILURE,
            closure=self._close(
                TransactionCloseReason.DEVICE_FAILURE,
                TransactionCompleteness.FAILED,
            ),
        )

    def poll(self, *, now: float) -> VendorEngineUpdate:
        current = self._observe_now(now)
        return VendorEngineUpdate(closure=self._expire(current))

    def cancel(self) -> VendorEngineUpdate:
        completeness = self._interrupted_completeness()
        return VendorEngineUpdate(
            closure=self._close(
                TransactionCloseReason.CANCELLED,
                completeness,
            )
        )

    def record_disconnected(self) -> VendorEngineUpdate:
        """Record an observed link teardown, invalidating all connection state."""

        completeness = self._interrupted_completeness()
        closure = self._close(
            TransactionCloseReason.DISCONNECTED,
            completeness,
        )
        self._expected_subscription_token = None
        self._phase = EnginePhase.DISCONNECTED
        return VendorEngineUpdate(closure=closure)
