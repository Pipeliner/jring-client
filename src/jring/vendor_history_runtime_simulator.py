"""Fake-only collector for shared vendor day-history projections.

The recovered day families have no common proven wire terminal.  Reaching a local
frame limit or observing local quiet therefore leaves completeness unknown.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import math

from .protocol import ProtocolError
from .uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from .vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    parse_vendor_advanced_sensor_day,
    parse_vendor_multi_sport_day,
    parse_vendor_oxygen_day,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport
from .vendor_transport import OfflineVendorOperation


class HistorySimulationReason(str, Enum):
    LIMIT_REACHED = "limit_reached"
    LOCAL_QUIET = "local_quiet"
    DEVICE_FAILURE = "device_failure"
    PREFLIGHT_FAILURE = "preflight_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_FRAME = "malformed_frame"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class HistoryCollectionCompleteness(str, Enum):
    UNKNOWN = "unknown"
    FAILED = "failed"
    ABORTED = "aborted"


Projection = tuple[str, int, str]


@dataclass(frozen=True, repr=False)
class HistorySimulationResult:
    operation_name: str
    reason: HistorySimulationReason
    completeness: HistoryCollectionCompleteness
    accepted_frame_count: int
    unrelated_frame_count: int
    projections: tuple[Projection, ...]
    command_written: bool
    cleanup_succeeded: bool
    local_end_projected: bool
    _parsed_frames: tuple[object, ...] = field(repr=False)
    _local_end_device_epoch_seconds: int | None = field(repr=False)

    @property
    def wire_terminal_observed(self) -> bool:
        return False

    @property
    def quiet_means_success(self) -> bool:
        return False

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    def parsed_frames_for_test(self) -> tuple[object, ...]:
        return tuple(self._parsed_frames)

    def local_end_device_epoch_seconds_for_test(self) -> int | None:
        return self._local_end_device_epoch_seconds

    def __repr__(self) -> str:
        return (
            "HistorySimulationResult("
            f"operation_name={self.operation_name!r}, reason={self.reason.value!r}, "
            f"completeness={self.completeness.value!r}, "
            f"accepted_frame_count={self.accepted_frame_count}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"projections={self.projections!r}, command_written={self.command_written!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            f"local_end_projected={self.local_end_projected!r}, "
            "parsed_frames=<redacted>, local_end_timestamp=<redacted>, "
            "wire_terminal_observed=False, quiet_means_success=False, "
            "simulation_only=True, hardware_eligible=False, hardware_verified=False)"
        )


_PARSERS = {
    StaticQuery.MULTI_SPORT_DAY: parse_vendor_multi_sport_day,
    StaticQuery.OXYGEN_DAY: parse_vendor_oxygen_day,
    StaticQuery.ADVANCED_SENSOR_DAY: parse_vendor_advanced_sensor_day,
}


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


class FakeVendorHistorySimulator:
    """Collect one of the three shared day families from the exact scripted fake."""

    simulation_only = True
    hardware_eligible = False

    def __init__(self, transport: ScriptedVendorFakeTransport) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        self._transport = transport

    async def collect(
        self,
        *,
        request: StaticVendorRequest,
        frame_limit: int = 1,
        quiet_timeout: float = 0.05,
    ) -> HistorySimulationResult:
        if type(request) is not StaticVendorRequest or request.operation not in _PARSERS:
            raise TypeError("request must be a closed shared day-history request")
        if isinstance(frame_limit, bool) or not isinstance(frame_limit, int):
            raise TypeError("frame_limit must be an integer")
        if frame_limit <= 0:
            raise ValueError("frame_limit must be positive")
        timeout = _positive_number(quiet_timeout, "quiet_timeout")
        operation = OfflineVendorOperation.from_static_request(request)
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        parsed: list[object] = []
        projections: list[Projection] = []
        unrelated = 0
        command_written = False
        subscribed = False
        reason = HistorySimulationReason.LOCAL_QUIET
        completeness = HistoryCollectionCompleteness.UNKNOWN

        try:
            await self._transport.connect()
            if not await self._preflight():
                reason = HistorySimulationReason.PREFLIGHT_FAILURE
                completeness = HistoryCollectionCompleteness.ABORTED
            else:
                await self._transport.subscribe(
                    VENDOR_CHARACTERISTIC_33F4, queue.put_nowait
                )
                subscribed = True
                await self._transport.write_with_response(
                    VENDOR_CHARACTERISTIC_33F3,
                    operation.synthetic_request_for_test(),
                )
                command_written = True
                loop = asyncio.get_running_loop()
                quiet_deadline = loop.time() + timeout

                while len(parsed) < frame_limit:
                    remaining = quiet_deadline - loop.time()
                    if remaining <= 0:
                        reason = HistorySimulationReason.LOCAL_QUIET
                        break
                    data_task = asyncio.create_task(queue.get())
                    disconnect_task = asyncio.create_task(
                        self._transport.disconnect_event.wait()
                    )
                    done, pending = await asyncio.wait(
                        {data_task, disconnect_task},
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    if not done:
                        reason = HistorySimulationReason.LOCAL_QUIET
                        break
                    if disconnect_task in done and disconnect_task.result():
                        if not data_task.done():
                            data_task.cancel()
                        reason = HistorySimulationReason.DISCONNECTED
                        completeness = HistoryCollectionCompleteness.ABORTED
                        break
                    data = data_task.result()
                    match = self._classify(request.operation, data)
                    if match == "unrelated":
                        unrelated += 1
                        continue
                    if match == "failure":
                        projections.append(
                            ("onGetMultipleSportData", 1, "wire_failure_frame")
                        )
                        reason = HistorySimulationReason.DEVICE_FAILURE
                        completeness = HistoryCollectionCompleteness.FAILED
                        break
                    try:
                        value = _PARSERS[request.operation](data)
                    except ProtocolError:
                        reason = HistorySimulationReason.MALFORMED_FRAME
                        completeness = HistoryCollectionCompleteness.ABORTED
                        break
                    parsed.append(value)
                    projections.extend(self._projections(request.operation, value))
                    quiet_deadline = loop.time() + timeout
                else:
                    reason = HistorySimulationReason.LIMIT_REACHED
        except (ConnectionError, LookupError, OSError):
            reason = (
                HistorySimulationReason.WRITE_FAILURE
                if subscribed else HistorySimulationReason.PREFLIGHT_FAILURE
            )
            completeness = HistoryCollectionCompleteness.ABORTED
        finally:
            cleanup_succeeded = await self._cleanup(subscribed)

        if not cleanup_succeeded:
            reason = HistorySimulationReason.CLEANUP_FAILURE
            completeness = HistoryCollectionCompleteness.ABORTED
        local_end_projected = False
        local_end_timestamp = None
        if (
            cleanup_succeeded
            and reason is HistorySimulationReason.LOCAL_QUIET
            and parsed
            and request.operation in {
                StaticQuery.OXYGEN_DAY,
                StaticQuery.ADVANCED_SENSOR_DAY,
            }
        ):
            callback = (
                "onGetOxygenOfflineDataEnd"
                if request.operation is StaticQuery.OXYGEN_DAY
                else "onGetAdvSensorOfflineDataEnd"
            )
            projections.append((callback, 1, "local_quiet_projection"))
            local_end_projected = True
            local_end_timestamp = parsed[-1].samples[-1].device_epoch_seconds
        return HistorySimulationResult(
            operation_name=request.operation.value,
            reason=reason,
            completeness=completeness,
            accepted_frame_count=len(parsed),
            unrelated_frame_count=unrelated,
            projections=tuple(projections),
            command_written=command_written,
            cleanup_succeeded=cleanup_succeeded,
            local_end_projected=local_end_projected,
            _parsed_frames=tuple(parsed),
            _local_end_device_epoch_seconds=local_end_timestamp,
        )

    @staticmethod
    def _classify(operation: StaticQuery, data: bytes) -> str:
        if not isinstance(data, bytes) or len(data) != 20:
            return "unrelated"
        opcode = data[0]
        if operation is StaticQuery.MULTI_SPORT_DAY:
            if opcode == 0xA5 and data[1] == 0xFF:
                return "failure"
            return "success" if opcode == 0x25 else "unrelated"
        expected = 0x40 if operation is StaticQuery.OXYGEN_DAY else 0x55
        return "success" if opcode == expected else "unrelated"

    @staticmethod
    def _projections(operation: StaticQuery, value: object) -> tuple[Projection, ...]:
        if operation is StaticQuery.MULTI_SPORT_DAY:
            return (
                ("onSetBloodPressureMode", 1, "wire_frame"),
                ("onGetMultipleSportData", len(value.samples), "wire_frame"),
            )
        if operation is StaticQuery.OXYGEN_DAY:
            count = len(value.samples)
            return (
                ("onGetDataByDay", count, "wire_frame"),
                ("onGetOxygenOfflineData", count, "wire_frame"),
            )
        count = len(value.samples)
        return (
            ("onGetDataByDay", count, "wire_frame"),
            ("onGetAdvSensorOfflineData", count, "wire_frame"),
        )

    async def _preflight(self) -> bool:
        services = await self._transport.service_uuids()
        if VENDOR_SERVICE_56FF not in {item.lower() for item in services}:
            return False
        metadata = await self._transport.gatt_characteristics()
        tx = [
            item for item in metadata
            if item.service_uuid.lower() == VENDOR_SERVICE_56FF
            and item.uuid.lower() == VENDOR_CHARACTERISTIC_33F3
        ]
        rx = [
            item for item in metadata
            if item.service_uuid.lower() == VENDOR_SERVICE_56FF
            and item.uuid.lower() == VENDOR_CHARACTERISTIC_33F4
        ]
        return (
            len(tx) == 1 and len(rx) == 1
            and "write" in tx[0].properties and "notify" in rx[0].properties
            and uuid16(0x2902) in rx[0].descriptor_uuids
        )

    async def _cleanup(self, subscribed: bool) -> bool:
        succeeded = True
        if subscribed and self._transport.connected:
            try:
                await self._transport.unsubscribe(VENDOR_CHARACTERISTIC_33F4)
            except (ConnectionError, OSError):
                succeeded = False
        try:
            await self._transport.close()
        except OSError:
            succeeded = False
        return succeeded


__all__ = [
    "FakeVendorHistorySimulator",
    "HistoryCollectionCompleteness",
    "HistorySimulationReason",
    "HistorySimulationResult",
]
