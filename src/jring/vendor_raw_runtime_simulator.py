"""Bounded fake-only collector for raw vendor notifications.

Typed raw notifications are events, not command acknowledgements.  This simulator
therefore reports unknown completeness even when an event limit is reached and never
promotes local quiet to success.
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
from .vendor_raw_protocol import (
    RawVendorNotification,
    StaticRawCommand,
    parse_raw_vendor_notification,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class RawSimulationReason(str, Enum):
    LIMIT_REACHED = "limit_reached"
    LOCAL_QUIET = "local_quiet"
    PREFLIGHT_FAILURE = "preflight_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_EVENT = "malformed_event"
    QUEUE_OVERFLOW = "queue_overflow"
    OVERALL_TIMEOUT = "overall_timeout"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class RawCollectionCompleteness(str, Enum):
    UNKNOWN = "unknown"
    ABORTED = "aborted"


@dataclass(frozen=True, repr=False)
class RawSimulationResult:
    reason: RawSimulationReason
    completeness: RawCollectionCompleteness
    event_count: int
    command_written: bool
    cleanup_succeeded: bool
    delivery_uncertain: bool
    _events: tuple[RawVendorNotification, ...] = field(repr=False)

    @property
    def command_acknowledged(self) -> bool:
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

    def events_for_test(self) -> tuple[RawVendorNotification, ...]:
        return tuple(self._events)

    def __repr__(self) -> str:
        return (
            "RawSimulationResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"event_count={self.event_count}, command_written={self.command_written!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, events=<redacted>, "
            f"delivery_uncertain={self.delivery_uncertain!r}, "
            "command_acknowledged=False, quiet_means_success=False, "
            "simulation_only=True, hardware_eligible=False, hardware_verified=False)"
        )


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


_MAX_EVENT_LIMIT = 4_096
_MAX_RAW_FRAME_BYTES = 245


class _OverallTimeoutError(TimeoutError):
    pass


class FakeRawEventSimulator:
    """Collect typed events only from the exact scripted raw fake route."""

    simulation_only = True
    hardware_eligible = False

    def __init__(self, transport: ScriptedVendorFakeTransport) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        self._transport = transport
        self._collecting = False

    def __repr__(self) -> str:
        return (
            "FakeRawEventSimulator(simulation_only=True, hardware_eligible=False)"
        )

    async def collect(
        self,
        *,
        command: StaticRawCommand | None = None,
        event_limit: int = 1,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
        cleanup_timeout: float = 0.05,
    ) -> RawSimulationResult:
        if self._collecting:
            raise RuntimeError("raw event collection is already in progress")
        lease_owner = object()
        if not self._transport.acquire_simulation_lease(lease_owner):
            raise RuntimeError("scripted fake transport is already connected or in use")
        self._collecting = True
        try:
            return await self._collect(
                command=command,
                event_limit=event_limit,
                quiet_timeout=quiet_timeout,
                overall_timeout=overall_timeout,
                stage_timeout=stage_timeout,
                cleanup_timeout=cleanup_timeout,
            )
        finally:
            self._collecting = False
            self._transport.release_simulation_lease(lease_owner)

    async def _collect(
        self,
        *,
        command: StaticRawCommand | None,
        event_limit: int,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
        cleanup_timeout: float,
    ) -> RawSimulationResult:
        if command is not None and type(command) is not StaticRawCommand:
            raise TypeError("command must be a StaticRawCommand or None")
        if isinstance(event_limit, bool) or not isinstance(event_limit, int):
            raise TypeError("event_limit must be an integer")
        if event_limit <= 0:
            raise ValueError("event_limit must be positive")
        if event_limit > _MAX_EVENT_LIMIT:
            raise ValueError(f"event_limit must be at most {_MAX_EVENT_LIMIT}")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")
        cleanup = _positive_number(cleanup_timeout, "cleanup_timeout")
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=event_limit + 1)
        events: list[RawVendorNotification] = []
        overflowed = False
        accepting = True
        write_issued = False
        command_written = False
        subscribed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        reason = RawSimulationReason.LOCAL_QUIET
        completeness = RawCollectionCompleteness.UNKNOWN
        loop = asyncio.get_running_loop()
        overall_deadline = loop.time() + overall

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not accepting:
                return
            bounded = bytes(data[:_MAX_RAW_FRAME_BYTES])
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
                reason = RawSimulationReason.PREFLIGHT_FAILURE
                completeness = RawCollectionCompleteness.ABORTED
            else:
                request_target = preflight.request_target
                response_target = preflight.response_target
                if (
                    request_target is None
                    or response_target is None
                    or not self._transport.owns_target(request_target)
                    or not self._transport.owns_target(response_target)
                ):
                    reason = RawSimulationReason.PREFLIGHT_FAILURE
                    completeness = RawCollectionCompleteness.ABORTED
                else:
                    await stage_call(
                        lambda: self._transport.subscribe_target(
                            response_target, receive
                        )
                    )
                    subscribed = True
                    if command is not None:
                        write_issued = True
                        await stage_call(
                            lambda: self._transport.write_target_with_response(
                                request_target,
                                command.synthetic_bytes_for_test(),
                            )
                        )
                        command_written = True

                    quiet_deadline = loop.time() + quiet
                    while len(events) < event_limit:
                        if overflowed:
                            reason = RawSimulationReason.QUEUE_OVERFLOW
                            completeness = RawCollectionCompleteness.ABORTED
                            break
                        now = loop.time()
                        remaining = min(quiet_deadline, overall_deadline) - now
                        if remaining <= 0:
                            if now >= overall_deadline:
                                reason = RawSimulationReason.OVERALL_TIMEOUT
                                completeness = RawCollectionCompleteness.ABORTED
                            else:
                                reason = RawSimulationReason.LOCAL_QUIET
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
                            reason = RawSimulationReason.QUEUE_OVERFLOW
                            completeness = RawCollectionCompleteness.ABORTED
                            break
                        if disconnect_task in done and disconnect_task.result():
                            if not data_task.done():
                                data_task.cancel()
                            reason = RawSimulationReason.DISCONNECTED
                            completeness = RawCollectionCompleteness.ABORTED
                            break
                        try:
                            data = data_task.result()
                            events.append(parse_raw_vendor_notification(data))
                        except ProtocolError:
                            reason = RawSimulationReason.MALFORMED_EVENT
                            completeness = RawCollectionCompleteness.ABORTED
                            break
                        quiet_deadline = loop.time() + quiet
                    else:
                        reason = RawSimulationReason.LIMIT_REACHED
        except _OverallTimeoutError:
            reason = RawSimulationReason.OVERALL_TIMEOUT
            completeness = RawCollectionCompleteness.ABORTED
        except Exception:
            reason = (
                RawSimulationReason.WRITE_FAILURE
                if write_issued else RawSimulationReason.PREFLIGHT_FAILURE
            )
            completeness = RawCollectionCompleteness.ABORTED
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
            reason = RawSimulationReason.CLEANUP_FAILURE
            completeness = RawCollectionCompleteness.ABORTED
        return self._result(
            reason,
            completeness,
            events,
            command_written,
            cleanup_succeeded,
            delivery_uncertain=(write_issued and not command_written),
        )

    async def _preflight(self) -> VendorGattPreflightResult:
        services = await self._transport.service_uuids()
        metadata = await self._transport.gatt_characteristics()
        return resolve_vendor_gatt_route(
            VendorGattRoute.RAW,
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

    @staticmethod
    def _result(
        reason: RawSimulationReason,
        completeness: RawCollectionCompleteness,
        events: list[RawVendorNotification],
        command_written: bool,
        cleanup_succeeded: bool,
        *,
        delivery_uncertain: bool,
    ) -> RawSimulationResult:
        return RawSimulationResult(
            reason=reason,
            completeness=completeness,
            event_count=len(events),
            command_written=command_written,
            cleanup_succeeded=cleanup_succeeded,
            delivery_uncertain=delivery_uncertain,
            _events=tuple(events),
        )


__all__ = [
    "FakeRawEventSimulator",
    "RawCollectionCompleteness",
    "RawSimulationReason",
    "RawSimulationResult",
]
