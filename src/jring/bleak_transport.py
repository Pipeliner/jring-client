from __future__ import annotations

from .errors import UnavailableError
from .transport import NotifyCallback


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
        await self._client.write_gatt_char(characteristic, data, response=True)

    async def subscribe(self, characteristic: str, callback: NotifyCallback) -> None:
        await self._client.start_notify(characteristic, lambda _sender, data: callback(bytes(data)))

    async def unsubscribe(self, characteristic: str) -> None:
        await self._client.stop_notify(characteristic)

    async def service_uuids(self) -> set[str]:
        services = self._client.services
        return {service.uuid.lower() for service in services}
