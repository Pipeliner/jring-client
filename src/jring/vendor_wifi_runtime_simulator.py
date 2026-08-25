"""Closed fake-only runtime for the recovered vendor Wi-Fi scan stream.

The advertised SSID count and completed fragment sequences are useful local
diagnostics, but neither is a proven whole-stream terminal.  This collector
therefore reports only unknown or aborted completeness and never performs host
networking, discovery, or a live Bluetooth operation.
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


Projection = tuple[str, int, str]


@dataclass(frozen=True, repr=False)
class WifiScanSimulationResult:
    reason: WifiScanSimulationReason
    completeness: WifiScanCompleteness
    advertised_count: int | None
    accepted_frame_count: int
    assembled_entry_count: int
    unrelated_frame_count: int
    projections: tuple[Projection, ...]
    command_written: bool
    cleanup_succeeded: bool
    delivery_uncertain: bool
    _ssids: tuple[VendorWifiSsid, ...] = field(repr=False)

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
    def host_network_action(self) -> str:
        return "not_performed"

    @property
    def user_guidance(self) -> str:
        return (
            "Locally observed counts are diagnostic only; no wire terminal, "
            "host scan, or live Bluetooth operation occurred."
        )

    def ssids_for_explicit_local_test_use(self) -> tuple[VendorWifiSsid, ...]:
        """Expose private assembled entries only to an explicit local fake test."""

        return tuple(self._ssids)

    def __repr__(self) -> str:
        return (
            "WifiScanSimulationResult("
            f"reason={self.reason.value!r}, completeness={self.completeness.value!r}, "
            f"advertised_count={self.advertised_count!r}, "
            f"accepted_frame_count={self.accepted_frame_count}, "
            f"assembled_entry_count={self.assembled_entry_count}, "
            f"unrelated_frame_count={self.unrelated_frame_count}, "
            f"projections={self.projections!r}, command_written={self.command_written!r}, "
            f"cleanup_succeeded={self.cleanup_succeeded!r}, "
            f"delivery_uncertain={self.delivery_uncertain!r}, ssids=<redacted>, "
            "wire_terminal_observed=False, quiet_means_success=False, "
            "host_network_action='not_performed', simulation_only=True, "
            "hardware_eligible=False, hardware_verified=False)"
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

    async def collect(
        self,
        *,
        request: NoArgumentMainCommandRequest,
        frame_limit: int = 64,
        quiet_timeout: float = 0.05,
        overall_timeout: float = 5.0,
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

        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=frame_limit + 1)
        assembler = VendorWifiSsidAssembler()
        ssids: list[VendorWifiSsid] = []
        projections: list[Projection] = []
        advertised_count: int | None = None
        accepted = 0
        unrelated = 0
        write_issued = False
        command_written = False
        subscribed = False
        overflowed = False
        reason = WifiScanSimulationReason.LOCAL_QUIET
        completeness = WifiScanCompleteness.UNKNOWN

        def receive(data: bytes) -> None:
            nonlocal overflowed
            try:
                queue.put_nowait(bytes(data))
            except asyncio.QueueFull:
                overflowed = True

        try:
            await self._transport.connect()
            if not await self._preflight():
                reason = WifiScanSimulationReason.PREFLIGHT_FAILURE
                completeness = WifiScanCompleteness.ABORTED
            else:
                await self._transport.subscribe(VENDOR_CHARACTERISTIC_33F4, receive)
                subscribed = True
                frame = request.frames()[0]
                write_issued = True
                await self._transport.write_with_response(
                    VENDOR_CHARACTERISTIC_33F3,
                    frame.synthetic_bytes_for_test(),
                )
                command_written = True
                loop = asyncio.get_running_loop()
                quiet_deadline = loop.time() + quiet
                overall_deadline = loop.time() + overall

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
                                # The recovered callback projects text, so do not
                                # count an entry that cannot be decoded as text.
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
        except (ConnectionError, LookupError, OSError, ProtocolError):
            reason = (
                WifiScanSimulationReason.WRITE_FAILURE
                if subscribed else WifiScanSimulationReason.PREFLIGHT_FAILURE
            )
            completeness = WifiScanCompleteness.ABORTED
        finally:
            cleanup_succeeded = await self._cleanup(subscribed)

        if not cleanup_succeeded:
            reason = WifiScanSimulationReason.CLEANUP_FAILURE
            completeness = WifiScanCompleteness.ABORTED
        return WifiScanSimulationResult(
            reason=reason,
            completeness=completeness,
            advertised_count=advertised_count,
            accepted_frame_count=accepted,
            assembled_entry_count=len(ssids),
            unrelated_frame_count=unrelated,
            projections=tuple(projections),
            command_written=command_written,
            cleanup_succeeded=cleanup_succeeded,
            delivery_uncertain=(write_issued and completeness is WifiScanCompleteness.ABORTED),
            _ssids=tuple(ssids),
        )

    @staticmethod
    def _classify(data: bytes) -> str:
        if not data or data[0] != 0x54:
            return "unrelated"
        if len(data) < 2:
            return "malformed"
        if data[1] not in {0x09, 0x0A}:
            return "unrelated"
        if len(data) != 20:
            return "malformed"
        return "count" if data[1] == 0x09 else "fragment"

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

    async def _cleanup(self, subscribed: bool) -> bool:
        succeeded = True
        if subscribed and self._transport.connected:
            try:
                await self._transport.unsubscribe(VENDOR_CHARACTERISTIC_33F4)
            except (ConnectionError, OSError):
                succeeded = False
        try:
            await self._transport.close()
        except OSError:
            succeeded = False
        return succeeded


__all__ = [
    "FakeVendorWifiScanSimulator",
    "WifiScanCompleteness",
    "WifiScanSimulationReason",
    "WifiScanSimulationResult",
]
