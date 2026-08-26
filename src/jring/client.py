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
    HeartRate, HistoryRecord, MAX_HEART_RATE_MEASUREMENT_LENGTH, ProtocolError,
    parse_battery, parse_device_text, parse_heart_rate,
)
from .transport import (
    BleTransport,
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
    HeartRateSubscriptionToken,
)
from .vendor_gatt_preflight import (
    VendorGattPreflightCode,
    VendorGattRoute,
    resolve_vendor_gatt_route,
)
from .uuids import (
    BATTERY_LEVEL, BOOT_KEYBOARD_INPUT, BOOT_KEYBOARD_OUTPUT, BOOT_MOUSE_INPUT,
    CURRENT_TIME, DEVICE_INFO_SERVICE, FIRMWARE, HARDWARE, HEART_RATE_MEASUREMENT,
    HEART_RATE_SERVICE, HID_CONTROL_POINT, HID_INFORMATION, HID_PROTOCOL_MODE,
    HID_REPORT, HID_REPORT_MAP, HUMAN_INTERFACE_DEVICE_SERVICE, MANUFACTURER, MODEL,
    REPORT_REFERENCE_DESCRIPTOR, SOFTWARE, VENDOR_UUIDS,
    CLIENT_CHARACTERISTIC_CONFIGURATION,
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
    instance_count: int = 0
    instance_resolution_state: str = "unavailable"
    instance_states: tuple[str, ...] = ()


@dataclass(frozen=True)
class VendorGattObservation:
    uuid: str
    observed_as: str
    meaning: str = "unknown"


@dataclass(frozen=True)
class VendorRouteCapability:
    route: str
    service_inventory_state: str
    metadata_inventory_state: str
    structural_state: str
    structurally_ready: bool
    transport_target_state: str
    metadata_only: bool = True
    values_read: bool = False
    subscription_attempted: bool = False
    write_attempted: bool = False
    runnable: bool = False
    live_eligible: bool = False
    owner_authorized: bool = False
    hardware_eligible: bool = False
    hardware_verified: bool = False


@dataclass(frozen=True)
class HidReportMetadataInstance:
    instance: int
    characteristic_instance_id: str
    characteristic_identity_state: str
    state: str
    report_reference_state: str
    report_reference_instance_ids: tuple[str, ...]
    targeting_state: str = "metadata_only_not_targetable"
    value_state: str = "not_read"


@dataclass(frozen=True)
class ObservationTargetMetadata:
    """Selector fields exposed only by an explicit metadata-manifest opt-in."""

    service_uuid: str
    characteristic_uuid: str
    instance_id: str


@dataclass(frozen=True)
class StandardHeartRateCapability:
    service_state: str
    measurement_characteristic_state: str
    instance_count: int
    instance_resolution_state: str
    cccd_state: str
    targeting_state: str
    value_state: str = "not_read"
    subscription_state: str = "not_attempted"
    live_delivery_state: str = "not_tested"


@dataclass(frozen=True)
class CapabilityInventory:
    inventory_state: str
    metadata_state: str
    hid_service_state: str
    characteristics: tuple[CapabilityFeature, ...]
    report_reference_state: str
    standard_heart_rate: StandardHeartRateCapability
    vendor_gatt: tuple[VendorGattObservation, ...] = ()
    hid_report_instances: tuple[HidReportMetadataInstance, ...] = ()
    usability_state: str = "not_verified"
    os_attachment_state: str = "not_checked"
    neutral_event_state: str = "unsupported"
    neutral_events: tuple[str, ...] = ()
    vendor_routes: tuple[VendorRouteCapability, ...] = ()
    observation_targets: tuple[ObservationTargetMetadata, ...] = ()


def _vendor_route_capabilities(
    services: set[str],
    services_state: str,
    metadata: tuple[object, ...],
    metadata_state: str,
    transport: BleTransport,
) -> tuple[VendorRouteCapability, ...]:
    rows = []
    try:
        connection_generation = getattr(transport, "connection_generation", 0)
    except Exception:
        connection_generation = 0
    for route in VendorGattRoute:
        if services_state != "available" or metadata_state != "available":
            rows.append(
                VendorRouteCapability(
                    route=route.value,
                    service_inventory_state=services_state,
                    metadata_inventory_state=metadata_state,
                    structural_state="not_evaluated",
                    structurally_ready=False,
                    transport_target_state="not_evaluated",
                )
            )
            continue
        preflight = resolve_vendor_gatt_route(
            route,
            services=services,
            metadata=metadata,
            connection_generation=connection_generation,
        )
        target_state = "not_evaluated"
        if preflight.structurally_ready:
            request_target = preflight.request_target
            response_target = preflight.response_target
            if request_target is None or response_target is None:
                raise RuntimeError("ready vendor route omitted closed targets")
            try:
                request_owned = transport.owns_target(request_target)
            except Exception:
                request_owned = False
            try:
                response_owned = transport.owns_target(response_target)
            except Exception:
                response_owned = False
            target_state = (
                "current_snapshot_owned"
                if request_owned and response_owned
                else "not_current_snapshot_owned"
            )
        rows.append(
            VendorRouteCapability(
                route=route.value,
                service_inventory_state=services_state,
                metadata_inventory_state=metadata_state,
                structural_state=(
                    "request_write_unavailable"
                    if preflight.code
                    is VendorGattPreflightCode.RESPONSE_WRITE_UNAVAILABLE
                    else preflight.code.value
                ),
                structurally_ready=preflight.structurally_ready,
                transport_target_state=target_state,
            )
        )
    return tuple(rows)


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


def _standard_heart_rate_record(
    services: set[str],
    metadata: tuple[object, ...],
    transport: BleTransport,
) -> GattCharacteristicMetadata:
    matches = tuple(
        record
        for record in metadata
        if type(record) is GattCharacteristicMetadata
        and isinstance(record.uuid, str)
        and record.uuid.lower() == HEART_RATE_MEASUREMENT
    )
    valid = False
    record = matches[0] if len(matches) == 1 else None
    if record is not None:
        properties = record.properties
        descriptor_uuids = record.descriptor_uuids
        descriptor_ids = record.descriptor_instance_ids
        target = record.target
        valid = bool(
            HEART_RATE_SERVICE in services
            and isinstance(record.service_uuid, str)
            and record.service_uuid.lower() == HEART_RATE_SERVICE
            and isinstance(properties, tuple)
            and all(isinstance(value, str) for value in properties)
            and "notify" in {value.lower() for value in properties}
            and isinstance(descriptor_uuids, tuple)
            and all(isinstance(value, str) for value in descriptor_uuids)
            and sum(
                value.lower() == CLIENT_CHARACTERISTIC_CONFIGURATION
                for value in descriptor_uuids
            ) == 1
            and isinstance(descriptor_ids, tuple)
            and len(descriptor_ids) == len(descriptor_uuids)
            and all(isinstance(value, str) and value for value in descriptor_ids)
            and type(target) is GattCharacteristicTarget
            and isinstance(record.instance_id, str)
            and bool(record.instance_id)
            and target.service_uuid == HEART_RATE_SERVICE
            and target.uuid == HEART_RATE_MEASUREMENT
            and target.instance_id == record.instance_id
            and target.connection_generation > 0
            and transport.owns_target(target)
        )
    if not valid:
        raise ProtocolError(
            "standard heart-rate endpoint is unavailable or ambiguous; "
            "no notification was started"
        )
    return record


def _standard_heart_rate_capability(
    services: set[str],
    services_state: str,
    metadata: tuple[object, ...],
    metadata_state: str,
    transport: BleTransport,
) -> StandardHeartRateCapability:
    matches = tuple(
        record
        for record in metadata
        if type(record) is GattCharacteristicMetadata
        and isinstance(record.uuid, str)
        and record.uuid.lower() == HEART_RATE_MEASUREMENT
    )
    service_records = tuple(
        record
        for record in matches
        if isinstance(record.service_uuid, str)
        and record.service_uuid.lower() == HEART_RATE_SERVICE
    )
    if HEART_RATE_SERVICE in services or service_records:
        service_state = "advertised"
    elif services_state == "available" or metadata_state == "available":
        service_state = "unsupported"
    else:
        service_state = (
            "timed_out"
            if "timed_out" in {services_state, metadata_state}
            else "unavailable"
        )
    count = len(matches)
    resolution = (
        "uuid_unique" if count == 1 else "uuid_ambiguous" if count > 1 else "unavailable"
    )
    record = matches[0] if count == 1 else None
    if metadata_state != "available":
        characteristic_state = metadata_state
        cccd_state = metadata_state
    elif record is None:
        characteristic_state = "unsupported" if count == 0 else "ambiguous"
        cccd_state = "unsupported" if count == 0 else "ambiguous"
    elif not isinstance(record.service_uuid, str) or record.service_uuid.lower() != HEART_RATE_SERVICE:
        characteristic_state = "wrong_service"
        cccd_state = "unavailable"
    elif not isinstance(record.properties, tuple) or not all(
        isinstance(value, str) for value in record.properties
    ):
        characteristic_state = "malformed"
        cccd_state = "unavailable"
    else:
        characteristic_state = (
            "notify_advertised"
            if "notify" in {value.lower() for value in record.properties}
            else "advertised_without_notify"
        )
        if not isinstance(record.descriptor_uuids, tuple) or not all(
            isinstance(value, str) for value in record.descriptor_uuids
        ):
            cccd_state = "malformed"
        else:
            cccd_count = sum(
                value.lower() == CLIENT_CHARACTERISTIC_CONFIGURATION
                for value in record.descriptor_uuids
            )
            ids_valid = (
                isinstance(record.descriptor_instance_ids, tuple)
                and len(record.descriptor_instance_ids) == len(record.descriptor_uuids)
                and all(
                    isinstance(value, str) and value
                    for value in record.descriptor_instance_ids
                )
            )
            cccd_state = (
                "advertised" if cccd_count == 1 and ids_valid
                else "unsupported" if cccd_count == 0
                else "ambiguous" if cccd_count > 1
                else "malformed"
            )
    targeting_state = "unavailable"
    try:
        _standard_heart_rate_record(services, metadata, transport)
    except ProtocolError:
        if record is not None and type(record.target) is GattCharacteristicTarget:
            targeting_state = "not_owned_or_malformed"
    else:
        targeting_state = "structurally_ready"
    return StandardHeartRateCapability(
        service_state,
        characteristic_state,
        count,
        resolution,
        cccd_state,
        targeting_state,
    )


class JRingClient:
    def __init__(self, transport: BleTransport, *, timeout: float = 8.0):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.transport = transport
        self.timeout = timeout
        self._heart_rate_active = False

    async def __aenter__(self) -> "JRingClient":
        try:
            await asyncio.wait_for(self.transport.connect(), self.timeout)
        except BaseException:
            try:
                await asyncio.wait_for(self.transport.close(), self.timeout)
            except Exception:
                pass
            raise
        return self

    async def __aexit__(self, *_args: object) -> None:
        await asyncio.wait_for(self.transport.close(), self.timeout)

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
            service_uuid = (
                record.service_uuid.lower()
                if isinstance(record.service_uuid, str)
                else ""
            )
            characteristic_uuid = (
                record.uuid.lower() if isinstance(record.uuid, str) else ""
            )
            if service_uuid in VENDOR_UUIDS:
                vendor_observations.add((service_uuid, "service"))
            if characteristic_uuid in VENDOR_UUIDS:
                vendor_observations.add((characteristic_uuid, "characteristic"))
        hid_records = tuple(
            record for record in metadata
            if isinstance(record, GattCharacteristicMetadata)
            and isinstance(record.service_uuid, str)
            and isinstance(record.uuid, str)
            and record.service_uuid.lower() == HUMAN_INTERFACE_DEVICE_SERVICE
        )
        if HUMAN_INTERFACE_DEVICE_SERVICE in services or hid_records:
            service_state = "advertised"
        elif services_state == "available" or metadata_state == "available":
            service_state = "unsupported"
        else:
            service_state = "timed_out" if "timed_out" in {services_state, metadata_state} else "unavailable"

        records_by_uuid: dict[str, list[GattCharacteristicMetadata]] = {}
        for record in hid_records:
            records_by_uuid.setdefault(record.uuid.lower(), []).append(record)
        features = []
        for name, uuid in _HID_FEATURES:
            records = tuple(records_by_uuid.get(uuid, ()))
            record_states: tuple[str, ...] = ()
            if service_state == "unsupported":
                state = "unsupported"
            elif metadata_state != "available":
                state = metadata_state
            elif not records:
                state = "unsupported"
            else:
                record_states = tuple(
                    "malformed"
                    if not isinstance(record.properties, tuple)
                    or not all(
                        isinstance(value, str) for value in record.properties
                    )
                    else "read_property_advertised"
                    if "read" in {
                        value.lower() for value in record.properties
                    }
                    else "advertised"
                    for record in records
                )
                state = (
                    record_states[0]
                    if len(record_states) == 1
                    else "multiple_consistent"
                    if len(set(record_states)) == 1
                    else "multiple_mixed"
                )
            record_states = tuple(sorted(record_states))
            instance_count = len(records)
            resolution = (
                "uuid_ambiguous"
                if instance_count > 1
                else "uuid_unique" if instance_count == 1 else "unavailable"
            )
            features.append(
                CapabilityFeature(
                    name, uuid, state, instance_count, resolution, record_states
                )
            )

        report_records = tuple(record for record in hid_records if record.uuid.lower() == HID_REPORT)
        report_instances = []
        for index, record in enumerate(report_records, start=1):
            characteristic_instance_id = (
                record.instance_id
                if isinstance(record.instance_id, str) and record.instance_id
                else f"inventory-report-{index}"
            )
            characteristic_identity_state = (
                "connection_scoped_metadata_only"
                if isinstance(record.instance_id, str) and record.instance_id
                else "inventory_only"
            )
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
            descriptor_uuids = (
                record.descriptor_uuids
                if isinstance(record.descriptor_uuids, tuple)
                else ()
            )
            descriptor_instance_ids = (
                record.descriptor_instance_ids
                if (
                    isinstance(record.descriptor_instance_ids, tuple)
                    and len(record.descriptor_instance_ids)
                    == len(descriptor_uuids)
                    and all(
                        isinstance(value, str) and value
                        for value in record.descriptor_instance_ids
                    )
                )
                else tuple(
                    f"{characteristic_instance_id}-descriptor-{descriptor_index}"
                    for descriptor_index, _value in enumerate(
                        descriptor_uuids, start=1
                    )
                )
            )
            report_reference_instance_ids = tuple(
                descriptor_instance_ids[descriptor_index]
                for descriptor_index, descriptor_uuid in enumerate(
                    descriptor_uuids
                )
                if isinstance(descriptor_uuid, str)
                and descriptor_uuid.lower() == REPORT_REFERENCE_DESCRIPTOR
            )
            report_instances.append(
                HidReportMetadataInstance(
                    instance=index,
                    characteristic_instance_id=characteristic_instance_id,
                    characteristic_identity_state=characteristic_identity_state,
                    state=report_state,
                    report_reference_state=instance_descriptor_state,
                    report_reference_instance_ids=report_reference_instance_ids,
                )
            )
        if service_state == "unsupported":
            descriptor_state = "unsupported"
        elif metadata_state != "available":
            descriptor_state = metadata_state
        else:
            descriptor_states = tuple(
                item.report_reference_state for item in report_instances
            )
            if not descriptor_states:
                descriptor_state = "unsupported"
            elif set(descriptor_states) == {"advertised"}:
                descriptor_state = "all"
            elif set(descriptor_states) == {"unsupported"}:
                descriptor_state = "none"
            elif "malformed" in descriptor_states:
                descriptor_state = (
                    "malformed"
                    if set(descriptor_states) == {"malformed"}
                    else "malformed_mixed"
                )
            else:
                descriptor_state = "mixed"

        states = {services_state, metadata_state}
        inventory_state = (
            "available" if states == {"available"}
            else "partial" if "available" in states
            else "timed_out" if "timed_out" in states
            else "unavailable"
        )
        standard_heart_rate = _standard_heart_rate_capability(
            services,
            services_state,
            metadata,
            metadata_state,
            self.transport,
        )
        observation_targets = tuple(
            ObservationTargetMetadata(
                service_uuid=record.service_uuid.lower(),
                characteristic_uuid=record.uuid.lower(),
                instance_id=record.instance_id,
            )
            for record in metadata
            if isinstance(record, GattCharacteristicMetadata)
            and isinstance(record.service_uuid, str)
            and isinstance(record.uuid, str)
            and isinstance(record.instance_id, str)
            and bool(record.instance_id)
            and isinstance(record.properties, tuple)
            and "notify" in {value.casefold() for value in record.properties}
            and record.descriptor_uuids.count(CLIENT_CHARACTERISTIC_CONFIGURATION) == 1
            and len(record.descriptor_targets) == 1
        )
        return CapabilityInventory(
            inventory_state=inventory_state,
            metadata_state=metadata_state,
            hid_service_state=service_state,
            characteristics=tuple(features),
            report_reference_state=descriptor_state,
            standard_heart_rate=standard_heart_rate,
            hid_report_instances=tuple(report_instances),
            vendor_gatt=tuple(
                VendorGattObservation(uuid, observed_as)
                for uuid, observed_as in sorted(
                    vendor_observations,
                    key=lambda item: (item[0], 0 if item[1] == "service" else 1),
                )
            ),
            vendor_routes=_vendor_route_capabilities(
                services,
                services_state,
                metadata,
                metadata_state,
                self.transport,
            ),
            observation_targets=observation_targets,
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

    async def heart_rate_sample(self) -> HeartRate:
        """Collect one standard Heart Rate Measurement within a bounded attempt.

        The result is returned only after notification cleanup succeeds. No UUID-only
        fallback, read, write, retry, persistence, or vendor operation is performed.
        """
        if self._heart_rate_active:
            raise RuntimeError("a heart-rate collection is already active")
        self._heart_rate_active = True
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout
        disconnected_marker = object()
        timeout_marker = object()
        malformed_marker = object()
        queue: asyncio.Queue[bytes | object] = asyncio.Queue(maxsize=1)
        overflowed = False
        accepting = False
        disconnected = asyncio.Event()
        token: HeartRateSubscriptionToken | None = None
        remove_listener = None
        wait_tasks: set[asyncio.Task[object]] = set()
        result: HeartRate | None = None
        primary_error: BaseException | None = None
        cleanup_error = False

        def remaining() -> float:
            value = deadline - loop.time()
            if value <= 0:
                raise TimeoutError("heart-rate measurement timed out; no value returned")
            return value

        async def before_deadline(awaitable, timeout_message: str):
            timed_out = False
            task = asyncio.ensure_future(awaitable)

            def expire_stage() -> None:
                nonlocal timed_out
                timed_out = True
                task.cancel()

            handle = loop.call_later(remaining(), expire_stage)
            try:
                return await task
            except asyncio.CancelledError as exc:
                if timed_out:
                    raise TimeoutError(timeout_message) from exc
                raise
            finally:
                handle.cancel()

        def receive(data: bytes) -> None:
            nonlocal overflowed
            try:
                view = memoryview(data)
                copied: bytes | object = (
                    bytes(MAX_HEART_RATE_MEASUREMENT_LENGTH + 1)
                    if view.nbytes > MAX_HEART_RATE_MEASUREMENT_LENGTH
                    else view.tobytes()
                )
            except Exception:
                copied = malformed_marker

            def deliver() -> None:
                nonlocal overflowed
                if not accepting:
                    return
                if queue.full():
                    overflowed = True
                    return
                queue.put_nowait(copied)

            # Defer one loop turn so a callback invoked synchronously inside the
            # backend's start-notify call cannot escape before confirmation.
            loop.call_soon(deliver)

        def on_disconnect(_error: BaseException | None) -> None:
            disconnected.set()
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(disconnected_marker)

        try:
            service_task = asyncio.create_task(self.transport.service_uuids())
            metadata_task = asyncio.create_task(self.transport.gatt_characteristics())
            try:
                services_value, metadata_value = await before_deadline(
                    asyncio.gather(service_task, metadata_task),
                    "heart-rate endpoint discovery timed out; "
                    "no notification was started",
                )
            except BaseException:
                for inventory_task in (service_task, metadata_task):
                    if not inventory_task.done():
                        inventory_task.cancel()
                await asyncio.gather(
                    service_task, metadata_task, return_exceptions=True
                )
                raise
            services = {
                value.lower() for value in services_value if isinstance(value, str)
            }
            metadata = tuple(metadata_value)
            record = _standard_heart_rate_record(services, metadata, self.transport)
            target = record.target
            assert type(target) is GattCharacteristicTarget
            remove_listener = self.transport.add_disconnect_listener(on_disconnect)
            if disconnected.is_set():
                raise ConnectionError(
                    "heart-rate collection disconnected; no value returned"
                )
            token = await before_deadline(
                self.transport.subscribe_heart_rate_measurement(target, receive),
                "heart-rate notification setup timed out; no value returned",
            )
            if type(token) is not HeartRateSubscriptionToken:
                raise ProtocolError(
                    "heart-rate notification setup returned an invalid token; "
                    "no value returned"
                )
            if disconnected.is_set():
                raise ConnectionError(
                    "heart-rate collection disconnected; no value returned"
                )
            accepting = True
            def expire() -> None:
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(timeout_marker)

            timeout_handle = loop.call_later(remaining(), expire)
            try:
                data = await queue.get()
            finally:
                timeout_handle.cancel()
            if data is timeout_marker:
                raise TimeoutError(
                    "heart-rate measurement timed out; no value returned"
                )
            accepting = False
            await asyncio.sleep(0)
            if data is disconnected_marker or disconnected.is_set():
                raise ConnectionError(
                    "heart-rate collection disconnected; no value returned"
                )
            if overflowed:
                raise ProtocolError(
                    "heart-rate measurement queue overflow; no value returned"
                )
            if not isinstance(data, bytes):
                raise ProtocolError(
                    "heart-rate measurement was malformed; no value returned"
                )
            try:
                result = parse_heart_rate(data)
            except ProtocolError as exc:
                raise ProtocolError(
                    "heart-rate measurement was malformed; no value returned"
                ) from exc
        except BaseException as exc:
            primary_error = exc
        finally:
            accepting = False
            for task in wait_tasks:
                if not task.done():
                    task.cancel()
            if wait_tasks:
                await asyncio.gather(*wait_tasks, return_exceptions=True)
            while not queue.empty():
                queue.get_nowait()
            if token is not None:
                try:
                    await asyncio.wait_for(
                        self.transport.unsubscribe_heart_rate_measurement(token),
                        min(self.timeout, 1.0),
                    )
                except BaseException:
                    cleanup_error = True
            if remove_listener is not None:
                remove_listener()
            self._heart_rate_active = False

        if isinstance(primary_error, asyncio.CancelledError):
            raise primary_error
        if cleanup_error:
            raise ConnectionError(
                "heart-rate notification cleanup could not be confirmed; "
                "no value returned"
            )
        if primary_error is not None:
            raise primary_error
        if result is None:
            raise ProtocolError("heart-rate measurement produced no value")
        return result

    async def heart_rate_events(self) -> AsyncIterator[HeartRate]:
        """Compatibility iterator yielding one bounded, cleaned-up measurement."""
        yield await self.heart_rate_sample()

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
