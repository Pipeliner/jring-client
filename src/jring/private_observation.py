"""Fail-closed planning for a future private owner-observation command."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import math
import os
from pathlib import Path
import stat
import time
from collections.abc import Callable
from weakref import WeakKeyDictionary

from .owner_hardware_evidence import (
    OwnerEvidenceError,
    _read_restrictive_json,
    _write_exclusive_json,
)
from .transport import (
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
    GattDescriptorTarget,
)
from .uuids import CLIENT_CHARACTERISTIC_CONFIGURATION


class ObservationError(ValueError):
    """Stable, value-free policy failure for private observation planning."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _PlanState:
    address: str
    timeout: float
    max_records: int
    private_output: Path
    parent_identity: tuple[int, int]


_PLANS: WeakKeyDictionary[object, _PlanState] = WeakKeyDictionary()
_RECORDERS: WeakKeyDictionary[object, tuple[ObservationPlan, list[bytes], bool]] = WeakKeyDictionary()
_AUTHORITIES: WeakKeyDictionary[object, tuple[ObservationPlan, int, object, bool]] = WeakKeyDictionary()
_PLAN_USED: WeakKeyDictionary[object, bool] = WeakKeyDictionary()
_RESULTS: WeakKeyDictionary[object, tuple[str, int, dict[str, str]]] = WeakKeyDictionary()


class ObservationPlan:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use prepare_observation_plan")

    def public_payload(self) -> dict[str, object]:
        state = _PLANS[self]
        return {
            "consent": ["connect", "observe", "subscribe"],
            "deadline": "bounded",
            "max_records": state.max_records,
            "private_output": "mode_0600",
            "single_use": True,
        }

    def __repr__(self) -> str:
        return "ObservationPlan(selection=<redacted>, private_output=<redacted>, single_use=True)"


class ObservationStatus(str, Enum):
    COMPLETED = "completed"
    CONNECTION_FAILED = "connection_failed"
    ROUTE_UNAVAILABLE = "route_unavailable"
    SUBSCRIPTION_FAILED = "subscription_failed"
    TIMED_OUT = "timed_out"
    DISCONNECTED = "disconnected"
    CLEANUP_UNCERTAIN = "cleanup_uncertain"
    CANCELLED = "cancelled"


class ObservationResult:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("private observation results are runner-owned")

    def public_payload(self) -> dict[str, object]:
        status, record_count, cleanup = _RESULTS[self]
        return {
            "capture_status": status,
            "record_count": record_count,
            "cleanup": dict(cleanup),
            "runtime_authorized": False,
            "decoder": "none",
        }

    def __repr__(self) -> str:
        return "ObservationResult(records=<private>, target=<redacted>)"


def load_private_observation(path: Path) -> dict[str, object]:
    """Validate a private capture and return only its value-free review summary."""

    try:
        payload = _read_restrictive_json(
            path,
            unsafe_code="unsafe_private_input",
            invalid_code="invalid_private_observation",
        )
    except OwnerEvidenceError as exc:
        raise ObservationError(exc.code) from exc
    if (
        type(payload) is not dict
        or payload.get("schema_version") != 1
        or payload.get("record_type") != "private_owner_observation"
        or payload.get("capture_status")
        not in {item.value for item in ObservationStatus}
    ):
        raise ObservationError("invalid_private_observation")
    records = payload.get("records")
    if not isinstance(records, list) or not 0 <= len(records) <= 128:
        raise ObservationError("invalid_private_observation")
    for record in records:
        if (
            not isinstance(record, str)
            or len(record) % 2
            or any(character not in "0123456789abcdef" for character in record)
        ):
            raise ObservationError("invalid_private_observation")
    return {
        "capture_status": payload["capture_status"],
        "record_count": len(records),
        "decoder": "none",
        "runtime_authorized": False,
    }


