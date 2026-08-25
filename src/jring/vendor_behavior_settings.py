"""Pure offline encoders for statically recovered vendor behavior settings.

This module has no transport integration.  Its frames are synthetic test/planning
artifacts and are permanently ineligible for hardware use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .uuids import VENDOR_CHARACTERISTIC_33F3
from .vendor_request_integrity import seal_vendor_request, validate_vendor_request


_FRAME_LENGTH = 20
_ALARM_CONTENT_LIMIT = 54
_ALARM_CHUNK_LENGTH = 18


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    return value


def _bounded_integer(value: object, label: str, minimum: int, maximum: int) -> int:
    result = _integer(value, label)
    if not minimum <= result <= maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return result


def _boolean(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{label} must be a boolean")
    return value


def _typed(value: object, expected: type, label: str) -> object:
    if type(value) is not expected:
        raise TypeError(f"{label} must be a {expected.__name__}")
    return value


def _frame(opcode: int, body: bytes = b"") -> bytes:
    payload = bytes((opcode,)) + body
    if len(payload) > _FRAME_LENGTH:
        raise ValueError("vendor behavior frame exceeds 20 bytes")
    return payload + bytes(_FRAME_LENGTH - len(payload))


def _bounded_utf8(text: str, maximum: int) -> bytes:
    if not isinstance(text, str):
        raise TypeError("alarm content must be a string")
    if "\x00" in text:
        raise ValueError("alarm content cannot contain a NUL byte")
    encoded = text.encode("utf-8")
    if len(encoded) > maximum:
        raise ValueError(f"alarm content must fit {maximum} UTF-8 bytes")
    return encoded


class _StaticOnly:
    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>, hardware_eligible=False)"

    def validate_for_fake_execution(self) -> None:
        frames = tuple(
            VendorBehaviorFrame.synthetic_bytes_for_test(frame)
            for frame in type(self).frames(self)
        )
        validate_vendor_request(
            self,
            operation=type(self),
            frames=frames,
        )


@dataclass(frozen=True, repr=False, init=False)
class VendorBehaviorFrame(_StaticOnly):
    endpoint_uuid: str
    _payload: bytes = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("vendor behavior frames are created only by typed requests")

    @classmethod
    def _create(cls, payload: bytes) -> "VendorBehaviorFrame":
        if type(payload) is not bytes or len(payload) != _FRAME_LENGTH:
            raise ValueError("vendor behavior payload must be exactly 20 bytes")
        instance = object.__new__(cls)
        object.__setattr__(instance, "endpoint_uuid", VENDOR_CHARACTERISTIC_33F3)
        object.__setattr__(instance, "_payload", payload)
        return instance

    def synthetic_bytes_for_test(self) -> bytes:
        return bytes(self._payload)

    def __repr__(self) -> str:
        return (
            "VendorBehaviorFrame("
            f"endpoint_uuid={self.endpoint_uuid!r}, payload=<redacted>, "
            "hardware_eligible=False)"
        )


def _frames(*payloads: bytes) -> tuple[VendorBehaviorFrame, ...]:
    return tuple(VendorBehaviorFrame._create(payload) for payload in payloads)


def _seal_behavior_request(request: _StaticOnly) -> None:
    frames = tuple(
        VendorBehaviorFrame.synthetic_bytes_for_test(frame)
        for frame in type(request).frames(request)
    )
    seal_vendor_request(request, operation=type(request), frames=frames)


@dataclass(frozen=True, repr=False)
class ClockTime:
    hour: int
    minute: int

    def __post_init__(self) -> None:
        _bounded_integer(self.hour, "hour", 0, 23)
        _bounded_integer(self.minute, "minute", 0, 59)

    def __repr__(self) -> str:
        return "ClockTime(<redacted>)"


@dataclass(frozen=True, repr=False)
class VibrationRequest(_StaticOnly):
    count: int

    def __post_init__(self) -> None:
        _bounded_integer(self.count, "vibration count", 0, 10)
        _seal_behavior_request(self)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        return _frames(_frame(0x04, bytes((self.count,))))


@dataclass(frozen=True, repr=False)
class AntiLostRequest(_StaticOnly):
    enabled: bool

    def __post_init__(self) -> None:
        _boolean(self.enabled, "anti-lost enabled state")
        _seal_behavior_request(self)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        return _frames(_frame(0x05, bytes((int(self.enabled),))))


@dataclass(frozen=True, repr=False)
class CameraModeRequest(_StaticOnly):
    enabled: bool

    def __post_init__(self) -> None:
        _boolean(self.enabled, "camera mode enabled state")
        _seal_behavior_request(self)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        return _frames(_frame(0x07, bytes((int(self.enabled),))))


@dataclass(frozen=True, repr=False, init=False)
class IdleReminderRequest(_StaticOnly):
    _interval_seconds: int = field(repr=False)
    _start: ClockTime = field(repr=False)
    _end: ClockTime = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("use IdleReminderRequest.enabled() or .disabled()")

    @classmethod
    def _create(
        cls, interval_seconds: int, start: ClockTime, end: ClockTime
    ) -> "IdleReminderRequest":
        _typed(start, ClockTime, "idle start")
        _typed(end, ClockTime, "idle end")
        instance = object.__new__(cls)
        object.__setattr__(instance, "_interval_seconds", interval_seconds)
        object.__setattr__(instance, "_start", start)
        object.__setattr__(instance, "_end", end)
        _seal_behavior_request(instance)
        return instance

    @classmethod
    def enabled(
        cls, *, interval_minutes: int, start: ClockTime, end: ClockTime
    ) -> "IdleReminderRequest":
        minutes = _bounded_integer(interval_minutes, "idle interval minutes", 1, 240)
        return cls._create(minutes * 60, start, end)

    @classmethod
    def disabled(cls, *, start: ClockTime, end: ClockTime) -> "IdleReminderRequest":
        return cls._create(0, start, end)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        body = self._interval_seconds.to_bytes(4, "little") + bytes(
            (self._start.hour, self._start.minute, self._end.hour, self._end.minute)
        )
        return _frames(_frame(0x08, body))


@dataclass(frozen=True, repr=False)
class SleepScheduleRequest(_StaticOnly):
    noon_start: ClockTime = field(repr=False)
    noon_end: ClockTime = field(repr=False)
    night_start: ClockTime = field(repr=False)
    night_end: ClockTime = field(repr=False)

    def __post_init__(self) -> None:
        for label, value in (
            ("noon start", self.noon_start),
            ("noon end", self.noon_end),
            ("night start", self.night_start),
            ("night end", self.night_end),
        ):
            _typed(value, ClockTime, label)
        _seal_behavior_request(self)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        body = bytes(
            (
                self.noon_start.hour,
                self.noon_start.minute,
                self.noon_end.hour,
                self.noon_end.minute,
                self.night_start.hour,
                self.night_start.minute,
                self.night_end.hour,
                self.night_end.minute,
            )
        )
        return _frames(_frame(0x09, body))


@dataclass(frozen=True, repr=False)
class AlarmWeekdays:
    sunday: bool
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool

    def __post_init__(self) -> None:
        for label, value in zip(
            ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"),
            self._wire_values(),
        ):
            _boolean(value, f"alarm {label} state")

    @classmethod
    def none(cls) -> "AlarmWeekdays":
        return cls(False, False, False, False, False, False, False)

    @classmethod
    def every_day(cls) -> "AlarmWeekdays":
        return cls(True, True, True, True, True, True, True)

    def _wire_values(self) -> tuple[bool, ...]:
        return (
            self.sunday,
            self.monday,
            self.tuesday,
            self.wednesday,
            self.thursday,
            self.friday,
            self.saturday,
        )

    def __repr__(self) -> str:
        return "AlarmWeekdays(<redacted>)"


@dataclass(frozen=True, repr=False)
class AlarmRequest(_StaticOnly):
    alarm_id: int
    enabled: bool
    time: ClockTime = field(repr=False)
    weekdays: AlarmWeekdays = field(repr=False)
    single: bool
    content: str = field(repr=False)
    _content_bytes: bytes = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _bounded_integer(self.alarm_id, "alarm id", 0, 15)
        _boolean(self.enabled, "alarm enabled state")
        _typed(self.time, ClockTime, "alarm time")
        _typed(self.weekdays, AlarmWeekdays, "alarm weekdays")
        _boolean(self.single, "single alarm state")
        object.__setattr__(
            self,
            "_content_bytes",
            _bounded_utf8(self.content, _ALARM_CONTENT_LIMIT),
        )

    @property
    def content_policy(self) -> str:
        return "reject_utf8_over_54_bytes"

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        base_body = bytes(
            (
                self.alarm_id,
                int(self.enabled),
                self.time.hour,
                self.time.minute,
                *(int(day) for day in self.weekdays._wire_values()),
                int(self.single),
            )
        )
        payloads = [_frame(0x0D, base_body)]
        chunks = tuple(
            self._content_bytes[offset : offset + _ALARM_CHUNK_LENGTH]
            for offset in range(0, len(self._content_bytes), _ALARM_CHUNK_LENGTH)
        )
        for index, chunk in enumerate(chunks):
            if index > 7:
                raise ValueError("alarm content chunk index exceeds header capacity")
            last = index == len(chunks) - 1
            header = (0x80 if last else 0) | (index << 4) | self.alarm_id
            payloads.append(_frame(0x1C, bytes((header,)) + chunk))
        return _frames(*payloads)


@dataclass(frozen=True, repr=False)
class AlarmBatchRequest(_StaticOnly):
    alarms: tuple[AlarmRequest, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.alarms) is not tuple:
            raise TypeError("alarms must be an explicit tuple")
        if not self.alarms:
            raise ValueError("alarm batch must contain at least one alarm")
        if len(self.alarms) > 16:
            raise ValueError("alarm batch cannot exceed 16 alarms")
        for alarm in self.alarms:
            _typed(alarm, AlarmRequest, "alarm batch item")
        ids = tuple(alarm.alarm_id for alarm in self.alarms)
        if len(ids) != len(set(ids)):
            raise ValueError("alarm ids must be unique within a batch")

    @property
    def alarm_count(self) -> int:
        return len(self.alarms)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        return tuple(frame for alarm in self.alarms for frame in alarm.frames())


class DeviceMode(Enum):
    NORMAL = 1
    LOW_POWER = 2
    RESTART = 3
    RESET = 4


_DEVICE_MODE_MAGIC = {
    DeviceMode.NORMAL: bytes.fromhex("12 34 56 78 fe dc ba 98"),
    DeviceMode.LOW_POWER: bytes.fromhex("fe dc ba 98 76 54 32 10"),
    DeviceMode.RESTART: bytes.fromhex("12 34 56 78 9a bc de f0"),
    DeviceMode.RESET: bytes.fromhex("12 34 12 34 12 34 12 34"),
}


@dataclass(frozen=True, repr=False)
class DeviceModeRequest(_StaticOnly):
    mode: DeviceMode

    def __post_init__(self) -> None:
        _typed(self.mode, DeviceMode, "device mode")
        _seal_behavior_request(self)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        return _frames(_frame(0x0E, _DEVICE_MODE_MAGIC[self.mode]))


@dataclass(frozen=True, repr=False)
class AutoHeartScheduleRequest(_StaticOnly):
    enabled: bool
    start: ClockTime = field(repr=False)
    end: ClockTime = field(repr=False)
    interval_minutes: int = field(repr=False)

    def __post_init__(self) -> None:
        _boolean(self.enabled, "automatic heart mode enabled state")
        _typed(self.start, ClockTime, "automatic heart start")
        _typed(self.end, ClockTime, "automatic heart end")
        _bounded_integer(
            self.interval_minutes,
            "automatic heart interval minutes",
            1,
            254,
        )
        _seal_behavior_request(self)

    @property
    def ignored_apk_argument_omitted(self) -> bool:
        return True

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        body = bytes(
            (
                self.start.hour,
                self.start.minute,
                self.end.hour,
                self.end.minute,
                int(self.enabled),
                self.interval_minutes % 255,
                1,
            )
        )
        return _frames(_frame(0x19, body))


@dataclass(frozen=True, repr=False)
class GoalStepRequest(_StaticOnly):
    steps: int

    def __post_init__(self) -> None:
        value = _bounded_integer(self.steps, "goal steps", 1_000, 20_000)
        if value % 1_000:
            raise ValueError("goal steps must use 1,000-step increments")
        _seal_behavior_request(self)

    def frames(self) -> tuple[VendorBehaviorFrame, ...]:
        return _frames(_frame(0x1A, self.steps.to_bytes(4, "little")))


@dataclass(frozen=True)
class BehaviorSettingsSafety:
    maturity: str = "static_apk_only"
    hardware_eligible: bool = False
    retains_alarm_list: bool = False
    allows_partial_send: bool = False
    truncates_alarm_content: bool = False
    logs_raw_frames: bool = False
    retries: bool = False
    invalid_device_mode_fallback: bool = False


BEHAVIOR_SETTINGS_SAFETY = BehaviorSettingsSafety()
