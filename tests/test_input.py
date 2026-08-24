import pytest

from jring.input import InputMapper, SensorEvent, parse_binding


class RecordingSink:
    def __init__(self):
        self.actions = []

    def emit(self, action):
        self.actions.append(action)


def test_step_can_map_to_allowlisted_mouse_or_keyboard_actions():
    click = parse_binding("step=click:left")
    key = parse_binding("step=key:space")

    assert click.action.description == "left mouse click"
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
