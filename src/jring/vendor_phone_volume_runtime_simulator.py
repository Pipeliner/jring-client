"""Fake-only reconstruction of the vendor phone-volume reverse pipeline.

The recovered app receives one MAIN ``0x49`` request and projects host volume state
back over the MAIN request characteristic.  This simulator composes those two closed
codecs against the exact scripted transport only.  It never reads host audio state,
opens Bluetooth hardware, retries a write, or treats ATT completion as an app ack.
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
from .vendor_main_commands import PhoneVolumeRequest
from .vendor_protocol import parse_vendor_phone_volume_request
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class PhoneVolumeProjectionReason(str, Enum):
    FAKE_WRITE_CALL_RETURNED = "fake_write_call_returned"
    LOCAL_QUIET = "local_quiet"
    PREFLIGHT_FAILURE = "preflight_failure"
    MALFORMED_REQUEST = "malformed_request"
    QUEUE_OVERFLOW = "queue_overflow"
    STAGE_TIMEOUT = "stage_timeout"
    WRITE_TIMEOUT = "write_timeout"
    WRITE_FAILURE = "write_failure"
    OVERALL_TIMEOUT = "overall_timeout"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class PhoneVolumeProjectionCompleteness(str, Enum):
    UNKNOWN = "unknown"
    ABORTED = "aborted"
    UNCERTAIN = "uncertain"


class PhoneVolumeSimulationTaintedError(RuntimeError):
    """An earlier attempt left dispatch or cleanup state uncertain."""


@dataclass(frozen=True, repr=False)
class PhoneVolumeProjectionResult:
    reason: PhoneVolumeProjectionReason
    completeness: PhoneVolumeProjectionCompleteness
    request_observed: bool
    unrelated_frame_count: int
    write_invoked: bool
    fake_write_call_completed: bool
    transport_call_uncertain: bool
    cleanup_succeeded: bool
    tainted: bool
    protocol_delivery: str = field(default="unknown", init=False)
    application_acknowledgement_observed: bool = field(default=False, init=False)
    protocol_terminal_observed: bool = field(default=False, init=False)
    quiet_means_success: bool = field(default=False, init=False)
    simulation_only: bool = field(default=True, init=False)
    live_available: bool = field(default=False, init=False)
    owner_authorized: bool = field(default=False, init=False)
    hardware_eligible: bool = field(default=False, init=False)
    hardware_verified: bool = field(default=False, init=False)
    host_state_source: str = field(
        default="caller_supplied_offline_values", init=False
    )
    host_audio_accessed: bool = field(default=False, init=False)
    host_audio_modified: bool = field(default=False, init=False)
    input_eligible: bool = field(default=False, init=False)

    def __repr__(self) -> str:
        return (
            "PhoneVolumeProjectionResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"request_observed={self.request_observed!r}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"write_invoked={self.write_invoked!r}, "
            f"fake_write_call_completed={self.fake_write_call_completed!r}, "
            f"transport_call_uncertain={self.transport_call_uncertain!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            f"tainted={self.tainted!r}, "
            "protocol_delivery='unknown', "
            "application_acknowledgement_observed=False, "
            "protocol_terminal_observed=False, "
            "quiet_means_success=False, simulation_only=True, "
            "hardware_eligible=False, hardware_verified=False, "
            "host_audio_accessed=False, host_audio_modified=False, "
            "host_state_source='caller_supplied_offline_values', live_available=False, "
            "owner_authorized=False, input_eligible=False)"
        )


class _StageTimeoutError(TimeoutError):
    pass


class _OverallTimeoutError(TimeoutError):
    pass


class _DisconnectedError(ConnectionError):
    pass


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return result


class FakeVendorPhoneVolumeSimulator:
    """Project caller-supplied offline values after one exact fake MAIN request."""

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
            "FakeVendorPhoneVolumeSimulator(simulation_only=True, "
            "hardware_eligible=False, input_eligible=False, "
            f"host_audio_accessed=False, tainted={self._tainted!r})"
        )

    async def project_once(
        self,
        projection: PhoneVolumeRequest,
        *,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
        cleanup_timeout: float = 0.05,
    ) -> PhoneVolumeProjectionResult:
        if type(projection) is not PhoneVolumeRequest:
            raise TypeError("projection must be a PhoneVolumeRequest")
        if self._tainted:
            raise PhoneVolumeSimulationTaintedError(
                "simulator is tainted by an uncertain attempt; create a new simulator"
            )
        if self._running:
            raise RuntimeError("phone-volume projection is already in progress")
        lease_owner = object()
        if not self._transport.acquire_simulation_lease(lease_owner):
            raise RuntimeError("scripted fake transport is already connected or in use")
        self._running = True
        try:
            return await self._project_once(
                projection,
                quiet_timeout=quiet_timeout,
                overall_timeout=overall_timeout,
                stage_timeout=stage_timeout,
                cleanup_timeout=cleanup_timeout,
            )
        finally:
            self._running = False
            self._transport.release_simulation_lease(lease_owner)

    async def _project_once(
        self,
        projection: PhoneVolumeRequest,
        *,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
        cleanup_timeout: float,
    ) -> PhoneVolumeProjectionResult:
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")
        cleanup = _positive_number(cleanup_timeout, "cleanup_timeout")

        frame = projection.frames()[0].synthetic_bytes_for_test()
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        overflowed = False
        accepting = True
        subscribed = False
        request_observed = False
        unrelated = 0
        write_invoked = False
        fake_write_call_completed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        reason = PhoneVolumeProjectionReason.LOCAL_QUIET
        completeness = PhoneVolumeProjectionCompleteness.UNKNOWN
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

        async def write_call() -> None:
            nonlocal write_invoked
            remaining = overall_deadline - loop.time()
            if remaining <= 0:
                raise _OverallTimeoutError
            overall_is_limit = remaining <= stage

            async def invoke_write() -> None:
                nonlocal write_invoked
                write_invoked = True
                await self._transport.write_target_with_response(request_target, frame)

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
            if disconnect_task in done and disconnect_task.result():
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise _DisconnectedError
            if task in done:
                task.result()
                return
            task.cancel()
            disconnect_task.cancel()
            await asyncio.gather(task, disconnect_task, return_exceptions=True)
            if overall_is_limit:
                raise _OverallTimeoutError
            raise _StageTimeoutError

        try:
            await stage_call(self._transport.connect)
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
                reason = PhoneVolumeProjectionReason.PREFLIGHT_FAILURE
                completeness = PhoneVolumeProjectionCompleteness.ABORTED
            else:
                subscribed = True
                await stage_call(
                    lambda: self._transport.subscribe_target(response_target, receive)
                )
                quiet_deadline = loop.time() + quiet
                while True:
                    if overflowed:
                        reason = PhoneVolumeProjectionReason.QUEUE_OVERFLOW
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    now = loop.time()
                    remaining = min(quiet_deadline, overall_deadline) - now
                    if remaining <= 0:
                        if now >= overall_deadline:
                            reason = PhoneVolumeProjectionReason.OVERALL_TIMEOUT
                            completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        else:
                            reason = PhoneVolumeProjectionReason.LOCAL_QUIET
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
                        reason = PhoneVolumeProjectionReason.QUEUE_OVERFLOW
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    if disconnect_task in done and disconnect_task.result():
                        reason = PhoneVolumeProjectionReason.DISCONNECTED
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    data = data_task.result()
                    if not data or data[0] != 0x49:
                        unrelated += 1
                        continue
                    if len(data) != 20:
                        reason = PhoneVolumeProjectionReason.MALFORMED_REQUEST
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    try:
                        parse_vendor_phone_volume_request(data)
                    except ProtocolError:
                        reason = PhoneVolumeProjectionReason.MALFORMED_REQUEST
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    request_observed = True
                    accepting = False
                    if (
                        not self._transport.owns_target(request_target)
                        or not self._transport.owns_target(response_target)
                    ):
                        reason = PhoneVolumeProjectionReason.DISCONNECTED
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    try:
                        await write_call()
                    except _DisconnectedError:
                        reason = PhoneVolumeProjectionReason.DISCONNECTED
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    except _StageTimeoutError:
                        reason = (
                            PhoneVolumeProjectionReason.DISCONNECTED
                            if self._transport.disconnect_event.is_set()
                            else PhoneVolumeProjectionReason.WRITE_TIMEOUT
                        )
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    except _OverallTimeoutError:
                        reason = PhoneVolumeProjectionReason.OVERALL_TIMEOUT
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    except Exception:
                        reason = (
                            PhoneVolumeProjectionReason.DISCONNECTED
                            if self._transport.disconnect_event.is_set()
                            else PhoneVolumeProjectionReason.WRITE_FAILURE
                        )
                        completeness = PhoneVolumeProjectionCompleteness.ABORTED
                        break
                    fake_write_call_completed = True
                    reason = PhoneVolumeProjectionReason.FAKE_WRITE_CALL_RETURNED
                    break
        except _OverallTimeoutError:
            reason = PhoneVolumeProjectionReason.OVERALL_TIMEOUT
            completeness = PhoneVolumeProjectionCompleteness.ABORTED
        except _StageTimeoutError:
            reason = PhoneVolumeProjectionReason.STAGE_TIMEOUT
            completeness = PhoneVolumeProjectionCompleteness.ABORTED
        except Exception:
            reason = PhoneVolumeProjectionReason.PREFLIGHT_FAILURE
            completeness = PhoneVolumeProjectionCompleteness.ABORTED
        except BaseException:
            if write_invoked:
                self._tainted = True
            raise
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
                self._tainted = True

        if not cleanup_succeeded:
            reason = PhoneVolumeProjectionReason.CLEANUP_FAILURE
            completeness = (
                PhoneVolumeProjectionCompleteness.UNCERTAIN
                if write_invoked
                else PhoneVolumeProjectionCompleteness.ABORTED
            )
        elif write_invoked and not fake_write_call_completed:
            completeness = PhoneVolumeProjectionCompleteness.UNCERTAIN
            self._tainted = True
        return PhoneVolumeProjectionResult(
            reason=reason,
            completeness=completeness,
            request_observed=request_observed,
            unrelated_frame_count=unrelated,
            write_invoked=write_invoked,
            fake_write_call_completed=fake_write_call_completed,
            transport_call_uncertain=write_invoked and not fake_write_call_completed,
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
    "FakeVendorPhoneVolumeSimulator",
    "PhoneVolumeProjectionCompleteness",
    "PhoneVolumeProjectionReason",
    "PhoneVolumeProjectionResult",
    "PhoneVolumeSimulationTaintedError",
]
