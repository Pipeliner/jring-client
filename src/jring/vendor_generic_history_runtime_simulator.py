"""Closed fake-only runtime for the generic ``getDataByDay`` history family.

The collector reproduces proven callback multiplicity while keeping local quiet and
caller limits distinct from device-confirmed completion.  It accepts neither a live
transport nor arbitrary bytes/UUIDs and retains no raw notification frames.
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
from .vendor_history import (
    HistoryCloseReason,
    HistoryCompleteness,
    HistoryStreamKind,
    VendorHistoryStream,
    VendorHistoryUpdate,
)
from .vendor_main_commands import DayDataKind, DayDataRequest
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class GenericHistorySimulationReason(str, Enum):
    WIRE_TERMINAL = "wire_terminal"
    DEVICE_METADATA = "device_metadata"
    DEVICE_FAILURE = "device_failure"
    LOCAL_QUIET = "local_quiet"
    LIMIT_REACHED = "limit_reached"
    OVERALL_TIMEOUT = "overall_timeout"
    PREFLIGHT_FAILURE = "preflight_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_FRAME = "malformed_frame"
    QUEUE_OVERFLOW = "queue_overflow"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


Projection = tuple[str, int, str]


@dataclass(frozen=True, repr=False)
class GenericHistorySimulationResult:
    request_kind: DayDataKind
    reason: GenericHistorySimulationReason
    completeness: HistoryCompleteness
    accepted_frame_count: int
    sample_count: int
    unrelated_frame_count: int
    projections: tuple[Projection, ...]
    command_written: bool
    cleanup_succeeded: bool
    local_end_projected: bool
    delivery_uncertain: bool
    _parsed_updates: tuple[VendorHistoryUpdate, ...] = field(repr=False)
    _local_end_arguments: tuple[int, int] | None = field(repr=False)

    @property
    def wire_terminal_observed(self) -> bool:
        return self.reason is GenericHistorySimulationReason.WIRE_TERMINAL

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
    def partial_data(self) -> bool:
        return (
            self.completeness is HistoryCompleteness.ABORTED
            and self.sample_count > 0
        )

    @property
    def user_guidance(self) -> str:
        prefix = "Synthetic history only; no real device was contacted. "
        if self.completeness is HistoryCompleteness.CONFIRMED:
            return prefix + "The fake reproduced explicit device completion evidence."
        if self.completeness is HistoryCompleteness.FAILED:
            return prefix + "The fake reproduced a device failure callback."
        if self.completeness is HistoryCompleteness.ABORTED:
            detail = (
                " Parsed values are partial and must not be treated as history."
                if self.partial_data
                else ""
            )
            return prefix + "Collection aborted without a completion claim." + detail
        return prefix + "Collection stopped locally; returned history may be incomplete."

    def parsed_updates_for_test(self) -> tuple[VendorHistoryUpdate, ...]:
        return tuple(self._parsed_updates)

    def local_end_arguments_for_explicit_test_use(self) -> tuple[int, int] | None:
        """Return source callback arguments only for defensive local parity tests."""

        return self._local_end_arguments

    def __repr__(self) -> str:
        return (
            "GenericHistorySimulationResult("
            f"request_kind={self.request_kind.name!r}, reason={self.reason.value!r}, "
            f"completeness={self.completeness.value!r}, "
            f"accepted_frame_count={self.accepted_frame_count}, "
            f"sample_count={self.sample_count}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"projections={self.projections!r}, command_written={self.command_written!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            f"local_end_projected={self.local_end_projected!r}, "
            f"delivery_uncertain={self.delivery_uncertain!r}, "
            f"partial_data={self.partial_data!r}, "
            "parsed_updates=<redacted>, quiet_means_success=False, "
            "simulation_only=True, hardware_eligible=False, hardware_verified=False)"
        )


_STREAM_KINDS = {
    DayDataKind.SDK_TYPE_1: HistoryStreamKind.DAILY,
    DayDataKind.SDK_TYPE_2: HistoryStreamKind.DETAIL,
    DayDataKind.SDK_TYPE_12: HistoryStreamKind.TEMPERATURE,
    DayDataKind.SDK_TYPE_13: HistoryStreamKind.OXYGEN,
}
_SUCCESS_OPCODES = {
    DayDataKind.SDK_TYPE_1: frozenset({0x10, 0x11}),
    DayDataKind.SDK_TYPE_2: frozenset({0x16}),
    DayDataKind.SDK_TYPE_12: frozenset({0x39}),
    DayDataKind.SDK_TYPE_13: frozenset({0x40}),
}
_FAILURE_OPCODES = {
    DayDataKind.SDK_TYPE_1: frozenset({0x90}),
    DayDataKind.SDK_TYPE_2: frozenset({0x96}),
    DayDataKind.SDK_TYPE_12: frozenset({0xB9}),
    DayDataKind.SDK_TYPE_13: frozenset(),
}


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return converted


class FakeVendorGenericHistorySimulator:
    """Collect one exact generic history request on the scripted fake route."""

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
        request: DayDataRequest,
        frame_limit: int = 64,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
    ) -> GenericHistorySimulationResult:
        if self._collecting:
            raise RuntimeError("generic history collection is already in progress")
        self._collecting = True
        try:
            return await self._collect(
                request=request,
                frame_limit=frame_limit,
                quiet_timeout=quiet_timeout,
                overall_timeout=overall_timeout,
                stage_timeout=stage_timeout,
            )
        finally:
            self._collecting = False

    async def _collect(
        self,
        *,
        request: DayDataRequest,
        frame_limit: int,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
    ) -> GenericHistorySimulationResult:
        if type(request) is not DayDataRequest:
            raise TypeError("request must be the exact DayDataRequest type")
        if isinstance(frame_limit, bool) or not isinstance(frame_limit, int):
            raise TypeError("frame_limit must be an integer")
        if frame_limit <= 0:
            raise ValueError("frame_limit must be positive")
        if frame_limit > 4_096:
            raise ValueError("frame_limit cannot exceed 4096")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")

        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=frame_limit + 1)
        updates: list[VendorHistoryUpdate] = []
        projections: list[Projection] = []
        accepted = 0
        sample_count = 0
        unrelated = 0
        write_issued = False
        command_written = False
        subscribed = False
        local_end_projected = False
        reason = GenericHistorySimulationReason.LOCAL_QUIET
        completeness = HistoryCompleteness.UNKNOWN
        loop = asyncio.get_running_loop()
        overflowed = False
        accepting = True

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not accepting:
                return
            bounded = data if len(data) <= 20 else data[:21]
            try:
                queue.put_nowait(bytes(bounded))
            except asyncio.QueueFull:
                # A bounded fake runtime aborts after observing overflow.  It never
                # discards an older frame and calls the resulting sequence complete.
                overflowed = True

        try:
            await asyncio.wait_for(self._transport.connect(), timeout=stage)
            if not await asyncio.wait_for(self._preflight(), timeout=stage):
                reason = GenericHistorySimulationReason.PREFLIGHT_FAILURE
                completeness = HistoryCompleteness.ABORTED
            else:
                await asyncio.wait_for(
                    self._transport.subscribe(VENDOR_CHARACTERISTIC_33F4, receive),
                    timeout=stage,
                )
                subscribed = True
                frame = request.frames()[0]
                write_issued = True
                await asyncio.wait_for(
                    self._transport.write_with_response(
                        VENDOR_CHARACTERISTIC_33F3,
                        frame.synthetic_bytes_for_test(),
                    ),
                    timeout=stage,
                )
                command_written = True
                stream = VendorHistoryStream(
                    _STREAM_KINDS[request.kind],
                    started_at=loop.time(),
                    first_frame_timeout=overall,
                    idle_timeout=quiet,
                    overall_timeout=overall,
                )
                quiet_deadline = loop.time() + quiet
                overall_deadline = loop.time() + overall

                while accepted < frame_limit:
                    if overflowed:
                        reason = GenericHistorySimulationReason.QUEUE_OVERFLOW
                        completeness = HistoryCompleteness.ABORTED
                        break
                    now = loop.time()
                    remaining = min(quiet_deadline, overall_deadline) - now
                    if remaining <= 0:
                        if now >= overall_deadline:
                            reason = GenericHistorySimulationReason.OVERALL_TIMEOUT
                            completeness = HistoryCompleteness.ABORTED
                        else:
                            reason = GenericHistorySimulationReason.LOCAL_QUIET
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
                    if disconnect_task in done and disconnect_task.result():
                        if not data_task.done():
                            data_task.cancel()
                        reason = GenericHistorySimulationReason.DISCONNECTED
                        completeness = HistoryCompleteness.ABORTED
                        break
                    data = data_task.result()
                    classification = self._classify(request.kind, data)
                    if classification == "unrelated":
                        unrelated += 1
                        continue
                    if classification == "malformed":
                        reason = GenericHistorySimulationReason.MALFORMED_FRAME
                        completeness = HistoryCompleteness.ABORTED
                        break
                    try:
                        update = stream.feed(data, now=loop.time())
                    except ProtocolError:
                        reason = GenericHistorySimulationReason.MALFORMED_FRAME
                        completeness = HistoryCompleteness.ABORTED
                        break
                    updates.append(update)
                    accepted += 1
                    if update.samples:
                        count = len(update.samples)
                        sample_count += count
                        projections.append(("onGetDataByDay", count, "wire_frame"))
                        if request.kind is DayDataKind.SDK_TYPE_13:
                            projections.append(
                                ("onGetOxygenOfflineData", count, "wire_frame")
                            )
                    quiet_deadline = loop.time() + quiet
                    closure = update.closure
                    if closure is None:
                        continue
                    if closure.reason is HistoryCloseReason.WIRE_TERMINAL:
                        reason = GenericHistorySimulationReason.WIRE_TERMINAL
                        origin = "wire_terminal"
                    elif closure.reason is HistoryCloseReason.DEVICE_METADATA:
                        reason = GenericHistorySimulationReason.DEVICE_METADATA
                        origin = "device_metadata"
                    elif closure.reason is HistoryCloseReason.DEVICE_FAILURE:
                        reason = GenericHistorySimulationReason.DEVICE_FAILURE
                        origin = "wire_failure_frame"
                    elif closure.reason in {
                        HistoryCloseReason.FIRST_FRAME_TIMEOUT,
                        HistoryCloseReason.OVERALL_TIMEOUT,
                    }:
                        reason = GenericHistorySimulationReason.OVERALL_TIMEOUT
                        completeness = closure.completeness
                        break
                    elif closure.reason is HistoryCloseReason.IDLE_TIMEOUT:
                        reason = GenericHistorySimulationReason.LOCAL_QUIET
                        completeness = closure.completeness
                        break
                    else:
                        reason = GenericHistorySimulationReason.DISCONNECTED
                        completeness = closure.completeness
                        break
                    completeness = closure.completeness
                    projections.append(("onGetDataByDayEnd", 1, origin))
                    break
                else:
                    reason = GenericHistorySimulationReason.LIMIT_REACHED
        except (ConnectionError, LookupError, OSError, TimeoutError):
            reason = (
                GenericHistorySimulationReason.WRITE_FAILURE
                if subscribed else GenericHistorySimulationReason.PREFLIGHT_FAILURE
            )
            completeness = HistoryCompleteness.ABORTED
        finally:
            accepting = False
            while not queue.empty():
                queue.get_nowait()
            cleanup_succeeded = await self._cleanup(subscribed, timeout=stage)

        if not cleanup_succeeded:
            reason = GenericHistorySimulationReason.CLEANUP_FAILURE
            completeness = HistoryCompleteness.ABORTED
        if (
            cleanup_succeeded
            and reason is GenericHistorySimulationReason.LOCAL_QUIET
            and sample_count
        ):
            projections.append(("onGetDataByDayEnd", 1, "local_quiet_projection"))
            local_end_projected = True
        local_end_arguments = None
        if local_end_projected:
            for update in reversed(updates):
                if update.samples:
                    last = update.samples[-1]
                    local_end_arguments = (
                        last.data_by_day_type,
                        last.device_epoch_seconds,
                    )
                    break

        return GenericHistorySimulationResult(
            request_kind=request.kind,
            reason=reason,
            completeness=completeness,
            accepted_frame_count=accepted,
            sample_count=sample_count,
            unrelated_frame_count=unrelated,
            projections=tuple(projections),
            command_written=command_written,
            cleanup_succeeded=cleanup_succeeded,
            local_end_projected=local_end_projected,
            delivery_uncertain=(
                write_issued and completeness is HistoryCompleteness.ABORTED
            ),
            _parsed_updates=tuple(updates),
            _local_end_arguments=local_end_arguments,
        )

    @staticmethod
    def _classify(kind: DayDataKind, data: bytes) -> str:
        if not data:
            return "unrelated"
        accepted = _SUCCESS_OPCODES[kind] | _FAILURE_OPCODES[kind]
        if data[0] not in accepted:
            return "unrelated"
        return "accepted" if len(data) == 20 else "malformed"

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
            len(tx) == 1
            and len(rx) == 1
            and "write" in tx[0].properties
            and "notify" in rx[0].properties
            and uuid16(0x2902) in rx[0].descriptor_uuids
        )

    async def _cleanup(self, subscribed: bool, *, timeout: float) -> bool:
        succeeded = True
        if subscribed and self._transport.connected:
            try:
                await asyncio.wait_for(
                    self._transport.unsubscribe(VENDOR_CHARACTERISTIC_33F4),
                    timeout=timeout,
                )
            except (ConnectionError, OSError, TimeoutError):
                succeeded = False
        try:
            await asyncio.wait_for(self._transport.close(), timeout=timeout)
        except (OSError, TimeoutError):
            succeeded = False
        return succeeded


__all__ = [
    "FakeVendorGenericHistorySimulator",
    "GenericHistorySimulationReason",
    "GenericHistorySimulationResult",
]
