"""Closed fake-only collector for the recovered ECG history callback stream.

The APK proves one descriptor frame followed by event and packed-sample callbacks,
but it does not prove that any event value terminates the history.  This simulator
therefore reports local bounds as unknown and never reports success or failure.
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
from .vendor_main_commands import EcgHistoryRequest
from .vendor_protocol import (
    VendorEcgHistoryInfo,
    VendorEcgStartEnd,
    VendorEcgValues,
    parse_vendor_ecg_history_info,
    parse_vendor_ecg_start_end,
    parse_vendor_ecg_values,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class EcgHistorySimulationReason(str, Enum):
    LOCAL_QUIET = "local_quiet"
    LIMIT_REACHED = "limit_reached"
    OVERALL_TIMEOUT = "overall_timeout"
    PREFLIGHT_FAILURE = "preflight_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_FRAME = "malformed_frame"
    ORDERING_VIOLATION = "ordering_violation"
    QUEUE_OVERFLOW = "queue_overflow"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class EcgHistoryCollectionCompleteness(str, Enum):
    UNKNOWN = "unknown"
    ABORTED = "aborted"


Projection = tuple[str, int, str]
ParsedEcgFrame = VendorEcgHistoryInfo | VendorEcgStartEnd | VendorEcgValues
_MAX_FRAME_LIMIT = 4_096


@dataclass(frozen=True, repr=False)
class EcgHistorySimulationResult:
    reason: EcgHistorySimulationReason
    completeness: EcgHistoryCollectionCompleteness
    accepted_frame_count: int
    sample_count: int
    unrelated_frame_count: int
    projections: tuple[Projection, ...]
    metadata_received: bool
    command_written: bool
    cleanup_succeeded: bool
    delivery_uncertain: bool
    _parsed_frames: tuple[ParsedEcgFrame, ...] = field(repr=False)

    @property
    def wire_terminal_observed(self) -> bool:
        return False

    @property
    def quiet_means_success(self) -> bool:
        return False

    @property
    def partial_data_requires_discard(self) -> bool:
        return (
            self.completeness is EcgHistoryCollectionCompleteness.ABORTED
            and self.accepted_frame_count > 0
        )

    @property
    def user_guidance(self) -> str:
        if self.partial_data_requires_discard:
            return "Discard partial synthetic ECG history; collection aborted."
        if self.completeness is EcgHistoryCollectionCompleteness.ABORTED:
            return "No complete synthetic ECG history is available; collection aborted."
        return "Synthetic ECG history is incomplete; no terminal was observed."

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    def parsed_frames_for_test(self) -> tuple[ParsedEcgFrame, ...]:
        """Return synthetic parsed values to focused tests only."""

        return tuple(self._parsed_frames)

    def __repr__(self) -> str:
        return (
            "EcgHistorySimulationResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"accepted_frame_count={self.accepted_frame_count}, "
            f"sample_count={self.sample_count}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"projections={self.projections!r}, "
            f"metadata_received={self.metadata_received!r}, "
            f"command_written={self.command_written!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            f"delivery_uncertain={self.delivery_uncertain!r}, "
            f"partial_data_requires_discard={self.partial_data_requires_discard!r}, "
            "user_guidance=<redacted>, parsed_frames=<redacted>, "
            "wire_terminal_observed=False, "
            "quiet_means_success=False, simulation_only=True, "
            "hardware_eligible=False, hardware_verified=False)"
        )


def _positive_number(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0:
        raise ValueError(f"{label} must be finite and positive")
    return converted


class FakeVendorEcgHistorySimulator:
    """Collect one exact ECG-history request on the scripted fake main route."""

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
        request: EcgHistoryRequest,
        frame_limit: int = 64,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
    ) -> EcgHistorySimulationResult:
        if self._collecting:
            raise RuntimeError("ECG history collection is already in progress")
        lease_owner = object()
        if not self._transport.acquire_simulation_lease(lease_owner):
            raise RuntimeError("scripted fake transport is already connected or in use")
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
            self._transport.release_simulation_lease(lease_owner)

    async def _collect(
        self,
        *,
        request: EcgHistoryRequest,
        frame_limit: int,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
    ) -> EcgHistorySimulationResult:
        if type(request) is not EcgHistoryRequest:
            raise TypeError("request must be the exact EcgHistoryRequest type")
        if isinstance(frame_limit, bool) or not isinstance(frame_limit, int):
            raise TypeError("frame_limit must be an integer")
        if frame_limit <= 0:
            raise ValueError("frame_limit must be positive")
        if frame_limit > _MAX_FRAME_LIMIT:
            raise ValueError(f"frame_limit must be at most {_MAX_FRAME_LIMIT}")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")

        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=frame_limit + 1)
        parsed: list[ParsedEcgFrame] = []
        projections: list[Projection] = []
        accepted = 0
        sample_count = 0
        unrelated = 0
        metadata_received = False
        overflowed = False
        receiving = True
        subscribed = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        write_issued = False
        command_written = False
        reason = EcgHistorySimulationReason.LOCAL_QUIET
        completeness = EcgHistoryCollectionCompleteness.UNKNOWN

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not receiving:
                return
            bounded = bytes(data) if len(data) == 20 else bytes(data[:1])
            try:
                queue.put_nowait(bounded)
            except asyncio.QueueFull:
                overflowed = True

        try:
            await asyncio.wait_for(self._transport.connect(), timeout=stage)
            preflight = await asyncio.wait_for(self._preflight(), timeout=stage)
            if not preflight.structurally_ready:
                reason = EcgHistorySimulationReason.PREFLIGHT_FAILURE
                completeness = EcgHistoryCollectionCompleteness.ABORTED
            else:
                request_target = preflight.request_target
                response_target = preflight.response_target
                if (
                    request_target is None
                    or response_target is None
                    or not self._transport.owns_target(request_target)
                    or not self._transport.owns_target(response_target)
                ):
                    reason = EcgHistorySimulationReason.PREFLIGHT_FAILURE
                    completeness = EcgHistoryCollectionCompleteness.ABORTED
                    raise LookupError("resolved GATT target is no longer owned")
                await asyncio.wait_for(
                    self._transport.subscribe_target(response_target, receive),
                    timeout=stage,
                )
                subscribed = True
                write_issued = True
                await asyncio.wait_for(
                    self._transport.write_target_with_response(
                        request_target,
                        request.frames()[0].synthetic_bytes_for_test(),
                    ),
                    timeout=stage,
                )
                command_written = True
                loop = asyncio.get_running_loop()
                quiet_deadline = loop.time() + quiet
                overall_deadline = loop.time() + overall

                while accepted < frame_limit:
                    if overflowed:
                        reason = EcgHistorySimulationReason.QUEUE_OVERFLOW
                        completeness = EcgHistoryCollectionCompleteness.ABORTED
                        break
                    now = loop.time()
                    remaining = min(quiet_deadline, overall_deadline) - now
                    if remaining <= 0:
                        if now >= overall_deadline:
                            reason = EcgHistorySimulationReason.OVERALL_TIMEOUT
                            completeness = EcgHistoryCollectionCompleteness.ABORTED
                        else:
                            reason = EcgHistorySimulationReason.LOCAL_QUIET
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
                        reason = EcgHistorySimulationReason.DISCONNECTED
                        completeness = EcgHistoryCollectionCompleteness.ABORTED
                        break

                    data = data_task.result()
                    classification = self._classify(data)
                    if classification == "unrelated":
                        unrelated += 1
                        continue
                    if classification == "malformed":
                        reason = EcgHistorySimulationReason.MALFORMED_FRAME
                        completeness = EcgHistoryCollectionCompleteness.ABORTED
                        break

                    opcode = data[0]
                    if opcode == 0x2C and metadata_received:
                        reason = EcgHistorySimulationReason.ORDERING_VIOLATION
                        completeness = EcgHistoryCollectionCompleteness.ABORTED
                        break
                    if opcode != 0x2C and not metadata_received:
                        reason = EcgHistorySimulationReason.ORDERING_VIOLATION
                        completeness = EcgHistoryCollectionCompleteness.ABORTED
                        break

                    try:
                        if opcode == 0x2C:
                            value = parse_vendor_ecg_history_info(data)
                            projection = ("onGetEcgHistory", 1, "wire_frame")
                            metadata_received = True
                        elif opcode == 0x2D:
                            value = parse_vendor_ecg_start_end(data)
                            projection = ("onGetEcgStartEnd", 1, "wire_frame")
                        else:
                            value = parse_vendor_ecg_values(data, kind="history")
                            sample_count += len(value.values)
                            projection = (
                                "onGetEcgHistoryData",
                                1,
                                "wire_frame",
                            )
                    except ProtocolError:
                        reason = EcgHistorySimulationReason.MALFORMED_FRAME
                        completeness = EcgHistoryCollectionCompleteness.ABORTED
                        break

                    parsed.append(value)
                    projections.append(projection)
                    accepted += 1
                    quiet_deadline = loop.time() + quiet
                else:
                    reason = EcgHistorySimulationReason.LIMIT_REACHED
        except Exception:
            reason = (
                EcgHistorySimulationReason.WRITE_FAILURE
                if write_issued
                else EcgHistorySimulationReason.PREFLIGHT_FAILURE
            )
            completeness = EcgHistoryCollectionCompleteness.ABORTED
        finally:
            receiving = False
            while True:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            cleanup_succeeded = await self._cleanup(
                subscribed, response_target, timeout=stage
            )

        if not cleanup_succeeded:
            reason = EcgHistorySimulationReason.CLEANUP_FAILURE
            completeness = EcgHistoryCollectionCompleteness.ABORTED

        return EcgHistorySimulationResult(
            reason=reason,
            completeness=completeness,
            accepted_frame_count=accepted,
            sample_count=sample_count,
            unrelated_frame_count=unrelated,
            projections=tuple(projections),
            metadata_received=metadata_received,
            command_written=command_written,
            cleanup_succeeded=cleanup_succeeded,
            delivery_uncertain=(
                write_issued and not command_written
            ),
            _parsed_frames=tuple(parsed),
        )

    @staticmethod
    def _classify(data: bytes) -> str:
        if not data or data[0] not in {0x2C, 0x2D, 0x2E}:
            return "unrelated"
        return "accepted" if len(data) == 20 else "malformed"

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
    "EcgHistoryCollectionCompleteness",
    "EcgHistorySimulationReason",
    "EcgHistorySimulationResult",
    "FakeVendorEcgHistorySimulator",
]
