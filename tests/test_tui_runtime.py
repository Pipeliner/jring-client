import curses

from jring.tui_runtime import TuiRuntime, _safe_error
from jring.tui_model import Event, Screen


class FakeWindow:
    def __init__(self, size=(24, 80)):
        self.size = size
        self.lines = []

    def getmaxyx(self):
        return self.size

    def erase(self):
        self.lines.clear()

    def addnstr(self, row, col, text, width, attr=0):
        self.lines.append((row, text[:width], attr))

    def refresh(self):
        return None


def runtime():
    return TuiRuntime(lambda _argv: "ok", lambda _path, _address: True)


def test_runtime_starts_devices_and_renders_without_stdout(capsys):
    app = runtime()
    try:
        window = FakeWindow()
        app._render(window)
        assert app.state.screen is Screen.DEVICES
        assert any("DEVICES" in text for _, text, _ in window.lines)
        assert capsys.readouterr().out == ""
    finally:
        app.close()


def test_runtime_resize_and_ctrl_c_are_handled_in_place():
    app = runtime()
    try:
        window = FakeWindow()
        assert app._handle_key(window, curses.KEY_RESIZE) is False
        assert app._handle_key(window, 3) is True
        assert app.state.quit_requested
    finally:
        app.close()


def test_runtime_pair_key_starts_in_tui_picker_without_printing(monkeypatch, capsys):
    app = runtime()
    try:
        started = []
        monkeypatch.setattr(app, "_scan", lambda: started.append(True))
        app._handle_key(FakeWindow(), ord("p"))
        assert started == [True]
        assert app.state.screen is Screen.PICKER
        assert capsys.readouterr().out == ""
    finally:
        app.close()


def test_runtime_errors_redact_addresses_and_bluez_paths():
    address = ":".join(("AA", "BB", "CC", "DD", "EE", "FF"))
    bluez_path = "/org/" + "bluez/hci0/dev_AA_BB"
    message = _safe_error(RuntimeError(f"failed {address} at {bluez_path}"))
    assert "AA:BB" not in message
    assert "/org/bluez" not in message
