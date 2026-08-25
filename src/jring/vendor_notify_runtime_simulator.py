"""Dedicated fake-only coordinator for recovered notification batch choreography.

Per-frame ``12`` callbacks expose a sequence marker, while ``92`` is an unmarked
failure-shaped callback.  Neither establishes whole-batch delivery or a terminal.
This module executes only against the exact scripted fake and retains no notification
request, plan, frame, marker identity, UID, digest, title, or content in its result.
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
from .vendor_notify import (
    NotifyDisposition,
    NotifyPlannerState,
    NotifyRequest,
    plan_notify,
)
from .vendor_protocol import parse_vendor_notify_ack
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class NotifyBatchSimulationReason(str, Enum):
    DEDUPLICATED = "deduplicated"
    LOCAL_QUIET = "local_quiet"
    OBSERVATION_LIMIT = "observation_limit"
    UNMARKED_FAILURE_OBSERVED = "unmarked_failure_observed"
    CONNECT_FAILURE = "connect_failure"
    PREFLIGHT_FAILURE = "preflight_failure"
    SUBSCRIPTION_FAILURE = "subscription_failure"
    WRITE_FAILURE = "write_failure"
    WRITE_TIMEOUT = "write_timeout"
    MALFORMED_MATCHING_CALLBACK = "malformed_matching_callback"
    QUEUE_OVERFLOW = "queue_overflow"
    STAGE_TIMEOUT = "stage_timeout"
    OVERALL_TIMEOUT = "overall_timeout"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class NotifyBatchCompleteness(str, Enum):
    NOT_DISPATCHED = "not_dispatched"
    UNKNOWN = "unknown"
    ABORTED = "aborted"
    UNCERTAIN = "uncertain"


class NotifyBatchSimulationTaintedError(RuntimeError):
    """An earlier fake notification attempt left dispatch or cleanup unsafe."""


class _StageTimeoutError(TimeoutError):
    pass


class _OverallTimeoutError(TimeoutError):
    pass


class _WriteTimeoutError(TimeoutError):
    pass


class _DisconnectedError(ConnectionError):
    pass


class _MalformedMatchingCallbackError(ValueError):
    pass


class _QueueOverflowError(OverflowError):
    pass


class _ObservationLimitError(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class NotifyBatchSimulationResult:
    disposition: NotifyDisposition
    reason: NotifyBatchSimulationReason
    completeness: NotifyBatchCompleteness
    write_invoked: bool
    all_planned_fake_write_calls_returned: bool
    all_invoked_fake_write_calls_returned: bool
    transport_call_uncertain: bool
    marker_matched_callback_observed: bool
    multiple_distinct_marker_callbacks_observed: bool
    duplicate_marker_callback_observed: bool
    unmarked_failure_callback_observed: bool
    multiple_unmarked_failure_callbacks_observed: bool
    unmatched_marker_callback_observed: bool
    future_writes_stopped_after_failure: bool
    unrelated_notification_observed: bool
    cleanup_succeeded: bool
    tainted: bool
    scripted_transport_contains_private_test_frames: bool
    protocol_delivery: str = field(default="not_attempted", init=False)
    acknowledgement_correlation: str = field(default="not_applicable", init=False)
    disposition_scope: str = field(default="offline_planner_only", init=False)
    transport_scope: str = field(default="exact_scripted_fake_only", init=False)
    fake_write_plan: str = field(default="none_deduplicated", init=False)
    batch_acknowledgement_observed: bool = field(default=False, init=False)
    batch_success_established: bool = field(default=False, init=False)
    batch_terminal_observed: bool = field(default=False, init=False)
    callback_marker_coverage_means_success: bool = field(default=False, init=False)
    quiet_means_success: bool = field(default=False, init=False)
    observation_limit_means_success: bool = field(default=False, init=False)
    planner_state_committed: bool = field(default=False, init=False)
    request_validation_atomic: bool = field(default=True, init=False)
    runtime_batch_atomic: bool = field(default=False, init=False)
    source_caller_throttle_reproduced: bool = field(default=False, init=False)
    source_global_overlap_race_reproduced: bool = field(default=False, init=False)
    simulator_single_batch_serialized: bool = field(default=True, init=False)
    automatic_retry: bool = field(default=False, init=False)
    ring_contacted: bool = field(default=False, init=False)
    ring_display_changed: bool = field(default=False, init=False)
    host_notification_changed: bool = field(default=False, init=False)
    input_emitted: bool = field(default=False, init=False)
    simulation_only: bool = field(default=True, init=False)
    live_available: bool = field(default=False, init=False)
    owner_authorized: bool = field(default=False, init=False)
    hardware_eligible: bool = field(default=False, init=False)
    hardware_verified: bool = field(default=False, init=False)
    input_eligible: bool = field(default=False, init=False)
    result_retains_private_notification_data: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.disposition is NotifyDisposition.PLANNED:
            object.__setattr__(self, "fake_write_plan", "planned_batch")
        if self.write_invoked:
            object.__setattr__(self, "protocol_delivery", "unknown")
            object.__setattr__(
                self, "acknowledgement_correlation", "per_invoked_marker_only"
            )

    @property
    def user_guidance(self) -> str:
        reason_leads = {
            NotifyBatchSimulationReason.CONNECT_FAILURE: (
                "The scripted fake connection failed before notification dispatch."
            ),
            NotifyBatchSimulationReason.PREFLIGHT_FAILURE: (
                "The scripted fake GATT preflight failed before notification dispatch."
            ),
            NotifyBatchSimulationReason.SUBSCRIPTION_FAILURE: (
                "The scripted fake callback subscription failed before notification dispatch."
            ),
            NotifyBatchSimulationReason.WRITE_FAILURE: (
                "A scripted fake notification write failed."
            ),
            NotifyBatchSimulationReason.WRITE_TIMEOUT: (
                "A scripted fake notification write timed out."
            ),
            NotifyBatchSimulationReason.MALFORMED_MATCHING_CALLBACK: (
                "A malformed notification callback was observed by the scripted fake."
            ),
            NotifyBatchSimulationReason.QUEUE_OVERFLOW: (
                "The scripted fake callback queue overflowed."
            ),
            NotifyBatchSimulationReason.STAGE_TIMEOUT: (
                "A scripted fake setup stage timed out."
            ),
            NotifyBatchSimulationReason.OVERALL_TIMEOUT: (
                "The scripted fake overall deadline expired."
            ),
            NotifyBatchSimulationReason.DISCONNECTED: (
                "The scripted fake disconnected during the notification attempt."
            ),
            NotifyBatchSimulationReason.CLEANUP_FAILURE: (
                "Scripted fake cleanup failed after the notification attempt."
            ),
            NotifyBatchSimulationReason.OBSERVATION_LIMIT: (
                "The scripted fake callback observation limit was reached."
            ),
        }
        if self.reason in reason_leads:
            lead = reason_leads[self.reason]
            if self.unmarked_failure_callback_observed:
                if self.future_writes_stopped_after_failure:
                    lead += (
                        " An unmarked failure-shaped callback stopped not-yet-invoked "
                        "synthetic writes without rollback."
                    )
                elif self.all_planned_fake_write_calls_returned:
                    lead += (
                        " An unmarked failure-shaped callback was also observed after "
                        "every planned fake write call returned."
                    )
                else:
                    lead += (
                        " An unmarked failure-shaped callback was also observed, but "
                        "the attempt ended before the planned fake calls returned; it "
                        "did not establish the primary outcome or stop policy."
                    )
            elif self.unmatched_marker_callback_observed:
                lead += (
                    " An unowned notification marker was observed and was not saved "
                    "for later correlation."
                )
            elif self.marker_matched_callback_observed:
                lead += (
                    " One or more per-frame marker-correlated callbacks were also "
                    "observed."
                )
        elif self.disposition is NotifyDisposition.DEDUPLICATED:
            lead = (
                "The offline planner deduplicated the notification, so the scripted "
                "fake was not contacted."
            )
        elif self.unmarked_failure_callback_observed:
            if self.future_writes_stopped_after_failure:
                lead = (
                    "The scripted fake observed an unmarked failure-shaped callback; "
                    "not-yet-invoked synthetic writes were stopped without rollback."
                )
            elif self.all_planned_fake_write_calls_returned:
                lead = (
                    "The scripted fake observed an unmarked failure-shaped callback "
                    "after every planned fake write call returned; no writes remained "
                    "to stop."
                )
            else:
                lead = (
                    "An unmarked failure-shaped callback was also observed, but the "
                    "attempt ended before the planned fake calls returned; it did not "
                    "establish the primary outcome or stop policy."
                )
        elif self.unmatched_marker_callback_observed:
            lead = (
                "The scripted fake observed a notification marker that did not name an "
                "already-invoked frame, so it was not saved for later correlation."
            )
        elif self.marker_matched_callback_observed:
            lead = (
                "The scripted fake observed one or more marker-correlated per-frame "
                "callbacks."
            )
        elif self.all_planned_fake_write_calls_returned:
            lead = "All planned scripted fake write calls returned."
        elif self.write_invoked:
            lead = "At least one scripted fake notification write was invoked."
        else:
            lead = "No scripted fake notification write was invoked."
        guidance = (
            f"{lead} This does not prove ring delivery, display change, batch "
            "acknowledgement, or planner-state commit."
        )
        if self.scripted_transport_contains_private_test_frames:
            guidance += (
                " The simulator-referenced scripted transport contains private test "
                "frames; call clear_sensitive_test_state() after inspection or discard "
                "both simulator and transport."
            )
        if self.tainted:
            guidance += " Do not retry or reuse this simulator."
        return guidance

    def __repr__(self) -> str:
        return (
            "NotifyBatchSimulationResult("
            f"disposition={self.disposition.value!r}, reason={self.reason.value!r}, "
            f"completeness={self.completeness.value!r}, "
            f"write_invoked={self.write_invoked!r}, "
            "all_planned_fake_write_calls_returned="
            f"{self.all_planned_fake_write_calls_returned!r}, "
            "all_invoked_fake_write_calls_returned="
            f"{self.all_invoked_fake_write_calls_returned!r}, "
            f"transport_call_uncertain={self.transport_call_uncertain!r}, "
            "marker_matched_callback_observed="
            f"{self.marker_matched_callback_observed!r}, "
            "multiple_distinct_marker_callbacks_observed="
            f"{self.multiple_distinct_marker_callbacks_observed!r}, "
            "duplicate_marker_callback_observed="
            f"{self.duplicate_marker_callback_observed!r}, "
            "unmarked_failure_callback_observed="
            f"{self.unmarked_failure_callback_observed!r}, "
            "multiple_unmarked_failure_callbacks_observed="
            f"{self.multiple_unmarked_failure_callbacks_observed!r}, "
            "unmatched_marker_callback_observed="
            f"{self.unmatched_marker_callback_observed!r}, "
            "future_writes_stopped_after_failure="
            f"{self.future_writes_stopped_after_failure!r}, "
            f"unrelated_notification_observed={self.unrelated_notification_observed!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, tainted={self.tainted!r}, "
            "scripted_transport_contains_private_test_frames="
            f"{self.scripted_transport_contains_private_test_frames!r}, "
            f"protocol_delivery={self.protocol_delivery!r}, "
            f"acknowledgement_correlation={self.acknowledgement_correlation!r}, "
            "disposition_scope='offline_planner_only', "
            "transport_scope='exact_scripted_fake_only', "
            "planner_state_committed=False, "
            "batch_success_established=False, batch_terminal_observed=False, "
            "ring_contacted=False, ring_display_changed=False, "
            "host_notification_changed=False, input_emitted=False, "
            "result_retains_private_notification_data=False, simulation_only=True, "
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


class FakeVendorNotifyBatchSimulator:
    """Simulate one planned notification batch on the exact scripted MAIN fake."""

    simulation_only = True
    hardware_eligible = False
    input_eligible = False

    @staticmethod
    def reproduced_request_names() -> frozenset[str]:
        return frozenset({"setNotify"})

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
            "FakeVendorNotifyBatchSimulator(simulation_only=True, "
            "hardware_eligible=False, input_eligible=False, "
            f"tainted={self._tainted!r})"
        )

    async def simulate(
        self,
        state: NotifyPlannerState,
        request: NotifyRequest,
        *,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
        cleanup_timeout: float = 0.05,
        observation_limit: int = 256,
    ) -> NotifyBatchSimulationResult:
        if type(state) is not NotifyPlannerState:
            raise TypeError("state must be the exact NotifyPlannerState type")
        if type(request) is not NotifyRequest:
            raise TypeError("request must be the exact NotifyRequest type")
        if self._tainted:
            raise NotifyBatchSimulationTaintedError(
                "simulator is tainted by an unsafe prior notification attempt or "
                "cleanup; create a new simulator"
            )
        if self._running:
            raise RuntimeError("notification batch simulation is already in progress")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")
        cleanup = _positive_number(cleanup_timeout, "cleanup_timeout")
        if isinstance(observation_limit, bool) or not isinstance(observation_limit, int):
            raise TypeError("observation_limit must be an integer")
        if not 1 <= observation_limit <= 4096:
            raise ValueError("observation_limit must be between 1 and 4096")

        plan = plan_notify(state, request)
        if plan.disposition is NotifyDisposition.DEDUPLICATED:
            return self._deduplicated_result()
        frames = plan.synthetic_frames_for_test()
        if not 3 <= len(frames) <= 255:
            raise ValueError("planned notification batch must contain 3 to 255 frames")
        if any(
            len(frame) != 20
            or frame[0] != 0x12
            or frame[1] != len(frames)
            or frame[2] != index
            for index, frame in enumerate(frames, start=1)
        ):
            raise ValueError("planned notification frame sequence is not closed")

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

    def _deduplicated_result(self) -> NotifyBatchSimulationResult:
        return NotifyBatchSimulationResult(
            disposition=NotifyDisposition.DEDUPLICATED,
            reason=NotifyBatchSimulationReason.DEDUPLICATED,
            completeness=NotifyBatchCompleteness.NOT_DISPATCHED,
            write_invoked=False,
            all_planned_fake_write_calls_returned=True,
            all_invoked_fake_write_calls_returned=True,
            transport_call_uncertain=False,
            marker_matched_callback_observed=False,
            multiple_distinct_marker_callbacks_observed=False,
            duplicate_marker_callback_observed=False,
            unmarked_failure_callback_observed=False,
            multiple_unmarked_failure_callbacks_observed=False,
            unmatched_marker_callback_observed=False,
            future_writes_stopped_after_failure=False,
            unrelated_notification_observed=False,
            cleanup_succeeded=True,
            tainted=False,
            scripted_transport_contains_private_test_frames=bool(
                self._transport.response_write_calls
            ),
        )

    async def _simulate(
        self,
        frames: tuple[bytes, ...],
        *,
        quiet: float,
        overall: float,
        stage: float,
        cleanup: float,
        observation_limit: int,
    ) -> NotifyBatchSimulationResult:
        queue: asyncio.Queue[tuple[bytes, bool]] = asyncio.Queue(maxsize=256)
        accepting = True
        batch_active = False
        overflowed = False
        subscribed = False
        write_invoked = False
        invoked_write_calls = 0
        returned_write_calls = 0
        observations = 0
        invoked_markers: set[int] = set()
        observed_markers: set[int] = set()
        marker_matched = False
        multiple_distinct = False
        duplicate_marker = False
        failure_observed = False
        multiple_failures = False
        unmatched_marker = False
        failure_stopped_future_writes = False
        unrelated_observed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        reason = NotifyBatchSimulationReason.LOCAL_QUIET
        completeness = NotifyBatchCompleteness.UNKNOWN
        phase = "connect"
        loop = asyncio.get_running_loop()
        overall_deadline = loop.time() + overall

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not accepting or not batch_active:
                return
            bounded = bytes(data) if len(data) <= 20 else bytes(data[:21])
            marker_owned_at_arrival = (
                len(bounded) >= 3
                and bounded[0] == 0x12
                and bounded[2] in invoked_markers
            )
            try:
                queue.put_nowait((bounded, marker_owned_at_arrival))
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
                invoked_markers.add(frame[2])
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

        def process_notification(data: bytes, marker_owned_at_arrival: bool) -> bool:
            nonlocal duplicate_marker, failure_observed, marker_matched
            nonlocal multiple_distinct, observations, unrelated_observed
            nonlocal multiple_failures, unmatched_marker
            observations += 1
            if not data or data[0] not in {0x12, 0x92}:
                unrelated_observed = True
                if observations >= observation_limit and not failure_observed:
                    raise _ObservationLimitError
                return False
            if len(data) != 20:
                raise _MalformedMatchingCallbackError
            if data[0] == 0x92:
                try:
                    parsed = parse_vendor_notify_ack(data, expected_marker=0)
                except ProtocolError:
                    raise _MalformedMatchingCallbackError from None
                if parsed.success:
                    raise _MalformedMatchingCallbackError
                multiple_failures = failure_observed
                failure_observed = True
                return True
            marker = data[2]
            if not marker_owned_at_arrival:
                unmatched_marker = True
                if observations >= observation_limit and not failure_observed:
                    raise _ObservationLimitError
                return False
            try:
                parsed = parse_vendor_notify_ack(data, expected_marker=marker)
            except ProtocolError:
                raise _MalformedMatchingCallbackError from None
            if not parsed.success:
                raise _MalformedMatchingCallbackError
            marker_matched = True
            if marker in observed_markers:
                duplicate_marker = True
            else:
                observed_markers.add(marker)
                multiple_distinct = len(observed_markers) > 1
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
                    data, marker_owned_at_arrival = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                matching_observed = (
                    process_notification(data, marker_owned_at_arrival)
                    or matching_observed
                )
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
                reason = NotifyBatchSimulationReason.PREFLIGHT_FAILURE
                completeness = NotifyBatchCompleteness.ABORTED
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
                    reason = NotifyBatchSimulationReason.UNMARKED_FAILURE_OBSERVED
                    completeness = NotifyBatchCompleteness.UNKNOWN
                    self._tainted = True
                elif returned_write_calls == len(frames):
                    quiet_deadline = loop.time() + quiet
                    while True:
                        matching = process_pending()
                        if failure_observed:
                            reason = (
                                NotifyBatchSimulationReason.UNMARKED_FAILURE_OBSERVED
                            )
                            completeness = NotifyBatchCompleteness.UNKNOWN
                            self._tainted = True
                            break
                        if matching:
                            quiet_deadline = loop.time() + quiet
                        now = loop.time()
                        remaining = min(quiet_deadline, overall_deadline) - now
                        if remaining <= 0:
                            if now >= overall_deadline:
                                reason = NotifyBatchSimulationReason.OVERALL_TIMEOUT
                            else:
                                reason = NotifyBatchSimulationReason.LOCAL_QUIET
                            completeness = NotifyBatchCompleteness.UNKNOWN
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
                            data, marker_owned_at_arrival = data_task.result()
                            matching = process_notification(
                                data, marker_owned_at_arrival
                            )
                            if matching:
                                quiet_deadline = loop.time() + quiet
                        if self._transport.disconnect_event.is_set():
                            raise _DisconnectedError
        except _MalformedMatchingCallbackError:
            reason = NotifyBatchSimulationReason.MALFORMED_MATCHING_CALLBACK
            completeness = (
                NotifyBatchCompleteness.UNCERTAIN
                if write_invoked else NotifyBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _QueueOverflowError:
            reason = NotifyBatchSimulationReason.QUEUE_OVERFLOW
            completeness = (
                NotifyBatchCompleteness.UNCERTAIN
                if write_invoked else NotifyBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _ObservationLimitError:
            reason = NotifyBatchSimulationReason.OBSERVATION_LIMIT
            completeness = (
                NotifyBatchCompleteness.UNKNOWN
                if returned_write_calls == len(frames)
                else NotifyBatchCompleteness.ABORTED
            )
            self._tainted = returned_write_calls != len(frames)
        except _DisconnectedError:
            classify_pending_after_primary_failure()
            reason = NotifyBatchSimulationReason.DISCONNECTED
            completeness = (
                NotifyBatchCompleteness.UNCERTAIN
                if write_invoked else NotifyBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _OverallTimeoutError:
            classify_pending_after_primary_failure()
            reason = NotifyBatchSimulationReason.OVERALL_TIMEOUT
            if invoked_write_calls > returned_write_calls:
                completeness = NotifyBatchCompleteness.UNCERTAIN
                self._tainted = True
            elif returned_write_calls == len(frames):
                completeness = NotifyBatchCompleteness.UNKNOWN
            else:
                completeness = NotifyBatchCompleteness.ABORTED
                if write_invoked:
                    self._tainted = True
        except _StageTimeoutError:
            reason = NotifyBatchSimulationReason.STAGE_TIMEOUT
            completeness = (
                NotifyBatchCompleteness.UNCERTAIN
                if write_invoked else NotifyBatchCompleteness.ABORTED
            )
            if write_invoked:
                self._tainted = True
        except _WriteTimeoutError:
            classify_pending_after_primary_failure()
            reason = NotifyBatchSimulationReason.WRITE_TIMEOUT
            completeness = NotifyBatchCompleteness.UNCERTAIN
            self._tainted = True
        except Exception:
            if write_invoked:
                classify_pending_after_primary_failure()
                reason = NotifyBatchSimulationReason.WRITE_FAILURE
            elif phase == "connect":
                reason = NotifyBatchSimulationReason.CONNECT_FAILURE
            elif phase == "subscribe":
                reason = NotifyBatchSimulationReason.SUBSCRIPTION_FAILURE
            else:
                reason = NotifyBatchSimulationReason.PREFLIGHT_FAILURE
            completeness = (
                NotifyBatchCompleteness.UNCERTAIN
                if write_invoked else NotifyBatchCompleteness.ABORTED
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
            reason = NotifyBatchSimulationReason.CLEANUP_FAILURE
            completeness = (
                NotifyBatchCompleteness.UNCERTAIN
                if write_invoked else NotifyBatchCompleteness.ABORTED
            )
        all_returned = returned_write_calls == len(frames)
        transport_uncertain = invoked_write_calls > returned_write_calls
        if transport_uncertain:
            completeness = NotifyBatchCompleteness.UNCERTAIN
            self._tainted = True
        return NotifyBatchSimulationResult(
            disposition=NotifyDisposition.PLANNED,
            reason=reason,
            completeness=completeness,
            write_invoked=write_invoked,
            all_planned_fake_write_calls_returned=all_returned,
            all_invoked_fake_write_calls_returned=(
                invoked_write_calls == returned_write_calls
            ),
            transport_call_uncertain=transport_uncertain,
            marker_matched_callback_observed=marker_matched,
            multiple_distinct_marker_callbacks_observed=multiple_distinct,
            duplicate_marker_callback_observed=duplicate_marker,
            unmarked_failure_callback_observed=failure_observed,
            multiple_unmarked_failure_callbacks_observed=multiple_failures,
            unmatched_marker_callback_observed=unmatched_marker,
            future_writes_stopped_after_failure=failure_stopped_future_writes,
            unrelated_notification_observed=unrelated_observed,
            cleanup_succeeded=cleanup_succeeded,
            tainted=self._tainted,
            scripted_transport_contains_private_test_frames=bool(
                self._transport.response_write_calls
            ),
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
    "FakeVendorNotifyBatchSimulator",
    "NotifyBatchCompleteness",
    "NotifyBatchSimulationReason",
    "NotifyBatchSimulationResult",
    "NotifyBatchSimulationTaintedError",
]
