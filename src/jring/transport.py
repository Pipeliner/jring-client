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
    CLIENT_CHARACTERISTIC_CONFIGURATION,
)

NotifyCallback = Callable[[bytes], None]
DisconnectListener = Callable[[BaseException | None], None]


@dataclass(frozen=True)
class GattCharacteristicTarget:
    """Opaque, connection-scoped identity for one enumerated characteristic.

    Transport implementations must validate object identity as well as these public
    fields.  Reconstructing an equal value must not grant access to a characteristic.
    """

    connection_generation: int
    service_uuid: str
    uuid: str
    instance_id: str


@dataclass(frozen=True)
class GattCharacteristicMetadata:
    service_uuid: str
    uuid: str
    properties: tuple[str, ...]
    descriptor_uuids: tuple[str, ...]
    instance_id: str | None = None
    descriptor_instance_ids: tuple[str, ...] = ()
    target: GattCharacteristicTarget | None = None


@dataclass(frozen=True, init=False, repr=False)
class HeartRateSubscriptionToken:
    """Opaque identity for one current-generation standard HR subscription."""

    connection_generation: int
    target_instance_id: str

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("heart-rate subscription tokens are transport-owned")

    @classmethod
    def _create(
        cls, connection_generation: int, target_instance_id: str
    ) -> "HeartRateSubscriptionToken":
        token = object.__new__(cls)
        object.__setattr__(token, "connection_generation", connection_generation)
        object.__setattr__(token, "target_instance_id", target_instance_id)
        return token

    def __repr__(self) -> str:
        return (
            "HeartRateSubscriptionToken("
            f"connection_generation={self.connection_generation!r}, target=<redacted>)"
        )


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

    async def write_with_response(self, characteristic: str, data: bytes) -> None:
        """Request an ATT response and return only after backend success.

        Failure to dispatch or receive that response must raise.  This transport-level
        response is not an application-level notification from the device.
        """
        ...

    async def service_uuids(self) -> set[str]: ...
    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]: ...
    def owns_target(self, target: GattCharacteristicTarget) -> bool: ...
    def add_disconnect_listener(
        self, listener: DisconnectListener
    ) -> Callable[[], None]: ...
    async def subscribe_heart_rate_measurement(
        self, target: GattCharacteristicTarget, callback: NotifyCallback
    ) -> HeartRateSubscriptionToken: ...
    async def unsubscribe_heart_rate_measurement(
        self, subscription: HeartRateSubscriptionToken
    ) -> None: ...


