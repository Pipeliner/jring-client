"""One-attempt owner-hardware evidence canary with no runtime promotion.

This module is the only authority issuer for the initial ``getDeviceInfo`` canary.
Authority is process-local, identity-sealed, operation-specific, single-use, and valid
only while :class:`OwnerHardwareEvidenceRunner` owns the attempt.  Results are
observations, never live-operation eligibility.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
import math
import os
import platform
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import time
from typing import Callable
from weakref import WeakKeyDictionary

from .protocol import ProtocolError
from .vendor_gatt_preflight import (
    VendorGattPreflightCode,
    VendorGattRoute,
    resolve_vendor_gatt_route,
)
from .vendor_operation_registry import (
    OperationTerminalStatus,
    VendorOperationRegistryError,
    operation_registry_entry,
)
from .vendor_protocol import StaticQuery, encode_static_query
from .vendor_transport import OfflineVendorOperation


_CANARY_OPERATION = "getDeviceInfo"
_CONSENTS = frozenset({"connect", "subscribe", "write"})
_SLUG_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


class OwnerEvidenceError(ValueError):
    """Machine-stable, value-free owner-evidence policy rejection."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class OwnerEvidenceStatus(str, Enum):
    SUCCEEDED = "succeeded"
    CONNECTION_FAILED = "connection_failed"
    STALE_GENERATION = "stale_generation"
    ROUTE_UNAVAILABLE = "route_unavailable"
    SUBSCRIPTION_FAILED = "subscription_failed"
    NEGATIVE_CONTROL_FAILED = "negative_control_failed"
    WRITE_FAILED = "write_failed"
    TIMED_OUT = "timed_out"
    DISCONNECTED = "disconnected"
    MALFORMED_RESPONSE = "malformed_response"
    DEVICE_REJECTED = "device_rejected"
    CLEANUP_UNCERTAIN = "cleanup_uncertain"
    PRIVATE_OUTPUT_FAILED = "private_output_failed"
    CANCELLED = "cancelled"
    PRECOMPLETION_TERMINAL = "precompletion_terminal"
    NOTIFICATION_OVERFLOW = "notification_overflow"


@dataclass(frozen=True)
class _SelectionState:
    address: str
    expected_connection_generation: int | None
    used: bool = False


@dataclass(frozen=True)
class _NegativeControlState:
    operation_id: str
    used: bool = False


@dataclass
class _PlanState:
    operation_id: str
    address: str
    expected_connection_generation: int | None
    consent: frozenset[str]
    timeout: float
    private_output: Path
    parent_device: int
    parent_inode: int
    model_family: str
    firmware_major: str
    phase: str = "fresh"
    current_generation: int | None = None
    action_phase: str = "inactive"
    response_target: object | None = None
    request_target: object | None = None
    descriptor_target: object | None = None
    subscribe_remaining: int = 1
    write_remaining: int = 1
    unsubscribe_remaining: int = 1


@dataclass(frozen=True)
class _ResultState:
    status: OwnerEvidenceStatus
    attempt_status: OwnerEvidenceStatus
    cleanup_status: str
    evidence_commit_status: str
    completeness: str
    negative_control: str
    route_observation: dict[str, str]
    cleanup_calls: dict[str, int]
    cleanup_outcomes: dict[str, str]
    write_dispatch: str
    response_terminal: str
    operation_id: str
    model_family: str
    firmware_major: str
    linux_family: str
    python_minor: str
    bluez_major: str
    bleak_major: str


_SELECTIONS: WeakKeyDictionary[object, _SelectionState] = WeakKeyDictionary()
_CONTROLS: WeakKeyDictionary[object, _NegativeControlState] = WeakKeyDictionary()
_PLANS: WeakKeyDictionary[object, _PlanState] = WeakKeyDictionary()
_RESULTS: WeakKeyDictionary[object, _ResultState] = WeakKeyDictionary()


class OwnerEvidenceSelection:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use prepare_owner_evidence_selection")

    def __repr__(self) -> str:
        return "OwnerEvidenceSelection(selected=True, address=<redacted>)"


class OwnerNegativeControl:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use prepare_owner_negative_control")

    def __repr__(self) -> str:
        return "OwnerNegativeControl(operation=<redacted>)"


class OwnerEvidenceRunPlan:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use prepare_owner_evidence_run")

    @property
    def operation_id(self) -> str:
        return _plan_state(self).operation_id

    def public_payload(self) -> dict[str, object]:
        state = _plan_state(self)
        return {
            "operation_id": state.operation_id,
            "consent": sorted(state.consent),
            "negative_control": "required",
            "deadline": "bounded",
            "private_output": "mode_0600",
            "single_use": True,
        }

    def __repr__(self) -> str:
        return (
            "OwnerEvidenceRunPlan(operation_id='getDeviceInfo', "
            "selection=<redacted>, consent=<sealed>, deadline=<bounded>, "
            "private_output=<redacted>, single_use=True)"
        )


