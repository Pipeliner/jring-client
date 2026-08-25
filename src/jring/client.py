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
from uuid import UUID

from .protocol import (
    HeartRate, HistoryRecord, ProtocolError, parse_battery, parse_device_text,
    parse_heart_rate,
)
from .transport import BleTransport, GattCharacteristicMetadata
from .uuids import (
    BATTERY_LEVEL, BOOT_KEYBOARD_INPUT, BOOT_KEYBOARD_OUTPUT, BOOT_MOUSE_INPUT,
    CURRENT_TIME, DEVICE_INFO_SERVICE, FIRMWARE, HARDWARE, HEART_RATE_MEASUREMENT,
    HEART_RATE_SERVICE, HID_CONTROL_POINT, HID_INFORMATION, HID_PROTOCOL_MODE,
    HID_REPORT, HID_REPORT_MAP, HUMAN_INTERFACE_DEVICE_SERVICE, MANUFACTURER, MODEL,
    REPORT_REFERENCE_DESCRIPTOR, SOFTWARE, VENDOR_UUIDS,
)


@dataclass(frozen=True)
class DeviceInfo:
    manufacturer: str | None = None
    model: str | None = None
    firmware: str | None = None
    hardware: str | None = None
    software: str | None = None


@dataclass(frozen=True)
class DeviceInfoStates:
    manufacturer: str
    model: str
    firmware: str
    hardware: str
    software: str


@dataclass(frozen=True)
class Capabilities:
    device_info: bool
    heart_rate: bool
    hid: bool
    vendor_services_seen: tuple[str, ...]
    vendor_writes: bool = False


@dataclass(frozen=True)
class Status:
    battery_percent: int | None
    battery_available: bool
    battery_state: str
    device_info: DeviceInfo
    device_info_states: DeviceInfoStates
    capabilities: Capabilities
    capabilities_state: str


@dataclass(frozen=True)
class CapabilityFeature:
    name: str
    uuid: str
    state: str


@dataclass(frozen=True)
class VendorGattObservation:
    uuid: str
    observed_as: str
    meaning: str = "unknown"


@dataclass(frozen=True)
class HidReportMetadataInstance:
    instance: int
    state: str
    report_reference_state: str
    value_state: str = "not_read"


@dataclass(frozen=True)
class CapabilityInventory:
    inventory_state: str
    metadata_state: str
    hid_service_state: str
    characteristics: tuple[CapabilityFeature, ...]
    report_reference_state: str
    vendor_gatt: tuple[VendorGattObservation, ...] = ()
    hid_report_instances: tuple[HidReportMetadataInstance, ...] = ()
    usability_state: str = "not_verified"
    os_attachment_state: str = "not_checked"
    neutral_event_state: str = "unsupported"
    neutral_events: tuple[str, ...] = ()


