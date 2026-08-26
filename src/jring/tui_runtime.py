"""Event-driven curses runtime for the JRing TUI."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
import curses
import os
import time
from typing import Any, Callable

from .discovery import SelectionCandidate, discover_for_selection
from .tui_model import Event, Screen, TuiState, reduce, render_model


class TuiRuntime:
    def __init__(self, command: Callable[[list[str]], str], store_address: Callable[[str, str], bool]):
        self.command = command
        self.store_address = store_address
        self.state = TuiState.initial()
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="jring-tui")
        self.future: Future[Any] | None = None
        self._cancelled = False

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
        self.future = self.executor.submit(self.command, argv)

    def _poll(self) -> None:
        if not self.future or not self.future.done():
            return
        future, self.future = self.future, None
        if future.cancelled() or self._cancelled:
            return
        try:
            value = future.result()
            if isinstance(value, list):
                generation = getattr(future, "_jring_generation", self.state.scan_generation)
                self.dispatch(Event.scan_completed(generation, value))
            else:
                self.state = self.state.__class__(**{**self.state.__dict__, "screen": Screen.RESULT, "status": "Task complete.", "body": str(value)})
        except Exception as exc:
            self.state = self.state.__class__(**{**self.state.__dict__, "screen": Screen.ERROR, "status": "Task failed; no automatic retry.", "body": str(exc)})

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
            self._cancelled = True
            self.dispatch(Event.key("ctrl-c" if key == 3 else "escape"))
            return self.state.quit_requested
        if key in (ord("q"), ord("Q")):
            self.dispatch(Event.key("q"))
            return self.state.quit_requested
        if key in (ord("r"), ord("R")) and self.state.screen is Screen.DEVICES:
            self.dispatch(Event.key("r")); self._scan(); return False
        if key in (ord("p"), ord("P")) and self.state.screen is Screen.DEVICES:
            self.dispatch(Event.key("p")); self._scan(); return False
        if self.state.screen is Screen.PICKER and key in (curses.KEY_DOWN, curses.KEY_UP, ord("j"), ord("k"), 10, 13):
            self.dispatch(Event.key({curses.KEY_DOWN: "down", curses.KEY_UP: "up", ord("j"): "j", ord("k"): "k"}.get(key, "enter")))
            return False
        if self.state.screen is Screen.PAIR_CONFIRM and key in (ord("y"), ord("Y")) and self.state.candidates:
            selected = self.state.candidates[self.state.focus_index]
            path = os.path.expanduser("~/.config/jring/address")
            if self.store_address(path, selected.connection_address()):
                self.state = self.state.__class__(**{**self.state.__dict__, "screen": Screen.TASK_RUNNING, "status": "Pairing…", "body": "BlueZ pairing is in progress."})
                self._start_task(["pair", "--address-file", path, "--allow-pairing"])
            return False
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