class ObservationRecorder:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use begin_observation")

    def record(self, frame: bytes) -> None:
        plan, frames, finished = _RECORDERS[self]
        if finished:
            raise ObservationError("observation_finished")
        if not isinstance(frame, bytes) or not frame:
            raise ObservationError("malformed_observation")
        if len(frames) >= _PLANS[plan].max_records:
            raise ObservationError("record_limit_reached")
        frames.append(frame)

    @property
    def record_count(self) -> int:
        return len(_RECORDERS[self][1])

    def finish(self, *, capture_status: str = "completed") -> dict[str, object]:
        plan, frames, finished = _RECORDERS[self]
        if finished:
            raise ObservationError("observation_finished")
        if capture_status not in {item.value for item in ObservationStatus}:
            raise ObservationError("invalid_capture_status")
        state = _PLANS[plan]
        try:
            _write_exclusive_json(state.private_output, {
                "schema_version": 1, "record_type": "private_owner_observation",
                "capture_status": capture_status,
                "records": [frame.hex() for frame in frames],
            }, mode=0o600, unsafe_code="unsafe_private_output",
               exists_code="private_output_exists", restrictive_parent=True,
               expected_parent=state.parent_identity)
        except OwnerEvidenceError as exc:
            raise ObservationError(exc.code) from exc
        _RECORDERS[self] = (plan, frames, True)
        return {"capture_status": capture_status, "record_count": len(frames),
                "private_output": "mode_0600", "runtime_authorized": False}

    def __repr__(self) -> str:
        return "ObservationRecorder(records=<private>)"


class ObservationAuthority:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use prepare_observation_authority")

    def __repr__(self) -> str:
        return "ObservationAuthority(generation=<sealed>, target=<redacted>, single_use=True)"


def prepare_observation_authority(
    plan: ObservationPlan, *, connection_generation: int, target: object
) -> ObservationAuthority:
    if type(plan) is not ObservationPlan or plan not in _PLANS:
        raise ObservationError("invalid_observation_plan")
    if isinstance(connection_generation, bool) or not isinstance(connection_generation, int) or connection_generation <= 0:
        raise ObservationError("invalid_connection_generation")
    if target is None:
        raise ObservationError("invalid_observation_target")
    authority = object.__new__(ObservationAuthority)
    _AUTHORITIES[authority] = (plan, connection_generation, target, False)
    return authority


def require_observation_authority(
    authority: ObservationAuthority, *, connection_generation: int, target: object
) -> None:
    if type(authority) is not ObservationAuthority or authority not in _AUTHORITIES:
        raise ObservationError("invalid_observation_authority")
    plan, expected_generation, expected_target, used = _AUTHORITIES[authority]
    if used or plan not in _PLANS:
        raise ObservationError("stale_observation_authority")
    if connection_generation != expected_generation or target is not expected_target:
        raise ObservationError("observation_authority_mismatch")
    _AUTHORITIES[authority] = (plan, expected_generation, expected_target, True)