class OwnerEvidenceResult:
    __slots__ = ("__weakref__",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("owner evidence results are runner-owned")

    @property
    def status(self) -> OwnerEvidenceStatus:
        return _result_state(self).status

    @property
    def completeness(self) -> str:
        return _result_state(self).completeness

    @property
    def negative_control(self) -> str:
        return _result_state(self).negative_control

    @property
    def route_observation(self) -> dict[str, str]:
        return dict(_result_state(self).route_observation)

    @property
    def cleanup_calls(self) -> dict[str, int]:
        return dict(_result_state(self).cleanup_calls)

    @property
    def replay_allowed(self) -> bool:
        return False

    @property
    def automatic_retry(self) -> str:
        return "prohibited"

    def public_payload(self) -> dict[str, object]:
        state = _result_state(self)
        return {
            "schema_version": 1,
            "operation_id": state.operation_id,
            "attempt_status": state.attempt_status.value,
            "outcome_status": state.status.value,
            "cleanup_status": state.cleanup_status,
            "evidence_commit_status": state.evidence_commit_status,
            "completeness": state.completeness,
            "negative_control": state.negative_control,
            "firmware_support": "unknown",
            "vendor_authorization": "unknown",
            "hardware_verified": False,
            "live_eligible": False,
            "replay_allowed": False,
            "automatic_retry": "prohibited",
            "write_dispatch": state.write_dispatch,
            "response_terminal": state.response_terminal,
            "cleanup": dict(state.cleanup_outcomes),
        }

    def review_payload(self) -> dict[str, object]:
        state = _result_state(self)
        return {
            **self.public_payload(),
            "declared_model_family": state.model_family,
            "declared_firmware_major": state.firmware_major,
            "linux_family": state.linux_family,
            "python_minor": state.python_minor,
            "bluez_major": state.bluez_major,
            "bleak_major": state.bleak_major,
        }

    def __repr__(self) -> str:
        state = _result_state(self)
        return (
            "OwnerEvidenceResult("
            f"status={state.status.value!r}, completeness={state.completeness!r}, "
            f"negative_control={state.negative_control!r}, private=<redacted>, "
            "live_eligible=False, hardware_verified=False, replay_allowed=False)"
        )


def _plan_state(plan: object) -> _PlanState:
    if type(plan) is not OwnerEvidenceRunPlan:
        raise OwnerEvidenceError("invalid_plan")
    try:
        return _PLANS[plan]
    except KeyError as exc:
        raise OwnerEvidenceError("invalid_plan") from exc


def _result_state(result: object) -> _ResultState:
    if type(result) is not OwnerEvidenceResult:
        raise OwnerEvidenceError("invalid_result")
    try:
        return _RESULTS[result]
    except KeyError as exc:
        raise OwnerEvidenceError("invalid_result") from exc


def _finite_timeout(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0 < float(value) <= 30
    ):
        raise OwnerEvidenceError("invalid_deadline")
    return float(value)


def _validate_private_output(path: object) -> tuple[Path, os.stat_result]:
    if not isinstance(path, Path):
        raise OwnerEvidenceError("unsafe_private_output")
    try:
        details = path.lstat()
        parent = path.parent.stat()
    except OSError as exc:
        raise OwnerEvidenceError("unsafe_private_output") from exc
    if (
        not stat.S_ISREG(details.st_mode)
        or stat.S_IMODE(details.st_mode) != 0o600
        or details.st_uid != os.getuid()
        or details.st_nlink != 1
        or not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.getuid()
        or stat.S_IMODE(parent.st_mode) & 0o077
    ):
        raise OwnerEvidenceError("unsafe_private_output")
    return path, details


def _validate_private_destination(path: object) -> tuple[Path, os.stat_result]:
    if not isinstance(path, Path) or not path.name or path.name in {".", ".."}:
        raise OwnerEvidenceError("unsafe_private_output")
    try:
        path.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise OwnerEvidenceError("unsafe_private_output") from exc
    else:
        raise OwnerEvidenceError("private_output_exists")
    try:
        parent = path.parent.lstat()
    except OSError as exc:
        raise OwnerEvidenceError("unsafe_private_output") from exc
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.getuid()
        or stat.S_IMODE(parent.st_mode) & 0o077
        or not parent.st_mode & stat.S_IWUSR
        or not parent.st_mode & stat.S_IXUSR
    ):
        raise OwnerEvidenceError("unsafe_private_output")
    return path, parent


def prepare_owner_evidence_selection(
    candidates: tuple[str, ...],
    *,
    expected_connection_generation: int | None = None,
) -> OwnerEvidenceSelection:
    if (
        type(candidates) is not tuple
        or len(candidates) != 1
        or type(candidates[0]) is not str
        or not candidates[0]
    ):
        raise OwnerEvidenceError(
            "missing_selection" if not candidates else "ambiguous_selection"
        )
    if expected_connection_generation is not None and (
        isinstance(expected_connection_generation, bool)
        or not isinstance(expected_connection_generation, int)
        or expected_connection_generation <= 0
    ):
        raise OwnerEvidenceError("invalid_selection_generation")
    selection = object.__new__(OwnerEvidenceSelection)
    _SELECTIONS[selection] = _SelectionState(
        candidates[0], expected_connection_generation
    )
    return selection


def prepare_owner_negative_control(operation_id: str) -> OwnerNegativeControl:
    try:
        operation_registry_entry(operation_id)
    except VendorOperationRegistryError as exc:
        raise OwnerEvidenceError("unregistered_operation") from exc
    control = object.__new__(OwnerNegativeControl)
    _CONTROLS[control] = _NegativeControlState(operation_id)
    return control


def prepare_owner_evidence_run(
    *,
    operation_id: str,
    selection: OwnerEvidenceSelection | None,
    allow_connect: bool,
    allow_subscribe: bool,
    allow_write: bool,
    negative_control: OwnerNegativeControl | None,
    timeout: float,
    private_output: Path,
    model_family: str = "withheld",
    firmware_major: str = "withheld",
) -> OwnerEvidenceRunPlan:
    try:
        entry = operation_registry_entry(operation_id)
    except VendorOperationRegistryError as exc:
        raise OwnerEvidenceError("unregistered_operation") from exc
    if operation_id != _CANARY_OPERATION:
        raise OwnerEvidenceError("unsupported_evidence_operation")
    if (
        not entry.ring_facing
        or entry.terminal_status is not OperationTerminalStatus.OFFLINE_ONLY
        or entry.interface_route != "main_command"
        or entry.endpoint_role != "main_tx_rx"
        or entry.response_terminal_rule != "single_matched_response"
    ):
        raise OwnerEvidenceError("unsupported_evidence_operation")
    if selection is None:
        raise OwnerEvidenceError("missing_selection")
    if type(selection) is not OwnerEvidenceSelection or selection not in _SELECTIONS:
        raise OwnerEvidenceError("invalid_selection")
    selection_state = _SELECTIONS[selection]
    if selection_state.used:
        raise OwnerEvidenceError("stale_selection")
    for allowed, code in (
        (allow_connect, "missing_connect_consent"),
        (allow_subscribe, "missing_subscribe_consent"),
        (allow_write, "missing_write_consent"),
    ):
        if allowed is not True:
            raise OwnerEvidenceError(code)
    if negative_control is None:
        raise OwnerEvidenceError("missing_negative_control")
    if type(negative_control) is not OwnerNegativeControl:
        raise OwnerEvidenceError("invalid_negative_control")
    control_state = _CONTROLS.get(negative_control)
    if control_state is None or control_state.operation_id != operation_id:
        raise OwnerEvidenceError("invalid_negative_control")
    if control_state.used:
        raise OwnerEvidenceError("stale_negative_control")
    bounded_timeout = _finite_timeout(timeout)
    output, parent_details = _validate_private_destination(private_output)
    model_scope = _slug(model_family)
    firmware_scope = _slug(firmware_major)

    _SELECTIONS[selection] = _SelectionState(
        selection_state.address,
        selection_state.expected_connection_generation,
        True,
    )
    _CONTROLS[negative_control] = _NegativeControlState(operation_id, True)
    plan = object.__new__(OwnerEvidenceRunPlan)
    _PLANS[plan] = _PlanState(
        operation_id=operation_id,
        address=selection_state.address,
        expected_connection_generation=selection_state.expected_connection_generation,
        consent=_CONSENTS,
        timeout=bounded_timeout,
        private_output=output,
        parent_device=parent_details.st_dev,
        parent_inode=parent_details.st_ino,
        model_family=model_scope,
        firmware_major=firmware_scope,
    )
    return plan


