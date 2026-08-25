"""Bounded fake-only collector for passive events on the vendor MAIN route.

The collector subscribes but never writes.  It recognizes only five statically
discriminated notification opcodes and does not treat local quiet or a caller limit
as a wire terminal.  In particular, opcode ``0x78`` is deliberately excluded because
its recovered subcommands collide across unrelated operations.
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
    Static45Notification,
    VendorClassicInfo,
    VendorDeviceAction,
    VendorPhoneVolumeRequest,
    VendorRedactedTextNotification,
    VendorStepCounter,
    parse_vendor_45_notification,
    parse_vendor_device_action,
    parse_vendor_phone_volume_request,
    parse_vendor_step_counter,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class MainEventKind(str, Enum):
    DEVICE_ACTION = "device_action"
    CUMULATIVE_STEP = "cumulative_step"
    PHONE_VOLUME_REQUEST = "phone_volume_request"
    CLASSIC_INFO = "classic_info"
    CLASSIC_NAME = "classic_name"


class MainEventSimulationReason(str, Enum):
    LIMIT_REACHED = "limit_reached"
    LOCAL_QUIET = "local_quiet"
    PREFLIGHT_FAILURE = "preflight_failure"
    MALFORMED_EVENT = "malformed_event"
    QUEUE_OVERFLOW = "queue_overflow"
    STAGE_TIMEOUT = "stage_timeout"
    OVERALL_TIMEOUT = "overall_timeout"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class MainEventCollectionCompleteness(str, Enum):
    UNKNOWN = "unknown"
    ABORTED = "aborted"


DecodedMainEvent = (
    VendorDeviceAction
    | VendorStepCounter
    | VendorPhoneVolumeRequest
    | VendorClassicInfo
    | VendorRedactedTextNotification
)


@dataclass(frozen=True, repr=False)
class MainPassiveEvent:
    kind: MainEventKind
    _value: DecodedMainEvent = field(repr=False)

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def input_eligible(self) -> bool:
        return False

    def value_for_test(self) -> DecodedMainEvent:
        """Expose a synthetic decoded value only to focused offline tests."""

        return self._value

    def __repr__(self) -> str:
        return (
            "MainPassiveEvent("
            f"kind={self.kind.value!r}, value=<redacted>, simulation_only=True, "
            "hardware_eligible=False, hardware_verified=False, input_eligible=False)"
        )


@dataclass(frozen=True, repr=False)
class MainEventSimulationResult:
    reason: MainEventSimulationReason
    completeness: MainEventCollectionCompleteness
    event_count: int
    unrelated_frame_count: int
    cleanup_succeeded: bool
    _events: tuple[MainPassiveEvent, ...] = field(repr=False)

    @property
    def event_kinds(self) -> tuple[MainEventKind, ...]:
        return tuple(event.kind for event in self._events)

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

    @property
    def input_eligible(self) -> bool:
        return False

    def events_for_test(self) -> tuple[MainPassiveEvent, ...]:
        """Return synthetic events to focused offline tests only."""

        return tuple(self._events)

    def __repr__(self) -> str:
        return (
            "MainEventSimulationResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"event_count={self.event_count}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, events=<redacted>, "
            "wire_terminal_observed=False, quiet_means_success=False, "
            "simulation_only=True, hardware_eligible=False, "
            "hardware_verified=False, input_eligible=False)"
        )


_MAX_EVENT_LIMIT = 4_096
_MATCHING_OPCODES = frozenset((0x06, 0x22, 0x45, 0x49, 0x51))
_CLASSIC_SELECTORS = frozenset((0x00, 0x01))


class _StageTimeoutError(TimeoutError):
    pass


class _OverallTimeoutError(TimeoutError):
    pass


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


class FakeVendorMainEventSimulator:
    """Collect passive MAIN events only from the exact scripted fake transport."""

    simulation_only = True
    hardware_eligible = False
    input_eligible = False

    def __init__(self, transport: ScriptedVendorFakeTransport) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        self._transport = transport
        self._collecting = False

    def __repr__(self) -> str:
        return (
            "FakeVendorMainEventSimulator(simulation_only=True, "
            "hardware_eligible=False, input_eligible=False)"
        )

    async def collect(
        self,
        *,
        event_limit: int = 1,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
        cleanup_timeout: float = 0.05,
    ) -> MainEventSimulationResult:
        if self._collecting:
            raise RuntimeError("passive MAIN event collection is already in progress")
        attempt_owner = object()
        if not self._transport.acquire_simulation_lease(attempt_owner):
            raise RuntimeError("scripted fake transport is already connected or in use")
        self._collecting = True
        try:
            return await self._collect(
                event_limit=event_limit,
                quiet_timeout=quiet_timeout,
                overall_timeout=overall_timeout,
                stage_timeout=stage_timeout,
                cleanup_timeout=cleanup_timeout,
            )
        finally:
            self._collecting = False
            self._transport.release_simulation_lease(attempt_owner)

    async def _collect(
        self,
        *,
        event_limit: int,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
        cleanup_timeout: float,
    ) -> MainEventSimulationResult:
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
        events: list[MainPassiveEvent] = []
        unrelated = 0
        overflowed = False
        accepting = True
        subscribed = False
        response_target: GattCharacteristicTarget | None = None
        cleanup_succeeded = False
        reason = MainEventSimulationReason.LOCAL_QUIET
        completeness = MainEventCollectionCompleteness.UNKNOWN
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
            task = asyncio.create_task(operation_factory())
            try:
                done, _pending = await asyncio.wait(
                    {task}, timeout=min(stage, remaining)
                )
            except BaseException:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise
            if task in done:
                return task.result()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if overall_is_limit:
                raise _OverallTimeoutError
            raise _StageTimeoutError

        try:
            await stage_call(self._transport.connect)
            preflight = await stage_call(self._preflight)
            response_target = preflight.response_target
            if (
                not preflight.structurally_ready
                or response_target is None
                or not self._transport.owns_target(response_target)
            ):
                reason = MainEventSimulationReason.PREFLIGHT_FAILURE
                completeness = MainEventCollectionCompleteness.ABORTED
            else:
                # The exact fake records the active callback before its await point.
                # Mark cleanup ownership first so cancellation at that boundary still
                # removes the callback instead of merely closing the transport.
                subscribed = True
                await stage_call(
                    lambda: self._transport.subscribe_target(response_target, receive)
                )
                quiet_deadline = loop.time() + quiet

                while len(events) < event_limit:
                    if overflowed:
                        reason = MainEventSimulationReason.QUEUE_OVERFLOW
                        completeness = MainEventCollectionCompleteness.ABORTED
                        break
                    now = loop.time()
                    remaining = min(quiet_deadline, overall_deadline) - now
                    if remaining <= 0:
                        if now >= overall_deadline:
                            reason = MainEventSimulationReason.OVERALL_TIMEOUT
                            completeness = MainEventCollectionCompleteness.ABORTED
                        else:
                            reason = MainEventSimulationReason.LOCAL_QUIET
                        break
                    data_task = asyncio.create_task(queue.get())
                    disconnect_task = asyncio.create_task(
                        self._transport.disconnect_event.wait()
                    )
                    try:
                        done, pending = await asyncio.wait(
                            {data_task, disconnect_task},
                            timeout=remaining,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                    except BaseException:
                        data_task.cancel()
                        disconnect_task.cancel()
                        await asyncio.gather(
                            data_task, disconnect_task, return_exceptions=True
                        )
                        raise
                    for task in pending:
                        task.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    if not done:
                        continue
                    if overflowed:
                        reason = MainEventSimulationReason.QUEUE_OVERFLOW
                        completeness = MainEventCollectionCompleteness.ABORTED
                        break
                    if disconnect_task in done and disconnect_task.result():
                        if not data_task.done():
                            data_task.cancel()
                        reason = MainEventSimulationReason.DISCONNECTED
                        completeness = MainEventCollectionCompleteness.ABORTED
                        break

                    data = data_task.result()
                    classification = self._classify(data)
                    if classification == "unrelated":
                        unrelated += 1
                        continue
                    if classification == "malformed":
                        reason = MainEventSimulationReason.MALFORMED_EVENT
                        completeness = MainEventCollectionCompleteness.ABORTED
                        break
                    try:
                        events.append(self._decode(data))
                    except ProtocolError:
                        reason = MainEventSimulationReason.MALFORMED_EVENT
                        completeness = MainEventCollectionCompleteness.ABORTED
                        break
                    quiet_deadline = loop.time() + quiet
                else:
                    reason = MainEventSimulationReason.LIMIT_REACHED
        except _OverallTimeoutError:
            reason = MainEventSimulationReason.OVERALL_TIMEOUT
            completeness = MainEventCollectionCompleteness.ABORTED
        except _StageTimeoutError:
            reason = MainEventSimulationReason.STAGE_TIMEOUT
            completeness = MainEventCollectionCompleteness.ABORTED
        except Exception:
            reason = MainEventSimulationReason.PREFLIGHT_FAILURE
            completeness = MainEventCollectionCompleteness.ABORTED
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
            reason = MainEventSimulationReason.CLEANUP_FAILURE
            completeness = MainEventCollectionCompleteness.ABORTED
        if completeness is MainEventCollectionCompleteness.ABORTED:
            events.clear()
        return MainEventSimulationResult(
            reason=reason,
            completeness=completeness,
            event_count=len(events),
            unrelated_frame_count=unrelated,
            cleanup_succeeded=cleanup_succeeded,
            _events=tuple(events),
        )

    @staticmethod
    def _classify(data: bytes) -> str:
        if not data or data[0] not in _MATCHING_OPCODES:
            return "unrelated"
        if data[0] == 0x45:
            if len(data) < 2:
                return "unrelated"
            if data[1] not in _CLASSIC_SELECTORS:
                return "unrelated"
        return "accepted" if len(data) == 20 else "malformed"

    @staticmethod
    def _decode(data: bytes) -> MainPassiveEvent:
        opcode = data[0]
        if opcode in {0x06, 0x22}:
            return MainPassiveEvent(
                MainEventKind.DEVICE_ACTION,
                parse_vendor_device_action(data),
            )
        if opcode == 0x51:
            return MainPassiveEvent(
                MainEventKind.CUMULATIVE_STEP,
                parse_vendor_step_counter(data),
            )
        if opcode == 0x45:
            kind = (
                Static45Notification.CLASSIC_INFO
                if data[1] == 0x00
                else Static45Notification.CLASSIC_NAME
            )
            return MainPassiveEvent(
                MainEventKind.CLASSIC_INFO
                if kind is Static45Notification.CLASSIC_INFO
                else MainEventKind.CLASSIC_NAME,
                parse_vendor_45_notification(data, expected_kind=kind),
            )
        return MainPassiveEvent(
            MainEventKind.PHONE_VOLUME_REQUEST,
            parse_vendor_phone_volume_request(data),
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
    "FakeVendorMainEventSimulator",
    "MainEventCollectionCompleteness",
    "MainEventKind",
    "MainEventSimulationReason",
    "MainEventSimulationResult",
    "MainPassiveEvent",
]
