import sys
from types import SimpleNamespace

import pytest

from jring.input import (
    InputAction,
    InputMapper,
    SensorEvent,
    UInputSink,
    input_action_inventory,
    parse_binding,
)


class RecordingSink:
    def __init__(self):
        self.actions = []

    def emit(self, action):
        self.actions.append(action)


def test_step_can_map_to_allowlisted_mouse_or_keyboard_actions():
    click = parse_binding("step=click:left")
    key = parse_binding("step=key:space")

    assert click.action.description == "primary (left) mouse click"
    assert key.action.description == "Space key"

    sink = RecordingSink()
    mapper = InputMapper((click,))
    assert mapper.dispatch(SensorEvent("step"), sink)
    assert sink.actions == [click.action]


@pytest.mark.parametrize(
    "mapping",
    [
        "step=shell:notify-send",
        "step=key:KEY_F13",
        "step=click:side",
        "heart_rate=key:space",
        "not-a-mapping",
    ],
)
def test_shell_mapping_is_rejected(mapping):
    with pytest.raises(ValueError):
        parse_binding(mapping)


def test_input_action_inventory_is_complete_and_stable():
    assert input_action_inventory() == {
        "events": [
            {
                "name": "step",
                "availability": "simulator_only",
                "hardware_verified": False,
            }
        ],
        "actions": [
            {"kind": "key", "name": "space", "labels": ["space"], "description": "Space key"},
            {"kind": "key", "name": "enter", "labels": ["enter"], "description": "Enter key"},
            {"kind": "key", "name": "escape", "labels": ["escape"], "description": "Escape key"},
            {"kind": "key", "name": "left", "labels": ["left"], "description": "Left arrow key"},
            {"kind": "key", "name": "right", "labels": ["right"], "description": "Right arrow key"},
            {"kind": "key", "name": "up", "labels": ["up"], "description": "Up arrow key"},
            {"kind": "key", "name": "down", "labels": ["down"], "description": "Down arrow key"},
            {"kind": "key", "name": "page-up", "labels": ["page-up"], "description": "Page Up key"},
            {"kind": "key", "name": "page-down", "labels": ["page-down"], "description": "Page Down key"},
            {
                "kind": "click", "name": "primary", "labels": ["primary", "left"],
                "description": "primary (left) mouse click",
            },
            {
                "kind": "click", "name": "secondary", "labels": ["secondary", "right"],
                "description": "secondary (right) mouse click",
            },
            {
                "kind": "click", "name": "middle", "labels": ["middle"],
                "description": "middle mouse click",
            },
        ],
        "hardware_events": [],
    }


def test_mouse_aliases_are_deterministic():
    assert parse_binding("step=click:primary") == parse_binding("step=click:left")
    assert parse_binding("step=click:secondary") == parse_binding("step=click:right")


def test_uinput_exposes_only_selected_capabilities(monkeypatch):
    created = []

    class FakeUInput:
        def __init__(self, capabilities, *, name):
            created.append((capabilities, name))

        def close(self):
            pass

    ecodes = SimpleNamespace(EV_KEY=1, BTN_LEFT=272, BTN_RIGHT=273, KEY_SPACE=57)
    monkeypatch.setitem(sys.modules, "evdev", SimpleNamespace(UInput=FakeUInput, ecodes=ecodes))

    sink = UInputSink((parse_binding("step=click:primary").action,))
    sink.close()

    assert created == [({1: [272]}, "JRing input mapper")]


def test_unsupported_action_fails_before_uinput_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "evdev", None)
    unsupported = InputAction("key", "f13", "KEY_F13", "F13 key")

    with pytest.raises(ValueError, match="unsupported input action"):
        UInputSink((unsupported,))
