from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Protocol

from .errors import UnavailableError


@dataclass(frozen=True)
class SensorEvent:
    kind: str


@dataclass(frozen=True, init=False)
class StepCounterPreviewCandidate:
    """Non-dispatchable candidate from experimental cumulative-counter logic."""

    kind: str
    preview_event_kind: str
    live_eligible: bool
    hardware_eligible: bool
    input_eligible: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("step-counter preview candidates are adapter-owned")

    @classmethod
    def _create(cls) -> "StepCounterPreviewCandidate":
        candidate = object.__new__(cls)
        object.__setattr__(candidate, "kind", "experimental_step_counter_preview")
        object.__setattr__(candidate, "preview_event_kind", "step")
        object.__setattr__(candidate, "live_eligible", False)
        object.__setattr__(candidate, "hardware_eligible", False)
        object.__setattr__(candidate, "input_eligible", False)
        return candidate


@dataclass(frozen=True)
class InputAction:
    kind: str
    value: str
    code: str
    description: str


@dataclass(frozen=True)
class InputBinding:
    event_kind: str
    action: InputAction


class InputSink(Protocol):
    def emit(self, action: InputAction) -> None: ...


_EVENTS = ("step",)
_KEYS = {
    "space": ("KEY_SPACE", "Space key"),
    "enter": ("KEY_ENTER", "Enter key"),
    "escape": ("KEY_ESC", "Escape key"),
    "left": ("KEY_LEFT", "Left arrow key"),
    "right": ("KEY_RIGHT", "Right arrow key"),
    "up": ("KEY_UP", "Up arrow key"),
    "down": ("KEY_DOWN", "Down arrow key"),
    "page-up": ("KEY_PAGEUP", "Page Up key"),
    "page-down": ("KEY_PAGEDOWN", "Page Down key"),
}
_CLICKS = {
    "primary": ("BTN_LEFT", "primary (left) mouse click"),
    "secondary": ("BTN_RIGHT", "secondary (right) mouse click"),
    "middle": ("BTN_MIDDLE", "middle mouse click"),
}
_CLICK_ALIASES = {
    "primary": "primary",
    "left": "primary",
    "secondary": "secondary",
    "right": "secondary",
    "middle": "middle",
}


def input_action_inventory() -> dict[str, list[dict[str, object]]]:
    """Return the stable, local vocabulary accepted by :func:`parse_binding`."""
    actions: list[dict[str, object]] = [
        {
            "kind": "key",
            "name": name,
            "labels": [name],
            "description": description,
        }
        for name, (_code, description) in _KEYS.items()
    ]
    click_labels = {
        "primary": ["primary", "left"],
        "secondary": ["secondary", "right"],
        "middle": ["middle"],
    }
    actions.extend(
        {
            "kind": "click",
            "name": name,
            "labels": click_labels[name],
            "description": description,
        }
        for name, (_code, description) in _CLICKS.items()
    )
    return {
        "events": [
            {
                "name": name,
                "availability": "simulator_only",
                "hardware_verified": False,
            }
            for name in _EVENTS
        ],
        "actions": actions,
        "hardware_events": [],
    }


def parse_binding(specification: str) -> InputBinding:
    try:
        event_kind, action_specification = specification.split("=", 1)
        action_kind, value = action_specification.split(":", 1)
    except ValueError as exc:
        raise ValueError("input mapping must look like step=key:space or step=click:left") from exc
    if event_kind not in _EVENTS:
        raise ValueError(f"unsupported sensor event: {event_kind}")
    if action_kind == "key":
        choices = _KEYS
        canonical_value = value
    elif action_kind == "click":
        choices = _CLICKS
        canonical_value = _CLICK_ALIASES.get(value, value)
    else:
        choices = None
        canonical_value = value
    if choices is None or canonical_value not in choices:
        raise ValueError(f"unsupported input action: {action_specification}")
    code, description = choices[canonical_value]
    return InputBinding(
        event_kind,
        InputAction(action_kind, canonical_value, code, description),
    )


class InputMapper:
    def __init__(self, bindings: tuple[InputBinding, ...]):
        self._actions: dict[str, InputAction] = {}
        for binding in bindings:
            if binding.event_kind in self._actions:
                raise ValueError(f"duplicate input mapping for {binding.event_kind}")
            self._actions[binding.event_kind] = binding.action

    def action_for(self, event: SensorEvent) -> InputAction | None:
        if type(event) is not SensorEvent:
            return None
        return self._actions.get(event.kind)

    def dispatch(self, event: SensorEvent, sink: InputSink) -> bool:
        action = self.action_for(event)
        if action is None:
            return False
        sink.emit(action)
        return True


