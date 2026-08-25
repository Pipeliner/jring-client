"""Deterministic, simulation-only transport support for vendor runtime tests.

This module cannot discover or open Bluetooth devices.  It deliberately exposes
test controls that a real transport must not expose, including retained callback
handles and synthetic disconnects.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from inspect import isawaitable

from .transport import (
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
    NotifyCallback,
)
from .uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F5,
    VENDOR_CHARACTERISTIC_33F6,
    VENDOR_SERVICE_56FF,
    uuid16,
)


Hook = Callable[["ScriptedVendorFakeTransport", object], Awaitable[None] | None]
DisconnectListener = Callable[[Exception | None], None]


class ScriptGate:
    """An awaitable boundary that tests can release deterministically."""

    def __init__(self, *, released: bool) -> None:
        import asyncio

        self._entered = asyncio.Event()
        self._released = asyncio.Event()
        if released:
            self._released.set()

    @classmethod
    def blocked(cls) -> "ScriptGate":
        return cls(released=False)

    @classmethod
    def open(cls) -> "ScriptGate":
        return cls(released=True)

    async def wait(self) -> None:
        self._entered.set()
        await self._released.wait()

    async def wait_until_entered(self) -> None:
        await self._entered.wait()

    def release(self) -> None:
        self._released.set()

    def block(self) -> None:
        self._released.clear()


@dataclass(frozen=True, repr=False)
class ResponseWriteCall:
    characteristic_uuid: str
    _data: bytes
    response_requested: bool
    connection_generation: int
    target_instance_id: str | None = None

    def data_for_test(self) -> bytes:
        """Return a defensive copy of the recorded fake payload."""

        return bytes(self._data)

    def __repr__(self) -> str:
        return (
            "ResponseWriteCall("
            f"characteristic_uuid={self.characteristic_uuid!r}, "
            f"payload=<redacted {len(self._data)} bytes>, "
            f"response={self.response_requested!r}, "
            f"connection_generation={self.connection_generation!r})"
        )


@dataclass(frozen=True, repr=False)
class SubscriptionCall:
    characteristic_uuid: str
    callback: NotifyCallback
    connection_generation: int
    target_instance_id: str | None = None

    def __repr__(self) -> str:
        return (
            "SubscriptionCall("
            f"characteristic_uuid={self.characteristic_uuid!r}, "
            "callback=<redacted>, "
            f"connection_generation={self.connection_generation!r})"
        )


@dataclass(frozen=True, repr=False)
class UnsubscribeCall:
    characteristic_uuid: str
    connection_generation: int
    target_instance_id: str | None = None

    def __repr__(self) -> str:
        return (
            "UnsubscribeCall("
            f"characteristic_uuid={self.characteristic_uuid!r}, "
            f"connection_generation={self.connection_generation!r})"
        )


async def _run_hook(hook: Hook | None, fake: "ScriptedVendorFakeTransport", call: object) -> None:
    if hook is None:
        return
    result = hook(fake, call)
    if isawaitable(result):
        await result


class ScriptedVendorFakeTransport:
    """A controllable fake for notification/write ordering and cleanup tests."""

    simulation_only = True
    hardware_eligible = False

    def __init__(
        self,
        *,
        services: set[str],
        metadata: tuple[GattCharacteristicMetadata, ...],
        values: dict[str, bytes] | None = None,
        connect_gate: ScriptGate | None = None,
        close_gate: ScriptGate | None = None,
        subscribe_gate: ScriptGate | None = None,
        write_gate: ScriptGate | None = None,
        unsubscribe_gate: ScriptGate | None = None,
        connect_error: Exception | None = None,
        close_error: Exception | None = None,
        subscribe_error: Exception | None = None,
        write_error: Exception | None = None,
        unsubscribe_error: Exception | None = None,
        service_inventory_error: Exception | None = None,
        metadata_error: Exception | None = None,
    ) -> None:
        import asyncio

        self._services = {item.lower() for item in services}
        self._metadata = tuple(metadata)
        self._values = {
            characteristic.lower(): bytes(value)
            for characteristic, value in (values or {}).items()
        }
        self._connect_gate = connect_gate or ScriptGate.open()
        self._close_gate = close_gate or ScriptGate.open()
        self._subscribe_gate = subscribe_gate or ScriptGate.open()
        self._write_gate = write_gate or ScriptGate.open()
        self._unsubscribe_gate = unsubscribe_gate or ScriptGate.open()
        self._connect_error = connect_error
        self._close_error = close_error
        self._subscribe_error = subscribe_error
        self._write_error = write_error
        self._unsubscribe_error = unsubscribe_error
        self._service_inventory_error = service_inventory_error
        self._metadata_error = metadata_error

        self.before_connect: Hook | None = None
        self.before_close: Hook | None = None
        self.before_subscribe: Hook | None = None
        self.before_write: Hook | None = None
        self.before_unsubscribe: Hook | None = None

        self.connected = False
        self.closed = False
        self._connecting = False
        self._closing = False
        self.connection_generation = 0
        self.connect_count = 0
        self.close_count = 0
        self.read_count = 0
        self.write_count = 0
        self.generic_write_count = 0
        self.write_with_response_count = 0
        self.subscribe_count = 0
        self.unsubscribe_count = 0
        self.service_inventory_count = 0
        self.metadata_inventory_count = 0
        self.disconnect_count = 0
        self.targeted_read_count = 0
        self.targeted_write_count = 0
        self.targeted_subscribe_count = 0
        self.targeted_unsubscribe_count = 0

        self.response_write_calls: list[ResponseWriteCall] = []
        self.subscription_calls: list[SubscriptionCall] = []
        self.unsubscribe_calls: list[UnsubscribeCall] = []
        self._active_callbacks: dict[str, NotifyCallback] = {}
        self._retained_subscriptions: list[SubscriptionCall] = []
        self._disconnect_listeners: list[DisconnectListener] = []
        self._targets: dict[int, tuple[GattCharacteristicTarget, str]] = {}
        self._targets_by_metadata_id: dict[int, GattCharacteristicTarget] = {}
        self._target_uuid_counts: dict[str, int] = {}
        self.disconnect_event = asyncio.Event()
        self.last_disconnect_error: Exception | None = None

    @classmethod
    def vendor_route(
        cls,
        *,
        services: set[str] | None = None,
        write_properties: tuple[str, ...] = ("write",),
        notify_properties: tuple[str, ...] = ("notify",),
        response_descriptors: tuple[str, ...] = (uuid16(0x2902),),
        **controls: object,
    ) -> "ScriptedVendorFakeTransport":
        route_services = {VENDOR_SERVICE_56FF} if services is None else services
        metadata = (
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F3,
                properties=write_properties,
                descriptor_uuids=(),
            ),
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F4,
                properties=notify_properties,
                descriptor_uuids=response_descriptors,
            ),
        )
        return cls(services=route_services, metadata=metadata, **controls)

    @classmethod
    def raw_vendor_route(
        cls,
        *,
        services: set[str] | None = None,
        write_properties: tuple[str, ...] = ("write",),
        notify_properties: tuple[str, ...] = ("notify",),
        response_descriptors: tuple[str, ...] = (uuid16(0x2902),),
        **controls: object,
    ) -> "ScriptedVendorFakeTransport":
        """Build the distinct raw TX/RX route for simulation-only tests."""

        route_services = {VENDOR_SERVICE_56FF} if services is None else services
        metadata = (
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F5,
                properties=write_properties,
                descriptor_uuids=(),
            ),
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F6,
                properties=notify_properties,
                descriptor_uuids=response_descriptors,
            ),
        )
        return cls(services=route_services, metadata=metadata, **controls)

    @property
    def active_callback_count(self) -> int:
        return len(self._active_callbacks)

    @property
    def retained_callback_count(self) -> int:
        return len(self._retained_subscriptions)

    async def connect(self) -> None:
        if self.connected or self._connecting or self._closing:
            raise ConnectionError("scripted fake is already connecting or connected")
        self._connecting = True
        self.connect_count += 1
        try:
            await _run_hook(self.before_connect, self, self.connect_count)
            await self._connect_gate.wait()
            if self._connect_error is not None:
                raise self._connect_error
            self.connection_generation += 1
            self._targets.clear()
            self._targets_by_metadata_id.clear()
            self._target_uuid_counts.clear()
            self.disconnect_event.clear()
            self.last_disconnect_error = None
            self.connected = True
            self.closed = False
        finally:
            self._connecting = False

    async def close(self) -> None:
        if self._connecting or self._closing:
            raise ConnectionError("scripted fake lifecycle operation is in progress")
        self._closing = True
        self.close_count += 1
        try:
            await _run_hook(self.before_close, self, self.close_count)
            await self._close_gate.wait()
            if self._close_error is not None:
                raise self._close_error
            self._active_callbacks.clear()
            self._targets.clear()
            self._targets_by_metadata_id.clear()
            self._target_uuid_counts.clear()
            self.connected = False
            self.closed = True
        finally:
            self._closing = False

    async def read(self, characteristic: str) -> bytes:
        self._require_connected()
        self.read_count += 1
        try:
            return bytes(self._values[characteristic.lower()])
        except KeyError as exc:
            raise LookupError("characteristic unavailable in scripted fake") from exc

    async def write(self, characteristic: str, data: bytes) -> None:
        self._require_connected()
        self.generic_write_count += 1
        await self._record_response_write(characteristic, data)

    async def write_with_response(self, characteristic: str, data: bytes) -> None:
        """Record the fake's explicit response-requested write boundary."""

        self._require_connected()
        self.write_with_response_count += 1
        await self._record_response_write(characteristic, data)

    async def _record_response_write(
        self,
        characteristic: str,
        data: bytes,
        *,
        target_instance_id: str | None = None,
        target_generation: int | None = None,
    ) -> None:
        call = ResponseWriteCall(
            characteristic_uuid=characteristic.lower(),
            _data=bytes(data),
            response_requested=True,
            connection_generation=self.connection_generation,
            target_instance_id=target_instance_id,
        )
        self.write_count += 1
        self.response_write_calls.append(call)
        await _run_hook(self.before_write, self, call)
        await self._write_gate.wait()
        if self._write_error is not None:
            raise self._write_error
        if target_generation is not None and (
            not self.connected or self.connection_generation != target_generation
        ):
            raise ConnectionError("target connection changed during write")
        self._values[call.characteristic_uuid] = call.data_for_test()

    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None:
        self._require_connected()
        await self._record_subscription(characteristic, callback)

    async def _record_subscription(
        self,
        characteristic: str,
        callback: NotifyCallback,
        *,
        target_instance_id: str | None = None,
        target_generation: int | None = None,
    ) -> None:
        call = SubscriptionCall(
            characteristic_uuid=characteristic.lower(),
            callback=callback,
            connection_generation=self.connection_generation,
            target_instance_id=target_instance_id,
        )
        self.subscribe_count += 1
        self.subscription_calls.append(call)
        self._retained_subscriptions.append(call)
        self._active_callbacks[call.characteristic_uuid] = callback
        await _run_hook(self.before_subscribe, self, call)
        await self._subscribe_gate.wait()
        if self._subscribe_error is not None:
            raise self._subscribe_error
        if target_generation is not None and (
            not self.connected or self.connection_generation != target_generation
        ):
            raise ConnectionError("target connection changed during subscription")

    async def unsubscribe(self, characteristic: str) -> None:
        self._require_connected()
        await self._record_unsubscribe(characteristic)

    async def _record_unsubscribe(
        self,
        characteristic: str,
        *,
        target_instance_id: str | None = None,
        target_generation: int | None = None,
    ) -> None:
        call = UnsubscribeCall(
            characteristic_uuid=characteristic.lower(),
            connection_generation=self.connection_generation,
            target_instance_id=target_instance_id,
        )
        self.unsubscribe_count += 1
        self.unsubscribe_calls.append(call)
        await _run_hook(self.before_unsubscribe, self, call)
        await self._unsubscribe_gate.wait()
        if self._unsubscribe_error is not None:
            raise self._unsubscribe_error
        if target_generation is not None and (
            not self.connected or self.connection_generation != target_generation
        ):
            raise ConnectionError("target connection changed during unsubscribe")
        self._active_callbacks.pop(call.characteristic_uuid, None)

    async def service_uuids(self) -> set[str]:
        self._require_connected()
        self.service_inventory_count += 1
        if self._service_inventory_error is not None:
            raise self._service_inventory_error
        return set(self._services)

    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]:
        self._require_connected()
        self.metadata_inventory_count += 1
        previous_targets = self._targets_by_metadata_id
        self._targets = {}
        self._targets_by_metadata_id = {}
        self._target_uuid_counts = {}
        if self._metadata_error is not None:
            raise self._metadata_error
        targets: dict[int, tuple[GattCharacteristicTarget, str]] = {}
        targets_by_metadata_id: dict[int, GattCharacteristicTarget] = {}
        records = []
        for index, record in enumerate(self._metadata, start=1):
            if (
                type(record) is GattCharacteristicMetadata
                and isinstance(record.service_uuid, str)
                and isinstance(record.uuid, str)
            ):
                instance_id = (
                    record.instance_id
                    if isinstance(record.instance_id, str) and record.instance_id
                    else f"fake-characteristic-{index}"
                )
                metadata_id = id(record)
                previous_target = previous_targets.get(metadata_id)
                target = (
                    previous_target
                    if (
                        previous_target is not None
                        and previous_target.connection_generation
                        == self.connection_generation
                        and previous_target.service_uuid == record.service_uuid.lower()
                        and previous_target.uuid == record.uuid.lower()
                        and previous_target.instance_id == instance_id
                    )
                    else GattCharacteristicTarget(
                        connection_generation=self.connection_generation,
                        service_uuid=record.service_uuid.lower(),
                        uuid=record.uuid.lower(),
                        instance_id=instance_id,
                    )
                )
                targets[id(target)] = (target, target.uuid)
                targets_by_metadata_id[metadata_id] = target
                records.append(
                    GattCharacteristicMetadata(
                        service_uuid=record.service_uuid,
                        uuid=record.uuid,
                        properties=record.properties,
                        descriptor_uuids=record.descriptor_uuids,
                        instance_id=instance_id,
                        descriptor_instance_ids=record.descriptor_instance_ids,
                        target=target,
                    )
                )
            else:
                records.append(record)
        self._targets = targets
        self._targets_by_metadata_id = targets_by_metadata_id
        counts: dict[str, int] = {}
        for record in records:
            if type(record) is GattCharacteristicMetadata and isinstance(record.uuid, str):
                uuid = record.uuid.lower()
                counts[uuid] = counts.get(uuid, 0) + 1
        self._target_uuid_counts = counts
        return tuple(records)

    def metadata_snapshot_for_test(self) -> tuple[GattCharacteristicMetadata, ...]:
        return tuple(self._metadata)

    def emit(self, characteristic: str, data: bytes) -> None:
        self._active_callbacks[characteristic.lower()](bytes(data))

    def emit_stale(self, retained_index: int, data: bytes) -> None:
        self._retained_subscriptions[retained_index].callback(bytes(data))

    def add_disconnect_listener(self, listener: DisconnectListener) -> Callable[[], None]:
        self._disconnect_listeners.append(listener)

        def remove() -> None:
            try:
                self._disconnect_listeners.remove(listener)
            except ValueError:
                pass

        return remove

    def emit_disconnect(self, error: Exception | None = None) -> None:
        self.disconnect_count += 1
        self.connected = False
        self.last_disconnect_error = error
        self.disconnect_event.set()
        self._active_callbacks.clear()
        self._targets.clear()
        self._targets_by_metadata_id.clear()
        self._target_uuid_counts.clear()
        for listener in tuple(self._disconnect_listeners):
            try:
                listener(error)
            except Exception:
                continue

    def clear_sensitive_test_state(self) -> None:
        """Drop retained payloads, callbacks, listeners, values, and errors."""

        self.response_write_calls.clear()
        self.subscription_calls.clear()
        self.unsubscribe_calls.clear()
        self._active_callbacks.clear()
        self._retained_subscriptions.clear()
        self._disconnect_listeners.clear()
        self._values.clear()
        self._targets.clear()
        self._targets_by_metadata_id.clear()
        self._target_uuid_counts.clear()
        self.last_disconnect_error = None

    def _require_connected(self) -> None:
        if not self.connected:
            raise ConnectionError("scripted fake is not connected")

    def _resolve_target(self, target: GattCharacteristicTarget) -> str:
        self._require_connected()
        if type(target) is not GattCharacteristicTarget:
            raise TypeError("target must be an exact GattCharacteristicTarget")
        record = self._targets.get(id(target))
        if (
            record is None
            or record[0] is not target
            or target.connection_generation != self.connection_generation
            or self._target_uuid_counts.get(record[1], 0) != 1
        ):
            raise LookupError("characteristic target is stale or unavailable")
        return record[1]

    def owns_target(self, target: GattCharacteristicTarget) -> bool:
        if not self.connected or type(target) is not GattCharacteristicTarget:
            return False
        record = self._targets.get(id(target))
        return bool(
            record is not None
            and record[0] is target
            and target.connection_generation == self.connection_generation
        )

    async def read_target(self, target: GattCharacteristicTarget) -> bytes:
        characteristic = self._resolve_target(target)
        self.targeted_read_count += 1
        self.read_count += 1
        try:
            return bytes(self._values[characteristic])
        except KeyError as exc:
            raise LookupError("characteristic unavailable in scripted fake") from exc

    async def write_target_with_response(
        self, target: GattCharacteristicTarget, data: bytes
    ) -> None:
        characteristic = self._resolve_target(target)
        self.targeted_write_count += 1
        await self._record_response_write(
            characteristic,
            data,
            target_instance_id=target.instance_id,
            target_generation=target.connection_generation,
        )

    async def subscribe_target(
        self, target: GattCharacteristicTarget, callback: NotifyCallback
    ) -> None:
        characteristic = self._resolve_target(target)
        self.targeted_subscribe_count += 1
        await self._record_subscription(
            characteristic,
            callback,
            target_instance_id=target.instance_id,
            target_generation=target.connection_generation,
        )

    async def unsubscribe_target(self, target: GattCharacteristicTarget) -> None:
        characteristic = self._resolve_target(target)
        self.targeted_unsubscribe_count += 1
        await self._record_unsubscribe(
            characteristic,
            target_instance_id=target.instance_id,
            target_generation=target.connection_generation,
        )

    def __repr__(self) -> str:
        return (
            "ScriptedVendorFakeTransport("
            "simulation_only=True, hardware_eligible=False, "
            f"connected={self.connected!r}, generation={self.connection_generation!r})"
        )


__all__ = [
    "ResponseWriteCall",
    "ScriptGate",
    "ScriptedVendorFakeTransport",
    "SubscriptionCall",
    "UnsubscribeCall",
]