def validate_owner_evidence_prerequisites(
    *,
    operation_id: str,
    allow_connect: bool,
    allow_subscribe: bool,
    allow_write: bool,
    negative_control: bool,
    timeout: float,
    private_output: Path,
    model_family: str,
    firmware_major: str,
) -> None:
    """Validate selection-independent gates before an optional active scan."""

    try:
        entry = operation_registry_entry(operation_id)
    except VendorOperationRegistryError as exc:
        raise OwnerEvidenceError("unregistered_operation") from exc
    if (
        operation_id != _CANARY_OPERATION
        or not entry.ring_facing
        or entry.terminal_status is not OperationTerminalStatus.OFFLINE_ONLY
        or entry.interface_route != "main_command"
        or entry.endpoint_role != "main_tx_rx"
        or entry.response_terminal_rule != "single_matched_response"
    ):
        raise OwnerEvidenceError("unsupported_evidence_operation")
    for allowed, code in (
        (allow_connect, "missing_connect_consent"),
        (allow_subscribe, "missing_subscribe_consent"),
        (allow_write, "missing_write_consent"),
    ):
        if allowed is not True:
            raise OwnerEvidenceError(code)
    if negative_control is not True:
        raise OwnerEvidenceError("missing_negative_control")
    _finite_timeout(timeout)
    _validate_private_destination(private_output)
    _slug(model_family)
    _slug(firmware_major)


def _require_canary_authority(
    authority: object,
    action: str,
    connection_generation: int | None,
    targets: tuple[object, ...] = (),
) -> None:
    state = _plan_state(authority)
    expected_phase = {
        "subscribe": "subscribing",
        "write": "writing",
        "unsubscribe": "unsubscribing",
    }.get(action)
    if state.phase != "active" or state.action_phase != expected_phase:
        raise PermissionError("owner-evidence authority is inactive")
    if (
        connection_generation is not None
        and state.current_generation != connection_generation
    ):
        raise PermissionError("owner-evidence authority generation mismatch")
    expected_targets = {
        "subscribe": (state.response_target, state.descriptor_target),
        "write": (state.request_target,),
        "unsubscribe": (),
    }[action]
    if len(targets) != len(expected_targets) or any(
        actual is not expected for actual, expected in zip(targets, expected_targets)
    ):
        raise PermissionError("owner-evidence authority target mismatch")
    budget_name = f"{action}_remaining"
    if getattr(state, budget_name) != 1:
        raise PermissionError("owner-evidence authority action was already consumed")
    setattr(state, budget_name, 0)
    state.action_phase = f"{action}_consumed"


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("owner-evidence deadline expired")
    return remaining


async def _bounded(awaitable: object, deadline: float):
    result = await asyncio.wait_for(awaitable, timeout=_remaining(deadline))
    _remaining(deadline)
    return result


def _private_payload(state: _ResultState) -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "private_owner_hardware_attempt",
        "operation_id": state.operation_id,
        "attempt_status": state.attempt_status.value,
        "outcome_status": state.status.value,
        "cleanup_status": state.cleanup_status,
        "evidence_commit_status": state.evidence_commit_status,
        "completeness": state.completeness,
        "negative_control": state.negative_control,
        "route": dict(state.route_observation),
        "cleanup": dict(state.cleanup_calls),
        "cleanup_outcomes": dict(state.cleanup_outcomes),
        "write_dispatch": state.write_dispatch,
        "response_terminal": state.response_terminal,
        "environment": {
            "model_family": state.model_family,
            "firmware_major": state.firmware_major,
            "linux_family": state.linux_family,
            "python_minor": state.python_minor,
            "bluez_major": state.bluez_major,
            "bleak_major": state.bleak_major,
        },
        "authority": {
            "repeat": False,
            "runtime": False,
            "input": False,
            "binding": False,
            "network": False,
            "ota": False,
            "publication": False,
        },
        "automatic_retry": "prohibited",
    }


def _write_exclusive_json_impl(
    path: Path,
    payload: dict[str, object],
    *,
    mode: int,
    unsafe_code: str,
    exists_code: str,
    restrictive_parent: bool,
    expected_parent: tuple[int, int] | None = None,
) -> None:
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    try:
        directory = os.open(path.parent, directory_flags)
    except OSError as exc:
        raise OwnerEvidenceError(unsafe_code) from exc
    temporary = None
    temporary_created = False
    published = False
    published_identity: tuple[int, int] | None = None
    temporary_name = f".{path.name}.jring-{secrets.token_hex(16)}.tmp"
    try:
        parent = os.fstat(directory)
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or (restrictive_parent and stat.S_IMODE(parent.st_mode) & 0o077)
            or (
                expected_parent is not None
                and (parent.st_dev, parent.st_ino) != expected_parent
            )
        ):
            raise OwnerEvidenceError(unsafe_code)
        try:
            os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise OwnerEvidenceError(exists_code)
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        temporary_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            temporary_flags |= os.O_NOFOLLOW
        temporary = os.open(
            temporary_name,
            temporary_flags,
            mode,
            dir_fd=directory,
        )
        temporary_created = True
        os.fchmod(temporary, mode)
        written = 0
        while written < len(encoded):
            count = os.write(temporary, encoded[written:])
            if count <= 0:
                raise OSError("private evidence write did not advance")
            written += count
        os.fsync(temporary)
        temporary_details = os.fstat(temporary)
        if (
            not stat.S_ISREG(temporary_details.st_mode)
            or stat.S_IMODE(temporary_details.st_mode) != mode
            or temporary_details.st_uid != os.getuid()
            or temporary_details.st_nlink != 1
        ):
            raise OwnerEvidenceError(unsafe_code)
        published_identity = (temporary_details.st_dev, temporary_details.st_ino)
        os.close(temporary)
        temporary = None
        try:
            os.link(
                temporary_name,
                path.name,
                src_dir_fd=directory,
                dst_dir_fd=directory,
                follow_symlinks=False,
            )
        except FileExistsError as exc:
            raise OwnerEvidenceError(exists_code) from exc
        published = True
        os.unlink(temporary_name, dir_fd=directory)
        temporary_created = False
        verification_flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            verification_flags |= os.O_NOFOLLOW
        verification = os.open(path.name, verification_flags, dir_fd=directory)
        try:
            final = os.fstat(verification)
            if (
                (final.st_dev, final.st_ino) != published_identity
                or not stat.S_ISREG(final.st_mode)
                or stat.S_IMODE(final.st_mode) != mode
                or final.st_uid != os.getuid()
                or final.st_nlink != 1
            ):
                raise OwnerEvidenceError(unsafe_code)
        finally:
            os.close(verification)
        os.fsync(directory)
        published = False
    finally:
        if temporary is not None:
            os.close(temporary)
        if published and published_identity is not None:
            try:
                current = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == published_identity:
                    os.unlink(path.name, dir_fd=directory)
            except FileNotFoundError:
                pass
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=directory)
            except FileNotFoundError:
                pass
        os.close(directory)


