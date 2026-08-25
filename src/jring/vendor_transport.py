"""Bounded offline model of a future vendor GATT transaction engine.

The objects in this module describe and simulate ordering; they cannot access a radio,
subscribe, unsubscribe, or write.  In particular, a returned write intent is test data
rather than authorization to send its bytes to hardware.  Planning and confirming a
live CCCD-disable operation remains a live-adapter blocker outside this offline slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import itertools
import math
from typing import Callable
from uuid import UUID

from .protocol import ProtocolError
from .uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    uuid16,
)
from .vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    encode_static_query,
    operation_opcode,
    parse_vendor_advanced_sensor_day,
    parse_vendor_band_functions,
    parse_vendor_battery,
    parse_vendor_current_sport,
    parse_vendor_device_info,
    parse_vendor_multi_sport_day,
    parse_vendor_oxygen_day,
    parse_vendor_screen_light_time,
    static_protocol_coverage,
)


CLIENT_CHARACTERISTIC_CONFIGURATION = uuid16(0x2902)
_ENGINE_IDS = itertools.count()


class EnginePhase(str, Enum):
    DISCONNECTED = "disconnected"
    DESCRIPTOR_REQUIRED = "descriptor_required"
    READY = "ready"


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
    DESCRIPTOR_FAILURE = "descriptor_failure"
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
    StaticQuery.MULTI_SPORT_DAY: parse_vendor_multi_sport_day,
    StaticQuery.OXYGEN_DAY: parse_vendor_oxygen_day,
    StaticQuery.ADVANCED_SENSOR_DAY: parse_vendor_advanced_sensor_day,
}
_ZERO_ARGUMENT_QUERIES = frozenset(
    {
        StaticQuery.CURRENT_SPORT,
        StaticQuery.BATTERY,
        StaticQuery.DEVICE_INFO,
        StaticQuery.BAND_FUNCTIONS,
    }
)


@dataclass(frozen=True, init=False, repr=False)
class OfflineVendorOperation:
    name: str
    request_endpoint_uuid: str
    response_endpoint_uuid: str
    _request_frame: bytes = field(repr=False)
    success_opcodes: tuple[int, ...]
    failure_opcodes: tuple[int, ...]
    expected_subcommand: int | None
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
    ) -> "OfflineVendorOperation":
        instance = object.__new__(cls)
        object.__setattr__(instance, "name", name)
        object.__setattr__(instance, "request_endpoint_uuid", VENDOR_CHARACTERISTIC_33F3)
        object.__setattr__(instance, "response_endpoint_uuid", VENDOR_CHARACTERISTIC_33F4)
        object.__setattr__(instance, "_request_frame", bytes(request_frame))
        object.__setattr__(instance, "success_opcodes", tuple(success_opcodes))
        object.__setattr__(instance, "failure_opcodes", tuple(failure_opcodes))
        object.__setattr__(instance, "expected_subcommand", expected_subcommand)
        object.__setattr__(instance, "_parser", parser)
        return instance

    @classmethod
    def from_static_request(
        cls, request: StaticVendorRequest
    ) -> "OfflineVendorOperation":
        """Build only from one of the closed, offline static-query encoders."""

        if type(request) is not StaticVendorRequest:
            raise TypeError("request must be a StaticVendorRequest")
        if not isinstance(request.operation, StaticQuery):
            raise TypeError("request operation must be a StaticQuery")
        frame = request.synthetic_bytes_for_test()
        if len(frame) != 20 or frame[0] != operation_opcode(request.operation):
            raise ValueError("static request does not match its operation opcode")
        if request.operation in _ZERO_ARGUMENT_QUERIES:
            expected = encode_static_query(request.operation).synthetic_bytes_for_test()
            if frame != expected:
                raise ValueError("static zero-argument request has an invalid shape")
        elif any(frame[2:]):
            raise ValueError("static day request has an invalid trailing shape")

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
    def screen_light_time(cls) -> "OfflineVendorOperation":
        """Closed static subcommand route used by offline matcher simulations."""

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
        if not isinstance(data, bytes) or len(data) != 20:
            raise ProtocolError("vendor response must be exactly 20 bytes")
        opcode = data[0]
        if opcode not in self.success_opcodes and opcode not in self.failure_opcodes:
            return _Match.UNRELATED, None
        if self.expected_subcommand is not None and data[1] != self.expected_subcommand:
            return _Match.UNRELATED, None
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
class CccdReadinessToken:
    generation: int
    _engine_id: int = field(repr=False)

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"CccdReadinessToken(generation={self.generation})"


@dataclass(frozen=True, repr=False)
class CccdEnableIntent:
    token: CccdReadinessToken
    characteristic_uuid: str
    descriptor_uuid: str
    _value: bytes = field(repr=False)

    @property
    def notifications_enabled(self) -> bool:
        return self._value == b"\x01\x00"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def synthetic_value_for_test(self) -> bytes:
        return bytes(self._value)

    def __repr__(self) -> str:
        return (
            "CccdEnableIntent("
            f"token={self.token!r}, characteristic_uuid={self.characteristic_uuid!r}, "
            f"descriptor_uuid={self.descriptor_uuid!r}, value=<redacted>, "
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
        self._expected_cccd_token: CccdReadinessToken | None = None
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
            f"has_in_flight={self._in_flight is not None}, hardware_eligible=False)"
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

    def mark_connected(self, *, now: float) -> CccdEnableIntent:
        self._observe_now(now)
        if self._phase is not EnginePhase.DISCONNECTED:
            raise ProtocolError("offline vendor engine is already connected")
        self._connection_generation += 1
        token = CccdReadinessToken(self._connection_generation, self._engine_id)
        self._expected_cccd_token = token
        self._phase = EnginePhase.DESCRIPTOR_REQUIRED
        return CccdEnableIntent(
            token=token,
            characteristic_uuid=VENDOR_CHARACTERISTIC_33F4,
            descriptor_uuid=CLIENT_CHARACTERISTIC_CONFIGURATION,
            _value=b"\x01\x00",
        )

    def confirm_cccd(
        self,
        *,
        token: CccdReadinessToken,
        characteristic_uuid: str,
        descriptor_uuid: str,
        enabled: bool,
        now: float,
    ) -> VendorEngineUpdate:
        self._observe_now(now)
        if self._phase is not EnginePhase.DESCRIPTOR_REQUIRED:
            raise ProtocolError("CCCD confirmation is not currently expected")
        if not isinstance(token, CccdReadinessToken):
            raise TypeError("CCCD token must be a CccdReadinessToken")
        if token != self._expected_cccd_token:
            raise ProtocolError("stale CCCD confirmation token")
        if type(enabled) is not bool:
            raise TypeError("CCCD enabled state must be a boolean")
        characteristic = _normalize_uuid(characteristic_uuid, "CCCD characteristic")
        descriptor = _normalize_uuid(descriptor_uuid, "CCCD descriptor")
        if (
            characteristic != VENDOR_CHARACTERISTIC_33F4
            or descriptor != CLIENT_CHARACTERISTIC_CONFIGURATION
        ):
            raise ProtocolError("CCCD confirmation does not match notification readiness")
        self._expected_cccd_token = None
        if not enabled:
            return VendorEngineUpdate(
                closure=self._close(
                    TransactionCloseReason.DESCRIPTOR_FAILURE,
                    TransactionCompleteness.FAILED,
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
        succeeded: bool,
        now: float,
    ) -> VendorEngineUpdate:
        if not isinstance(token, VendorOperationToken):
            raise TypeError("operation token must be a VendorOperationToken")
        if type(succeeded) is not bool:
            raise TypeError("write confirmation state must be a boolean")
        current = self._observe_now(now)
        if token != self.active_token:
            return VendorEngineUpdate()
        expired = self._expire(current)
        if expired is not None:
            return VendorEngineUpdate(closure=expired)
        if self._write_pending is None:
            raise ProtocolError("characteristic write confirmation was not expected")
        if not succeeded:
            return VendorEngineUpdate(
                closure=self._close(
                    TransactionCloseReason.WRITE_FAILURE,
                    TransactionCompleteness.FAILED,
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

    def disconnect(self) -> VendorEngineUpdate:
        completeness = self._interrupted_completeness()
        closure = self._close(
            TransactionCloseReason.DISCONNECTED,
            completeness,
        )
        self._expected_cccd_token = None
        self._phase = EnginePhase.DISCONNECTED
        return VendorEngineUpdate(closure=closure)
