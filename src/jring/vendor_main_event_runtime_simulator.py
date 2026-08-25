"""Bounded fake-only collector for passive events on the vendor MAIN route.

The collector subscribes but never writes.  It recognizes seven statically
discriminated notification opcodes across nine event kinds and does not treat local
quiet or a caller limit as a wire terminal.  Shared opcode ``0x78`` is accepted only
for exact motion-candidate selectors ``0x00``/``0x01`` and touch-setting selector
``0x09``; every other selector stays unrelated.
"""

from __future__ import annotations

import asyncio
from dataclasses import InitVar, dataclass, field
from enum import Enum
import math
from types import MappingProxyType
from typing import ClassVar

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
    parse_vendor_chat_action,
    parse_vendor_device_action,
    parse_vendor_motion_frame,
    parse_vendor_phone_volume_request,
    parse_vendor_step_counter,
    parse_vendor_touch_mode,
)
from .vendor_runtime_fake import ScriptedVendorFakeTransport


class MainEventKind(str, Enum):
    DEVICE_ACTION = "device_action"
    CUMULATIVE_STEP = "cumulative_step"
    PHONE_VOLUME_REQUEST = "phone_volume_request"
    CLASSIC_INFO = "classic_info"
    CLASSIC_NAME = "classic_name"
    APP_ID = "app_id"
    TOUCH_MODE_SETTING_PROJECTION = "touch_mode_setting_projection"
    UNKNOWN_MOTION_CHANNEL_PROJECTION = "unknown_motion_channel_projection"
    MAIN_CHAT_ACTION_PROJECTION = "main_chat_action_projection"


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


