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
from .transport import GattCharacteristicTarget
from .vendor_gatt_preflight import (
    VendorGattPreflightResult,
    VendorGattRoute,
    resolve_vendor_gatt_route,
)
from .vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    parse_vendor_advanced_sensor_day,
    parse_vendor_multi_sport_day,
    parse_vendor_oxygen_day,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class HistorySimulationReason(str, Enum):
    LIMIT_REACHED = "limit_reached"
    LOCAL_QUIET = "local_quiet"
    DEVICE_FAILURE = "device_failure"
    PREFLIGHT_FAILURE = "preflight_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_FRAME = "malformed_frame"
    QUEUE_OVERFLOW = "queue_overflow"
    OVERALL_TIMEOUT = "overall_timeout"
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
    delivery_uncertain: bool
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
            f"delivery_uncertain={self.delivery_uncertain!r}, "
            "parsed_frames=<redacted>, local_end_timestamp=<redacted>, "
            "wire_terminal_observed=False, quiet_means_success=False, "
            "simulation_only=True, hardware_eligible=False, hardware_verified=False)"
        )


_PARSERS = {
    StaticQuery.MULTI_SPORT_DAY: parse_vendor_multi_sport_day,
    StaticQuery.OXYGEN_DAY: parse_vendor_oxygen_day,
    StaticQuery.ADVANCED_SENSOR_DAY: parse_vendor_advanced_sensor_day,
}
_MAX_FRAME_LIMIT = 4_096


