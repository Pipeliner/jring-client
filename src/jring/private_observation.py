"""Fail-closed planning for a future private owner-observation command."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import stat
from weakref import WeakKeyDictionary


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


_PLANS: WeakKeyDictionary[object, _PlanState] = WeakKeyDictionary()


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
    _PLANS[plan] = _PlanState(address, timeout, max_records, private_output)
    return plan