class ExperimentalStepCounterAdapter:
    """Turn isolated counter increments into neutral events without replaying batches."""

    def __init__(self, *, minimum_interval: float = 0.5):
        if not isinstance(minimum_interval, (int, float)) or isinstance(
            minimum_interval, bool
        ):
            raise TypeError("minimum interval must be a finite number")
        if not math.isfinite(minimum_interval) or minimum_interval < 0:
            raise ValueError("minimum interval must be finite and non-negative")
        self._minimum_interval = float(minimum_interval)
        self._connection_epoch: int | None = None
        self._counter: int | None = None
        self._last_observed_at: float | None = None
        self._last_emitted_at: float | None = None
        self._requires_rebaseline = False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def requires_rebaseline(self) -> bool:
        return self._requires_rebaseline

    @staticmethod
    def _validate_connection_epoch(connection_epoch: object) -> int:
        if type(connection_epoch) is not int:
            raise TypeError("connection generation must be an exact integer")
        if connection_epoch <= 0:
            raise ValueError("connection generation must be positive")
        return connection_epoch

    def _validate_observation(self, cumulative_steps: int, observed_at: float) -> float:
        if type(cumulative_steps) is not int:
            raise TypeError("cumulative step count must be an integer")
        if not 0 <= cumulative_steps <= 0xFFFFFFFF:
            raise ValueError("cumulative step count must fit an unsigned 32-bit value")
        if not isinstance(observed_at, (int, float)) or isinstance(observed_at, bool):
            raise TypeError("observation time must be a finite number")
        timestamp = float(observed_at)
        if not math.isfinite(timestamp):
            raise ValueError("observation time must be finite")
        if self._last_observed_at is not None and timestamp < self._last_observed_at:
            raise ValueError("observation time must be monotonic")
        return timestamp

    def rebaseline(
        self,
        *,
        connection_epoch: int,
        cumulative_steps: int,
        observed_at: float,
    ) -> None:
        """Explicitly accept a new counter baseline after a reset/stale sample."""

        connection_epoch = self._validate_connection_epoch(connection_epoch)
        timestamp = self._validate_observation(cumulative_steps, observed_at)
        if self._connection_epoch is None or connection_epoch != self._connection_epoch:
            raise ValueError("rebaseline requires the current connection generation")
        self._last_observed_at = timestamp
        self._counter = cumulative_steps
        self._requires_rebaseline = False

    def observe(
        self,
        *,
        connection_epoch: int,
        cumulative_steps: int,
        observed_at: float,
    ) -> StepCounterPreviewCandidate | None:
        connection_epoch = self._validate_connection_epoch(connection_epoch)
        timestamp = self._validate_observation(cumulative_steps, observed_at)

        if (
            self._connection_epoch is not None
            and connection_epoch < self._connection_epoch
        ):
            return None
        self._last_observed_at = timestamp
        if self._connection_epoch is None or connection_epoch > self._connection_epoch:
            self._connection_epoch = connection_epoch
            self._counter = cumulative_steps
            self._requires_rebaseline = False
            return None

        if self._requires_rebaseline:
            return None

        previous = self._counter
        if previous is None:
            self._requires_rebaseline = True
            return None
        if cumulative_steps == previous:
            return None
        if cumulative_steps < previous:
            self._counter = None
            self._requires_rebaseline = True
            return None
        self._counter = cumulative_steps
        if cumulative_steps - previous != 1:
            return None
        if (
            self._last_emitted_at is not None
            and timestamp - self._last_emitted_at < self._minimum_interval
        ):
            return None
        self._last_emitted_at = timestamp
        return StepCounterPreviewCandidate._create()


def _supported_action(action: InputAction) -> bool:
    choices = _KEYS if action.kind == "key" else _CLICKS if action.kind == "click" else {}
    definition = choices.get(action.value)
    return definition is not None and definition == (action.code, action.description)


class UInputSink:
    def __init__(self, actions: tuple[InputAction, ...]):
        if not actions or any(not _supported_action(action) for action in actions):
            raise ValueError("unsupported input action for uinput sink")
        try:
            from evdev import UInput, ecodes
        except ImportError as exc:
            raise UnavailableError("input injection requires the installed package dependencies") from exc
        codes = list(dict.fromkeys(getattr(ecodes, action.code) for action in actions))
        try:
            self._device = UInput({ecodes.EV_KEY: codes}, name="JRing input mapper")
        except OSError as exc:
            raise PermissionError(
                "cannot open Linux uinput; ensure /dev/uinput exists and your user has access"
            ) from exc
        self._ecodes = ecodes

    def emit(self, action: InputAction) -> None:
        code = getattr(self._ecodes, action.code)
        self._device.write(self._ecodes.EV_KEY, code, 1)
        self._device.syn()
        self._device.write(self._ecodes.EV_KEY, code, 0)
        self._device.syn()

    def close(self) -> None:
        self._device.close()


def create_uinput_sink(actions: tuple[InputAction, ...]) -> UInputSink:
    return UInputSink(actions)
