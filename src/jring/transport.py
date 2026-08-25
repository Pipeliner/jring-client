from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from .protocol import HistoryRecord
from .uuids import (
    BATTERY_LEVEL, DEVICE_INFO_SERVICE, FIRMWARE, HEART_RATE_MEASUREMENT,
    HEART_RATE_SERVICE, MANUFACTURER, MODEL,
)

NotifyCallback = Callable[[bytes], None]


@dataclass(frozen=True)
class GattCharacteristicMetadata:
    service_uuid: str
    uuid: str
    properties: tuple[str, ...]
    descriptor_uuids: tuple[str, ...]


@dataclass(frozen=True)
class SimulatorProfile:
    name: str
    description: str
    standard_hid_advertised: bool


SIMULATOR_PROFILES = (
    SimulatorProfile(
        name="basic",
        description="standard ring metadata; standard HID not advertised",
        standard_hid_advertised=False,
    ),
    SimulatorProfile(
        name="hid",
        description=(
            "basic metadata plus standard HID advertisement metadata; "
            "no HID reports are read or emitted"
        ),
        standard_hid_advertised=True,
    ),
)


def simulator_profile(name: str) -> SimulatorProfile:
    for profile in SIMULATOR_PROFILES:
        if profile.name == name:
            return profile
    raise ValueError("simulator profile must be basic or hid")


class BleTransport(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def read(self, characteristic: str) -> bytes: ...
    async def write(self, characteristic: str, data: bytes) -> None: ...
    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None: ...
    async def unsubscribe(self, characteristic: str) -> None: ...
    async def service_uuids(self) -> set[str]: ...
    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]: ...


class FakeTransport:
    def __init__(
        self,
        values: dict[str, bytes],
        services: set[str],
        *,
        read_delay: float = 0,
        gatt_metadata: tuple[GattCharacteristicMetadata, ...] = (),
    ):
        self.values = {key.lower(): value for key, value in values.items()}
        self.services = {value.lower() for value in services}
        self.read_delay = read_delay
        self.gatt_metadata = gatt_metadata
        self.callbacks: dict[str, NotifyCallback] = {}
        self.connected = False
        self.closed = False
        self.records = [HistoryRecord(datetime(2026, 1, 1, tzinfo=timezone.utc), "heart_rate", 70)]

    @classmethod
    def standard_ring(cls, *, read_delay: float = 0) -> "FakeTransport":
        return cls({BATTERY_LEVEL: b"\x54", MANUFACTURER: b"Simulated", MODEL: b"JR-SIM",
                    FIRMWARE: b"0.0-test"}, {DEVICE_INFO_SERVICE, HEART_RATE_SERVICE},
                   read_delay=read_delay)

    @classmethod
    def standard_hid_ring(cls) -> "FakeTransport":
        from .uuids import (
            HID_INFORMATION,
            HID_REPORT,
            HID_REPORT_MAP,
            HUMAN_INTERFACE_DEVICE_SERVICE,
            REPORT_REFERENCE_DESCRIPTOR,
        )

        transport = cls.standard_ring()
        transport.services.add(HUMAN_INTERFACE_DEVICE_SERVICE)
        transport.gatt_metadata = (
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE, HID_INFORMATION, ("read",), ()
            ),
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE, HID_REPORT_MAP, ("read",), ()
            ),
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE,
                HID_REPORT,
                ("notify",),
                (REPORT_REFERENCE_DESCRIPTOR,),
            ),
        )
        return transport

    @classmethod
    def for_simulator_profile(cls, name: str = "basic") -> "FakeTransport":
        profile = simulator_profile(name)
        return (
            cls.standard_hid_ring()
            if profile.standard_hid_advertised
            else cls.standard_ring()
        )

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

    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]:
        return tuple(self.gatt_metadata)

    def emit(self, characteristic: str, data: bytes) -> None:
        self.callbacks[characteristic.lower()](data)
