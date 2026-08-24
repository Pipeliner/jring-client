from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class HeartRate:
    bpm: int
    contact_detected: bool | None = None


@dataclass(frozen=True)
class HistoryRecord:
    timestamp: datetime
    kind: str
    value: int | float

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


def parse_battery(data: bytes) -> int:
    if len(data) != 1 or data[0] > 100:
        raise ProtocolError("invalid battery level")
    return data[0]


def parse_device_text(data: bytes, *, maximum: int = 64) -> str:
    if not data or len(data) > maximum:
        raise ProtocolError("invalid device-information length")
    try:
        value = data.rstrip(b"\x00").decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError("device information is not UTF-8") from exc
    if not value or any(ord(char) < 32 for char in value):
        raise ProtocolError("invalid device-information text")
    return value


def parse_heart_rate(data: bytes) -> HeartRate:
    if len(data) < 2:
        raise ProtocolError("truncated heart-rate measurement")
    flags = data[0]
    width = 2 if flags & 1 else 1
    if len(data) < 1 + width:
        raise ProtocolError("truncated heart-rate value")
    bpm = int.from_bytes(data[1:1 + width], "little")
    if not 1 <= bpm <= 300:
        raise ProtocolError("implausible heart-rate value")
    contact = None
    if flags & 0x04:
        contact = bool(flags & 0x02)
    return HeartRate(bpm, contact)


def _xor(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
    return value


@dataclass(frozen=True)
class SimEnvelope:
    """Client-owned test format. Never transmitted to hardware."""

    kind: int
    payload: bytes

    def encode(self) -> bytes:
        if not 0 <= self.kind <= 255 or len(self.payload) > 4096:
            raise ProtocolError("invalid simulator envelope")
        body = bytes((self.kind,)) + len(self.payload).to_bytes(2, "little") + self.payload
        return b"JR" + body + bytes((_xor(body),))

    @classmethod
    def decode(cls, data: bytes) -> "SimEnvelope":
        if len(data) < 6 or data[:2] != b"JR":
            raise ProtocolError("invalid simulator envelope header")
        size = int.from_bytes(data[3:5], "little")
        if size > 4096 or len(data) != size + 6:
            raise ProtocolError("invalid simulator envelope length")
        if _xor(data[2:-1]) != data[-1]:
            raise ProtocolError("simulator envelope checksum mismatch")
        return cls(data[2], data[5:-1])
