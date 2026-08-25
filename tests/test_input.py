import sys
from types import SimpleNamespace

import pytest

from jring.input import (
    InputAction,
    InputMapper,
    ExperimentalStepCounterAdapter,
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


def test_experimental_step_counter_baselines_and_emits_only_single_increments():
    adapter = ExperimentalStepCounterAdapter(minimum_interval=0.5)

    assert adapter.observe(connection_epoch=1, cumulative_steps=100, observed_at=1.0) is None
    assert adapter.observe(connection_epoch=1, cumulative_steps=101, observed_at=2.0) == SensorEvent("step")
    assert adapter.observe(connection_epoch=1, cumulative_steps=102, observed_at=2.1) is None
    assert adapter.observe(connection_epoch=1, cumulative_steps=103, observed_at=3.0) == SensorEvent("step")


def test_experimental_step_counter_never_replays_batches_resets_or_reconnects():
    adapter = ExperimentalStepCounterAdapter(minimum_interval=0.0)

    assert adapter.observe(connection_epoch=1, cumulative_steps=10, observed_at=1.0) is None
    assert adapter.observe(connection_epoch=1, cumulative_steps=14, observed_at=2.0) is None
    assert adapter.observe(connection_epoch=1, cumulative_steps=15, observed_at=3.0) == SensorEvent("step")
    assert adapter.observe(connection_epoch=1, cumulative_steps=2, observed_at=4.0) is None
    assert adapter.requires_rebaseline is True
    assert adapter.observe(connection_epoch=1, cumulative_steps=3, observed_at=5.0) is None
    assert adapter.requires_rebaseline is True
    adapter.rebaseline(connection_epoch=1, cumulative_steps=3, observed_at=5.0)
    assert adapter.requires_rebaseline is False
    assert adapter.observe(connection_epoch=1, cumulative_steps=4, observed_at=5.5) == SensorEvent("step")
    assert adapter.observe(connection_epoch=2, cumulative_steps=200, observed_at=6.0) is None


def test_step_counter_duplicate_quarantines_instead_of_manufacturing_next_click():
    adapter = ExperimentalStepCounterAdapter(minimum_interval=0.0)

    assert adapter.observe(connection_epoch=1, cumulative_steps=20, observed_at=1.0) is None
    assert adapter.observe(connection_epoch=1, cumulative_steps=20, observed_at=2.0) is None
    assert adapter.observe(connection_epoch=1, cumulative_steps=21, observed_at=3.0) is None
    assert adapter.requires_rebaseline is True


def test_experimental_step_counter_is_not_hardware_eligible_and_rejects_bad_input():
    adapter = ExperimentalStepCounterAdapter()

    assert adapter.hardware_eligible is False
    with pytest.raises((TypeError, ValueError)):
        adapter.observe(connection_epoch=1, cumulative_steps=True, observed_at=1.0)
    with pytest.raises((TypeError, ValueError)):
        adapter.observe(connection_epoch=1, cumulative_steps=2**32, observed_at=1.0)
    with pytest.raises((TypeError, ValueError)):
        adapter.observe(connection_epoch=1, cumulative_steps=1, observed_at=float("nan"))
