from __future__ import annotations

import asyncio
import csv
import json
import os
import tempfile
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .protocol import HeartRate, HistoryRecord, parse_battery, parse_device_text, parse_heart_rate
from .transport import BleTransport
from .uuids import (BATTERY_LEVEL, CURRENT_TIME, DEVICE_INFO_SERVICE, FIRMWARE,
                    HARDWARE, HEART_RATE_MEASUREMENT, HEART_RATE_SERVICE,
                    HUMAN_INTERFACE_DEVICE_SERVICE, MANUFACTURER, MODEL, SOFTWARE,
                    VENDOR_UUIDS)


@dataclass(frozen=True)
class DeviceInfo:
    manufacturer: str | None = None
    model: str | None = None
    firmware: str | None = None
    hardware: str | None = None
    software: str | None = None


@dataclass(frozen=True)
class Capabilities:
    device_info: bool
    heart_rate: bool
    hid: bool
    vendor_services_seen: tuple[str, ...]
    vendor_writes: bool = False


class JRingClient:
    def __init__(self, transport: BleTransport, *, timeout: float = 8.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.transport = transport
        self.timeout = timeout

    async def __aenter__(self) -> "JRingClient":
        try:
            await asyncio.wait_for(self.transport.connect(), self.timeout)
        except BaseException:
            try:
                await self.transport.close()
            except Exception:
                pass
            raise
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.transport.close()

    async def _read(self, uuid: str) -> bytes:
        try:
            return await asyncio.wait_for(self.transport.read(uuid), self.timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("BLE read timed out") from exc

    async def battery(self) -> int:
        return parse_battery(await self._read(BATTERY_LEVEL))

    async def device_info(self) -> DeviceInfo:
        async def optional(uuid: str) -> str | None:
            try:
                return parse_device_text(await self._read(uuid))
            except LookupError:
                return None
        values = []
        for uuid in (MANUFACTURER, MODEL, FIRMWARE, HARDWARE, SOFTWARE):
            values.append(await optional(uuid))
        return DeviceInfo(*values)

    async def capabilities(self) -> Capabilities:
        services = {item.lower() for item in await self.transport.service_uuids()}
        return Capabilities(
            DEVICE_INFO_SERVICE in services,
            HEART_RATE_SERVICE in services,
            HUMAN_INTERFACE_DEVICE_SERVICE in services,
            tuple(sorted(services & VENDOR_UUIDS)),
        )

    async def heart_rate_events(self) -> AsyncIterator[HeartRate]:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=32)
        def receive(data: bytes) -> None:
            if not queue.full():
                queue.put_nowait(bytes(data))
        await self.transport.subscribe(HEART_RATE_MEASUREMENT, receive)
        try:
            while True:
                yield parse_heart_rate(await asyncio.wait_for(queue.get(), self.timeout))
        finally:
            await self.transport.unsubscribe(HEART_RATE_MEASUREMENT)

    async def sync_time(self, moment: datetime, *, allow_write: bool = False) -> None:
        if not allow_write:
            raise PermissionError("time sync requires explicit write authorization")
        if moment.tzinfo is None:
            raise ValueError("time must be timezone-aware")
        # Bluetooth Current Time characteristic, exact-time-256 and reason omitted.
        weekday = moment.isoweekday()
        payload = (moment.year.to_bytes(2, "little") + bytes((moment.month, moment.day,
                   moment.hour, moment.minute, moment.second, weekday, 0, 1)))
        await asyncio.wait_for(self.transport.write(CURRENT_TIME, payload), self.timeout)

    async def history(self) -> list[HistoryRecord]:
        # Only simulator transports expose records until the vendor protocol is verified.
        records = getattr(self.transport, "records", None)
        if records is None:
            raise NotImplementedError("hardware history protocol is not verified")
        return list(records)

    @staticmethod
    def export_history(records: Iterable[HistoryRecord], destination: Path) -> None:
        destination = Path(destination)
        suffix = destination.suffix.lower()
        if suffix not in {".csv", ".jsonl"}:
            raise ValueError("history output must end in .csv or .jsonl")
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows = [record.to_dict() for record in records]
        fd, temporary = tempfile.mkstemp(prefix=".jring-", dir=destination.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                if suffix == ".csv":
                    writer = csv.DictWriter(handle, fieldnames=("timestamp", "kind", "value"))
                    writer.writeheader(); writer.writerows(rows)
                else:
                    for row in rows:
                        handle.write(json.dumps(row, sort_keys=True) + "\n")
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, destination)
        except BaseException:
            try: os.unlink(temporary)
            except FileNotFoundError: pass
            raise


async def connect_with_backoff(factory, *, attempts: int = 3, base_delay: float = 0.25):
    if attempts < 1:
        raise ValueError("attempts must be positive")
    last_error = None
    for attempt in range(attempts):
        transport = factory()
        try:
            await transport.connect()
            return transport
        except (TimeoutError, OSError) as exc:
            last_error = exc
            await transport.close()
            if attempt + 1 < attempts:
                await asyncio.sleep(min(base_delay * (2 ** attempt), 4.0))
    raise ConnectionError("bounded connection attempts exhausted") from last_error