_HID_FEATURES = (
    ("hid_information", HID_INFORMATION),
    ("report_map", HID_REPORT_MAP),
    ("report", HID_REPORT),
    ("protocol_mode", HID_PROTOCOL_MODE),
    ("control_point", HID_CONTROL_POINT),
    ("boot_keyboard_input", BOOT_KEYBOARD_INPUT),
    ("boot_keyboard_output", BOOT_KEYBOARD_OUTPUT),
    ("boot_mouse_input", BOOT_MOUSE_INPUT),
)


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


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
            except (LookupError, ProtocolError, TimeoutError):
                return None
        values = []
        for uuid in (MANUFACTURER, MODEL, FIRMWARE, HARDWARE, SOFTWARE):
            values.append(await optional(uuid))
        return DeviceInfo(*values)

    async def capabilities(self) -> Capabilities:
        try:
            discovered = await asyncio.wait_for(self.transport.service_uuids(), self.timeout)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("BLE service discovery timed out") from exc
        services = {item.lower() for item in discovered}
        return Capabilities(
            DEVICE_INFO_SERVICE in services,
            HEART_RATE_SERVICE in services,
            HUMAN_INTERFACE_DEVICE_SERVICE in services,
            tuple(sorted(services & VENDOR_UUIDS)),
        )

    async def capability_inventory(self) -> CapabilityInventory:
        tasks = {
            "services": asyncio.create_task(self.transport.service_uuids()),
            "metadata": asyncio.create_task(self.transport.gatt_characteristics()),
        }
        _done, pending = await asyncio.wait(tasks.values(), timeout=self.timeout)
        for task in pending:
            task.cancel()
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        outcomes = dict(zip(tasks, gathered, strict=True))

        def outcome(name: str) -> tuple[object, str]:
            task = tasks[name]
            if task in pending:
                return (), "timed_out"
            value = outcomes[name]
            if isinstance(value, (LookupError, OSError, TimeoutError)):
                return (), "unavailable"
            if isinstance(value, BaseException):
                raise value
            return value, "available"

        services_value, services_state = outcome("services")
        metadata_value, metadata_state = outcome("metadata")
        services = {
            str(value).lower() for value in services_value
        } if services_state == "available" else set()
        metadata = tuple(metadata_value) if metadata_state == "available" else ()
        vendor_observations = {
            (uuid, "service")
            for uuid in services
            if uuid in VENDOR_UUIDS
        }
        for record in metadata:
            if not isinstance(record, GattCharacteristicMetadata):
                continue
            service_uuid = record.service_uuid.lower()
            characteristic_uuid = record.uuid.lower()
            if service_uuid in VENDOR_UUIDS:
                vendor_observations.add((service_uuid, "service"))
            if characteristic_uuid in VENDOR_UUIDS:
                vendor_observations.add((characteristic_uuid, "characteristic"))
        hid_records = tuple(
            record for record in metadata
            if isinstance(record, GattCharacteristicMetadata)
            and record.service_uuid.lower() == HUMAN_INTERFACE_DEVICE_SERVICE
        )
        if HUMAN_INTERFACE_DEVICE_SERVICE in services or hid_records:
            service_state = "advertised"
        elif services_state == "available" or metadata_state == "available":
            service_state = "unsupported"
        else:
            service_state = "timed_out" if "timed_out" in {services_state, metadata_state} else "unavailable"

        records_by_uuid = {record.uuid.lower(): record for record in hid_records}
        features = []
        for name, uuid in _HID_FEATURES:
            record = records_by_uuid.get(uuid)
            if service_state == "unsupported":
                state = "unsupported"
            elif metadata_state != "available":
                state = metadata_state
            elif record is None:
                state = "unsupported"
            elif not isinstance(record.properties, tuple) or not all(
                isinstance(value, str) for value in record.properties
            ):
                state = "malformed"
            else:
                properties = {value.lower() for value in record.properties}
                state = (
                    "read_property_advertised"
                    if "read" in properties
                    else "advertised"
                )
            features.append(CapabilityFeature(name, uuid, state))

        report_records = tuple(record for record in hid_records if record.uuid.lower() == HID_REPORT)
        report_instances = []
        for index, record in enumerate(report_records, start=1):
            if not isinstance(record.properties, tuple) or not all(
                isinstance(value, str) for value in record.properties
            ):
                report_state = "malformed"
            else:
                report_properties = {
                    value.lower() for value in record.properties
                }
                report_state = (
                    "read_property_advertised"
                    if "read" in report_properties
                    else "advertised"
                )
            if not isinstance(record.descriptor_uuids, tuple):
                instance_descriptor_state = "malformed"
            elif REPORT_REFERENCE_DESCRIPTOR in {
                value.lower()
                for value in record.descriptor_uuids
                if isinstance(value, str)
            }:
                instance_descriptor_state = "advertised"
            elif any(
                not _valid_uuid(value) for value in record.descriptor_uuids
            ):
                instance_descriptor_state = "malformed"
            else:
                instance_descriptor_state = "unsupported"
            report_instances.append(
                HidReportMetadataInstance(
                    instance=index,
                    state=report_state,
                    report_reference_state=instance_descriptor_state,
                )
            )
        descriptor_values = tuple(
            value for record in report_records for value in record.descriptor_uuids
        )
        if service_state == "unsupported":
            descriptor_state = "unsupported"
        elif metadata_state != "available":
            descriptor_state = metadata_state
        elif REPORT_REFERENCE_DESCRIPTOR in {
            value.lower() for value in descriptor_values if isinstance(value, str)
        }:
            descriptor_state = "advertised"
        elif any(not _valid_uuid(value) for value in descriptor_values):
            descriptor_state = "malformed"
        else:
            descriptor_state = "unsupported"

        states = {services_state, metadata_state}
        inventory_state = (
            "available" if states == {"available"}
            else "partial" if "available" in states
            else "timed_out" if "timed_out" in states
            else "unavailable"
        )
        return CapabilityInventory(
            inventory_state=inventory_state,
            metadata_state=metadata_state,
            hid_service_state=service_state,
            characteristics=tuple(features),
            report_reference_state=descriptor_state,
            hid_report_instances=tuple(report_instances),
            vendor_gatt=tuple(
                VendorGattObservation(uuid, observed_as)
                for uuid, observed_as in sorted(
                    vendor_observations,
                    key=lambda item: (item[0], 0 if item[1] == "service" else 1),
                )
            ),
        )

    async def status(self) -> Status:
        names_and_uuids = (
            ("manufacturer", MANUFACTURER),
            ("model", MODEL),
            ("firmware", FIRMWARE),
            ("hardware", HARDWARE),
            ("software", SOFTWARE),
        )

        async def device_text(uuid: str) -> str:
            return parse_device_text(await self._read(uuid))

        tasks = {
            "battery": asyncio.create_task(self.battery()),
            "capabilities": asyncio.create_task(self.capabilities()),
            **{
                name: asyncio.create_task(device_text(uuid))
                for name, uuid in names_and_uuids
            },
        }
        _done, pending = await asyncio.wait(tasks.values(), timeout=self.timeout)
        for task in pending:
            task.cancel()
        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        outcomes = dict(zip(tasks, gathered, strict=True))
        pending_names = {name for name, task in tasks.items() if task in pending}

        def optional(name: str) -> tuple[object | None, str]:
            if name in pending_names:
                return None, "timed_out"
            outcome = outcomes[name]
            if isinstance(outcome, (LookupError, OSError)):
                return None, "unavailable"
            if isinstance(outcome, ProtocolError):
                return None, "malformed"
            if isinstance(outcome, TimeoutError):
                return None, "timed_out"
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome, "available"

        battery_value, battery_state = optional("battery")
        capabilities_value, capabilities_state = optional("capabilities")
        if capabilities_state == "available":
            capabilities = capabilities_value
            if not isinstance(capabilities, Capabilities):
                raise TypeError("invalid capabilities result")
        else:
            capabilities = Capabilities(False, False, False, ())

        values: dict[str, str | None] = {}
        states: dict[str, str] = {}
        for name, _uuid in names_and_uuids:
            value, state = optional(name)
            values[name] = value if isinstance(value, str) else None
            states[name] = state

        if capabilities_state == "available" and not capabilities.device_info:
            values = {name: None for name, _uuid in names_and_uuids}
            states = {name: "not_advertised" for name, _uuid in names_and_uuids}

        return Status(
            battery_percent=battery_value if isinstance(battery_value, int) else None,
            battery_available=battery_state == "available",
            battery_state=battery_state,
            device_info=DeviceInfo(**values),
            device_info_states=DeviceInfoStates(**states),
            capabilities=capabilities,
            capabilities_state=capabilities_state,
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
    def export_history(
        records: Iterable[HistoryRecord],
        destination: Path,
        *,
        source: str = "hardware",
        force: bool = False,
    ) -> None:
        destination = Path(destination)
        if source not in {"hardware", "simulator"}:
            raise ValueError("history source must be hardware or simulator")
        suffix = destination.suffix.lower()
        if suffix not in {".csv", ".jsonl"}:
            raise ValueError("history output must end in .csv or .jsonl")
        if destination.exists() and not force:
            raise FileExistsError(f"history output already exists: {destination}; use --force")
        destination.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for record in records:
            row = record.to_dict()
            row.update({"schema_version": 1, "source": source, "synthetic": source == "simulator"})
            rows.append(row)
        fd, temporary = tempfile.mkstemp(prefix=".jring-", dir=destination.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                if suffix == ".csv":
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=(
                            "schema_version", "source", "synthetic", "timestamp", "kind", "value"
                        ),
                    )
                    writer.writeheader(); writer.writerows(rows)
                else:
                    for row in rows:
                        handle.write(json.dumps(row, sort_keys=True) + "\n")
                handle.flush(); os.fsync(handle.fileno())
            if destination.exists() and not force:
                raise FileExistsError(f"history output already exists: {destination}; use --force")
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
