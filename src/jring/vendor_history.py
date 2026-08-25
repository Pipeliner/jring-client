"""Pure, offline state machines for statically recovered history notifications.

This module never subscribes, writes, or turns a locally observed quiet period into a
wire-level end marker.  Device timestamps remain opaque epoch-like integers: callers
must not apply the host's current timezone offset to historical records.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import itertools
import math

from .protocol import ProtocolError
from .vendor_protocol import (
    parse_vendor_advanced_sensor_day,
    parse_vendor_oxygen_day,
)


class HistoryFamily(str, Enum):
    DAY_TYPE_1 = "day_type_1"
    DAY_TYPE_2 = "day_type_2"
    DAY_TYPE_3 = "day_type_3"
    TEMPERATURE = "temperature"
    OXYGEN = "oxygen"
    ADVANCED_SENSOR = "advanced_sensor"


class HistoryStreamKind(str, Enum):
    DAILY = "daily"
    DETAIL = "detail"
    TEMPERATURE = "temperature"
    OXYGEN = "oxygen"
    ADVANCED_SENSOR = "advanced_sensor"


class HistoryPhase(str, Enum):
    WAITING_FIRST_FRAME = "waiting_first_frame"
    RECEIVING = "receiving"
    CLOSED = "closed"


class HistoryCompleteness(str, Enum):
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"
    FAILED = "failed"
    ABORTED = "aborted"


class HistoryCloseReason(str, Enum):
    WIRE_TERMINAL = "wire_terminal"
    DEVICE_METADATA = "device_metadata"
    DEVICE_FAILURE = "device_failure"
    FIRST_FRAME_TIMEOUT = "first_frame_timeout"
    IDLE_TIMEOUT = "idle_timeout"
    OVERALL_TIMEOUT = "overall_timeout"
    DISCONNECTED = "disconnected"
    CANCELLED = "cancelled"


_DAY_TYPE_BY_FAMILY = {
    HistoryFamily.DAY_TYPE_1: 1,
    HistoryFamily.DAY_TYPE_2: 2,
    HistoryFamily.DAY_TYPE_3: 3,
    HistoryFamily.TEMPERATURE: 12,
    HistoryFamily.OXYGEN: 13,
    HistoryFamily.ADVANCED_SENSOR: 14,
}

_SESSION_IDS = itertools.count()


@dataclass(frozen=True, repr=False)
class VendorHistorySample:
    family: HistoryFamily
    device_epoch_seconds: int
    values: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.family, HistoryFamily):
            raise TypeError("history sample family must be a HistoryFamily")
        if type(self.device_epoch_seconds) is not int:
            raise TypeError("device timestamp must be an integer")
        if self.device_epoch_seconds < 0:
            raise ValueError("device timestamp cannot be negative")
        if not isinstance(self.values, tuple):
            raise TypeError("history sample values must be a tuple")
        if any(type(value) is not int for value in self.values):
            raise TypeError("history sample values must be integers")

        expected_lengths = {
            HistoryFamily.DAY_TYPE_1: 2,
            HistoryFamily.DAY_TYPE_2: 2,
            HistoryFamily.DAY_TYPE_3: 2,
            HistoryFamily.TEMPERATURE: 2,
            HistoryFamily.OXYGEN: 1,
            HistoryFamily.ADVANCED_SENSOR: 5,
        }
        if len(self.values) != expected_lengths[self.family]:
            raise ValueError("history sample has the wrong value count for its family")

        maximum = 0xFFFF if self.family is HistoryFamily.TEMPERATURE else 0xFF
        if any(not 0 <= value <= maximum for value in self.values):
            raise ValueError("history sample value is outside its wire field width")
        if self.family in {HistoryFamily.DAY_TYPE_1, HistoryFamily.DAY_TYPE_2}:
            if self.values[1] != 0:
                raise ValueError("day type 1/2 second value must be zero")
        if self.family is HistoryFamily.DAY_TYPE_3 and self.values[0] != 0:
            raise ValueError("day type 3 first value must be zero")

    @property
    def timestamp_policy(self) -> str:
        return "raw_device_epoch"

    @property
    def data_by_day_type(self) -> int:
        return _DAY_TYPE_BY_FAMILY[self.family]

    @property
    def data_by_day_values(self) -> tuple[int, int]:
        if self.family is HistoryFamily.ADVANCED_SENSOR:
            return self.values[0], 0
        if len(self.values) < 2:
            return self.values[0], 0
        return self.values[0], self.values[1]

    @property
    def hardware_verified(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "VendorHistorySample("
            f"family={self.family.value!r}, "
            "device_epoch_seconds=<redacted>, values=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class DecodedVendorHistoryFrame:
    opcode: int
    samples: tuple[VendorHistorySample, ...] = ()
    metadata_kind: str | None = None
    metadata_values: tuple[int, ...] = ()
    explicit_terminal: bool = False
    failure: bool = False

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "DecodedVendorHistoryFrame("
            f"opcode=0x{self.opcode:02x}, sample_count={len(self.samples)}, "
            f"metadata_kind={self.metadata_kind!r}, "
            f"explicit_terminal={self.explicit_terminal}, failure={self.failure})"
        )


@dataclass(frozen=True, repr=False)
class HistoryClosure:
    stream_kind: HistoryStreamKind
    reason: HistoryCloseReason
    completeness: HistoryCompleteness
    families: tuple[HistoryFamily, ...]
    last_device_epoch_seconds: int | None = None
    last_timestamp_by_family: tuple[tuple[HistoryFamily, int], ...] = ()

    @property
    def wire_terminal(self) -> bool:
        return self.reason is HistoryCloseReason.WIRE_TERMINAL

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def source(self) -> str:
        if self.reason is HistoryCloseReason.WIRE_TERMINAL:
            return "wire"
        if self.reason is HistoryCloseReason.DEVICE_METADATA:
            return "device_metadata"
        if self.reason is HistoryCloseReason.DEVICE_FAILURE:
            return "device"
        return "local"

    def __repr__(self) -> str:
        return (
            "HistoryClosure("
            f"stream_kind={self.stream_kind.value!r}, reason={self.reason.value!r}, "
            f"completeness={self.completeness.value!r}, "
            f"families={tuple(item.value for item in self.families)!r}, "
            "last_device_epoch_seconds=<redacted>)"
        )


@dataclass(frozen=True, repr=False)
class VendorHistoryUpdate:
    samples: tuple[VendorHistorySample, ...] = ()
    closure: HistoryClosure | None = None

    def __repr__(self) -> str:
        reason = None if self.closure is None else self.closure.reason.value
        return (
            "VendorHistoryUpdate("
            f"sample_count={len(self.samples)}, closure_reason={reason!r})"
        )


@dataclass(frozen=True, repr=False)
class HistoryDeadlineToken:
    """Opaque generation guard for an adapter-owned scheduled callback."""

    generation: int
    deadline: float
    _session_id: int

    def __repr__(self) -> str:
        return (
            "HistoryDeadlineToken("
            f"generation={self.generation}, deadline={self.deadline!r})"
        )


def _response(data: bytes) -> bytes:
    if not isinstance(data, bytes) or len(data) != 20:
        raise ProtocolError("vendor history notification must be exactly 20 bytes")
    return data


def _minute_samples(
    response: bytes, family: HistoryFamily
) -> tuple[VendorHistorySample, ...]:
    base = int.from_bytes(response[1:5], "little")
    return tuple(
        VendorHistorySample(
            family=family,
            device_epoch_seconds=base + index * 60,
            values=(value, 0),
        )
        for index, value in enumerate(response[5:20])
    )


def _decode_detail(response: bytes) -> DecodedVendorHistoryFrame:
    marker = response[1]
    if marker == 0xFF:
        return DecodedVendorHistoryFrame(
            opcode=0x16,
            metadata_kind="terminal",
            explicit_terminal=True,
        )
    if marker == 0xF0:
        return DecodedVendorHistoryFrame(
            opcode=0x16,
            metadata_kind="f0",
            metadata_values=(int.from_bytes(response[6:8], "little"),),
        )
    if marker == 0xAA:
        return DecodedVendorHistoryFrame(
            opcode=0x16,
            metadata_kind="aa",
            metadata_values=(
                response[2],
                int.from_bytes(response[7:9], "little"),
            ),
        )
    if marker != 0xA0:
        raise ProtocolError("unsupported vendor detail-history marker")

    base = int.from_bytes(response[2:6], "little")
    samples = []
    for index, offset in enumerate((8, 14)):
        # Java Math.round is floor(x + 0.5) for these non-negative byte sums;
        # Python's round() would incorrectly use ties-to-even.
        average = (sum(response[offset : offset + 6]) + 3) // 6
        samples.append(
            VendorHistorySample(
                family=HistoryFamily.DAY_TYPE_3,
                device_epoch_seconds=base + index * 60,
                values=(0, average),
            )
        )
    return DecodedVendorHistoryFrame(
        opcode=0x16,
        samples=tuple(samples),
        metadata_kind="a0",
        metadata_values=(int.from_bytes(response[6:8], "little"),),
    )


def decode_vendor_history_frame(data: bytes) -> DecodedVendorHistoryFrame:
    """Decode one static history notification without retaining its raw bytes."""

    response = _response(data)
    opcode = response[0]
    if opcode == 0x10:
        return DecodedVendorHistoryFrame(
            opcode=opcode,
            samples=_minute_samples(response, HistoryFamily.DAY_TYPE_1),
        )
    if opcode == 0x11:
        return DecodedVendorHistoryFrame(
            opcode=opcode,
            samples=_minute_samples(response, HistoryFamily.DAY_TYPE_2),
        )
    if opcode == 0x16:
        return _decode_detail(response)
    if opcode == 0x39:
        base = int.from_bytes(response[1:5], "little")
        samples = tuple(
            VendorHistorySample(
                family=HistoryFamily.TEMPERATURE,
                device_epoch_seconds=base + index * 300,
                values=(
                    int.from_bytes(response[5 + index * 4 : 7 + index * 4], "little"),
                    int.from_bytes(response[7 + index * 4 : 9 + index * 4], "little"),
                ),
            )
            for index in range(3)
        )
        return DecodedVendorHistoryFrame(opcode=opcode, samples=samples)
    if opcode == 0x40:
        decoded = parse_vendor_oxygen_day(response)
        return DecodedVendorHistoryFrame(
            opcode=opcode,
            samples=tuple(
                VendorHistorySample(
                    family=HistoryFamily.OXYGEN,
                    device_epoch_seconds=sample.device_epoch_seconds,
                    values=(sample.value,),
                )
                for sample in decoded.samples
            ),
        )
    if opcode == 0x55:
        decoded = parse_vendor_advanced_sensor_day(response)
        return DecodedVendorHistoryFrame(
            opcode=opcode,
            samples=tuple(
                VendorHistorySample(
                    family=HistoryFamily.ADVANCED_SENSOR,
                    device_epoch_seconds=sample.device_epoch_seconds,
                    values=sample.fields,
                )
                for sample in decoded.samples
            ),
        )
    if opcode in {0x90, 0x96, 0xB9}:
        return DecodedVendorHistoryFrame(opcode=opcode, failure=True)
    raise ProtocolError("unsupported vendor history notification opcode")


_SUCCESS_OPCODES = {
    HistoryStreamKind.DAILY: frozenset({0x10, 0x11}),
    HistoryStreamKind.DETAIL: frozenset({0x16}),
    HistoryStreamKind.TEMPERATURE: frozenset({0x39}),
    HistoryStreamKind.OXYGEN: frozenset({0x40}),
    HistoryStreamKind.ADVANCED_SENSOR: frozenset({0x55}),
}
_FAILURE_OPCODES = {
    HistoryStreamKind.DAILY: frozenset({0x90}),
    HistoryStreamKind.DETAIL: frozenset({0x96}),
    HistoryStreamKind.TEMPERATURE: frozenset({0xB9}),
    HistoryStreamKind.OXYGEN: frozenset(),
    HistoryStreamKind.ADVANCED_SENSOR: frozenset(),
}
_DETAIL_FAMILY = (HistoryFamily.DAY_TYPE_3,)


def _finite_positive(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return converted


class VendorHistoryStream:
    """Deterministic state for one offline history request/response sequence."""

    def __init__(
        self,
        kind: HistoryStreamKind,
        *,
        started_at: float,
        first_frame_timeout: float = 8.0,
        idle_timeout: float = 2.0,
        overall_timeout: float = 30.0,
    ) -> None:
        if not isinstance(kind, HistoryStreamKind):
            raise TypeError("history stream kind must be a HistoryStreamKind")
        if isinstance(started_at, bool) or not isinstance(started_at, (int, float)):
            raise TypeError("started_at must be a monotonic number")
        self._started_at = float(started_at)
        if not math.isfinite(self._started_at):
            raise ValueError("started_at must be finite")
        self._first_timeout = _finite_positive(first_frame_timeout, "first-frame timeout")
        self._idle_timeout = _finite_positive(idle_timeout, "idle timeout")
        self._overall_timeout = _finite_positive(overall_timeout, "overall timeout")
        if self._overall_timeout < self._first_timeout:
            raise ValueError("overall timeout cannot precede first-frame timeout")

        self._kind = kind
        self._phase = HistoryPhase.WAITING_FIRST_FRAME
        self._first_deadline = self._started_at + self._first_timeout
        self._overall_deadline = self._started_at + self._overall_timeout
        if not (
            math.isfinite(self._first_deadline)
            and math.isfinite(self._overall_deadline)
        ):
            raise ValueError("calculated history deadline must be finite")
        self._idle_deadline: float | None = None
        self._last_now = self._started_at
        self._session_id = next(_SESSION_IDS)
        self._generation = 0
        self._families: set[HistoryFamily] = set()
        self._last_by_family: dict[HistoryFamily, int] = {}
        self._last_emitted: int | None = None
        self._detail_f0: int | None = None
        self._detail_aa: tuple[int, int] | None = None

    def __repr__(self) -> str:
        return (
            "VendorHistoryStream("
            f"kind={self.kind.value!r}, phase={self.phase.value!r})"
        )

    @property
    def kind(self) -> HistoryStreamKind:
        return self._kind

    @property
    def phase(self) -> HistoryPhase:
        return self._phase

    @property
    def next_deadline(self) -> float | None:
        if self._phase is HistoryPhase.CLOSED:
            return None
        if self._phase is HistoryPhase.WAITING_FIRST_FRAME:
            return min(self._first_deadline, self._overall_deadline)
        if self._idle_deadline is None:
            return self._overall_deadline
        return min(self._idle_deadline, self._overall_deadline)

    def deadline_token(self) -> HistoryDeadlineToken | None:
        deadline = self.next_deadline
        if deadline is None:
            return None
        return HistoryDeadlineToken(self._generation, deadline, self._session_id)

    def _validate_now(self, now: float) -> float:
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise TypeError("now must be a monotonic number")
        converted = float(now)
        if not math.isfinite(converted) or converted < self._started_at:
            raise ValueError("now must be finite and not precede stream start")
        if converted < self._last_now:
            raise ValueError("monotonic time cannot move backwards")
        self._last_now = converted
        return converted

    def _ordered_families(self) -> tuple[HistoryFamily, ...]:
        return tuple(family for family in HistoryFamily if family in self._families)

    def _close(
        self,
        reason: HistoryCloseReason,
        completeness: HistoryCompleteness,
    ) -> HistoryClosure | None:
        if self._phase is HistoryPhase.CLOSED:
            return None
        self._phase = HistoryPhase.CLOSED
        self._generation += 1
        self._idle_deadline = None
        families = self._ordered_families()
        by_family = tuple(
            (family, self._last_by_family[family])
            for family in families
            if family in self._last_by_family
        )
        self._detail_f0 = None
        self._detail_aa = None
        return HistoryClosure(
            stream_kind=self._kind,
            reason=reason,
            completeness=completeness,
            families=families,
            last_device_epoch_seconds=self._last_emitted,
            last_timestamp_by_family=by_family,
        )

    def _expire(self, now: float) -> HistoryClosure | None:
        if self._phase is HistoryPhase.CLOSED:
            return None
        if self._phase is HistoryPhase.WAITING_FIRST_FRAME and now >= self._first_deadline:
            return self._close(
                HistoryCloseReason.FIRST_FRAME_TIMEOUT,
                HistoryCompleteness.ABORTED,
            )
        if now >= self._overall_deadline:
            return self._close(
                HistoryCloseReason.OVERALL_TIMEOUT,
                HistoryCompleteness.ABORTED,
            )
        if self._idle_deadline is not None and now >= self._idle_deadline:
            return self._close(
                HistoryCloseReason.IDLE_TIMEOUT,
                HistoryCompleteness.UNKNOWN,
            )
        return None

    def _record_samples(self, samples: tuple[VendorHistorySample, ...]) -> None:
        for sample in samples:
            self._families.add(sample.family)
            self._last_by_family[sample.family] = sample.device_epoch_seconds
            self._last_emitted = sample.device_epoch_seconds

    def feed(self, data: bytes, *, now: float) -> VendorHistoryUpdate:
        current = self._validate_now(now)
        if self._phase is HistoryPhase.CLOSED:
            raise ProtocolError("vendor history stream is closed")
        expired = self._expire(current)
        if expired is not None:
            return VendorHistoryUpdate(closure=expired)

        decoded = decode_vendor_history_frame(data)
        accepted = _SUCCESS_OPCODES[self._kind] | _FAILURE_OPCODES[self._kind]
        if decoded.opcode not in accepted:
            raise ProtocolError("history notification does not match active stream")

        if decoded.failure:
            return VendorHistoryUpdate(
                closure=self._close(
                    HistoryCloseReason.DEVICE_FAILURE,
                    HistoryCompleteness.FAILED,
                )
            )

        self._phase = HistoryPhase.RECEIVING
        self._generation += 1
        remaining = self._overall_deadline - current
        self._idle_deadline = (
            self._overall_deadline
            if self._idle_timeout >= remaining
            else current + self._idle_timeout
        )
        self._record_samples(decoded.samples)

        if self._kind is HistoryStreamKind.DETAIL:
            self._families.update(_DETAIL_FAMILY)
            if decoded.metadata_kind == "f0":
                self._detail_f0 = decoded.metadata_values[0]
            elif decoded.metadata_kind == "aa":
                self._detail_aa = (
                    decoded.metadata_values[0],
                    decoded.metadata_values[1],
                )

        if decoded.explicit_terminal:
            return VendorHistoryUpdate(
                samples=decoded.samples,
                closure=self._close(
                    HistoryCloseReason.WIRE_TERMINAL,
                    HistoryCompleteness.CONFIRMED,
                ),
            )

        if (
            self._kind is HistoryStreamKind.DETAIL
            and decoded.metadata_kind == "a0"
            and self._detail_f0 is not None
            and self._detail_aa is not None
            and self._detail_aa[0] == self._detail_f0
            and self._detail_aa[1] == decoded.metadata_values[0] + 1
        ):
            return VendorHistoryUpdate(
                samples=decoded.samples,
                closure=self._close(
                    HistoryCloseReason.DEVICE_METADATA,
                    HistoryCompleteness.CONFIRMED,
                ),
            )

        return VendorHistoryUpdate(samples=decoded.samples)

    def poll(
        self,
        *,
        now: float,
        token: HistoryDeadlineToken | None = None,
    ) -> VendorHistoryUpdate:
        if token is not None and not isinstance(token, HistoryDeadlineToken):
            raise TypeError("history deadline token must be a HistoryDeadlineToken")
        current = self._validate_now(now)
        if token is not None:
            current_token = self.deadline_token()
            if current_token != token:
                return VendorHistoryUpdate()
        return VendorHistoryUpdate(closure=self._expire(current))

    def disconnect(self) -> VendorHistoryUpdate:
        return VendorHistoryUpdate(
            closure=self._close(
                HistoryCloseReason.DISCONNECTED,
                HistoryCompleteness.ABORTED,
            )
        )

    def cancel(self) -> VendorHistoryUpdate:
        return VendorHistoryUpdate(
            closure=self._close(
                HistoryCloseReason.CANCELLED,
                HistoryCompleteness.ABORTED,
            )
        )