def _write_exclusive_json(
    path: Path,
    payload: dict[str, object],
    *,
    mode: int,
    unsafe_code: str,
    exists_code: str,
    restrictive_parent: bool,
    expected_parent: tuple[int, int] | None = None,
) -> None:
    try:
        _write_exclusive_json_impl(
            path,
            payload,
            mode=mode,
            unsafe_code=unsafe_code,
            exists_code=exists_code,
            restrictive_parent=restrictive_parent,
            expected_parent=expected_parent,
        )
    except OwnerEvidenceError:
        raise
    except OSError as exc:
        raise OwnerEvidenceError(unsafe_code) from exc


def _write_private(plan_state: _PlanState, result_state: _ResultState) -> None:
    _write_exclusive_json(
        plan_state.private_output,
        _private_payload(result_state),
        mode=0o600,
        unsafe_code="unsafe_private_output",
        exists_code="private_output_exists",
        restrictive_parent=True,
        expected_parent=(plan_state.parent_device, plan_state.parent_inode),
    )


def _environment() -> tuple[str, str, str, str]:
    try:
        linux = platform.freedesktop_os_release().get("ID", "linux").casefold()
    except (OSError, AttributeError):
        linux = platform.system().casefold() or "unknown"
    python_minor = f"{sys.version_info.major}.{sys.version_info.minor}"
    try:
        import bleak

        from importlib.metadata import version

        try:
            bleak_version = version("bleak")
        except Exception:
            bleak_version = getattr(bleak, "__version__")
        bleak_major = bleak_version.split(".", 1)[0]
        bleak_major = _slug(bleak_major)
    except Exception:
        bleak_major = "unknown"
    bluez = "unknown"
    bluetoothctl = shutil.which("bluetoothctl")
    if bluetoothctl is not None and bleak_major != "unknown":
        try:
            completed = subprocess.run(
                [bluetoothctl, "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.5,
            )
            bluez = next(
                (
                    part.split(".", 1)[0]
                    for part in completed.stdout.strip().split()
                    if part[:1].isdigit()
                ),
                "unknown",
            )
            bluez = _slug(bluez)
        except (OSError, subprocess.SubprocessError, OwnerEvidenceError):
            bluez = "unknown"
    return linux, python_minor, bluez, bleak_major


def _create_result(
    *,
    status: OwnerEvidenceStatus,
    attempt_status: OwnerEvidenceStatus | None = None,
    cleanup_status: str = "confirmed",
    evidence_commit_status: str = "committed",
    completeness: str,
    negative_control: str,
    route_observation: dict[str, str] | None,
    cleanup_calls: dict[str, int],
    cleanup_outcomes: dict[str, str],
    write_dispatch: str,
    response_terminal: str,
    model_family: str,
    firmware_major: str,
    environment: tuple[str, str, str, str],
) -> OwnerEvidenceResult:
    linux, python_minor, bluez, bleak = environment
    result = object.__new__(OwnerEvidenceResult)
    _RESULTS[result] = _ResultState(
        status=status,
        attempt_status=attempt_status or status,
        cleanup_status=cleanup_status,
        evidence_commit_status=evidence_commit_status,
        completeness=completeness,
        negative_control=negative_control,
        route_observation=dict(route_observation or {
            "route": "main",
            "service": "unknown",
            "request": "unknown",
            "response": "unknown",
            "cccd": "unknown",
        }),
        cleanup_calls=dict(cleanup_calls),
        cleanup_outcomes=dict(cleanup_outcomes),
        write_dispatch=write_dispatch,
        response_terminal=response_terminal,
        operation_id=_CANARY_OPERATION,
        model_family=model_family,
        firmware_major=firmware_major,
        linux_family=linux,
        python_minor=python_minor,
        bluez_major=bluez,
        bleak_major=bleak,
    )
    return result


class OwnerHardwareEvidenceRunner:
    """Execute one sealed canary through the production Bleak transport."""

    def __init__(self, *, transport_factory: object | None = None) -> None:
        self._interrupted_result: OwnerEvidenceResult | None = None
        if transport_factory is not None:
            from .bleak_transport import BleakTransport

            if transport_factory is not BleakTransport:
                raise TypeError("owner evidence requires the production BleakTransport")

    @property
    def interrupted_result(self) -> OwnerEvidenceResult | None:
        """Return only the sanitized result retained for an interrupted CLI run."""

        return self._interrupted_result

    async def run(self, plan: OwnerEvidenceRunPlan) -> OwnerEvidenceResult:
        from .bleak_transport import BleakTransport

        plan_state = _plan_state(plan)
        self._interrupted_result = None
        if plan_state.phase != "fresh":
            raise OwnerEvidenceError("stale_plan")
        plan_state.phase = "active"
        try:
            _output, current_parent = _validate_private_destination(
                plan_state.private_output
            )
            if (current_parent.st_dev, current_parent.st_ino) != (
                plan_state.parent_device,
                plan_state.parent_inode,
            ):
                raise OwnerEvidenceError("unsafe_private_output")
        except Exception:
            plan_state.phase = "spent"
            raise
        environment = _environment()
        started = time.monotonic()
        deadline = started + plan_state.timeout
        cleanup_reserve = min(1.0, max(0.01, plan_state.timeout * 0.2))
        work_deadline = deadline - cleanup_reserve
        if not math.isfinite(deadline) or work_deadline <= started:
            plan_state.phase = "spent"
            raise OwnerEvidenceError("invalid_deadline")

        transport = None
        subscription = None
        remove_listener: Callable[[], None] | None = None
        cleanup_calls = {"unsubscribe": 0, "close": 0}
        cleanup_outcomes = {"unsubscribe": "not_required", "close": "not_attempted"}
        route_observation: dict[str, str] | None = None
        status = OwnerEvidenceStatus.CONNECTION_FAILED
        control_status = "not_reached"
        write_invoked = False
        write_completed = False
        response_terminal = "not_observed"
        cancelled: asyncio.CancelledError | None = None
        callback_phase = "setup"
        premature_terminal = False
        notification_overflow = False
        disconnect_event = asyncio.Event()
        notifications: asyncio.Queue[tuple[str, bool | None]] = asyncio.Queue(
            maxsize=32
        )

        operation = OfflineVendorOperation.from_static_request(
            encode_static_query(StaticQuery.DEVICE_INFO)
        )

        def disconnected(_error: BaseException | None) -> None:
            disconnect_event.set()

        def notified(target: object, data: bytes) -> None:
            nonlocal premature_terminal, notification_overflow
            if target is not plan_state.response_target:
                return
            try:
                match, private_value = operation._match(target.uuid, data)
                kind = match.value
                integrity = getattr(private_value, "integrity_valid", None)
                integrity = integrity if type(integrity) is bool else None
            except ProtocolError:
                kind, integrity = "malformed", None
            if callback_phase == "writing" and kind != "unrelated":
                premature_terminal = True
                return
            if callback_phase not in {"negative_control", "awaiting_terminal"}:
                return
            try:
                notifications.put_nowait((kind, integrity))
            except asyncio.QueueFull:
                notification_overflow = True

        async def wait_for_event() -> tuple[str, bool | None] | None:
            notification_task = asyncio.create_task(notifications.get())
            disconnect_task = asyncio.create_task(disconnect_event.wait())
            tasks = (notification_task, disconnect_task)
            try:
                done, _pending = await asyncio.wait(
                    tasks,
                    timeout=_remaining(work_deadline),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not done:
                    return None
                _remaining(work_deadline)
                if disconnect_task in done and disconnect_event.is_set():
                    return ("disconnected", None)
                return notification_task.result()
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        async def cleanup_step(awaitable: object, steps_left: int) -> bool:
            nonlocal cancelled
            remaining = max(0.001, deadline - time.monotonic())
            timeout = max(0.001, remaining / max(1, steps_left))
            try:
                await asyncio.wait_for(awaitable, timeout=timeout)
            except asyncio.CancelledError as exc:
                if cancelled is None:
                    cancelled = exc
                return False
            except Exception:
                return False
            return True

        try:
            transport = BleakTransport(plan_state.address, timeout=plan_state.timeout)
            remove_listener = transport.add_disconnect_listener(disconnected)
            await _bounded(transport.connect(), work_deadline)
            generation = transport.connection_generation
            plan_state.current_generation = generation
            if (
                plan_state.expected_connection_generation is not None
                and generation != plan_state.expected_connection_generation
            ):
                status = OwnerEvidenceStatus.STALE_GENERATION
            else:
                services = await _bounded(transport.service_uuids(), work_deadline)
                metadata = await _bounded(
                    transport.gatt_characteristics(), work_deadline
                )
                route = resolve_vendor_gatt_route(
                    VendorGattRoute.MAIN,
                    services=services,
                    metadata=metadata,
                    connection_generation=generation,
                )
                if (
                    route.code is not VendorGattPreflightCode.STRUCTURALLY_READY
                    or route.request_target is None
                    or route.response_target is None
                    or route.cccd_target is None
                    or not transport.owns_target(route.request_target)
                    or not transport.owns_target(route.response_target)
                    or not transport.owns_descriptor_target(route.cccd_target)
                ):
                    status = OwnerEvidenceStatus.ROUTE_UNAVAILABLE
                else:
                    plan_state.request_target = route.request_target
                    plan_state.response_target = route.response_target
                    plan_state.descriptor_target = route.cccd_target
                    route_observation = {
                        "route": "main",
                        "service": "exact",
                        "request": "exact_owned_current_generation",
                        "response": "exact_owned_current_generation",
                        "cccd": "exact_owned_current_generation",
                    }
                    callback_phase = "negative_control"
                    plan_state.action_phase = "subscribing"
                    subscription = await _bounded(
                        transport._owner_evidence_subscribe(
                            route.response_target,
                            route.cccd_target,
                            notified,
                            plan,
                            lambda: None,
                            min(0.1, cleanup_reserve / 2),
                        ),
                        work_deadline,
                    )

                    control_end = min(
                        work_deadline,
                        time.monotonic()
                        + min(0.05, max(0.001, plan_state.timeout * 0.1)),
                    )
                    while time.monotonic() < control_end:
                        if notification_overflow:
                            status = OwnerEvidenceStatus.NOTIFICATION_OVERFLOW
                            control_status = "failed_before_write"
                            break
                        try:
                            item = await asyncio.wait_for(
                                notifications.get(),
                                timeout=_remaining(control_end),
                            )
                        except (TimeoutError, asyncio.TimeoutError):
                            break
                        if item[0] != "unrelated":
                            status = OwnerEvidenceStatus.NEGATIVE_CONTROL_FAILED
                            control_status = "failed_before_write"
                            break
                    else:
                        _remaining(work_deadline)
                    if control_status != "failed_before_write":
                        _remaining(work_deadline)
                        control_status = "passed_before_write"
                        callback_phase = "writing"
                        plan_state.action_phase = "writing"

                        def write_started() -> None:
                            nonlocal write_invoked
                            write_invoked = True

                        def write_finished() -> None:
                            nonlocal write_completed, callback_phase
                            write_completed = True
                            callback_phase = "awaiting_terminal"

                        await _bounded(
                            transport._owner_evidence_write(
                                route.request_target,
                                operation.closed_request_frame(),
                                plan,
                                write_started,
                                write_finished,
                            ),
                            work_deadline,
                        )
                        if premature_terminal:
                            status = OwnerEvidenceStatus.PRECOMPLETION_TERMINAL
                            response_terminal = "precompletion_terminal"
                        else:
                            while True:
                                if notification_overflow:
                                    status = OwnerEvidenceStatus.NOTIFICATION_OVERFLOW
                                    break
                                event = await wait_for_event()
                                if event is None:
                                    status = OwnerEvidenceStatus.TIMED_OUT
                                    break
                                kind, integrity = event
                                if kind == "unrelated":
                                    continue
                                if kind == "disconnected":
                                    status = OwnerEvidenceStatus.DISCONNECTED
                                elif kind == "malformed" or (
                                    kind == "success" and integrity is not True
                                ):
                                    status = OwnerEvidenceStatus.MALFORMED_RESPONSE
                                    response_terminal = "invalid"
                                elif kind == "failure":
                                    status = OwnerEvidenceStatus.DEVICE_REJECTED
                                    response_terminal = "matched_failure"
                                else:
                                    status = OwnerEvidenceStatus.SUCCEEDED
                                    response_terminal = "matched_success"
                                break
        except asyncio.CancelledError as exc:
            cancelled = exc
            status = OwnerEvidenceStatus.CANCELLED
        except (TimeoutError, asyncio.TimeoutError):
            status = OwnerEvidenceStatus.TIMED_OUT
        except (PermissionError, ProtocolError):
            status = (
                OwnerEvidenceStatus.WRITE_FAILED
                if write_invoked
                else OwnerEvidenceStatus.ROUTE_UNAVAILABLE
            )
        except Exception:
            status = (
                OwnerEvidenceStatus.WRITE_FAILED
                if write_invoked
                else OwnerEvidenceStatus.CONNECTION_FAILED
            )
        finally:
            attempt_status = status
            callback_phase = "cleanup"
            cleanup_uncertain = False
            steps_left = int(subscription is not None) + int(transport is not None)
            if subscription is not None and transport is not None:
                cleanup_calls["unsubscribe"] += 1
                plan_state.action_phase = "unsubscribing"
                unsubscribe_confirmed = await cleanup_step(
                    transport._owner_evidence_unsubscribe(subscription, plan),
                    steps_left,
                )
                cleanup_outcomes["unsubscribe"] = (
                    "confirmed" if unsubscribe_confirmed else "uncertain"
                )
                cleanup_uncertain = not unsubscribe_confirmed
                steps_left -= 1
            if transport is not None:
                cleanup_calls["close"] += 1
                close_confirmed = await cleanup_step(transport.close(), steps_left)
                cleanup_outcomes["close"] = (
                    "confirmed" if close_confirmed else "uncertain"
                )
                if not close_confirmed:
                    cleanup_uncertain = True
            if remove_listener is not None:
                try:
                    remove_listener()
                except Exception:
                    cleanup_uncertain = True
            if cancelled is not None:
                status = OwnerEvidenceStatus.CANCELLED
            elif cleanup_uncertain and write_invoked:
                status = OwnerEvidenceStatus.CLEANUP_UNCERTAIN
            completeness = (
                "succeeded"
                if attempt_status is OwnerEvidenceStatus.SUCCEEDED
                and not cleanup_uncertain
                and cancelled is None
                else "uncertain"
                if write_invoked
                else "aborted"
            )
            result = _create_result(
                status=status,
                attempt_status=attempt_status,
                cleanup_status="uncertain" if cleanup_uncertain else "confirmed",
                evidence_commit_status="committed",
                completeness=completeness,
                negative_control=control_status,
                route_observation=route_observation,
                cleanup_calls=cleanup_calls,
                cleanup_outcomes=cleanup_outcomes,
                write_dispatch=(
                    "completed" if write_completed else "started" if write_invoked else "not_started"
                ),
                response_terminal=response_terminal,
                model_family=plan_state.model_family,
                firmware_major=plan_state.firmware_major,
                environment=environment,
            )
            try:
                _write_private(plan_state, _result_state(result))
            except Exception:
                result = _create_result(
                    status=OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED,
                    attempt_status=attempt_status,
                    cleanup_status=(
                        "uncertain" if cleanup_uncertain else "confirmed"
                    ),
                    evidence_commit_status="failed",
                    completeness="uncertain" if write_invoked else "aborted",
                    negative_control=control_status,
                    route_observation=route_observation,
                    cleanup_calls=cleanup_calls,
                    cleanup_outcomes=cleanup_outcomes,
                    write_dispatch=(
                        "completed" if write_completed else "started" if write_invoked else "not_started"
                    ),
                    response_terminal=response_terminal,
                    model_family=plan_state.model_family,
                    firmware_major=plan_state.firmware_major,
                    environment=environment,
                )
            plan_state.action_phase = "inactive"
            plan_state.phase = "spent"
        if cancelled is not None:
            self._interrupted_result = result
            raise cancelled
        return result


def _slug(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 64
        or value in {".", ".."}
        or value[0] not in _SLUG_CHARS
        or any(character not in _SLUG_CHARS for character in value)
    ):
        raise OwnerEvidenceError("invalid_evidence_reference")
    return value


def render_approved_compatibility_row(
    result: OwnerEvidenceResult,
    *,
    review_decision: str,
    approved_evidence_reference: str,
) -> dict[str, object]:
    """Render a review candidate without mutating or authorizing the registry."""

    state = _result_state(result)
    reference = _slug(approved_evidence_reference)
    if review_decision not in {"promote", "reject"}:
        raise OwnerEvidenceError("invalid_review_decision")
    if review_decision == "promote" and (
        state.attempt_status is not OwnerEvidenceStatus.SUCCEEDED
        or state.cleanup_status != "confirmed"
        or state.evidence_commit_status != "committed"
    ):
        raise OwnerEvidenceError("invalid_promotion_decision")
    if review_decision == "promote" and any(
        value in {"unknown", "withheld"}
        for value in (
            state.model_family,
            state.firmware_major,
            state.linux_family,
            state.python_minor,
            state.bluez_major,
            state.bleak_major,
        )
    ):
        raise OwnerEvidenceError("incomplete_promotion_scope")
    public_status = (
        "candidate_success"
        if state.attempt_status is OwnerEvidenceStatus.SUCCEEDED
        else "device_rejected"
        if state.attempt_status is OwnerEvidenceStatus.DEVICE_REJECTED
        else "uncertain"
        if state.completeness == "uncertain"
        else "protocol_incompatible"
        if state.attempt_status is OwnerEvidenceStatus.MALFORMED_RESPONSE
        else "environment_unavailable"
        if state.attempt_status in {
            OwnerEvidenceStatus.CONNECTION_FAILED,
            OwnerEvidenceStatus.ROUTE_UNAVAILABLE,
            OwnerEvidenceStatus.STALE_GENERATION,
        }
        else "aborted"
    )
    return {
        "schema_version": 1,
        "record_type": "sanitized_owner_hardware_evidence",
        "declared_model_family": state.model_family,
        "declared_firmware_major": state.firmware_major,
        "scope_provenance": "owner_declared",
        "linux_family": state.linux_family,
        "python_minor": state.python_minor,
        "bluez_major": state.bluez_major,
        "bleak_major": state.bleak_major,
        "operation_id": state.operation_id,
        "operation_status": public_status,
        "approved_evidence_reference": reference,
        "review_decision": review_decision,
        "authority": {
            "live_eligible": False,
            "runtime_registry_changed": False,
            "repeat_authorized": False,
            "hardware_support_claimed": False,
        },
    }


def write_reviewed_compatibility_row(
    private_input: Path,
    review_receipt: Path,
    public_output: Path,
) -> dict[str, object]:
    """Load, review, and exclusively create one sanitized public row."""

    result = load_private_owner_evidence(private_input)
    receipt = load_owner_evidence_review(review_receipt)
    if receipt["private_record_digest"] != _review_digest(result):
        raise OwnerEvidenceError("review_receipt_mismatch")
    row = render_approved_compatibility_row(
        result,
        review_decision=str(receipt["review_decision"]),
        approved_evidence_reference=str(receipt["approved_evidence_reference"]),
    )
    if not isinstance(public_output, Path) or not public_output.name:
        raise OwnerEvidenceError("unsafe_public_output")
    try:
        public_output.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise OwnerEvidenceError("unsafe_public_output") from exc
    else:
        raise OwnerEvidenceError("public_output_exists")
    try:
        parent_details = public_output.parent.lstat()
    except OSError as exc:
        raise OwnerEvidenceError("unsafe_public_output") from exc
    if not stat.S_ISDIR(parent_details.st_mode) or parent_details.st_uid != os.getuid():
        raise OwnerEvidenceError("unsafe_public_output")

    _write_exclusive_json(
        public_output,
        row,
        mode=0o644,
        unsafe_code="unsafe_public_output",
        exists_code="public_output_exists",
        restrictive_parent=False,
        expected_parent=(parent_details.st_dev, parent_details.st_ino),
    )
    return row


_PRIVATE_FIELDS = frozenset({
    "schema_version",
    "record_type",
    "operation_id",
    "attempt_status",
    "outcome_status",
    "cleanup_status",
    "evidence_commit_status",
    "completeness",
    "negative_control",
    "route",
    "cleanup",
    "cleanup_outcomes",
    "write_dispatch",
    "response_terminal",
    "environment",
    "authority",
    "automatic_retry",
})


def _validated_private_state(payload: object) -> _ResultState:
    if type(payload) is not dict or set(payload) != _PRIVATE_FIELDS:
        raise OwnerEvidenceError("invalid_private_evidence")
    if (
        type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("record_type") != "private_owner_hardware_attempt"
        or payload.get("operation_id") != _CANARY_OPERATION
        or payload.get("automatic_retry") != "prohibited"
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    try:
        attempt_status = OwnerEvidenceStatus(payload["attempt_status"])
        status = OwnerEvidenceStatus(payload["outcome_status"])
    except (TypeError, ValueError) as exc:
        raise OwnerEvidenceError("invalid_private_evidence") from exc
    if attempt_status in {
        OwnerEvidenceStatus.CLEANUP_UNCERTAIN,
        OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED,
    }:
        raise OwnerEvidenceError("invalid_private_evidence")
    cleanup_status = payload.get("cleanup_status")
    evidence_commit_status = payload.get("evidence_commit_status")
    completeness = payload.get("completeness")
    if completeness not in {"succeeded", "aborted", "uncertain"} or (
        (attempt_status is OwnerEvidenceStatus.SUCCEEDED
        and status is OwnerEvidenceStatus.SUCCEEDED)
        != (completeness == "succeeded")
    ) or cleanup_status not in {"confirmed", "uncertain"} or (
        evidence_commit_status != "committed"
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    negative_control = payload.get("negative_control")
    if negative_control not in {
        "not_reached",
        "passed_before_write",
        "failed_before_write",
    }:
        raise OwnerEvidenceError("invalid_private_evidence")
    route = payload.get("route")
    cleanup = payload.get("cleanup")
    cleanup_outcomes = payload.get("cleanup_outcomes")
    write_dispatch = payload.get("write_dispatch")
    response_terminal = payload.get("response_terminal")
    environment = payload.get("environment")
    authority = payload.get("authority")
    exact_route = {
        "route": "main",
        "service": "exact",
        "request": "exact_owned_current_generation",
        "response": "exact_owned_current_generation",
        "cccd": "exact_owned_current_generation",
    }
    unknown_route = {
        "route": "main",
        "service": "unknown",
        "request": "unknown",
        "response": "unknown",
        "cccd": "unknown",
    }
    try:
        environment_valid = (
            type(environment) is dict
            and set(environment) == {
                "model_family", "firmware_major", "linux_family", "python_minor",
                "bluez_major", "bleak_major",
            }
            and all(
                type(value) is str and _slug(value) == value
                for value in environment.values()
            )
        )
    except OwnerEvidenceError:
        environment_valid = False
    if (
        type(route) is not dict
        or set(route) != {"route", "service", "request", "response", "cccd"}
        or route not in (exact_route, unknown_route)
        or type(cleanup) is not dict
        or set(cleanup) != {"unsubscribe", "close"}
        or any(type(value) is not int or value not in {0, 1} for value in cleanup.values())
        or type(cleanup_outcomes) is not dict
        or set(cleanup_outcomes) != {"unsubscribe", "close"}
        or cleanup_outcomes.get("unsubscribe") not in {
            "not_required", "confirmed", "uncertain"
        }
        or cleanup_outcomes.get("close") not in {
            "not_attempted", "confirmed", "uncertain"
        }
        or write_dispatch not in {"not_started", "started", "completed"}
        or response_terminal not in {
            "not_observed", "matched_success", "matched_failure", "invalid",
            "precompletion_terminal",
        }
        or not environment_valid
        or type(authority) is not dict
        or set(authority) != {
            "repeat", "runtime", "input", "binding", "network", "ota", "publication"
        }
        or any(value is not False for value in authority.values())
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    if attempt_status is OwnerEvidenceStatus.SUCCEEDED and (
        negative_control != "passed_before_write"
        or route != exact_route
        or cleanup != {"unsubscribe": 1, "close": 1}
        or write_dispatch != "completed"
        or response_terminal != "matched_success"
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    if status is OwnerEvidenceStatus.SUCCEEDED and (
        attempt_status is not OwnerEvidenceStatus.SUCCEEDED
        or cleanup_status != "confirmed"
        or cleanup_outcomes
        != {"unsubscribe": "confirmed", "close": "confirmed"}
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    if write_dispatch != "not_started" and (
        negative_control != "passed_before_write" or route != exact_route
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    if write_dispatch == "not_started" and (
        response_terminal != "not_observed" or completeness != "aborted"
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    terminal_contract = {
        OwnerEvidenceStatus.SUCCEEDED: "matched_success",
        OwnerEvidenceStatus.DEVICE_REJECTED: "matched_failure",
        OwnerEvidenceStatus.MALFORMED_RESPONSE: "invalid",
        OwnerEvidenceStatus.PRECOMPLETION_TERMINAL: "precompletion_terminal",
    }
    if attempt_status in terminal_contract and (
        write_dispatch != "completed"
        or response_terminal != terminal_contract[attempt_status]
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    if (write_dispatch == "not_started") != (completeness == "aborted"):
        raise OwnerEvidenceError("invalid_private_evidence")
    if any(
        (cleanup[name] == 0) != (
            cleanup_outcomes[name] in {"not_required", "not_attempted"}
        )
        for name in cleanup
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    any_cleanup_uncertain = "uncertain" in cleanup_outcomes.values()
    if cleanup_status == "confirmed" and any_cleanup_uncertain:
        raise OwnerEvidenceError("invalid_private_evidence")
    if status is OwnerEvidenceStatus.CLEANUP_UNCERTAIN and (
        cleanup_status != "uncertain" or write_dispatch == "not_started"
    ):
        raise OwnerEvidenceError("invalid_private_evidence")
    if status is OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED:
        raise OwnerEvidenceError("invalid_private_evidence")
    permitted_outcomes = {attempt_status}
    if cleanup_status == "uncertain" and write_dispatch != "not_started":
        permitted_outcomes.add(OwnerEvidenceStatus.CLEANUP_UNCERTAIN)
    if cleanup_status == "uncertain":
        permitted_outcomes.add(OwnerEvidenceStatus.CANCELLED)
    if attempt_status is OwnerEvidenceStatus.CANCELLED:
        permitted_outcomes.add(OwnerEvidenceStatus.CANCELLED)
    if status not in permitted_outcomes:
        raise OwnerEvidenceError("invalid_private_evidence")
    nonterminal = {
        OwnerEvidenceStatus.CONNECTION_FAILED,
        OwnerEvidenceStatus.STALE_GENERATION,
        OwnerEvidenceStatus.ROUTE_UNAVAILABLE,
        OwnerEvidenceStatus.SUBSCRIPTION_FAILED,
        OwnerEvidenceStatus.NEGATIVE_CONTROL_FAILED,
        OwnerEvidenceStatus.WRITE_FAILED,
        OwnerEvidenceStatus.TIMED_OUT,
        OwnerEvidenceStatus.DISCONNECTED,
        OwnerEvidenceStatus.CLEANUP_UNCERTAIN,
        OwnerEvidenceStatus.CANCELLED,
        OwnerEvidenceStatus.NOTIFICATION_OVERFLOW,
    }
    if attempt_status in nonterminal and response_terminal != "not_observed":
        raise OwnerEvidenceError("invalid_private_evidence")
    return _ResultState(
        status=status,
        attempt_status=attempt_status,
        cleanup_status=cleanup_status,
        evidence_commit_status=evidence_commit_status,
        completeness=completeness,
        negative_control=negative_control,
        route_observation=dict(route),
        cleanup_calls=dict(cleanup),
        cleanup_outcomes=dict(cleanup_outcomes),
        write_dispatch=write_dispatch,
        response_terminal=response_terminal,
        operation_id=_CANARY_OPERATION,
        model_family=environment["model_family"],
        firmware_major=environment["firmware_major"],
        linux_family=environment["linux_family"],
        python_minor=environment["python_minor"],
        bluez_major=environment["bluez_major"],
        bleak_major=environment["bleak_major"],
    )


def _read_restrictive_json(
    path: Path, *, unsafe_code: str, invalid_code: str
) -> object:
    try:
        validated_path, details = _validate_private_output(path)
    except OwnerEvidenceError as exc:
        raise OwnerEvidenceError(unsafe_code) from exc
    try:
        parent_details = validated_path.parent.lstat()
    except OSError as exc:
        raise OwnerEvidenceError(unsafe_code) from exc
    directory_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        directory_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        directory_flags |= os.O_NOFOLLOW
    try:
        directory = os.open(validated_path.parent, directory_flags)
    except OSError as exc:
        raise OwnerEvidenceError(unsafe_code) from exc
    descriptor = None
    try:
        opened_parent = os.fstat(directory)
        if (
            opened_parent.st_dev != parent_details.st_dev
            or opened_parent.st_ino != parent_details.st_ino
            or not stat.S_ISDIR(opened_parent.st_mode)
            or opened_parent.st_uid != os.getuid()
            or stat.S_IMODE(opened_parent.st_mode) & 0o077
        ):
            raise OwnerEvidenceError(unsafe_code)
        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(validated_path.name, flags, dir_fd=directory)
        current = os.fstat(descriptor)
        if (
            current.st_dev != details.st_dev
            or current.st_ino != details.st_ino
            or not stat.S_ISREG(current.st_mode)
            or stat.S_IMODE(current.st_mode) != 0o600
            or current.st_uid != os.getuid()
            or current.st_nlink != 1
            or current.st_size > 64 * 1024
        ):
            raise OwnerEvidenceError(unsafe_code)
        content = os.read(descriptor, 64 * 1024 + 1)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)
    if len(content) > 64 * 1024:
        raise OwnerEvidenceError(invalid_code)

    def unique_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise OwnerEvidenceError(invalid_code)
            result[key] = value
        return result

    try:
        payload = json.loads(
            content.decode("utf-8"), object_pairs_hook=unique_members
        )
    except OwnerEvidenceError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise OwnerEvidenceError(invalid_code) from exc
    return payload


def load_private_owner_evidence(path: Path) -> OwnerEvidenceResult:
    """Load one restrictive private record without exposing its path or contents."""

    payload = _read_restrictive_json(
        path,
        unsafe_code="unsafe_private_output",
        invalid_code="invalid_private_evidence",
    )
    state = _validated_private_state(payload)
    result = object.__new__(OwnerEvidenceResult)
    _RESULTS[result] = state
    return result


def _review_digest(result: OwnerEvidenceResult) -> str:
    encoded = json.dumps(
        _private_payload(_result_state(result)),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_owner_evidence_review(
    private_input: Path,
    review_output: Path,
    *,
    review_decision: str,
    approved_evidence_reference: str,
) -> dict[str, object]:
    """Create a private review receipt bound to the exact reviewed record."""

    result = load_private_owner_evidence(private_input)
    render_approved_compatibility_row(
        result,
        review_decision=review_decision,
        approved_evidence_reference=approved_evidence_reference,
    )
    try:
        output, parent = _validate_private_destination(review_output)
    except OwnerEvidenceError as exc:
        code = (
            "review_output_exists"
            if exc.code == "private_output_exists"
            else "unsafe_review_output"
        )
        raise OwnerEvidenceError(code) from exc
    receipt: dict[str, object] = {
        "schema_version": 1,
        "record_type": "private_owner_evidence_review",
        "private_record_digest": _review_digest(result),
        "review_decision": review_decision,
        "approved_evidence_reference": _slug(approved_evidence_reference),
        "authority": {
            "publication": False,
            "runtime": False,
            "repeat": False,
        },
    }
    _write_exclusive_json(
        output,
        receipt,
        mode=0o600,
        unsafe_code="unsafe_review_output",
        exists_code="review_output_exists",
        restrictive_parent=True,
        expected_parent=(parent.st_dev, parent.st_ino),
    )
    return receipt


def load_owner_evidence_review(path: Path) -> dict[str, object]:
    """Load and validate one private review receipt."""

    payload = _read_restrictive_json(
        path,
        unsafe_code="unsafe_review_receipt",
        invalid_code="invalid_review_receipt",
    )
    if (
        type(payload) is not dict
        or set(payload) != {
            "schema_version",
            "record_type",
            "private_record_digest",
            "review_decision",
            "approved_evidence_reference",
            "authority",
        }
        or type(payload.get("schema_version")) is not int
        or payload.get("schema_version") != 1
        or payload.get("record_type") != "private_owner_evidence_review"
        or payload.get("review_decision") not in {"promote", "reject"}
        or type(payload.get("private_record_digest")) is not str
        or len(payload["private_record_digest"]) != 64
        or any(
            character not in "0123456789abcdef"
            for character in payload["private_record_digest"]
        )
        or payload.get("authority")
        != {"publication": False, "runtime": False, "repeat": False}
    ):
        raise OwnerEvidenceError("invalid_review_receipt")
    try:
        _slug(payload.get("approved_evidence_reference"))
    except OwnerEvidenceError as exc:
        raise OwnerEvidenceError("invalid_review_receipt") from exc
    return dict(payload)


__all__ = [
    "OwnerEvidenceError",
    "OwnerEvidenceResult",
    "OwnerEvidenceRunPlan",
    "OwnerEvidenceSelection",
    "OwnerEvidenceStatus",
    "OwnerHardwareEvidenceRunner",
    "OwnerNegativeControl",
    "load_private_owner_evidence",
    "load_owner_evidence_review",
    "prepare_owner_evidence_run",
    "prepare_owner_evidence_selection",
    "prepare_owner_negative_control",
    "validate_owner_evidence_prerequisites",
    "render_approved_compatibility_row",
    "write_reviewed_compatibility_row",
    "write_owner_evidence_review",
]
