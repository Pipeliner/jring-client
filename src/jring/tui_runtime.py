"""Event-driven curses runtime for the JRing TUI."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
try:
    import curses
except ImportError:  # pragma: no cover - exercised by minimal non-curses Python builds
    curses = None  # type: ignore[assignment]
import os
import re
import time
from typing import Any, Callable

from .discovery import SelectionCandidate, discover_for_selection
from .tui_model import Event, Screen, TuiState, reduce, render_model

_ADDRESS = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")
_BLUEZ_PATH = re.compile(r"/org/bluez(?:/[A-Za-z0-9_]+)+")


def _safe_error(exc: BaseException) -> str:
    text = _BLUEZ_PATH.sub("[redacted Bluetooth path]", _ADDRESS.sub("[redacted device]", str(exc))).strip()
    return text or "the operation failed"


class TuiRuntime:
    def __init__(self, command: Callable[[list[str]], str], store_address: Callable[[str, str], bool]):
        self.command = command
        self.store_address = store_address
        self.state = TuiState.initial()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="jring-tui")
        self.future: Future[Any] | None = None
        self.active_operation: str | None = None

    def close(self) -> None:
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def dispatch(self, event: Event) -> None:
        self.state = reduce(self.state, event)

    def _scan(self) -> None:
        generation = self.state.scan_generation
        self.future = self.executor.submit(lambda: asyncio.run(discover_for_selection(timeout=5.0)))
        self.future._jring_generation = generation  # type: ignore[attr-defined]

    def _start_task(self, argv: list[str]) -> None:
        self.active_operation = argv[0] if argv else None
        self.future = self.executor.submit(self.command, argv)

    def _set_task_state(self, label: str, argv: list[str]) -> None:
        self.state = self.state.__class__(**{**self.state.__dict__, "screen": Screen.TASK_RUNNING,
                                             "status": f"Running {label}…",
                                             "body": "The task is running; Ctrl-C cancels waiting."})
        self._start_task(argv)

    @staticmethod
    def _prompt_path(stdscr: Any, current: str | None = None) -> str | None:
        default = current or "~/.config/jring/address"
        width = max(1, stdscr.getmaxyx()[1] - 1)
        stdscr.erase()
        stdscr.addnstr(0, 0, " SELECT ADDRESS FILE ", width, curses.A_REVERSE)
        stdscr.addnstr(2, 0, f"Path [{default}] (Enter accepts, Ctrl-C/Esc cancels):", width)
        stdscr.refresh(); stdscr.nodelay(False); curses.echo()
        try:
            value = stdscr.getstr(3, 0, min(240, width)).decode("utf-8").strip()
        except (KeyboardInterrupt, curses.error):
            return None
        finally:
            curses.noecho(); stdscr.nodelay(True)
        return os.path.expanduser(value or default)

    def _poll(self) -> None:
        if not self.future or not self.future.done():
            return
        future, self.future = self.future, None
        if future.cancelled():
            return
        try:
            value = future.result()
            if isinstance(value, list):
                generation = getattr(future, "_jring_generation", self.state.scan_generation)
                self.dispatch(Event.scan_completed(generation, value))
            else:
                operation = self.active_operation
                self.active_operation = None
                if operation in {"pair", "trust"}:
                    text = str(value).lower()
                    outcome = "paired" if "paired" in text else "trusted" if "trusted" in text else "rejected"
                    self.dispatch(Event.task_completed(self.state.scan_generation, operation, outcome))
                else:
                    self.state = self.state.__class__(**{**self.state.__dict__, "screen": Screen.RESULT, "status": "Task complete.", "body": str(value)})
        except Exception as exc:
            self.state = self.state.__class__(**{**self.state.__dict__, "screen": Screen.ERROR, "status": "Task failed; no automatic retry.", "body": _safe_error(exc)})

    @staticmethod
    def _draw_lines(stdscr: Any, lines: list[str], start: int, height: int, width: int) -> None:
        for row, line in enumerate(lines, start=start):
            if row >= height - 1:
                break
            clean = "".join(char if char.isprintable() or char == "\t" else "�" for char in line)
            try:
                stdscr.addnstr(row, 0, clean, max(1, width - 1))
            except curses.error:
                pass

    def _render(self, stdscr: Any) -> None:
        model = render_model(self.state)
        height, width = stdscr.getmaxyx()
        stdscr.erase()
        try:
            stdscr.addnstr(0, 0, f" {model['title']} ", max(1, width - 1), curses.A_REVERSE)
            stdscr.addnstr(1, 0, str(model["purpose"]), max(1, width - 1))
            self._draw_lines(stdscr, str(model["body"]).splitlines(), 3, height, width)
            stdscr.addnstr(max(0, height - 2), 0, str(model["status"]), max(1, width - 1), curses.A_BOLD)
            stdscr.addnstr(max(0, height - 1), 0, str(model["keys"]), max(1, width - 1))
        except curses.error:
            pass
        stdscr.refresh()

    def _handle_key(self, stdscr: Any, key: int) -> bool:
        if key == curses.KEY_RESIZE:
            try:
                curses.update_lines_cols()
            except curses.error:
                pass
            return False
        if key in (3, 27):
            self.dispatch(Event.key("ctrl-c" if key == 3 else "escape"))
            return self.state.quit_requested
        if key in (ord("q"), ord("Q")):
            self.dispatch(Event.key("q"))
            return self.state.quit_requested
        if key in (ord("r"), ord("R")) and self.state.screen is Screen.DEVICES:
            self.dispatch(Event.key("r")); self._scan(); return False
        if key in (ord("r"), ord("R")) and self.state.screen is Screen.PICKER:
            self.dispatch(Event.key("p")); self._scan(); return False
        if key in (ord("r"), ord("R")) and self.state.screen in {Screen.ERROR, Screen.RESULT}:
            self.dispatch(Event.key("r")); self._scan(); return False
        if key in (ord("p"), ord("P")) and self.state.screen is Screen.DEVICES:
            self.dispatch(Event.key("p")); self._scan(); return False
        if self.state.screen is Screen.DEVICES and key in (ord("v"), ord("V")):
            self._set_task_state("offline simulator", ["status", "--simulate"]); return False
        if self.state.screen is Screen.DEVICES and key in (ord("d"), ord("D")):
            self._set_task_state("local readiness check", ["doctor"]); return False
        if self.state.screen is Screen.DEVICES and key in (ord("i"), ord("I")):
            self._set_task_state("input action inventory", ["input-actions"]); return False
        if self.state.screen is Screen.DEVICES and key in (ord("s"), ord("S"), ord("c"), ord("C")):
            command = "status" if key in (ord("s"), ord("S")) else "capabilities"
            path = self._prompt_path(stdscr)
            if path:
                self._set_task_state(command, [command, "--address-file", path])
            return False
        if self.state.screen is Screen.PICKER and key in (curses.KEY_DOWN, curses.KEY_UP, ord("j"), ord("k"), 10, 13):
            self.dispatch(Event.key({curses.KEY_DOWN: "down", curses.KEY_UP: "up", ord("j"): "j", ord("k"): "k"}.get(key, "enter")))
            return False
        if self.state.screen is Screen.PICKER and ord("1") <= key <= ord("9"):
            index = key - ord("1")
            if index < len(self.state.candidates):
                self.state = self.state.__class__(**{**self.state.__dict__, "focus_index": index})
                self.dispatch(Event.key("enter"))
            return False
        if self.state.screen is Screen.PAIR_CONFIRM and key in (ord("y"), ord("Y"), 10, 13) and self.state.selected_candidate:
            selected = self.state.selected_candidate
            path = self._prompt_path(stdscr, self.state.address_file)
            if not path:
                return False
            if self.store_address(path, selected.connection_address()):
                self.state = self.state.__class__(**{**self.state.__dict__, "address_file": path})
                self.dispatch(Event.key("confirm-pair"))
                self._start_task(["pair", "--address-file", path, "--allow-pairing"])
            return False
        if self.state.screen is Screen.TRUST_CONFIRM and key in (ord("t"), ord("T")) and self.state.selected_candidate:
            path = self.state.address_file or os.path.expanduser("~/.config/jring/address")
            self.dispatch(Event.key("confirm-trust"))
            self._start_task(["trust", "--address-file", path, "--allow-trust"])
            return False
        if self.state.screen is Screen.TRUST_CONFIRM and key in (ord("n"), ord("N")):
            self.dispatch(Event.key("escape")); return False
        return False

    def run(self, stdscr: Any) -> int:
        curses.curs_set(0); stdscr.nodelay(True); stdscr.keypad(True); stdscr.timeout(50)
        try:
            while not self.state.quit_requested:
                self._poll(); self._render(stdscr)
                key = stdscr.getch()
                if key != curses.ERR and self._handle_key(stdscr, key):
                    break
                time.sleep(0.01)
        finally:
            self.close()
        return 0
