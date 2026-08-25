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


class FakeRawEventSimulator:
    """Collect typed events only from the exact scripted raw fake route."""

    simulation_only = True
    hardware_eligible = False

    def __init__(self, transport: ScriptedVendorFakeTransport) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        self._transport = transport

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
    ) -> RawSimulationResult:
        if command is not None and type(command) is not StaticRawCommand:
            raise TypeError("command must be a StaticRawCommand or None")
        if isinstance(event_limit, bool) or not isinstance(event_limit, int):
            raise TypeError("event_limit must be an integer")
        if event_limit <= 0:
            raise ValueError("event_limit must be positive")
        timeout = _positive_number(quiet_timeout, "quiet_timeout")
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        events: list[RawVendorNotification] = []
        command_written = False
        subscribed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        reason = RawSimulationReason.LOCAL_QUIET
        completeness = RawCollectionCompleteness.UNKNOWN

        try:
            await self._transport.connect()
            preflight = await self._preflight()
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
                    return self._result(
                        operation,
                        reason,
                        completeness,
                        events,
                        write_invoked=False,
                    )
                await self._transport.subscribe_target(response_target, queue.put_nowait)
                subscribed = True
                if command is not None:
                    await self._transport.write_target_with_response(
                        request_target,
                        command.synthetic_bytes_for_test(),
                    )
                    command_written = True

                while len(events) < event_limit:
                    data_task = asyncio.create_task(queue.get())
                    disconnect_task = asyncio.create_task(
                        self._transport.disconnect_event.wait()
                    )
                    done, pending = await asyncio.wait(
                        {data_task, disconnect_task},
                        timeout=timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in pending:
                        task.cancel()
                    if not done:
                        reason = RawSimulationReason.LOCAL_QUIET
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
                else:
                    reason = RawSimulationReason.LIMIT_REACHED
        except (ConnectionError, LookupError, OSError):
            reason = (
                RawSimulationReason.WRITE_FAILURE
                if subscribed else RawSimulationReason.PREFLIGHT_FAILURE
            )
            completeness = RawCollectionCompleteness.ABORTED
        finally:
            cleanup_succeeded = await self._cleanup(subscribed, response_target)

        if not cleanup_succeeded:
            reason = RawSimulationReason.CLEANUP_FAILURE
            completeness = RawCollectionCompleteness.ABORTED
        return self._result(
            reason, completeness, events, command_written, cleanup_succeeded
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
    ) -> bool:
        succeeded = True
        if subscribed and self._transport.connected:
            try:
                if response_target is None:
                    raise RuntimeError("subscription target is unavailable")
                await self._transport.unsubscribe_target(response_target)
            except (ConnectionError, LookupError, OSError, RuntimeError):
                succeeded = False
        try:
            await self._transport.close()
        except OSError:
            succeeded = False
        return succeeded

    @staticmethod
    def _result(
        reason: RawSimulationReason,
        completeness: RawCollectionCompleteness,
        events: list[RawVendorNotification],
        command_written: bool,
        cleanup_succeeded: bool,
    ) -> RawSimulationResult:
        return RawSimulationResult(
            reason=reason,
            completeness=completeness,
            event_count=len(events),
            command_written=command_written,
            cleanup_succeeded=cleanup_succeeded,
            _events=tuple(events),
        )


__all__ = [
    "FakeRawEventSimulator",
    "RawCollectionCompleteness",
    "RawSimulationReason",
    "RawSimulationResult",
]