def select_observation_target(
    metadata: tuple[GattCharacteristicMetadata, ...],
    *,
    connection_generation: int,
    service_uuid: str,
    characteristic_uuid: str,
    instance_id: str,
) -> GattCharacteristicTarget:
    """Select one locally enumerated current-generation notify endpoint.

    This is deliberately metadata-only. It has no knowledge of prior art, field
    semantics, frame decoders, or runtime eligibility; the production transport
    still validates object identity before it can subscribe.
    """

    if (
        isinstance(connection_generation, bool)
        or not isinstance(connection_generation, int)
        or connection_generation <= 0
    ):
        raise ObservationError("invalid_connection_generation")
    if not all(
        isinstance(value, str) and value
        for value in (service_uuid, characteristic_uuid, instance_id)
    ):
        raise ObservationError("invalid_observation_selector")
    if not isinstance(metadata, tuple) or not all(
        type(item) is GattCharacteristicMetadata for item in metadata
    ):
        raise ObservationError("invalid_observation_metadata")
    matches = [
        item
        for item in metadata
        if (
            item.service_uuid == service_uuid
            and item.uuid == characteristic_uuid
            and item.instance_id == instance_id
        )
    ]
    if len(matches) != 1:
        raise ObservationError("ambiguous_observation_target")
    candidate = matches[0]
    if (
        type(candidate.target) is not GattCharacteristicTarget
        or candidate.target.connection_generation != connection_generation
        or candidate.target.service_uuid != service_uuid
        or candidate.target.uuid != characteristic_uuid
        or candidate.target.instance_id != instance_id
        or "notify" not in candidate.properties
        or candidate.descriptor_uuids.count(CLIENT_CHARACTERISTIC_CONFIGURATION) != 1
        or len(candidate.descriptor_targets) != 1
        or type(candidate.descriptor_targets[0]) is not GattDescriptorTarget
        or candidate.descriptor_targets[0].connection_generation
        != connection_generation
        or candidate.descriptor_targets[0].uuid
        != CLIENT_CHARACTERISTIC_CONFIGURATION
        or candidate.descriptor_targets[0].characteristic_instance_id != instance_id
    ):
        raise ObservationError("unsupported_observation_target")
    return candidate.target


def begin_observation(plan: ObservationPlan) -> ObservationRecorder:
    if type(plan) is not ObservationPlan or plan not in _PLANS:
        raise ObservationError("invalid_observation_plan")
    recorder = object.__new__(ObservationRecorder)
    _RECORDERS[recorder] = (plan, [], False)
    return recorder


