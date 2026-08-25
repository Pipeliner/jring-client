"""Dedicated fake-only coordinator for the multi-frame alarm batch topology.

Recovered ``0d``/``8d`` callback projections expose no proven alarm, content-chunk,
batch, or request identity; their uninterpreted body cannot establish correlation.
This module can therefore reproduce ordered fake dispatch and bounded callback
observation, but it can never establish high-level batch completion.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
import math

from .protocol import ProtocolError
from .transport import GattCharacteristicTarget
from .vendor_behavior_settings import (
    AlarmBatchRequest,
    AlarmRequest,
    AlarmWeekdays,
    ClockTime,
)
from .vendor_gatt_preflight import (
    VendorGattPreflightResult,
    VendorGattRoute,
    resolve_vendor_gatt_route,
)
from .vendor_protocol import StaticAckOperation, parse_vendor_ack
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class AlarmBatchSimulationReason(str, Enum):
    LOCAL_QUIET = "local_quiet"
    OBSERVATION_LIMIT = "observation_limit"
    FAILURE_SHAPED_CALLBACK_OBSERVED = "failure_shaped_callback_observed"
    CONNECT_FAILURE = "connect_failure"
    PREFLIGHT_FAILURE = "preflight_failure"
    SUBSCRIPTION_FAILURE = "subscription_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_MATCHING_CALLBACK = "malformed_matching_callback"
    QUEUE_OVERFLOW = "queue_overflow"
    STAGE_TIMEOUT = "stage_timeout"
    WRITE_TIMEOUT = "write_timeout"
    OVERALL_TIMEOUT = "overall_timeout"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class AlarmBatchCompleteness(str, Enum):
    UNKNOWN = "unknown"
    ABORTED = "aborted"
    UNCERTAIN = "uncertain"


class AlarmBatchSimulationTaintedError(RuntimeError):
    """An earlier alarm attempt left fake batch or cleanup state unsafe to reuse."""


class _StageTimeoutError(TimeoutError):
    pass


class _OverallTimeoutError(TimeoutError):
    pass


class _DisconnectedError(ConnectionError):
    pass


class _MalformedMatchingCallbackError(ValueError):
    pass


class _QueueOverflowError(OverflowError):
    pass


class _ObservationLimitError(RuntimeError):
    pass


class _WriteTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True, repr=False)
class AlarmBatchSimulationResult:
    reason: AlarmBatchSimulationReason
    completeness: AlarmBatchCompleteness
    write_invoked: bool
    all_planned_fake_write_calls_returned: bool
    all_invoked_fake_write_calls_returned: bool
    transport_call_uncertain: bool
    success_shaped_callback_observed: bool
    failure_shaped_callback_observed: bool
    success_shaped_callback_count: int
    failure_shaped_callback_count: int
    future_writes_stopped_after_failure: bool
    unrelated_notification_observed: bool
    cleanup_succeeded: bool
    tainted: bool
    protocol_delivery: str = field(default="unknown", init=False)
    acknowledgement_correlation: str = field(default="unavailable", init=False)
    correlated_application_acknowledgement_observed: bool = field(
        default=False, init=False
    )
    batch_acknowledgement_observed: bool = field(default=False, init=False)
    batch_success_established: bool = field(default=False, init=False)
    batch_terminal_observed: bool = field(default=False, init=False)
    quiet_means_success: bool = field(default=False, init=False)
    callback_count_equality_means_success: bool = field(default=False, init=False)
    failure_stop_policy: str = field(
        default="stop_not_yet_invoked_after_uncorrelated_failure", init=False
    )
    request_validation_atomic: bool = field(default=True, init=False)
    runtime_batch_atomic: bool = field(default=False, init=False)
    source_retained_alarm_list_reproduced: bool = field(default=False, init=False)
    source_partial_enqueue_semantics_reproduced: bool = field(
        default=False, init=False
    )
    automatic_retry: bool = field(default=False, init=False)
    simulation_only: bool = field(default=True, init=False)
    live_available: bool = field(default=False, init=False)
    owner_authorized: bool = field(default=False, init=False)
    hardware_eligible: bool = field(default=False, init=False)
    hardware_verified: bool = field(default=False, init=False)
    input_eligible: bool = field(default=False, init=False)
    private_alarm_data_retained: bool = field(default=False, init=False)
    ring_contacted: bool = field(default=False, init=False)
    ring_alarm_state_changed: bool = field(default=False, init=False)
    host_alarm_state_changed: bool = field(default=False, init=False)
    input_emitted: bool = field(default=False, init=False)

    @property
    def user_guidance(self) -> str:
        if self.failure_shaped_callback_observed:
            if self.future_writes_stopped_after_failure:
                lead = (
                    "The scripted fake observed an uncorrelated failure-shaped "
                    "callback; remaining synthetic writes were stopped and earlier "
                    "writes were not rolled back."
                )
            elif self.all_planned_fake_write_calls_returned:
                lead = (
                    "The scripted fake observed an uncorrelated failure-shaped "
                    "callback after every fake write call returned; no synthetic "
                    "writes remained to stop."
                )
            else:
                lead = (
                    "An uncorrelated failure-shaped callback was also observed, but "
                    "the attempt ended before the planned fake calls returned; the "
                    "callback did not establish the primary outcome or stop policy."
                )
        elif self.all_planned_fake_write_calls_returned:
            lead = (
                "All scripted fake write calls returned, but this is not protocol-level "
                "alarm batch completion."
            )
        elif self.write_invoked:
            lead = (
                "At least one scripted fake write was invoked without a complete batch "
                "result."
            )
        else:
            lead = "No scripted fake alarm write was invoked."
        guidance = (
            f"{lead} No ring was contacted or alarm changed; protocol delivery remains "
            "unknown."
        )
        if self.tainted:
            guidance += " Do not retry or reuse this simulator."
        return guidance

    def __repr__(self) -> str:
        return (
            "AlarmBatchSimulationResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"write_invoked={self.write_invoked!r}, "
            "all_planned_fake_write_calls_returned="
            f"{self.all_planned_fake_write_calls_returned!r}, "
            "all_invoked_fake_write_calls_returned="
            f"{self.all_invoked_fake_write_calls_returned!r}, "
            f"transport_call_uncertain={self.transport_call_uncertain!r}, "
            "success_shaped_callback_observed="
            f"{self.success_shaped_callback_observed!r}, "
            "failure_shaped_callback_observed="
            f"{self.failure_shaped_callback_observed!r}, "
            f"success_shaped_callback_count={self.success_shaped_callback_count!r}, "
            f"failure_shaped_callback_count={self.failure_shaped_callback_count!r}, "
            "future_writes_stopped_after_failure="
            f"{self.future_writes_stopped_after_failure!r}, "
            f"unrelated_notification_observed={self.unrelated_notification_observed!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, tainted={self.tainted!r}, "
            "protocol_delivery='unknown', acknowledgement_correlation='unavailable', "
            "batch_acknowledgement_observed=False, batch_success_established=False, "
            "batch_terminal_observed=False, ring_contacted=False, "
            "ring_alarm_state_changed=False, host_alarm_state_changed=False, "
            "input_emitted=False, "
            "private_alarm_data_retained=False, simulation_only=True, "
            "live_available=False, owner_authorized=False, hardware_eligible=False, "
            "hardware_verified=False, input_eligible=False)"
        )


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return converted


class FakeVendorAlarmBatchSimulator:
    """Simulate one closed alarm batch only on the exact scripted MAIN fake."""

    simulation_only = True
    hardware_eligible = False
    input_eligible = False

    def __init__(self, transport: ScriptedVendorFakeTransport) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        self._transport = transport
        self._running = False
        self._tainted = False

    @property
    def tainted(self) -> bool:
        return self._tainted

    def __repr__(self) -> str:
        return (
            "FakeVendorAlarmBatchSimulator(simulation_only=True, "
            "hardware_eligible=False, input_eligible=False, "
            f"tainted={self._tainted!r})"
        )

    async def simulate(
        self,
        batch: AlarmBatchRequest,
        *,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
        cleanup_timeout: float = 0.05,
        observation_limit: int = 64,
    ) -> AlarmBatchSimulationResult:
        if type(batch) is not AlarmBatchRequest:
            raise TypeError("batch must be the exact AlarmBatchRequest type")
        if self._tainted:
            raise AlarmBatchSimulationTaintedError(
                "simulator is tainted by an unsafe prior alarm attempt or cleanup; "
                "create a new simulator"
            )
        if self._running:
            raise RuntimeError("alarm batch simulation is already in progress")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")
        cleanup = _positive_number(cleanup_timeout, "cleanup_timeout")
        if isinstance(observation_limit, bool) or not isinstance(observation_limit, int):
            raise TypeError("observation_limit must be an integer")
        if not 1 <= observation_limit <= 4096:
            raise ValueError("observation_limit must be between 1 and 4096")
        validated_container = AlarmBatchRequest(batch.alarms)
        validated_alarms = tuple(
            AlarmRequest(
                alarm_id=alarm.alarm_id,
                enabled=alarm.enabled,
                time=ClockTime(alarm.time.hour, alarm.time.minute),
                weekdays=AlarmWeekdays(
                    alarm.weekdays.sunday,
                    alarm.weekdays.monday,
                    alarm.weekdays.tuesday,
                    alarm.weekdays.wednesday,
                    alarm.weekdays.thursday,
                    alarm.weekdays.friday,
                    alarm.weekdays.saturday,
                ),
                single=alarm.single,
                content=alarm.content,
            )
            for alarm in validated_container.alarms
        )
        validated_batch = AlarmBatchRequest(validated_alarms)
        frames = tuple(
            frame.synthetic_bytes_for_test() for frame in validated_batch.frames()
        )
        lease_owner = object()
        if not self._transport.acquire_simulation_lease(lease_owner):
            raise RuntimeError("scripted fake transport is already connected or in use")
        self._running = True
        try:
            return await self._simulate(
                frames,
                quiet=quiet,
                overall=overall,
                stage=stage,
                cleanup=cleanup,
                observation_limit=observation_limit,
            )
        finally:
            self._running = False
            self._transport.release_simulation_lease(lease_owner)

    async def _simulate(
        self,
        frames: tuple[bytes, ...],
        *,
        quiet: float,
        overall: float,
        stage: float,
        cleanup: float,
        observation_limit: int,
    ) -> AlarmBatchSimulationResult:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=256)
        accepting = True
        batch_active = False
        overflowed = False
        subscribed = False
        write_invoked = False
        invoked_write_calls = 0
        returned_write_calls = 0
        observations = 0
        success_count = 0
        failure_count = 0
        failure_stopped_future_writes = False
        success_observed = False
        failure_observed = False
        unrelated_observed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        reason = AlarmBatchSimulationReason.LOCAL_QUIET
        completeness = AlarmBatchCompleteness.UNKNOWN
        phase = "connect"
        loop = asyncio.get_running_loop()
        overall_deadline = loop.time() + overall

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not accepting or not batch_active:
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

        async def write_call(target: GattCharacteristicTarget, frame: bytes) -> None:
            nonlocal batch_active, invoked_write_calls, returned_write_calls
            nonlocal write_invoked
            remaining = overall_deadline - loop.time()
            if remaining <= 0:
                raise _OverallTimeoutError
            overall_is_limit = remaining <= stage

            async def invoke_write() -> None:
                nonlocal batch_active, invoked_write_calls, write_invoked
                write_invoked = True
                invoked_write_calls += 1
                batch_active = True
                await self._transport.write_target_with_response(target, frame)

            task = asyncio.create_task(invoke_write())
            disconnect_task = asyncio.create_task(
                self._transport.disconnect_event.wait()
            )
            try:
                done, pending = await asyncio.wait(
                    {task, disconnect_task},
                    timeout=min(stage, remaining),
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except BaseException:
                task.cancel()
                disconnect_task.cancel()
                await asyncio.gather(task, disconnect_task, return_exceptions=True)
                raise
            for pending_task in pending:
                pending_task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            write_returned = False
            if task in done:
                try:
                    task.result()
                except Exception:
                    if self._transport.disconnect_event.is_set():
                        raise _DisconnectedError
                    raise
                returned_write_calls += 1
                write_returned = True
            if self._transport.disconnect_event.is_set():
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise _DisconnectedError
            if write_returned:
                return
            task.cancel()
            disconnect_task.cancel()
            await asyncio.gather(task, disconnect_task, return_exceptions=True)
            if overall_is_limit:
                raise _OverallTimeoutError
            raise _WriteTimeoutError

        def process_notification(data: bytes) -> bool:
            nonlocal failure_count, failure_observed, observations
            nonlocal success_count, success_observed, unrelated_observed
            observations += 1
            if not data or data[0] not in {0x0D, 0x8D}:
                unrelated_observed = True
                if observations >= observation_limit and not failure_observed:
                    raise _ObservationLimitError
                return False
            if len(data) != 20:
                raise _MalformedMatchingCallbackError
            try:
                acknowledgement = parse_vendor_ack(
                    data, StaticAckOperation.ALARM
                )
            except ProtocolError as exc:
                raise _MalformedMatchingCallbackError from exc
            if acknowledgement.success:
                success_observed = True
                success_count += 1
            else:
                failure_observed = True
                failure_count += 1
            if observations >= observation_limit and not failure_observed:
                raise _ObservationLimitError
            return True

        def process_pending() -> bool:
            matching_observed = False
            if overflowed:
                raise _QueueOverflowError
            if observations >= observation_limit:
                return False
            while True:
                try:
                    data = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                matching_observed = process_notification(data) or matching_observed
                if observations >= observation_limit:
                    break
            if overflowed:
                raise _QueueOverflowError
            return matching_observed

        def classify_pending_after_primary_failure() -> None:
            try:
                process_pending()
            except (
                _MalformedMatchingCallbackError,
                _ObservationLimitError,
                _QueueOverflowError,
            ):
                self._tainted = True

        try:
            await stage_call(self._transport.connect)
            phase = "preflight"
            preflight = await stage_call(self._preflight)
            request_target = preflight.request_target
            response_target = preflight.response_target
            if (
                not preflight.structurally_ready
                or request_target is None
                or response_target is None
                or not self._transport.owns_target(request_target)
                or not self._transport.owns_target(response_target)
            ):
                reason = AlarmBatchSimulationReason.PREFLIGHT_FAILURE
                completeness = AlarmBatchCompleteness.ABORTED
            else:
                subscribed = True
                phase = "subscribe"
                await stage_call(
                    lambda: self._transport.subscribe_target(response_target, receive)
                )
                phase = "write"
                for frame in frames:
                    await asyncio.sleep(0)
                    process_pending()
                    if failure_observed:
                        failure_stopped_future_writes = (
                            returned_write_calls < len(frames)
                        )
                        break
                    if (
                        not self._transport.owns_target(request_target)
                        or not self._transport.owns_target(response_target)
                    ):
                        raise _DisconnectedError
                    await write_call(request_target, frame)
                    await asyncio.sleep(0)
                    process_pending()
                    if failure_observed:
                        failure_stopped_future_writes = (
                            returned_write_calls < len(frames)
                        )
                        break

                if failure_observed:
                    reason = (
                        AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
                    )
                    completeness = AlarmBatchCompleteness.UNKNOWN
                    self._tainted = True
                elif returned_write_calls == len(frames):
                    quiet_deadline = loop.time() + quiet
                    while True:
                        matching = process_pending()
                        if failure_observed:
                            reason = (
                                AlarmBatchSimulationReason.FAILURE_SHAPED_CALLBACK_OBSERVED
                            )
                            completeness = AlarmBatchCompleteness.UNKNOWN
                            self._tainted = True
                            break
                        if matching:
                            quiet_deadline = loop.time() + quiet
                        now = loop.time()
                        remaining = min(quiet_deadline, overall_deadline) - now
                        if remaining <= 0:
                            if now >= overall_deadline:
                                reason = AlarmBatchSimulationReason.OVERALL_TIMEOUT
                                completeness = AlarmBatchCompleteness.UNKNOWN
                            else:
                                reason = AlarmBatchSimulationReason.LOCAL_QUIET
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
                        if overflowed:
                            raise _QueueOverflowError
                        if not done:
                            continue
                        if data_task in done:
                            matching = process_notification(data_task.result())
                            if matching:
                                quiet_deadline = loop.time() + quiet
                        if disconnect_task in done and disconnect_task.result():
                            if not data_task.done():
                                data_task.cancel()
                            raise _DisconnectedError
        except _MalformedMatchingCallbackError:
            reason = AlarmBatchSimulationReason.MALFORMED_MATCHING_CALLBACK
            completeness = (
                AlarmBatchCompleteness.UNCERTAIN
                if write_invoked else AlarmBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _QueueOverflowError:
            reason = AlarmBatchSimulationReason.QUEUE_OVERFLOW
            completeness = (
                AlarmBatchCompleteness.UNCERTAIN
                if write_invoked else AlarmBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _ObservationLimitError:
            reason = AlarmBatchSimulationReason.OBSERVATION_LIMIT
            completeness = (
                AlarmBatchCompleteness.UNKNOWN
                if returned_write_calls == len(frames)
                else AlarmBatchCompleteness.ABORTED
            )
            self._tainted = returned_write_calls != len(frames)
        except _DisconnectedError:
            classify_pending_after_primary_failure()
            reason = AlarmBatchSimulationReason.DISCONNECTED
            completeness = (
                AlarmBatchCompleteness.UNCERTAIN
                if write_invoked else AlarmBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _OverallTimeoutError:
            classify_pending_after_primary_failure()
            reason = AlarmBatchSimulationReason.OVERALL_TIMEOUT
            if invoked_write_calls > returned_write_calls:
                completeness = AlarmBatchCompleteness.UNCERTAIN
                self._tainted = True
            elif returned_write_calls == len(frames):
                completeness = AlarmBatchCompleteness.UNKNOWN
            else:
                completeness = AlarmBatchCompleteness.ABORTED
                if write_invoked:
                    self._tainted = True
        except _StageTimeoutError:
            reason = AlarmBatchSimulationReason.STAGE_TIMEOUT
            completeness = (
                AlarmBatchCompleteness.UNCERTAIN
                if write_invoked else AlarmBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _WriteTimeoutError:
            classify_pending_after_primary_failure()
            reason = AlarmBatchSimulationReason.WRITE_TIMEOUT
            completeness = AlarmBatchCompleteness.UNCERTAIN
            self._tainted = True
        except Exception:
            if write_invoked:
                classify_pending_after_primary_failure()
                reason = AlarmBatchSimulationReason.WRITE_FAILURE
            elif phase == "connect":
                reason = AlarmBatchSimulationReason.CONNECT_FAILURE
            elif phase == "subscribe":
                reason = AlarmBatchSimulationReason.SUBSCRIPTION_FAILURE
            else:
                reason = AlarmBatchSimulationReason.PREFLIGHT_FAILURE
            completeness = (
                AlarmBatchCompleteness.UNCERTAIN
                if write_invoked else AlarmBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except BaseException:
            if write_invoked:
                self._tainted = True
            raise
        finally:
            batch_active = False
            accepting = False
            while True:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            cleanup_task = asyncio.create_task(
                self._cleanup(subscribed, response_target, timeout=cleanup)
            )
            try:
                cleanup_succeeded = await asyncio.shield(cleanup_task)
            except BaseException as interruption:
                self._tainted = True
                try:
                    cleanup_succeeded = await asyncio.shield(cleanup_task)
                except BaseException:
                    cleanup_task.cancel()
                    await asyncio.gather(cleanup_task, return_exceptions=True)
                raise interruption
            if not cleanup_succeeded:
                self._tainted = True

        if not cleanup_succeeded:
            reason = AlarmBatchSimulationReason.CLEANUP_FAILURE
            completeness = (
                AlarmBatchCompleteness.UNCERTAIN
                if write_invoked else AlarmBatchCompleteness.ABORTED
            )
        all_returned = returned_write_calls == len(frames)
        transport_uncertain = invoked_write_calls > returned_write_calls
        if transport_uncertain:
            completeness = AlarmBatchCompleteness.UNCERTAIN
            self._tainted = True
        return AlarmBatchSimulationResult(
            reason=reason,
            completeness=completeness,
            write_invoked=write_invoked,
            all_planned_fake_write_calls_returned=all_returned,
            all_invoked_fake_write_calls_returned=(
                invoked_write_calls == returned_write_calls
            ),
            transport_call_uncertain=transport_uncertain,
            success_shaped_callback_observed=success_observed,
            failure_shaped_callback_observed=failure_observed,
            success_shaped_callback_count=success_count,
            failure_shaped_callback_count=failure_count,
            future_writes_stopped_after_failure=failure_stopped_future_writes,
            unrelated_notification_observed=unrelated_observed,
            cleanup_succeeded=cleanup_succeeded,
            tainted=self._tainted,
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
    "AlarmBatchCompleteness",
    "AlarmBatchSimulationReason",
    "AlarmBatchSimulationResult",
    "AlarmBatchSimulationTaintedError",
    "FakeVendorAlarmBatchSimulator",
]
