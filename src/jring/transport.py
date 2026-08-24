from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from .protocol import HistoryRecord
from .uuids import (
    BATTERY_LEVEL, DEVICE_INFO_SERVICE, FIRMWARE, HEART_RATE_MEASUREMENT,
    HEART_RATE_SERVICE, MANUFACTURER, MODEL,
)

NotifyCallback = Callable[[bytes], None]


class BleTransport(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def read(self, characteristic: str) -> bytes: ...
    async def write(self, characteristic: str, data: bytes) -> None: ...
    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None: ...
    async def unsubscribe(self, characteristic: str) -> None: ...
    async def service_uuids(self) -> set[str]: ...


class FakeTransport:
    def __init__(self, values: dict[str, bytes], services: set[str], *, read_delay: float = 0):
        self.values = {key.lower(): value for key, value in values.items()}
        self.services = {value.lower() for value in services}
        self.read_delay = read_delay
        self.callbacks: dict[str, NotifyCallback] = {}
        self.connected = False
        self.closed = False
        self.records = [HistoryRecord(datetime(2026, 1, 1, tzinfo=timezone.utc), "heart_rate", 70)]

    @classmethod
    def standard_ring(cls, *, read_delay: float = 0) -> "FakeTransport":
        return cls({BATTERY_LEVEL: b"\x54", MANUFACTURER: b"Simulated", MODEL: b"JR-SIM",
                    FIRMWARE: b"0.0-test"}, {DEVICE_INFO_SERVICE, HEART_RATE_SERVICE},
                   read_delay=read_delay)

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.callbacks.clear()
        self.connected = False
        self.closed = True

    async def read(self, characteristic: str) -> bytes:
        await asyncio.sleep(self.read_delay)
        try:
            return self.values[characteristic.lower()]
        except KeyError as exc:
            raise LookupError("characteristic unavailable") from exc

    async def write(self, characteristic: str, data: bytes) -> None:
        self.values[characteristic.lower()] = bytes(data)

    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None:
        self.callbacks[characteristic.lower()] = callback

    async def unsubscribe(self, characteristic: str) -> None:
        self.callbacks.pop(characteristic.lower(), None)

    async def service_uuids(self) -> set[str]:
        return set(self.services)

    def emit(self, characteristic: str, data: bytes) -> None:
        self.callbacks[characteristic.lower()](data)
