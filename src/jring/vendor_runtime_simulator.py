"""Fake-only coordinator for adversarial vendor transaction simulations.

The coordinator accepts exactly :class:`ScriptedVendorFakeTransport`.  It has no
Bleak or client integration and cannot make an operation hardware eligible.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from collections import deque
from dataclasses import dataclass, field, replace
from enum import Enum
import math
import time
from typing import Any, TypeVar

from .transport import GattCharacteristicTarget, NotifyCallback
from .vendor_gatt_preflight import (
    VendorGattRoute,
    resolve_vendor_gatt_route,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport
from .vendor_transport import (
    NotificationDisposition,
    NotificationSubscriptionOutcome,
    OfflineVendorOperation,
    OfflineVendorTransactionEngine,
    TransactionCloseReason,
    TransactionClosure,
    TransactionCompleteness,
    VendorOperationToken,
    WriteOutcome,
)


class SimulationReason(str, Enum):
    SUCCESS = "success"
    DEVICE_FAILURE = "device_failure"
    TIMEOUT = "timeout"
    WRITE_FAILURE = "write_failure"
    SUBSCRIPTION_FAILURE = "subscription_failure"
    PREFLIGHT_FAILURE = "preflight_failure"
    CONNECT_FAILURE = "connect_failure"
    MALFORMED_RESPONSE = "malformed_response"
    FRAME_QUEUE_OVERFLOW = "frame_queue_overflow"
    CLEANUP_FAILURE = "cleanup_failure"
    CANCELLED = "cancelled"
    DISCONNECTED = "disconnected"


class SimulationBusyError(RuntimeError):
    pass


class SimulationTaintedError(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class SimulationResult:
    operation_name: str
    reason: SimulationReason
    completeness: TransactionCompleteness
    write_invoked: bool
    tainted: bool
    cleanup_succeeded: bool = True
    _parsed_value: object | None = field(default=None, repr=False)

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
    def user_guidance(self) -> str:
        """Plain-language synthetic outcome and safe next action."""

        if self.tainted and self.write_invoked:
            return (
                "The scripted fake may have received the command. It was not repeated; "
                "create a new simulator before continuing."
            )
        if self.tainted:
            return (
                "No vendor command was sent, but cleanup did not finish; create a new "
                "simulator before continuing."
            )
        if self.completeness is TransactionCompleteness.SUCCEEDED:
            return "A synthetic response matched; real hardware remains unverified."
        if self.completeness is TransactionCompleteness.FAILED:
            return "The scripted fake returned an explicit device-level failure."
        return "No vendor command was sent by this simulation attempt."

    def parsed_value_for_test(self) -> object | None:
        return self._parsed_value

    def __repr__(self) -> str:
        return (
            "SimulationResult("
            f"operation_name={self.operation_name!r}, reason={self.reason.value!r}, "
            f"completeness={self.completeness.value!r}, "
            f"write_invoked={self.write_invoked!r}, tainted={self.tainted!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            "parsed_value=<redacted>, simulation_only=True, "
            "hardware_eligible=False, hardware_verified=False)"
        )


class _Stage(Enum):
    CONNECT = "connect"
    PREFLIGHT = "preflight"
    SUBSCRIBE = "subscribe"
    PRE_WRITE = "pre_write"
    WRITE = "write"
    RESPONSE = "response"
    DONE = "done"


@dataclass
class _Attempt:
    generation: int
    deadline: float
    notification_event: asyncio.Event
    disconnect_event: asyncio.Event
    frames: deque[bytes] = field(default_factory=deque)
    stage: _Stage = _Stage.CONNECT
    connect_invoked: bool = False
    subscribe_invoked: bool = False
    write_invoked: bool = False
    overflowed: bool = False
    notify: NotifyCallback | None = None
    remove_disconnect_listener: Callable[[], None] | None = None
    engine: OfflineVendorTransactionEngine | None = None
    token: VendorOperationToken | None = None
    request_target: GattCharacteristicTarget | None = None
    response_target: GattCharacteristicTarget | None = None


class _DeadlineExpired(Exception):
    pass


class _Disconnected(Exception):
    pass


_T = TypeVar("_T")


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


_CLOSURE_REASONS = {
    TransactionCloseReason.SUCCESS: SimulationReason.SUCCESS,
    TransactionCloseReason.DEVICE_FAILURE: SimulationReason.DEVICE_FAILURE,
    TransactionCloseReason.TIMEOUT: SimulationReason.TIMEOUT,
    TransactionCloseReason.WRITE_FAILURE: SimulationReason.WRITE_FAILURE,
    TransactionCloseReason.SUBSCRIPTION_FAILURE: SimulationReason.SUBSCRIPTION_FAILURE,
    TransactionCloseReason.MALFORMED_RESPONSE: SimulationReason.MALFORMED_RESPONSE,
    TransactionCloseReason.CANCELLED: SimulationReason.CANCELLED,
    TransactionCloseReason.DISCONNECTED: SimulationReason.DISCONNECTED,
}


class FakeVendorRuntimeSimulator:
    """Coordinate one bounded transaction against the dedicated scripted fake."""

    simulation_only = True
    hardware_eligible = False

    def __init__(
        self,
        transport: ScriptedVendorFakeTransport,
        *,
        max_buffered_frames: int = 8,
        cleanup_timeout: float = 0.05,
    ) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        if isinstance(max_buffered_frames, bool) or not isinstance(
            max_buffered_frames, int
        ):
            raise TypeError("max_buffered_frames must be an integer")
        if max_buffered_frames <= 0:
            raise ValueError("max_buffered_frames must be positive")
        self._transport = transport
        self._max_buffered_frames = max_buffered_frames
        self._cleanup_timeout = _positive_number(cleanup_timeout, "cleanup_timeout")
        self._single_flight = asyncio.Lock()
        self._generation = 0
        self._active_generation: int | None = None
        self._tainted = False
        self.discarded_frame_count = 0
        self.stale_frame_count = 0
        self.unrelated_frame_count = 0
        self.last_result_for_test: SimulationResult | None = None

    @property
    def tainted(self) -> bool:
        return self._tainted

    def __repr__(self) -> str:
        return (
            "FakeVendorRuntimeSimulator("
            f"busy={self._single_flight.locked()!r}, tainted={self._tainted!r}, "
            "simulation_only=True, hardware_eligible=False)"
        )

    async def execute(
        self, operation: OfflineVendorOperation, *, timeout: float = 8.0
    ) -> SimulationResult:
        if type(operation) is not OfflineVendorOperation:
            raise TypeError("operation must be an exact OfflineVendorOperation")
        duration = _positive_number(timeout, "timeout")
        if self._tainted:
            raise SimulationTaintedError(
                "simulator is tainted by an uncertain attempt; create a new simulator"
            )
        if self._single_flight.locked():
            raise SimulationBusyError("a simulation attempt is already active")

        await self._single_flight.acquire()
        self._generation += 1
        generation = self._generation
        self._active_generation = generation
        attempt = _Attempt(
            generation=generation,
            deadline=time.monotonic() + duration,
            notification_event=asyncio.Event(),
            disconnect_event=asyncio.Event(),
        )
        self._install_callbacks(attempt)
        result: SimulationResult
        try:
            result = await self._drive(operation, attempt)
        except _DeadlineExpired:
            result = self._interruption_result(
                operation, attempt, SimulationReason.TIMEOUT
            )
        except _Disconnected:
            result = self._interruption_result(
                operation, attempt, SimulationReason.DISCONNECTED
            )
        except asyncio.CancelledError:
            result = self._interruption_result(
                operation, attempt, SimulationReason.CANCELLED
            )
        except Exception:
            result = self._stage_failure_result(operation, attempt)

        # Invalidate before unsubscribe/close so cleanup-time or retained callbacks can
        # never mutate the completed attempt.
        self._active_generation = None
        cleanup_ok = await self._cleanup(attempt)
        attempt.stage = _Stage.DONE
        if not cleanup_ok and result.completeness is TransactionCompleteness.UNCERTAIN:
            result = replace(result, cleanup_succeeded=False)
        elif not cleanup_ok:
            completeness = (
                TransactionCompleteness.UNCERTAIN
                if attempt.write_invoked
                else TransactionCompleteness.ABORTED
            )
            result = self._result(
                operation,
                reason=SimulationReason.CLEANUP_FAILURE,
                completeness=completeness,
                write_invoked=attempt.write_invoked,
                cleanup_succeeded=False,
                force_tainted=True,
            )
        self._single_flight.release()
        self.last_result_for_test = result
        return result

    def _install_callbacks(self, attempt: _Attempt) -> None:
        generation = attempt.generation

        def disconnected(_error: BaseException | None) -> None:
            if self._active_generation == generation:
                attempt.disconnect_event.set()

        def notified(data: bytes) -> None:
            if self._active_generation != generation:
                self.stale_frame_count += 1
                return
            if attempt.stage not in {_Stage.WRITE, _Stage.RESPONSE}:
                self.discarded_frame_count += 1
                return
            if len(attempt.frames) >= self._max_buffered_frames:
                attempt.overflowed = True
            else:
                attempt.frames.append(bytes(data))
            attempt.notification_event.set()

        attempt.remove_disconnect_listener = self._transport.add_disconnect_listener(
            disconnected
        )
        attempt.notify = notified

    async def _drive(
        self, operation: OfflineVendorOperation, attempt: _Attempt
    ) -> SimulationResult:
        attempt.connect_invoked = True
        await self._await_boundary(self._transport.connect(), attempt)

        attempt.stage = _Stage.PREFLIGHT
        services = await self._await_boundary(self._transport.service_uuids(), attempt)
        metadata = await self._await_boundary(
            self._transport.gatt_characteristics(), attempt
        )
        preflight = resolve_vendor_gatt_route(
            VendorGattRoute.MAIN,
            services=services,
            metadata=metadata,
            connection_generation=self._transport.connection_generation,
        )
        if not preflight.structurally_ready:
            return self._result(
                operation,
                reason=SimulationReason.PREFLIGHT_FAILURE,
                completeness=TransactionCompleteness.ABORTED,
                write_invoked=False,
            )
        attempt.request_target = preflight.request_target
        attempt.response_target = preflight.response_target
        if (
            attempt.request_target is None
            or attempt.response_target is None
            or not self._transport.owns_target(attempt.request_target)
            or not self._transport.owns_target(attempt.response_target)
        ):
            return self._result(
                operation,
                reason=SimulationReason.PREFLIGHT_FAILURE,
                completeness=TransactionCompleteness.ABORTED,
                write_invoked=False,
            )

        now = time.monotonic()
        remaining = attempt.deadline - now
        if remaining <= 0:
            raise _DeadlineExpired
        engine = OfflineVendorTransactionEngine(operation_timeout=remaining)
        subscription = engine.mark_connected(now=now)
        token = engine.enqueue(operation, now=now)
        attempt.engine = engine
        attempt.token = token

        attempt.stage = _Stage.SUBSCRIBE
        attempt.subscribe_invoked = True
        callback = attempt.notify
        if callback is None:
            raise RuntimeError("attempt notification callback was not installed")
        await self._await_boundary(
            self._transport.subscribe_target(attempt.response_target, callback),
            attempt,
        )
        now = time.monotonic()
        confirmed = engine.confirm_subscription(
            token=subscription.token,
            characteristic_uuid=subscription.characteristic_uuid,
            outcome=NotificationSubscriptionOutcome.TRANSPORT_CALL_COMPLETED,
            now=now,
        )
        if confirmed.closure is not None:
            return self._from_closure(operation, attempt, confirmed.closure)

        attempt.stage = _Stage.PRE_WRITE
        await asyncio.sleep(0)
        if time.monotonic() >= attempt.deadline:
            raise _DeadlineExpired
        update = engine.take_write(now=time.monotonic())
        if update.closure is not None:
            return self._from_closure(operation, attempt, update.closure)
        if update.write_intent is None:
            raise RuntimeError("offline engine did not provide one write intent")

        if attempt.disconnect_event.is_set():
            raise _Disconnected
        attempt.stage = _Stage.WRITE
        attempt.write_invoked = True
        await self._await_boundary(
            self._transport.write_target_with_response(
                attempt.request_target,
                update.write_intent.synthetic_bytes_for_test(),
            ),
            attempt,
        )
        acknowledged = engine.confirm_write(
            token,
            outcome=WriteOutcome.ACKNOWLEDGED,
            now=time.monotonic(),
        )
        if acknowledged.closure is not None:
            return self._from_closure(operation, attempt, acknowledged.closure)

        attempt.stage = _Stage.RESPONSE
        while True:
            if attempt.overflowed:
                engine.cancel()
                return self._result(
                    operation,
                    reason=SimulationReason.FRAME_QUEUE_OVERFLOW,
                    completeness=TransactionCompleteness.UNCERTAIN,
                    write_invoked=True,
                )
            while attempt.frames:
                notification = engine.receive(
                    token,
                    endpoint_uuid=attempt.response_target.uuid,
                    data=attempt.frames.popleft(),
                    now=time.monotonic(),
                )
                if notification.disposition is NotificationDisposition.UNRELATED:
                    self.unrelated_frame_count += 1
                    continue
                if notification.closure is not None:
                    return self._from_closure(
                        operation,
                        attempt,
                        notification.closure,
                        parsed_value=notification.parsed_value,
                    )
            attempt.notification_event.clear()
            if attempt.frames or attempt.overflowed:
                continue
            await self._await_boundary(attempt.notification_event.wait(), attempt)

    async def _await_boundary(
        self, operation: Coroutine[Any, Any, _T], attempt: _Attempt
    ) -> _T:
        operation_task = asyncio.create_task(operation)
        disconnect_task = asyncio.create_task(attempt.disconnect_event.wait())
        remaining = attempt.deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise _DeadlineExpired
            done, _pending = await asyncio.wait(
                {operation_task, disconnect_task},
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                raise _DeadlineExpired
            if disconnect_task in done:
                raise _Disconnected
            return await operation_task
        finally:
            for task in (operation_task, disconnect_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(
                operation_task, disconnect_task, return_exceptions=True
            )

    async def _cleanup(self, attempt: _Attempt) -> bool:
        succeeded = True
        if attempt.subscribe_invoked:
            try:
                if attempt.response_target is None:
                    raise RuntimeError("subscription target is unavailable")
                await asyncio.wait_for(
                    self._transport.unsubscribe_target(attempt.response_target),
                    timeout=self._cleanup_timeout,
                )
            except BaseException:
                succeeded = False
        if attempt.connect_invoked:
            try:
                await asyncio.wait_for(
                    self._transport.close(), timeout=self._cleanup_timeout
                )
            except BaseException:
                succeeded = False
        if attempt.remove_disconnect_listener is not None:
            attempt.remove_disconnect_listener()
            attempt.remove_disconnect_listener = None
        return succeeded

    def _stage_failure_result(
        self, operation: OfflineVendorOperation, attempt: _Attempt
    ) -> SimulationResult:
        if (
            attempt.stage is _Stage.WRITE
            and attempt.engine is not None
            and attempt.token is not None
        ):
            update = attempt.engine.confirm_write(
                attempt.token,
                outcome=WriteOutcome.OUTCOME_UNKNOWN,
                now=time.monotonic(),
            )
            if update.closure is not None:
                return self._from_closure(operation, attempt, update.closure)
        reasons = {
            _Stage.CONNECT: SimulationReason.CONNECT_FAILURE,
            _Stage.PREFLIGHT: SimulationReason.PREFLIGHT_FAILURE,
            _Stage.SUBSCRIBE: SimulationReason.SUBSCRIPTION_FAILURE,
            _Stage.WRITE: SimulationReason.WRITE_FAILURE,
            _Stage.RESPONSE: SimulationReason.MALFORMED_RESPONSE,
        }
        return self._result(
            operation,
            reason=reasons.get(attempt.stage, SimulationReason.PREFLIGHT_FAILURE),
            completeness=(
                TransactionCompleteness.UNCERTAIN
                if attempt.write_invoked
                else TransactionCompleteness.ABORTED
            ),
            write_invoked=attempt.write_invoked,
        )

    def _interruption_result(
        self,
        operation: OfflineVendorOperation,
        attempt: _Attempt,
        reason: SimulationReason,
    ) -> SimulationResult:
        if attempt.engine is not None:
            if reason is SimulationReason.TIMEOUT:
                update = attempt.engine.poll(
                    now=max(time.monotonic(), attempt.deadline)
                )
            elif reason is SimulationReason.DISCONNECTED:
                update = attempt.engine.record_disconnected()
            elif reason is SimulationReason.CANCELLED:
                update = attempt.engine.cancel()
            else:
                update = None
            if update is not None and update.closure is not None:
                return self._from_closure(operation, attempt, update.closure)
        return self._result(
            operation,
            reason=reason,
            completeness=(
                TransactionCompleteness.UNCERTAIN
                if attempt.write_invoked
                else TransactionCompleteness.ABORTED
            ),
            write_invoked=attempt.write_invoked,
        )

    def _from_closure(
        self,
        operation: OfflineVendorOperation,
        attempt: _Attempt,
        closure: TransactionClosure,
        *,
        parsed_value: object | None = None,
    ) -> SimulationResult:
        return self._result(
            operation,
            reason=_CLOSURE_REASONS[closure.reason],
            completeness=closure.completeness,
            write_invoked=attempt.write_invoked,
            parsed_value=parsed_value,
        )

    def _result(
        self,
        operation: OfflineVendorOperation,
        *,
        reason: SimulationReason,
        completeness: TransactionCompleteness,
        write_invoked: bool,
        parsed_value: object | None = None,
        cleanup_succeeded: bool = True,
        force_tainted: bool = False,
    ) -> SimulationResult:
        tainted = (
            force_tainted
            or completeness is TransactionCompleteness.UNCERTAIN
        )
        if tainted:
            self._tainted = True
        return SimulationResult(
            operation_name=operation.name,
            reason=reason,
            completeness=completeness,
            write_invoked=write_invoked,
            tainted=tainted,
            cleanup_succeeded=cleanup_succeeded,
            _parsed_value=parsed_value,
        )


__all__ = [
    "FakeVendorRuntimeSimulator",
    "SimulationBusyError",
    "SimulationReason",
    "SimulationResult",
    "SimulationTaintedError",
]
