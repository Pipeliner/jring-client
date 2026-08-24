from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SensorEvent:
    kind: str


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


_EVENTS = frozenset({"step"})
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
    "left": ("BTN_LEFT", "left mouse click"),
    "right": ("BTN_RIGHT", "right mouse click"),
    "middle": ("BTN_MIDDLE", "middle mouse click"),
}


def parse_binding(specification: str) -> InputBinding:
    try:
        event_kind, action_specification = specification.split("=", 1)
        action_kind, value = action_specification.split(":", 1)
    except ValueError as exc:
        raise ValueError("input mapping must look like step=key:space or step=click:left") from exc
    if event_kind not in _EVENTS:
        raise ValueError(f"unsupported sensor event: {event_kind}")
    choices = _KEYS if action_kind == "key" else _CLICKS if action_kind == "click" else None
    if choices is None or value not in choices:
        raise ValueError(f"unsupported input action: {action_specification}")
    code, description = choices[value]
    return InputBinding(event_kind, InputAction(action_kind, value, code, description))


class InputMapper:
    def __init__(self, bindings: tuple[InputBinding, ...]):
        self._actions: dict[str, InputAction] = {}
        for binding in bindings:
            if binding.event_kind in self._actions:
                raise ValueError(f"duplicate input mapping for {binding.event_kind}")
            self._actions[binding.event_kind] = binding.action

    def action_for(self, event: SensorEvent) -> InputAction | None:
        return self._actions.get(event.kind)

    def dispatch(self, event: SensorEvent, sink: InputSink) -> bool:
        action = self.action_for(event)
        if action is None:
            return False
        sink.emit(action)
        return True


class UInputSink:
    def __init__(self):
        try:
            from evdev import UInput, ecodes
        except ImportError as exc:
            raise RuntimeError("input injection requires: pip install -e '.[input]'") from exc
        codes = [getattr(ecodes, code) for code, _description in (*_KEYS.values(), *_CLICKS.values())]
        try:
            self._device = UInput({ecodes.EV_KEY: codes}, name="JRing input mapper")
        except OSError as exc:
            raise RuntimeError(
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


def create_uinput_sink() -> UInputSink:
    return UInputSink()