class TargetedBleTransport(Protocol):
    """Current-snapshot identity checks for a future reviewed vendor runtime.

    This protocol deliberately exposes no target I/O.  It only lets pure route
    preparation be followed by a separate transport-ownership check.
    """

    def add_disconnect_listener(
        self, listener: DisconnectListener
    ) -> Callable[[], None]: ...
    def owns_target(self, target: GattCharacteristicTarget) -> bool: ...


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
        self.retained_heart_rate_callbacks: list[NotifyCallback] = []
        self.connected = False
        self.closed = False
        self.connection_generation = 0
        self.connect_count = 0
        self.close_count = 0
        self.write_count = 0
        self.heart_rate_subscription_count = 0
        self.heart_rate_unsubscription_count = 0
        self._targets: dict[
            int, tuple[GattCharacteristicTarget, GattCharacteristicMetadata]
        ] = {}
        self._heart_rate_subscriptions: dict[
            int, tuple[HeartRateSubscriptionToken, GattCharacteristicTarget]
        ] = {}
        self._disconnect_listeners: dict[int, DisconnectListener] = {}
        self._next_disconnect_listener = 0
        self.records = [HistoryRecord(datetime(2026, 1, 1, tzinfo=timezone.utc), "heart_rate", 70)]

    @classmethod
    def standard_ring(cls, *, read_delay: float = 0) -> "FakeTransport":
        return cls(
            {
                BATTERY_LEVEL: b"\x54",
                MANUFACTURER: b"Simulated",
                MODEL: b"JR-SIM",
                FIRMWARE: b"0.0-test",
            },
            {DEVICE_INFO_SERVICE, HEART_RATE_SERVICE},
            read_delay=read_delay,
            gatt_metadata=(
                GattCharacteristicMetadata(
                    HEART_RATE_SERVICE,
                    HEART_RATE_MEASUREMENT,
                    ("notify",),
                    (CLIENT_CHARACTERISTIC_CONFIGURATION,),
                ),
            ),
        )

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
        transport.gatt_metadata = (*transport.gatt_metadata,
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
        if self.connected:
            raise ConnectionError("fake transport is already connected")
        self.connect_count += 1
        self.connection_generation += 1
        self._targets.clear()
        self._heart_rate_subscriptions.clear()
        self.connected = True
        self.closed = False

    async def close(self) -> None:
        self.close_count += 1
        self.callbacks.clear()
        self._heart_rate_subscriptions.clear()
        self._targets.clear()
        self.connected = False
        self.closed = True

    async def read(self, characteristic: str) -> bytes:
        await asyncio.sleep(self.read_delay)
        try:
            return self.values[characteristic.lower()]
        except KeyError as exc:
            raise LookupError("characteristic unavailable") from exc

    async def write(self, characteristic: str, data: bytes) -> None:
        await self.write_with_response(characteristic, data)

    async def write_with_response(self, characteristic: str, data: bytes) -> None:
        """Record a completed response-requesting write in this in-memory fake."""
        self.write_count += 1
        self.values[characteristic.lower()] = bytes(data)

    async def service_uuids(self) -> set[str]:
        return set(self.services)

    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]:
        if not self.connected:
            raise ConnectionError("fake transport is not connected")
        records = []
        current_targets: dict[
            int, tuple[GattCharacteristicTarget, GattCharacteristicMetadata]
        ] = {}
        for index, record in enumerate(self.gatt_metadata, start=1):
            instance_id = record.instance_id or f"fake-characteristic-{index}"
            descriptor_ids = record.descriptor_instance_ids or tuple(
                f"{instance_id}-descriptor-{descriptor_index}"
                for descriptor_index, _uuid in enumerate(
                    record.descriptor_uuids, start=1
                )
            )
            target = GattCharacteristicTarget(
                self.connection_generation,
                record.service_uuid.lower(),
                record.uuid.lower(),
                instance_id,
            )
            is_standard_heart_rate = (
                record.service_uuid.lower() == HEART_RATE_SERVICE
                and record.uuid.lower() == HEART_RATE_MEASUREMENT
            )
            resolved = GattCharacteristicMetadata(
                record.service_uuid.lower(),
                record.uuid.lower(),
                record.properties,
                record.descriptor_uuids,
                instance_id if is_standard_heart_rate else record.instance_id,
                (
                    descriptor_ids
                    if is_standard_heart_rate
                    else record.descriptor_instance_ids
                ),
                target if is_standard_heart_rate else record.target,
            )
            current_targets[id(target)] = (target, resolved)
            records.append(resolved)
        self._targets = current_targets
        return tuple(records)

    def owns_target(self, target: GattCharacteristicTarget) -> bool:
        record = self._targets.get(id(target))
        return bool(
            self.connected
            and record is not None
            and record[0] is target
            and target.connection_generation == self.connection_generation
        )

    def add_disconnect_listener(
        self, listener: DisconnectListener
    ) -> Callable[[], None]:
        self._next_disconnect_listener += 1
        listener_id = self._next_disconnect_listener
        self._disconnect_listeners[listener_id] = listener

        def remove() -> None:
            self._disconnect_listeners.pop(listener_id, None)

        return remove

    async def subscribe_heart_rate_measurement(
        self, target: GattCharacteristicTarget, callback: NotifyCallback
    ) -> HeartRateSubscriptionToken:
        if not callable(callback):
            raise TypeError("heart-rate callback must be callable")
        if self._heart_rate_subscriptions:
            raise RuntimeError("a heart-rate subscription is already active")
        record = self._targets.get(id(target))
        if (
            record is None
            or record[0] is not target
            or not self.owns_target(target)
            or target.service_uuid != HEART_RATE_SERVICE
            or target.uuid != HEART_RATE_MEASUREMENT
        ):
            raise PermissionError("invalid standard heart-rate target")
        metadata = record[1]
        if (
            not isinstance(metadata.properties, tuple)
            or not all(isinstance(value, str) for value in metadata.properties)
            or "notify" not in {value.lower() for value in metadata.properties}
            or not isinstance(metadata.descriptor_uuids, tuple)
            or not all(
                isinstance(value, str) for value in metadata.descriptor_uuids
            )
            or sum(
                value.lower() == CLIENT_CHARACTERISTIC_CONFIGURATION
                for value in metadata.descriptor_uuids
            ) != 1
            or not isinstance(metadata.descriptor_instance_ids, tuple)
            or len(metadata.descriptor_instance_ids)
            != len(metadata.descriptor_uuids)
            or not all(
                isinstance(value, str) and value
                for value in metadata.descriptor_instance_ids
            )
        ):
            raise PermissionError("invalid standard heart-rate target")
        token = HeartRateSubscriptionToken._create(
            self.connection_generation, target.instance_id
        )
        self.heart_rate_subscription_count += 1
        self._heart_rate_subscriptions[id(token)] = (token, target)
        self.retained_heart_rate_callbacks.append(callback)
        self.callbacks[HEART_RATE_MEASUREMENT] = callback
        return token

    async def unsubscribe_heart_rate_measurement(
        self, subscription: HeartRateSubscriptionToken
    ) -> None:
        if type(subscription) is not HeartRateSubscriptionToken:
            raise TypeError("subscription must be a heart-rate token")
        record = self._heart_rate_subscriptions.pop(id(subscription), None)
        if record is None:
            return
        if record[0] is not subscription:
            raise PermissionError("invalid heart-rate subscription token")
        self.heart_rate_unsubscription_count += 1
        self.callbacks.pop(HEART_RATE_MEASUREMENT, None)

    def emit_disconnect(self) -> None:
        self.connected = False
        self.callbacks.clear()
        self._heart_rate_subscriptions.clear()
        self._targets.clear()
        for listener in tuple(self._disconnect_listeners.values()):
            listener(None)

    def emit(self, characteristic: str, data: bytes) -> None:
        self.callbacks[characteristic.lower()](data)
