from __future__ import annotations

from .errors import UnavailableError
from .transport import GattCharacteristicMetadata, NotifyCallback


class BleakTransport:
    def __init__(self, address: str, *, timeout: float = 10.0):
        try:
            from bleak import BleakClient
        except ImportError as exc:
            raise UnavailableError("hardware support requires: pip install '.[ble]'") from exc
        self._client = BleakClient(address, timeout=timeout)

    async def connect(self) -> None:
        await self._client.connect()
        if not self._client.is_connected:
            raise ConnectionError("BLE connection failed")

    async def close(self) -> None:
        if self._client.is_connected:
            await self._client.disconnect()

    async def read(self, characteristic: str) -> bytes:
        return bytes(await self._client.read_gatt_char(characteristic))

    async def write(self, characteristic: str, data: bytes) -> None:
        await self.write_with_response(characteristic, data)

    async def write_with_response(self, characteristic: str, data: bytes) -> None:
        """Return after Bleak completes an explicitly response-requesting write."""
        await self._client.write_gatt_char(characteristic, data, response=True)

    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None:
        await self._client.start_notify(characteristic, lambda _sender, data: callback(bytes(data)))

    async def unsubscribe(self, characteristic: str) -> None:
        await self._client.stop_notify(characteristic)

    async def service_uuids(self) -> set[str]:
        services = self._client.services
        return {service.uuid.lower() for service in services}

    async def gatt_characteristics(self) -> tuple[GattCharacteristicMetadata, ...]:
        records = []
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
                records.append(
                    GattCharacteristicMetadata(
                        service.uuid.lower(),
                        characteristic.uuid.lower(),
                        tuple(sorted(
                            str(value).lower()
                            for value in characteristic.properties
                        )),
                        tuple(descriptor.uuid.lower() for descriptor in descriptors),
                        instance_id,
                        tuple(
                            f"{instance_id}-descriptor-{index}"
                            for index, _descriptor in enumerate(descriptors, start=1)
                        ),
                    )
                )
        return tuple(records)
