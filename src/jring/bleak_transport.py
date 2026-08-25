from __future__ import annotations

from collections.abc import Callable
from datetime import date

from .errors import UnavailableError
from .transport import (
    DisconnectListener,
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
    NotifyCallback,
)
from .uuids import CURRENT_TIME, CURRENT_TIME_SERVICE


class BleakTransport:
    def __init__(self, address: str, *, timeout: float = 10.0):
        try:
            from bleak import BleakClient
        except ImportError as exc:
            raise UnavailableError("hardware support requires: pip install '.[ble]'") from exc
        self._connection_generation = 0
        self._disconnect_notified_generation = 0
        self._disconnect_listeners: dict[int, DisconnectListener] = {}
        self._next_listener_id = 0
        self._connecting = False
        self._closing = False
        self._active_io = 0
        self._targets: dict[int, tuple[GattCharacteristicTarget, object]] = {}
        self._targets_by_backend_id: dict[
            int, tuple[GattCharacteristicTarget, object]
        ] = {}
        self._client_factory = BleakClient
        self._address = address
        self._timeout = timeout
        self._client_generation = 0
        self._client = self._build_client(self._client_generation)

    def _build_client(self, generation: int) -> object:
        return self._client_factory(
            self._address,
            disconnected_callback=(
                lambda client: self._on_disconnected(generation, client)
            ),
            timeout=self._timeout,
        )

    async def connect(self) -> None:
        if (
            self._connecting
            or self._closing
            or self._active_io
            or self._client.is_connected
        ):
            raise ConnectionError("BLE transport is already connecting or connected")
        self._connecting = True
        self._targets.clear()
        self._targets_by_backend_id.clear()
        expected_generation = self._connection_generation + 1
        try:
            self._client_generation = expected_generation
            self._client = self._build_client(expected_generation)
            await self._client.connect()
            if not self._client.is_connected:
                raise ConnectionError("BLE connection failed")
            self._connection_generation = expected_generation
            self._disconnect_notified_generation = 0
        finally:
            self._connecting = False

    async def close(self) -> None:
        if self._connecting or self._closing or self._active_io:
            raise ConnectionError("BLE transport lifecycle operation is in progress")
        self._closing = True
        self._targets.clear()
        self._targets_by_backend_id.clear()
        try:
            if self._client.is_connected:
                await self._client.disconnect()
        finally:
            self._closing = False

    def _on_disconnected(self, generation: int, _client: object) -> None:
        if generation != self._connection_generation or _client is not self._client:
            return
        self._targets.clear()
        self._targets_by_backend_id.clear()
        if generation <= 0 or self._disconnect_notified_generation == generation:
            return
        self._disconnect_notified_generation = generation
        for listener in tuple(self._disconnect_listeners.values()):
            try:
                listener(None)
            except Exception:
                # A consumer callback must never prevent target invalidation or other
                # listeners from observing the disconnect.
                continue

    def add_disconnect_listener(
        self, listener: DisconnectListener
    ) -> Callable[[], None]:
        if not callable(listener):
            raise TypeError("disconnect listener must be callable")
        self._next_listener_id += 1
        listener_id = self._next_listener_id
        self._disconnect_listeners[listener_id] = listener

        def remove() -> None:
            self._disconnect_listeners.pop(listener_id, None)

        return remove

    def _begin_io(self) -> None:
        if (
            self._connecting
            or self._closing
            or self._connection_generation <= 0
            or self._client_generation != self._connection_generation
            or not self._client.is_connected
        ):
            raise ConnectionError("BLE transport is not connected and idle")
        self._active_io += 1

    def _end_io(self) -> None:
        self._active_io -= 1

    def _current_time_target(self) -> object:
        matches: list[tuple[str, object]] = []
        for service in self._client.services:
            service_uuid = str(getattr(service, "uuid", "")).lower()
            for characteristic in getattr(service, "characteristics", ()):
                if str(getattr(characteristic, "uuid", "")).lower() == CURRENT_TIME:
                    matches.append((service_uuid, characteristic))
        if len(matches) != 1:
            raise PermissionError(
                "Current Time write requires one unambiguous characteristic"
            )
        service_uuid, characteristic = matches[0]
        properties = getattr(characteristic, "properties", ())
        if (
            service_uuid != CURRENT_TIME_SERVICE
            or not isinstance(properties, (list, tuple, set, frozenset))
            or not all(isinstance(value, str) for value in properties)
            or "write" not in {value.casefold() for value in properties}
        ):
            raise PermissionError(
                "Current Time write requires the standard writable service endpoint"
            )
        return characteristic

    @staticmethod
    def _current_time_payload_is_canonical(data: object) -> bool:
        if type(data) is not bytes or len(data) != 10:
            return False
        year = int.from_bytes(data[:2], "little")
        try:
            calendar_day = date(year, data[2], data[3])
        except ValueError:
            return False
        return (
            1582 <= year <= 9999
            and data[4] <= 23
            and data[5] <= 59
            and data[6] <= 59
            and data[7] == calendar_day.isoweekday()
            and data[9] & 0xF0 == 0
        )

    async def read(self, characteristic: str) -> bytes:
        self._begin_io()
        try:
            return bytes(await self._client.read_gatt_char(characteristic))
        finally:
            self._end_io()

    async def write(self, characteristic: str, data: bytes) -> None:
        await self.write_with_response(characteristic, data)

    async def write_with_response(self, characteristic: str, data: bytes) -> None:
        """Return after Bleak completes an explicitly response-requesting write."""
        if type(characteristic) is not str or characteristic.lower() != CURRENT_TIME:
            raise PermissionError("only the guarded standard Current Time write is enabled")
        if not self._current_time_payload_is_canonical(data):
            raise PermissionError("Current Time write requires a canonical 10-byte value")
        self._begin_io()
        try:
            target = self._current_time_target()
            await self._client.write_gatt_char(target, data, response=True)
        finally:
            self._end_io()

    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None:
        self._begin_io()
        try:
            await self._client.start_notify(
                characteristic, lambda _sender, data: callback(bytes(data))
            )
        finally:
            self._end_io()

    async def unsubscribe(self, characteristic: str) -> None:
        self._begin_io()
        try:
            await self._client.stop_notify(characteristic)
        finally:
            self._end_io()

    async def service_uuids(self) -> set[str]:
        self._begin_io()
        try:
            services = self._client.services
            return {service.uuid.lower() for service in services}
        finally:
            self._end_io()

    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]:
        self._begin_io()
        try:
            records = []
            targets: dict[int, tuple[GattCharacteristicTarget, object]] = {}
            previous_targets = self._targets_by_backend_id
            targets_by_backend_id: dict[
                int, tuple[GattCharacteristicTarget, object]
            ] = {}
            self._targets = {}
            self._targets_by_backend_id = {}
            for service_index, service in enumerate(self._client.services, start=1):
                for characteristic_index, characteristic in enumerate(
                    service.characteristics, start=1
                ):
                    instance_id = (
                        f"service-{service_index}-characteristic-{characteristic_index}"
                    )
                    descriptors = sorted(
                        characteristic.descriptors,
                        key=lambda item: str(item.uuid).lower(),
                    )
                    backend_id = id(characteristic)
                    previous_record = previous_targets.get(backend_id)
                    previous_target = (
                        previous_record[0]
                        if previous_record is not None
                        and previous_record[1] is characteristic
                        else None
                    )
                    target = (
                        previous_target
                        if (
                            previous_target is not None
                            and previous_target.connection_generation
                            == self._connection_generation
                            and previous_target.service_uuid == service.uuid.lower()
                            and previous_target.uuid == characteristic.uuid.lower()
                            and previous_target.instance_id == instance_id
                        )
                        else GattCharacteristicTarget(
                            connection_generation=self._connection_generation,
                            service_uuid=service.uuid.lower(),
                            uuid=characteristic.uuid.lower(),
                            instance_id=instance_id,
                        )
                    )
                    targets[id(target)] = (target, characteristic)
                    targets_by_backend_id[backend_id] = (target, characteristic)
                    records.append(
                        GattCharacteristicMetadata(
                            service.uuid.lower(),
                            characteristic.uuid.lower(),
                            tuple(
                                sorted(
                                    str(value).lower()
                                    for value in characteristic.properties
                                )
                            ),
                            tuple(
                                descriptor.uuid.lower() for descriptor in descriptors
                            ),
                            instance_id,
                            tuple(
                                f"{instance_id}-descriptor-{index}"
                                for index, _descriptor in enumerate(descriptors, start=1)
                            ),
                            target,
                        )
                    )
            self._targets = targets
            self._targets_by_backend_id = targets_by_backend_id
            return tuple(records)
        finally:
            self._end_io()

    def owns_target(self, target: GattCharacteristicTarget) -> bool:
        if type(target) is not GattCharacteristicTarget:
            return False
        record = self._targets.get(id(target))
        return not (
            record is None
            or record[0] is not target
            or target.connection_generation != self._connection_generation
            or self._client_generation != self._connection_generation
            or not self._client.is_connected
            or self._connecting
            or self._closing
        )