def prepare_observation_plan(
    *,
    address: str,
    allow_connect: bool,
    allow_notifications: bool,
    allow_observation: bool,
    timeout: float,
    max_records: int,
    private_output: Path,
) -> ObservationPlan:
    if not isinstance(address, str) or not address:
        raise ObservationError("missing_selection")
    for allowed, code in (
        (allow_connect, "missing_connect_consent"),
        (allow_notifications, "missing_subscribe_consent"),
        (allow_observation, "missing_observation_consent"),
    ):
        if allowed is not True:
            raise ObservationError(code)
    if not isinstance(timeout, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ObservationError("invalid_timeout")
    if isinstance(max_records, bool) or not isinstance(max_records, int) or not 1 <= max_records <= 128:
        raise ObservationError("invalid_record_limit")
    if not isinstance(private_output, Path) or not private_output.name:
        raise ObservationError("unsafe_private_output")
    try:
        private_output.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ObservationError("unsafe_private_output") from exc
    else:
        raise ObservationError("private_output_exists")
    try:
        parent = private_output.parent.lstat()
    except OSError as exc:
        raise ObservationError("unsafe_private_output") from exc
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o077:
        raise ObservationError("unsafe_private_output")
    plan = object.__new__(ObservationPlan)
    _PLANS[plan] = _PlanState(address, timeout, max_records, private_output, (parent.st_dev, parent.st_ino))
    _PLAN_USED[plan] = False
    return plan


class PrivateObservationRunner:
    """Run one private, no-write notification capture through ``BleakTransport``."""

    def __init__(self, *, transport_factory: object | None = None) -> None:
        if transport_factory is not None:
            from .bleak_transport import BleakTransport

            if transport_factory is not BleakTransport:
                raise TypeError("private observation requires the production BleakTransport")

    async def run(
        self,
        plan: ObservationPlan,
        *,
        service_uuid: str,
        characteristic_uuid: str,
        instance_id: str,
    ) -> ObservationResult:
        from .bleak_transport import BleakTransport

        if type(plan) is not ObservationPlan or plan not in _PLANS:
            raise ObservationError("invalid_observation_plan")
        if _PLAN_USED[plan]:
            raise ObservationError("stale_observation_plan")
        _PLAN_USED[plan] = True
        state = _PLANS[plan]
        recorder = begin_observation(plan)
        deadline = time.monotonic() + state.timeout
        transport: BleakTransport | None = None
        token: object | None = None
        remove_listener: Callable[[], None] | None = None
        disconnected = asyncio.Event()
        completed = asyncio.Event()
        status = ObservationStatus.CONNECTION_FAILED
        cleanup = {"unsubscribe": "not_required", "close": "not_attempted"}
        cancelled: asyncio.CancelledError | None = None

        def on_disconnect(_error: BaseException | None) -> None:
            disconnected.set()

        def on_notification(frame: bytes) -> None:
            if recorder.record_count >= state.max_records:
                return
            try:
                recorder.record(frame)
            except ObservationError:
                return
            if recorder.record_count == state.max_records:
                completed.set()

        async def bounded(awaitable: object) -> object:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("private-observation deadline expired")
            return await asyncio.wait_for(awaitable, remaining)

        async def cleanup_step(awaitable: object) -> bool:
            remaining = deadline - time.monotonic()
            timeout = max(0.01, min(1.0, remaining if remaining > 0 else 0.1))
            try:
                await asyncio.wait_for(awaitable, timeout)
            except BaseException:
                return False
            return True

        try:
            transport = BleakTransport(state.address, timeout=state.timeout)
            remove_listener = transport.add_disconnect_listener(on_disconnect)
            await bounded(transport.connect())
            metadata = await bounded(transport.gatt_characteristics())
            target = select_observation_target(
                metadata,
                connection_generation=transport.connection_generation,
                service_uuid=service_uuid,
                characteristic_uuid=characteristic_uuid,
                instance_id=instance_id,
            )
            authority = prepare_observation_authority(
                plan,
                connection_generation=transport.connection_generation,
                target=target,
            )
            try:
                token = await bounded(
                    transport._private_observation_subscribe(
                        target, on_notification, authority, 0.1
                    )
                )
            except (PermissionError, ConnectionError, RuntimeError, ValueError):
                status = ObservationStatus.SUBSCRIPTION_FAILED
            else:
                completion = asyncio.create_task(completed.wait())
                disconnection = asyncio.create_task(disconnected.wait())
                try:
                    done, _pending = await asyncio.wait(
                        (completion, disconnection),
                        timeout=max(0, deadline - time.monotonic()),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if completion in done and completed.is_set():
                        status = ObservationStatus.COMPLETED
                    elif disconnection in done and disconnected.is_set():
                        status = ObservationStatus.DISCONNECTED
                    else:
                        status = ObservationStatus.TIMED_OUT
                finally:
                    for task in (completion, disconnection):
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(completion, disconnection, return_exceptions=True)
        except asyncio.CancelledError as exc:
            cancelled = exc
            status = ObservationStatus.CANCELLED
        except TimeoutError:
            status = ObservationStatus.TIMED_OUT
        except ObservationError:
            status = ObservationStatus.ROUTE_UNAVAILABLE
        except Exception:
            status = ObservationStatus.CONNECTION_FAILED
        finally:
            if token is not None and transport is not None:
                cleanup["unsubscribe"] = (
                    "confirmed"
                    if await cleanup_step(transport._private_observation_unsubscribe(token))
                    else "uncertain"
                )
            if transport is not None:
                cleanup["close"] = (
                    "confirmed" if await cleanup_step(transport.close()) else "uncertain"
                )
            if remove_listener is not None:
                remove_listener()
            if "uncertain" in cleanup.values() and status is not ObservationStatus.CANCELLED:
                status = ObservationStatus.CLEANUP_UNCERTAIN
            try:
                summary = recorder.finish(capture_status=status.value)
            except ObservationError:
                raise ObservationError("private_output_failed") from None
            result = object.__new__(ObservationResult)
            _RESULTS[result] = (status.value, int(summary["record_count"]), cleanup)
        if cancelled is not None:
            raise cancelled
        return result