class _OverallTimeoutError(TimeoutError):
    pass


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
        self._collecting = False

    async def collect(
        self,
        *,
        request: StaticVendorRequest,
        frame_limit: int = 1,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
        cleanup_timeout: float = 0.05,
    ) -> HistorySimulationResult:
        if self._collecting:
            raise RuntimeError("shared day-history collection is already in progress")
        self._collecting = True
        try:
            return await self._collect(
                request=request,
                frame_limit=frame_limit,
                quiet_timeout=quiet_timeout,
                overall_timeout=overall_timeout,
                stage_timeout=stage_timeout,
                cleanup_timeout=cleanup_timeout,
            )
        finally:
            self._collecting = False

    async def _collect(
        self,
        *,
        request: StaticVendorRequest,
        frame_limit: int,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
        cleanup_timeout: float,
    ) -> HistorySimulationResult:
        if type(request) is not StaticVendorRequest or request.operation not in _PARSERS:
            raise TypeError("request must be a closed shared day-history request")
        if isinstance(frame_limit, bool) or not isinstance(frame_limit, int):
            raise TypeError("frame_limit must be an integer")
        if frame_limit <= 0:
            raise ValueError("frame_limit must be positive")
        if frame_limit > _MAX_FRAME_LIMIT:
            raise ValueError(f"frame_limit must be at most {_MAX_FRAME_LIMIT}")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")
        cleanup = _positive_number(cleanup_timeout, "cleanup_timeout")
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=frame_limit + 1)
        parsed: list[object] = []
        projections: list[Projection] = []
        unrelated = 0
        overflowed = False
        accepting = True
        write_issued = False
        command_written = False
        subscribed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        reason = HistorySimulationReason.LOCAL_QUIET
        completeness = HistoryCollectionCompleteness.UNKNOWN
        loop = asyncio.get_running_loop()
        overall_deadline = loop.time() + overall

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not accepting:
                return
            bounded = bytes(data) if len(data) <= 20 else bytes(data[:21])
            try:
                queue.put_nowait(bounded)
            except asyncio.QueueFull:
                overflowed = True

        async def stage_call(operation_factory):
            remaining = overall_deadline - loop.time()
            if remaining <= 0:
                raise _OverallTimeoutError
            overall_is_limit = remaining <= stage
            operation_task = asyncio.create_task(operation_factory())
            try:
                done, _pending = await asyncio.wait(
                    {operation_task}, timeout=min(stage, remaining)
                )
            except BaseException:
                operation_task.cancel()
                await asyncio.gather(operation_task, return_exceptions=True)
                raise
            if operation_task in done:
                return operation_task.result()
            operation_task.cancel()
            await asyncio.gather(operation_task, return_exceptions=True)
            if overall_is_limit:
                raise _OverallTimeoutError
            raise asyncio.TimeoutError

        try:
            await stage_call(self._transport.connect)
            preflight = await stage_call(self._preflight)
            if not preflight.structurally_ready:
                reason = HistorySimulationReason.PREFLIGHT_FAILURE
                completeness = HistoryCollectionCompleteness.ABORTED
            else:
                request_target = preflight.request_target
                response_target = preflight.response_target
                if (
                    request_target is None
                    or response_target is None
                    or not self._transport.owns_target(request_target)
                    or not self._transport.owns_target(response_target)
                ):
                    reason = HistorySimulationReason.PREFLIGHT_FAILURE
                    completeness = HistoryCollectionCompleteness.ABORTED
                else:
                    await stage_call(
                        lambda: self._transport.subscribe_target(
                            response_target, receive
                        )
                    )
                    subscribed = True
                    write_issued = True
                    await stage_call(
                        lambda: self._transport.write_target_with_response(
                            request_target,
                            request.synthetic_bytes_for_test(),
                        )
                    )
                    command_written = True
                    quiet_deadline = loop.time() + quiet

                    while len(parsed) < frame_limit:
                        if overflowed:
                            reason = HistorySimulationReason.QUEUE_OVERFLOW
                            completeness = HistoryCollectionCompleteness.ABORTED
                            break
                        now = loop.time()
                        remaining = min(quiet_deadline, overall_deadline) - now
                        if remaining <= 0:
                            if now >= overall_deadline:
                                reason = HistorySimulationReason.OVERALL_TIMEOUT
                                completeness = HistoryCollectionCompleteness.ABORTED
                            else:
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
                        if pending:
                            await asyncio.gather(*pending, return_exceptions=True)
                        if not done:
                            continue
                        if overflowed:
                            reason = HistorySimulationReason.QUEUE_OVERFLOW
                            completeness = HistoryCollectionCompleteness.ABORTED
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
                        projections.extend(
                            self._projections(request.operation, value)
                        )
                        quiet_deadline = loop.time() + quiet
                    else:
                        reason = HistorySimulationReason.LIMIT_REACHED
        except _OverallTimeoutError:
            reason = HistorySimulationReason.OVERALL_TIMEOUT
            completeness = HistoryCollectionCompleteness.ABORTED
        except Exception:
            reason = (
                HistorySimulationReason.WRITE_FAILURE
                if write_issued else HistorySimulationReason.PREFLIGHT_FAILURE
            )
            completeness = HistoryCollectionCompleteness.ABORTED
        finally:
            accepting = False
            while True:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            cleanup_succeeded = await self._cleanup(
                subscribed, response_target, timeout=cleanup
            )

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
            delivery_uncertain=(
                write_issued and not command_written
            ),
            _parsed_frames=tuple(parsed),
            _local_end_device_epoch_seconds=local_end_timestamp,
        )

    @staticmethod
    def _classify(operation: StaticQuery, data: bytes) -> str:
        if not isinstance(data, bytes) or not data:
            return "unrelated"
        opcode = data[0]
        if operation is StaticQuery.MULTI_SPORT_DAY:
            if opcode not in {0x25, 0xA5}:
                return "unrelated"
            if len(data) != 20:
                return "malformed"
            if opcode == 0xA5 and data[1] == 0xFF:
                return "failure"
            return "success" if opcode == 0x25 else "unrelated"
        expected = 0x40 if operation is StaticQuery.OXYGEN_DAY else 0x55
        if opcode != expected:
            return "unrelated"
        return "success" if len(data) == 20 else "malformed"

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

    async def _preflight(self) -> VendorGattPreflightResult:
        services = await self._transport.service_uuids()
        metadata = await self._transport.gatt_characteristics()
        return resolve_vendor_gatt_route(
            VendorGattRoute.MAIN,
            services=services,
            metadata=metadata,
            connection_generation=self._transport.connection_generation,
        )

    async def _cleanup(
        self,
        subscribed: bool,
        response_target: GattCharacteristicTarget | None,
        *,
        timeout: float,
    ) -> bool:
        succeeded = True
        if subscribed and self._transport.connected:
            try:
                if response_target is None:
                    raise RuntimeError("subscription target is unavailable")
                await asyncio.wait_for(
                    self._transport.unsubscribe_target(response_target),
                    timeout=timeout,
                )
            except Exception:
                succeeded = False
        try:
            await asyncio.wait_for(self._transport.close(), timeout=timeout)
        except Exception:
            succeeded = False
        return succeeded


__all__ = [
    "FakeVendorHistorySimulator",
    "HistoryCollectionCompleteness",
    "HistorySimulationReason",
    "HistorySimulationResult",
]
