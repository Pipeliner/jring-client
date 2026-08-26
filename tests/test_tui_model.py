from jring.discovery import SelectionCandidate
from jring.tui_model import Event, Screen, TuiState, reduce, render_model


def candidate(name, *, likely=False, rssi=-70, alias="device"):
    return SelectionCandidate(
        alias=alias, likely_jring=likely, service_uuids=(), rssi=rssi,
        _address=":".join(("AA", "BB", "CC", "DD", "EE", "FF")),
        display_name=name,
    )


def test_default_state_is_devices_without_radio_work():
    state = TuiState.initial()
    assert state.screen is Screen.DEVICES
    assert state.candidates == ()
    assert state.scan_generation == 0


def test_refresh_enters_scanning_and_completion_returns_sorted_devices():
    state = reduce(TuiState.initial(), Event.key("r"))
    assert state.screen is Screen.SCANNING
    assert state.scan_generation == 1
    state = reduce(state, Event.scan_completed(1, (
        candidate("Keyboard", rssi=-30, alias="b"),
        candidate("SR08 JRing", likely=True, rssi=-80, alias="a"),
    )))
    assert state.screen is Screen.DEVICES
    assert [item.display_name for item in state.candidates] == ["SR08 JRing", "Keyboard"]


def test_pair_from_empty_devices_opens_picker_and_accepts_scan_result_in_place():
    state = reduce(TuiState.initial(), Event.key("p"))
    assert state.screen is Screen.PICKER
    assert state.scan_generation == 1
    state = reduce(state, Event.scan_completed(1, (candidate("SR08", likely=True),)))
    assert state.screen is Screen.PICKER
    assert state.candidates[0].display_name == "SR08"


def test_stale_scan_result_cannot_replace_current_results():
    state = reduce(TuiState.initial(), Event.key("r"))
    state = reduce(state, Event.key("r"))
    state = reduce(state, Event.scan_completed(1, (candidate("old"),)))
    assert state.screen is Screen.SCANNING
    assert state.candidates == ()


def test_escape_cancels_modal_and_ctrl_c_quits_root():
    state = reduce(TuiState.initial(), Event.key("p"))
    assert state.screen is Screen.PICKER
    assert reduce(state, Event.key("escape")).screen is Screen.DEVICES
    assert reduce(TuiState.initial(), Event.key("ctrl-c")).quit_requested


def test_render_model_has_accessible_screen_contract():
    model = render_model(TuiState.initial())
    assert set(("screen", "title", "purpose", "body", "focus_index", "status", "keys")) <= set(model)
    assert model["screen"] == "devices"
    assert "simulator" not in model["title"].lower()
