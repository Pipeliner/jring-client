"""Offline-only clean-room codecs for the optional vendor raw channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .protocol import ProtocolError
from .uuids import VENDOR_CHARACTERISTIC_33F5, VENDOR_CHARACTERISTIC_33F6


class RawCommandOperation(str, Enum):
    AI_SERVER_NOTIFICATION = "ai_server_notification"
    AI_EXTRA_ACTION = "ai_extra_action"
    AI_STATE = "ai_state"
    AI_STATE_QUERY = "ai_state_query"
    AI_AUDIO_STATE = "ai_audio_state"
    AI_COMMAND_TYPE = "ai_command_type"


@dataclass(frozen=True, init=False, repr=False)
class StaticRawCommand:
    operation: RawCommandOperation
    _encoded: bytes = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("use a closed typed raw-command encoder")

    @classmethod
    def _create(
        cls, operation: RawCommandOperation, encoded: bytes
    ) -> "StaticRawCommand":
        if type(operation) is not RawCommandOperation:
            raise TypeError("raw command operation must be closed")
        if type(encoded) is not bytes or len(encoded) != 20:
            raise ValueError("raw command must be exactly 20 bytes")
        instance = object.__new__(cls)
        object.__setattr__(instance, "operation", operation)
        object.__setattr__(instance, "_encoded", encoded)
        return instance

    def __repr__(self) -> str:
        return f"StaticRawCommand(operation={self.operation.value!r}, payload=<redacted>)"

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F5

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def synthetic_bytes_for_test(self) -> bytes:
        return bytes(self._encoded)


@dataclass(frozen=True, init=False)
class RawNotificationControlEvidence:
    """Static behavior record that intentionally cannot drive a descriptor write."""

    requested_enabled: bool
    requested_mtu: int | None
    fixed_delay_ms: int
    observed_raw_cccd_action: str
    observed_other_endpoints_action: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("use analyze_raw_notification_control()")

    @classmethod
    def _create(
        cls,
        *,
        requested_enabled: bool,
        requested_mtu: int | None,
        fixed_delay_ms: int,
        observed_raw_cccd_action: str,
        observed_other_endpoints_action: str,
    ) -> "RawNotificationControlEvidence":
        instance = object.__new__(cls)
        object.__setattr__(instance, "requested_enabled", requested_enabled)
        object.__setattr__(instance, "requested_mtu", requested_mtu)
        object.__setattr__(instance, "fixed_delay_ms", fixed_delay_ms)
        object.__setattr__(instance, "observed_raw_cccd_action", observed_raw_cccd_action)
        object.__setattr__(
            instance,
            "observed_other_endpoints_action",
            observed_other_endpoints_action,
        )
        return instance

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F6

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
    def safe_live_plan_available(self) -> bool:
        return False

    @property
    def unsafe_recovered_branch(self) -> bool:
        return True


def analyze_raw_notification_control(enabled: bool) -> RawNotificationControlEvidence:
    """Describe the recovered APK branch without producing a runnable CCCD plan.

    The disabled branch is deliberately recorded as unsafe: it selects an enable
    action for the raw endpoint before disabling separately configured endpoints.
    """

    if type(enabled) is not bool:
        raise TypeError("enabled must be a boolean")
    return RawNotificationControlEvidence._create(
        requested_enabled=enabled,
        requested_mtu=247 if enabled else None,
        fixed_delay_ms=2000 if enabled else 0,
        observed_raw_cccd_action="enable",
        observed_other_endpoints_action="enable" if enabled else "disable",
    )


class RawVendorNotification:
    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F6

    @property
    def hardware_verified(self) -> bool:
        return False


@dataclass(frozen=True)
class RawSingleValueNotification(RawVendorNotification):
    kind: str
    value: int
    trailing_bytes_ignored: int


@dataclass(frozen=True)
class RawAiStateNotification(RawVendorNotification):
    first_value: int
    second_value: int
    trailing_bytes_ignored: int


@dataclass(frozen=True)
class RawPayloadNotification(RawVendorNotification):
    kind: str
    first_value: int
    second_value: int
    declared_length: int
    _payload: bytes = field(repr=False)

    def payload_for_explicit_local_use(self) -> bytes:
        return bytes(self._payload)


def _argument(value: int) -> int:
    if type(value) is not int:
        raise TypeError("raw command argument must be an integer")
    if not 0 <= value <= 0xFF:
        raise ValueError("raw command argument must fit one unsigned byte")
    return value


def _raw_request(
    operation: RawCommandOperation, command_type: int, argument: int
) -> StaticRawCommand:
    encoded = (
        command_type.to_bytes(2, "little")
        + bytes((1, 0, 1, 0, 1, 0, argument))
        + bytes(11)
    )
    return StaticRawCommand._create(operation, encoded)


def encode_raw_ai_server_notification(enabled: bool) -> StaticRawCommand:
    if type(enabled) is not bool:
        raise TypeError("enabled must be a boolean")
    return _raw_request(
        RawCommandOperation.AI_SERVER_NOTIFICATION,
        0x0001,
        0x02 if enabled else 0x04,
    )


def encode_raw_ai_extra_action(value: int) -> StaticRawCommand:
    return _raw_request(RawCommandOperation.AI_EXTRA_ACTION, 0x0004, _argument(value))


def encode_raw_ai_state(enabled: bool) -> StaticRawCommand:
    if type(enabled) is not bool:
        raise TypeError("enabled must be a boolean")
    return _raw_request(RawCommandOperation.AI_STATE, 0x0005, int(enabled))


def encode_raw_ai_state_query() -> StaticRawCommand:
    return _raw_request(RawCommandOperation.AI_STATE_QUERY, 0x0007, 0)


def encode_raw_ai_audio_state(enabled: bool) -> StaticRawCommand:
    if type(enabled) is not bool:
        raise TypeError("enabled must be a boolean")
    return _raw_request(RawCommandOperation.AI_AUDIO_STATE, 0x0008, int(enabled))


def encode_raw_ai_command_type(value: int) -> StaticRawCommand:
    return _raw_request(RawCommandOperation.AI_COMMAND_TYPE, 0x000A, _argument(value))


def parse_raw_vendor_notification(
    data: bytes, *, max_payload_bytes: int = 236
) -> RawVendorNotification:
    if not isinstance(data, bytes) or len(data) < 8:
        raise ProtocolError("raw vendor notification must be at least 8 bytes")
    if type(max_payload_bytes) is not int or max_payload_bytes < 0:
        raise ValueError("maximum raw payload size must be a non-negative integer")
    if len(data) > max_payload_bytes + 8:
        raise ProtocolError("raw vendor notification exceeds configured frame bound")

    raw_type = int.from_bytes(data[0:2], "little")
    if raw_type in {0x0002, 0x0003}:
        declared_length = int.from_bytes(data[6:8], "little")
        payload = data[8:]
        if declared_length != len(payload):
            raise ProtocolError("raw vendor payload length does not match frame")
        if declared_length > max_payload_bytes:
            raise ProtocolError("raw vendor payload exceeds configured bound")
        return RawPayloadNotification(
            kind="audio" if raw_type == 0x0002 else "image",
            first_value=int.from_bytes(data[2:4], "little"),
            second_value=int.from_bytes(data[4:6], "little"),
            declared_length=declared_length,
            _payload=bytes(payload),
        )
    if raw_type == 0x0006:
        if len(data) < 10:
            raise ProtocolError("raw AI state notification must be at least 10 bytes")
        return RawAiStateNotification(
            first_value=data[8],
            second_value=data[9],
            trailing_bytes_ignored=len(data) - 10,
        )
    kinds = {
        0x0001: "ai_action",
        0x0009: "voice_command_confirmation",
        0x000A: "ai_command_type",
    }
    if raw_type in kinds:
        if len(data) < 9:
            raise ProtocolError("raw value notification must be at least 9 bytes")
        return RawSingleValueNotification(
            kind=kinds[raw_type],
            value=data[8],
            trailing_bytes_ignored=len(data) - 9,
        )
    raise ProtocolError("unsupported raw vendor notification type")
