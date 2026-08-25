"""Closed fake-only runtime for the recovered vendor Wi-Fi scan stream.

The advertised SSID count and completed fragment sequences are useful local
diagnostics, but neither is a proven whole-stream terminal.  This collector
therefore reports unknown, aborted, or transport-uncertain completeness and never
performs host networking, discovery, or a live Bluetooth operation.
"""

from __future__ import annotations

import asyncio
from dataclasses import InitVar, dataclass, field
from enum import Enum
import math

from .protocol import ProtocolError
from .transport import GattCharacteristicTarget
from .vendor_gatt_preflight import (
    VendorGattPreflightResult,
    VendorGattRoute,
    resolve_vendor_gatt_route,
)
from .vendor_main_commands import (
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
)
from .vendor_protocol import (
    VendorWifiSsid,
    VendorWifiSsidAssembler,
    parse_vendor_wifi_ssid_count,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class WifiScanSimulationReason(str, Enum):
    LOCAL_QUIET = "local_quiet"
    LIMIT_REACHED = "limit_reached"
    OVERALL_TIMEOUT = "overall_timeout"
    PREFLIGHT_FAILURE = "preflight_failure"
    WRITE_FAILURE = "write_failure"
    MALFORMED_FRAME = "malformed_frame"
    QUEUE_OVERFLOW = "queue_overflow"
    DISCONNECTED = "disconnected"
    CLEANUP_FAILURE = "cleanup_failure"


class WifiScanCompleteness(str, Enum):
    UNKNOWN = "unknown"
    ABORTED = "aborted"
    UNCERTAIN = "uncertain"


Projection = tuple[str, int, str]


class WifiScanSimulationTaintedError(RuntimeError):
    """An earlier attempt left fake dispatch or cleanup state uncertain."""


class _StageTimeoutError(TimeoutError):
    pass


class _OverallTimeoutError(TimeoutError):
    pass


class _DisconnectedError(ConnectionError):
    pass


@dataclass(frozen=True, repr=False)
class WifiScanSimulationResult:
    reason: WifiScanSimulationReason
    completeness: WifiScanCompleteness
    advertised_count: int | None
    accepted_frame_count: int
    assembled_entry_count: int
    unrelated_frame_count: int
    projections: tuple[Projection, ...]
    write_invoked: bool
    fake_write_call_completed: bool
    cleanup_succeeded: bool
    transport_call_uncertain: bool
    tainted: bool
    _ssids_init: InitVar[tuple[VendorWifiSsid, ...]]
    protocol_delivery: str = field(default="unknown", init=False)
    application_acknowledgement_observed: bool = field(default=False, init=False)
    wire_terminal_observed: bool = field(default=False, init=False)
    quiet_means_success: bool = field(default=False, init=False)
    simulation_only: bool = field(default=True, init=False)
    live_available: bool = field(default=False, init=False)
    owner_authorized: bool = field(default=False, init=False)
    hardware_eligible: bool = field(default=False, init=False)
    hardware_verified: bool = field(default=False, init=False)
    host_network_accessed: bool = field(default=False, init=False)
    host_network_modified: bool = field(default=False, init=False)
    input_eligible: bool = field(default=False, init=False)
    provenance: str = field(
        default="caller_supplied_offline_fake_frames", init=False
    )
    host_network_action: str = field(default="not_performed", init=False)

    def __post_init__(self, _ssids_init: tuple[VendorWifiSsid, ...]) -> None:
        if type(_ssids_init) is not tuple or any(
            type(item) is not VendorWifiSsid for item in _ssids_init
        ):
            raise TypeError("private Wi-Fi entries must be an exact tuple")
        object.__setattr__(self, "_ssids", _ssids_init)

    @property
    def command_written(self) -> bool:
        """Compatibility alias; this means only that the fake call returned."""

        return self.fake_write_call_completed

    @property
    def delivery_uncertain(self) -> bool:
        """Compatibility alias for fake transport-call uncertainty."""

        return self.transport_call_uncertain

    @property
    def locally_observed_count_matches(self) -> bool:
        """Whether callback entries locally equal the advertised count.

        Entries are not deduplicated into distinct networks, and equality is not
        evidence of a device terminal.
        """

        return (
            self.advertised_count is not None
            and self.assembled_entry_count == self.advertised_count
        )

    @property
    def user_guidance(self) -> str:
        if not self.write_invoked:
            write_state = "No fake write was invoked."
        elif not self.fake_write_call_completed:
            write_state = (
                "The fake write was invoked without a confirmed return; transport "
                "state is uncertain."
            )
        else:
            write_state = "The fake write call returned without proving delivery."
        guidance = (
            f"{write_state} Locally observed counts are diagnostic only; protocol "
            "delivery is unknown and no acknowledgement, wire terminal, host scan, "
            "or live Bluetooth operation occurred."
        )
        if self.tainted:
            guidance += " This simulator is tainted and must not be reused."
        return guidance

    def ssids_for_explicit_local_test_use(self) -> tuple[VendorWifiSsid, ...]:
        """Expose private assembled entries only to an explicit local fake test."""

        return tuple(getattr(self, "_ssids", ()))

    def __repr__(self) -> str:
        return (
            "WifiScanSimulationResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"advertised_count={self.advertised_count!r}, "
            f"accepted_frame_count={self.accepted_frame_count}, "
            f"assembled_entry_count={self.assembled_entry_count}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"projections={self.projections!r}, "
            f"write_invoked={self.write_invoked!r}, "
            f"fake_write_call_completed={self.fake_write_call_completed!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            f"transport_call_uncertain={self.transport_call_uncertain!r}, "
            f"tainted={self.tainted!r}, "
            "protocol_delivery='unknown', ssids=<redacted>, "
            "application_acknowledgement_observed=False, "
            "wire_terminal_observed=False, quiet_means_success=False, "
            "host_network_accessed=False, host_network_modified=False, "
            "host_network_action='not_performed', simulation_only=True, "
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


class FakeVendorWifiScanSimulator:
    """Collect one exact Wi-Fi scan request on the scripted main route."""

    simulation_only = True
    hardware_eligible = False

    def __init__(self, transport: ScriptedVendorFakeTransport) -> None:
        if type(transport) is not ScriptedVendorFakeTransport:
            raise TypeError("transport must be the exact ScriptedVendorFakeTransport type")
        self._transport = transport
        self._collecting = False
        self._tainted = False

    @property
    def tainted(self) -> bool:
        return self._tainted

    async def collect(
        self,
        *,
        request: NoArgumentMainCommandRequest,
        frame_limit: int = 64,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
        stage_timeout: float = 5.0,
    ) -> WifiScanSimulationResult:
        if self._collecting:
            raise RuntimeError("Wi-Fi scan collection is already in progress")
        if self._tainted:
            raise WifiScanSimulationTaintedError(
                "simulator is tainted by an uncertain attempt; create a new simulator"
            )
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
        request: NoArgumentMainCommandRequest,
        frame_limit: int,
        quiet_timeout: float,
        overall_timeout: float,
        stage_timeout: float,
    ) -> WifiScanSimulationResult:
        if (
            type(request) is not NoArgumentMainCommandRequest
            or request.command is not NoArgumentMainCommand.SCAN_WIFI
        ):
            raise TypeError("request must be the exact scan Wi-Fi request")
        if isinstance(frame_limit, bool) or not isinstance(frame_limit, int):
            raise TypeError("frame_limit must be an integer")
        if not 1 <= frame_limit <= 4096:
            raise ValueError("frame_limit must be between 1 and 4096")
        quiet = _positive_number(quiet_timeout, "quiet_timeout")
        overall = _positive_number(overall_timeout, "overall_timeout")
        stage = _positive_number(stage_timeout, "stage_timeout")

        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=frame_limit + 1)
        assembler = VendorWifiSsidAssembler()
        ssids: list[VendorWifiSsid] = []
        projections: list[Projection] = []
        advertised_count: int | None = None
        accepted = 0
        unrelated = 0
        write_invoked = False
        fake_write_call_completed = False
        subscribed = False
        request_active = False
        request_target: GattCharacteristicTarget | None = None
        response_target: GattCharacteristicTarget | None = None
        overflowed = False
        receiving = True
        reason = WifiScanSimulationReason.LOCAL_QUIET
        completeness = WifiScanCompleteness.UNKNOWN
        loop = asyncio.get_running_loop()
        overall_deadline = loop.time() + overall

        def receive(data: bytes) -> None:
            nonlocal overflowed
            if not receiving or not request_active:
                return
            bounded = data if len(data) <= 20 else data[:21]
            try:
                queue.put_nowait(bytes(bounded))
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
            nonlocal request_active, write_invoked
            remaining = overall_deadline - loop.time()
            if remaining <= 0:
                raise _OverallTimeoutError
            overall_is_limit = remaining <= stage

            async def invoke_write() -> None:
                nonlocal request_active, write_invoked
                write_invoked = True
                request_active = True
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
            if not preflight.structurally_ready:
                reason = WifiScanSimulationReason.PREFLIGHT_FAILURE
                completeness = WifiScanCompleteness.ABORTED
            else:
                request_target = preflight.request_target
                response_target = preflight.response_target
                if (
                    request_target is None
                    or response_target is None
                    or not self._transport.owns_target(request_target)
                    or not self._transport.owns_target(response_target)
                ):
                    raise LookupError("resolved GATT target is no longer owned")
                subscribed = True
                await stage_call(
                    lambda: self._transport.subscribe_target(response_target, receive)
                )
                frame = request.frames()[0].synthetic_bytes_for_test()
                await write_call(request_target, frame)
                fake_write_call_completed = True
                quiet_deadline = loop.time() + quiet

                while accepted < frame_limit:
                    if overflowed:
                        reason = WifiScanSimulationReason.QUEUE_OVERFLOW
                        completeness = WifiScanCompleteness.ABORTED
                        break
                    now = loop.time()
                    remaining = min(quiet_deadline, overall_deadline) - now
                    if remaining <= 0:
                        if now >= overall_deadline:
                            reason = WifiScanSimulationReason.OVERALL_TIMEOUT
                            completeness = WifiScanCompleteness.ABORTED
                        else:
                            reason = WifiScanSimulationReason.LOCAL_QUIET
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
                        reason = WifiScanSimulationReason.QUEUE_OVERFLOW
                        completeness = WifiScanCompleteness.ABORTED
                        break
                    if not done:
                        continue
                    if disconnect_task in done and disconnect_task.result():
                        if not data_task.done():
                            data_task.cancel()
                        reason = WifiScanSimulationReason.DISCONNECTED
                        completeness = WifiScanCompleteness.ABORTED
                        break

                    data = data_task.result()
                    classification = self._classify(data)
                    if classification == "unrelated":
                        unrelated += 1
                        continue
                    if classification == "malformed":
                        reason = WifiScanSimulationReason.MALFORMED_FRAME
                        completeness = WifiScanCompleteness.ABORTED
                        break
                    if classification == "count":
                        if advertised_count is not None:
                            reason = WifiScanSimulationReason.MALFORMED_FRAME
                            completeness = WifiScanCompleteness.ABORTED
                            break
                        advertised_count = parse_vendor_wifi_ssid_count(data).count
                        accepted += 1
                        projections.append(("onGetWifiSsidCount", 1, "wire_frame"))
                    else:
                        if advertised_count is None:
                            reason = WifiScanSimulationReason.MALFORMED_FRAME
                            completeness = WifiScanCompleteness.ABORTED
                            break
                        try:
                            ssid = assembler.feed(data)
                            if ssid is not None:
                                ssid.ssid_for_explicit_local_use()
                        except (ProtocolError, UnicodeDecodeError):
                            assembler.reset()
                            reason = WifiScanSimulationReason.MALFORMED_FRAME
                            completeness = WifiScanCompleteness.ABORTED
                            break
                        accepted += 1
                        if ssid is not None:
                            ssids.append(ssid)
                            projections.append(
                                ("onGetWifiSsid", 1, "assembled_wire_fragments")
                            )
                    quiet_deadline = loop.time() + quiet
                else:
                    reason = WifiScanSimulationReason.LIMIT_REACHED
        except _DisconnectedError:
            reason = WifiScanSimulationReason.DISCONNECTED
            completeness = WifiScanCompleteness.ABORTED
        except _OverallTimeoutError:
            reason = WifiScanSimulationReason.OVERALL_TIMEOUT
            completeness = WifiScanCompleteness.ABORTED
        except _StageTimeoutError:
            reason = (
                WifiScanSimulationReason.WRITE_FAILURE
                if write_invoked
                else WifiScanSimulationReason.PREFLIGHT_FAILURE
            )
            completeness = WifiScanCompleteness.ABORTED
        except Exception:
            reason = (
                WifiScanSimulationReason.WRITE_FAILURE
                if write_invoked
                else WifiScanSimulationReason.PREFLIGHT_FAILURE
            )
            completeness = WifiScanCompleteness.ABORTED
        except BaseException:
            if write_invoked:
                self._tainted = True
            raise
        finally:
            request_active = False
            receiving = False
            while True:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            cleanup_task = asyncio.create_task(
                self._cleanup(subscribed, response_target, timeout=stage)
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
            reason = WifiScanSimulationReason.CLEANUP_FAILURE
            completeness = (
                WifiScanCompleteness.UNCERTAIN
                if write_invoked
                else WifiScanCompleteness.ABORTED
            )
        elif write_invoked and not fake_write_call_completed:
            completeness = WifiScanCompleteness.UNCERTAIN
            self._tainted = True
        result = WifiScanSimulationResult(
            reason=reason,
            completeness=completeness,
            advertised_count=advertised_count,
            accepted_frame_count=accepted,
            assembled_entry_count=len(ssids),
            unrelated_frame_count=unrelated,
            projections=tuple(projections),
            write_invoked=write_invoked,
            fake_write_call_completed=fake_write_call_completed,
            cleanup_succeeded=cleanup_succeeded,
            transport_call_uncertain=(
                write_invoked and not fake_write_call_completed
            ),
            tainted=self._tainted,
            _ssids_init=tuple(ssids),
        )
        return result

    @staticmethod
    def _classify(data: bytes) -> str:
        if not data or data[0] != 0x54:
            return "unrelated"
        if len(data) < 2:
            return "unrelated"
        if data[1] not in {0x09, 0x0A}:
            return "unrelated"
        if len(data) != 20:
            return "malformed"
        return "count" if data[1] == 0x09 else "fragment"

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
    "FakeVendorWifiScanSimulator",
    "WifiScanCompleteness",
    "WifiScanSimulationReason",
    "WifiScanSimulationTaintedError",
    "WifiScanSimulationResult",
]