class TouchModeSettingProjection:
    """Redacted holder for one synthetic, neutral touch-mode setting value."""

    __slots__ = ("_value",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("touch-mode setting projections are decoder-owned")

    @classmethod
    def _create(cls, value: int) -> "TouchModeSettingProjection":
        if type(value) is not int or not 0 <= value <= 0xFF:
            raise ValueError("touch-mode projection value must fit one unsigned byte")
        projection = object.__new__(cls)
        projection._value = value
        return projection

    @property
    def projection_role(self) -> str:
        return "touch_mode_setting_value_or_event"

    @property
    def acknowledgement_state(self) -> str:
        return "not_proven"

    @property
    def setting_application_state(self) -> str:
        return "unknown"

    @property
    def terminal_observed(self) -> bool:
        return False

    @property
    def gesture_semantics(self) -> str:
        return "not_proven"

    @property
    def touch_event_observed(self) -> bool:
        return False

    @property
    def sensor_event_observed(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def input_eligible(self) -> bool:
        return False

    def value_for_test(self) -> int:
        """Return the synthetic neutral value only to focused offline tests."""

        return self._value

    def __repr__(self) -> str:
        return (
            "TouchModeSettingProjection(value=<redacted>, "
            "projection_role='touch_mode_setting_value_or_event', "
            "acknowledgement_state='not_proven', "
            "setting_application_state='unknown', terminal_observed=False, "
            "gesture_semantics='not_proven', touch_event_observed=False, "
            "sensor_event_observed=False, hardware_verified=False, "
            "input_eligible=False)"
        )


class UnknownMotionChannelProjection:
    """Redacted holder for one synthetic neutral G-sensor callback payload."""

    __slots__ = ("_selector", "_channels")

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("unknown motion channel projections are decoder-owned")

    @classmethod
    def _create(
        cls,
        selector: int,
        channels: tuple[int, int, int, int, int, int, int, int, int],
    ) -> "UnknownMotionChannelProjection":
        if type(selector) is not int or selector not in {0x00, 0x01}:
            raise ValueError("motion candidate selector must be exact 0x00 or 0x01")
        if type(channels) is not tuple or len(channels) != 9:
            raise TypeError(
                "motion candidate channels must be an exact nine-value tuple"
            )
        if any(
            type(value) is not int or not -32_768 <= value <= 32_767
            for value in channels
        ):
            raise ValueError("motion candidate channels must be signed 16-bit integers")
        projection = object.__new__(cls)
        object.__setattr__(projection, "_selector", selector)
        object.__setattr__(projection, "_channels", tuple(channels))
        return projection

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("unknown motion channel projections are immutable")

    def __copy__(self) -> "UnknownMotionChannelProjection":
        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> "UnknownMotionChannelProjection":
        return self

    @property
    def projection_role(self) -> str:
        return "source_labeled_g_sensor_callback_payload"

    @property
    def selector_scope(self) -> str:
        return "exact_78_00_or_01"

    @property
    def channel_count(self) -> int:
        return 9

    @property
    def channel_meaning(self) -> str:
        return "unknown"

    @property
    def selector_meaning(self) -> str:
        return "unknown"

    @property
    def axes(self) -> str:
        return "not_proven"

    @property
    def units(self) -> str:
        return "not_proven"

    @property
    def sample_interval(self) -> str:
        return "not_proven"

    @property
    def gesture_semantics(self) -> str:
        return "not_proven"

    @property
    def sensor_event_promoted(self) -> bool:
        return False

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def transport_write_invoked(self) -> bool:
        return False

    @property
    def setter_causation_observed(self) -> bool:
        return False

    @property
    def acknowledgement_observed(self) -> bool:
        return False

    @property
    def wire_terminal_observed(self) -> bool:
        return False

    @property
    def live_available(self) -> bool:
        return False

    @property
    def ring_contacted(self) -> bool:
        return False

    @property
    def host_input_emitted(self) -> bool:
        return False

    @property
    def private_motion_channels_redacted(self) -> bool:
        return True

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def input_eligible(self) -> bool:
        return False

    def selector_for_test(self) -> int:
        """Return the synthetic selector only to focused offline tests."""

        return self._selector

    def channels_for_test(self) -> tuple[int, int, int, int, int, int, int, int, int]:
        """Return the synthetic private channels only to focused offline tests."""

        return self._channels

    def __repr__(self) -> str:
        return (
            "UnknownMotionChannelProjection(selector=<redacted>, "
            "channels=<redacted>, projection_role="
            "'source_labeled_g_sensor_callback_payload', "
            "selector_scope='exact_78_00_or_01', channel_count=9, "
            "channel_meaning='unknown', selector_meaning='unknown', "
            "axes='not_proven', units='not_proven', "
            "sample_interval='not_proven', gesture_semantics='not_proven', "
            "sensor_event_promoted=False, simulation_only=True, "
            "transport_write_invoked=False, setter_causation_observed=False, "
            "acknowledgement_observed=False, wire_terminal_observed=False, "
            "live_available=False, ring_contacted=False, host_input_emitted=False, "
            "private_motion_channels_redacted=True, "
            "hardware_verified=False, input_eligible=False)"
        )


class MainChatActionProjection:
    """Redacted holder for one synthetic passive MAIN chat-action code."""

    __slots__ = ("_value",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("main chat action projections are decoder-owned")

    @classmethod
    def _create(cls, value: int) -> "MainChatActionProjection":
        if type(value) is not int or not 0 <= value <= 0xFF:
            raise ValueError("main chat action code must fit one unsigned byte")
        projection = object.__new__(cls)
        object.__setattr__(projection, "_value", value)
        return projection

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("main chat action projections are immutable")

    def __copy__(self) -> "MainChatActionProjection":
        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> "MainChatActionProjection":
        return self

    @property
    def projection_role(self) -> str:
        return "passive_main_chat_action_code_candidate"

    @property
    def action_meaning(self) -> str:
        return "unknown"

    @property
    def protocol_request_relationship(self) -> str:
        return "unknown"

    @property
    def fake_attempt_request_owned(self) -> bool:
        return False

    @property
    def chat_execution_observed(self) -> bool:
        return False

    @property
    def content_handling_observed(self) -> bool:
        return False

    @property
    def setter_causation_observed(self) -> bool:
        return False

    @property
    def acknowledgement_observed(self) -> bool:
        return False

    @property
    def wire_terminal_observed(self) -> bool:
        return False

    @property
    def private_action_code_redacted(self) -> bool:
        return True

    @property
    def simulation_only(self) -> bool:
        return True

    @property
    def transport_write_invoked(self) -> bool:
        return False

    @property
    def live_available(self) -> bool:
        return False

    @property
    def ring_contacted(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def host_input_emitted(self) -> bool:
        return False

    @property
    def input_eligible(self) -> bool:
        return False

    def value_for_test(self) -> int:
        """Return the synthetic neutral action code only to focused tests."""

        return self._value

    def __repr__(self) -> str:
        return (
            "MainChatActionProjection(value=<redacted>, "
            "projection_role='passive_main_chat_action_code_candidate', "
            "action_meaning='unknown', protocol_request_relationship='unknown', "
            "fake_attempt_request_owned=False, "
            "chat_execution_observed=False, content_handling_observed=False, "
            "setter_causation_observed=False, acknowledgement_observed=False, "
            "wire_terminal_observed=False, private_action_code_redacted=True, "
            "simulation_only=True, transport_write_invoked=False, "
            "live_available=False, ring_contacted=False, hardware_verified=False, "
            "host_input_emitted=False, input_eligible=False)"
        )


DecodedMainEvent = (
    VendorDeviceAction
    | VendorStepCounter
    | VendorPhoneVolumeRequest
    | VendorClassicInfo
    | VendorRedactedTextNotification
    | TouchModeSettingProjection
    | UnknownMotionChannelProjection
    | MainChatActionProjection
)


_EVENT_VALUE_TYPES = MappingProxyType({
    MainEventKind.DEVICE_ACTION: VendorDeviceAction,
    MainEventKind.CUMULATIVE_STEP: VendorStepCounter,
    MainEventKind.PHONE_VOLUME_REQUEST: VendorPhoneVolumeRequest,
    MainEventKind.CLASSIC_INFO: VendorClassicInfo,
    MainEventKind.CLASSIC_NAME: VendorRedactedTextNotification,
    MainEventKind.APP_ID: VendorRedactedTextNotification,
    MainEventKind.TOUCH_MODE_SETTING_PROJECTION: TouchModeSettingProjection,
    MainEventKind.UNKNOWN_MOTION_CHANNEL_PROJECTION: UnknownMotionChannelProjection,
    MainEventKind.MAIN_CHAT_ACTION_PROJECTION: MainChatActionProjection,
})
_EVENT_45_KINDS = MappingProxyType({
    MainEventKind.CLASSIC_NAME: Static45Notification.CLASSIC_NAME,
    MainEventKind.APP_ID: Static45Notification.APP_ID,
})


@dataclass(frozen=True, repr=False)
class MainPassiveEvent:
    kind: MainEventKind
    _decoded_value: InitVar[DecodedMainEvent]
    simulation_only: bool = field(default=True, init=False)
    hardware_eligible: bool = field(default=False, init=False)
    hardware_verified: bool = field(default=False, init=False)
    input_eligible: bool = field(default=False, init=False)
    _value: ClassVar[DecodedMainEvent | None] = None

    def __post_init__(self, _decoded_value: DecodedMainEvent) -> None:
        if type(self.kind) is not MainEventKind:
            raise TypeError("event kind must be an exact MainEventKind")
        expected_type = _EVENT_VALUE_TYPES[self.kind]
        if type(_decoded_value) is not expected_type:
            raise TypeError("decoded event value does not match its event kind")
        expected_45_kind = _EVENT_45_KINDS.get(self.kind)
        if (
            expected_45_kind is not None
            and _decoded_value.kind is not expected_45_kind
        ):
            raise ValueError("decoded 45 event value does not match its event kind")
        object.__setattr__(self, "_value", _decoded_value)

    def value_for_test(self) -> DecodedMainEvent:
        """Expose a synthetic decoded value only to focused offline tests."""

        if self._value is None:
            raise RuntimeError("synthetic event value is unavailable")
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
    _decoded_events: InitVar[tuple[MainPassiveEvent, ...]]
    wire_terminal_observed: bool = field(default=False, init=False)
    quiet_means_success: bool = field(default=False, init=False)
    transport_write_invoked: bool = field(default=False, init=False)
    setter_invoked: bool = field(default=False, init=False)
    setter_causation_observed: bool = field(default=False, init=False)
    acknowledgement_observed: bool = field(default=False, init=False)
    simulation_only: bool = field(default=True, init=False)
    live_available: bool = field(default=False, init=False)
    ring_contacted: bool = field(default=False, init=False)
    gesture_semantics: str = field(default="not_proven", init=False)
    touch_event_observed: bool = field(default=False, init=False)
    touch_sensor_event_observed: bool = field(default=False, init=False)
    motion_sensor_event_promoted: bool = field(default=False, init=False)
    chat_execution_observed: bool = field(default=False, init=False)
    chat_content_handled: bool = field(default=False, init=False)
    host_input_emitted: bool = field(default=False, init=False)
    decoded_values_redacted: bool = field(default=True, init=False)
    event_storage_serialized: bool = field(default=False, init=False)
    hardware_eligible: bool = field(default=False, init=False)
    hardware_verified: bool = field(default=False, init=False)
    input_eligible: bool = field(default=False, init=False)
    _events: ClassVar[tuple[MainPassiveEvent, ...]] = ()

    def __post_init__(self, _decoded_events: tuple[MainPassiveEvent, ...]) -> None:
        if type(self.event_count) is not int or self.event_count < 0:
            raise ValueError("event count must be a non-negative integer")
        if type(self.unrelated_frame_count) is not int or self.unrelated_frame_count < 0:
            raise ValueError("unrelated frame count must be a non-negative integer")
        if type(_decoded_events) is not tuple or any(
            type(event) is not MainPassiveEvent for event in _decoded_events
        ):
            raise TypeError("decoded events must be exact MainPassiveEvent values")
        if self.event_count != len(_decoded_events):
            raise ValueError("event count must match decoded event storage")
        object.__setattr__(self, "_events", tuple(_decoded_events))

    @property
    def event_kinds(self) -> tuple[MainEventKind, ...]:
        return tuple(event.kind for event in self._events)

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
            "transport_write_invoked=False, setter_invoked=False, "
            "setter_causation_observed=False, acknowledgement_observed=False, "
            "simulation_only=True, live_available=False, ring_contacted=False, "
            "gesture_semantics='not_proven', touch_event_observed=False, "
            "touch_sensor_event_observed=False, motion_sensor_event_promoted=False, "
            "chat_execution_observed=False, chat_content_handled=False, "
            "host_input_emitted=False, "
            "decoded_values_redacted=True, event_storage_serialized=False, "
            "hardware_eligible=False, "
            "hardware_verified=False, input_eligible=False)"
        )


_MAX_EVENT_LIMIT = 4_096
_MATCHING_OPCODES = frozenset((0x06, 0x22, 0x45, 0x49, 0x4E, 0x51, 0x78))
_STATIC_45_EVENTS = MappingProxyType({
    0x00: (MainEventKind.CLASSIC_INFO, Static45Notification.CLASSIC_INFO),
    0x01: (MainEventKind.CLASSIC_NAME, Static45Notification.CLASSIC_NAME),
    0x02: (MainEventKind.APP_ID, Static45Notification.APP_ID),
})


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
            cleanup_task = asyncio.create_task(
                self._cleanup(subscribed, response_target, timeout=cleanup)
            )
            try:
                cleanup_succeeded = await asyncio.shield(cleanup_task)
            except BaseException as interruption:
                try:
                    cleanup_succeeded = await asyncio.shield(cleanup_task)
                except BaseException:
                    cleanup_task.cancel()
                    await asyncio.gather(cleanup_task, return_exceptions=True)
                raise interruption

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
            _decoded_events=tuple(events),
        )

    @staticmethod
    def _classify(data: bytes) -> str:
        if not data or data[0] not in _MATCHING_OPCODES:
            return "unrelated"
        if data[0] == 0x45:
            if len(data) < 2:
                return "unrelated"
            if data[1] not in _STATIC_45_EVENTS:
                return "unrelated"
        if data[0] == 0x78:
            if len(data) < 2 or data[1] not in {0x00, 0x01, 0x09}:
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
        if opcode == 0x4E:
            parsed_chat_action = parse_vendor_chat_action(data)
            return MainPassiveEvent(
                MainEventKind.MAIN_CHAT_ACTION_PROJECTION,
                MainChatActionProjection._create(parsed_chat_action.value),
            )
        if opcode == 0x45:
            event_kind, parser_kind = _STATIC_45_EVENTS[data[1]]
            return MainPassiveEvent(
                event_kind,
                parse_vendor_45_notification(data, expected_kind=parser_kind),
            )
        if opcode == 0x78:
            if data[1] in {0x00, 0x01}:
                parsed_motion = parse_vendor_motion_frame(
                    data,
                    expected_subcommand=data[1],
                )
                return MainPassiveEvent(
                    MainEventKind.UNKNOWN_MOTION_CHANNEL_PROJECTION,
                    UnknownMotionChannelProjection._create(
                        parsed_motion.subcommand,
                        parsed_motion.channels,
                    ),
                )
            parsed = parse_vendor_touch_mode(data)
            return MainPassiveEvent(
                MainEventKind.TOUCH_MODE_SETTING_PROJECTION,
                TouchModeSettingProjection._create(parsed.value),
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
    "MainChatActionProjection",
    "MainEventSimulationReason",
    "MainEventSimulationResult",
    "MainPassiveEvent",
    "TouchModeSettingProjection",
    "UnknownMotionChannelProjection",
]
