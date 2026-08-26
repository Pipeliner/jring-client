"""Pure event/state model for the JRing terminal UI."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

from .discovery import SelectionCandidate


class Screen(str, Enum):
    DEVICES = "devices"
    SCANNING = "scanning"
    PICKER = "picker"
    PAIR_CONFIRM = "pair_confirm"
    TRUST_CONFIRM = "trust_confirm"
    TASK_RUNNING = "task_running"
    RESULT = "result"
    ERROR = "error"


@dataclass(frozen=True)
class Event:
    kind: str
    key_name: str | None = None
    generation: int | None = None
    candidates: tuple[SelectionCandidate, ...] = ()
    message: str = ""

    @classmethod
    def key(cls, key_name: str) -> "Event":
        return cls("key", key_name=key_name)

    @classmethod
    def scan_completed(cls, generation: int, candidates: Iterable[SelectionCandidate]) -> "Event":
        return cls("scan_completed", generation=generation, candidates=tuple(candidates))


@dataclass(frozen=True)
class TuiState:
    screen: Screen
    candidates: tuple[SelectionCandidate, ...] = ()
    focus_index: int = 0
    scan_generation: int = 0
    quit_requested: bool = False
    status: str = "Ready. No Bluetooth operation has started."
    body: str = "Press r to scan nearby devices, p to pair, or v for the offline simulator."

    @classmethod
    def initial(cls) -> "TuiState":
        return cls(screen=Screen.DEVICES)


def _sort_candidates(candidates: Iterable[SelectionCandidate]) -> tuple[SelectionCandidate, ...]:
    return tuple(sorted(candidates, key=lambda item: (
        not item.likely_jring,
        -(item.rssi if item.rssi is not None else -999),
        (item.display_name or "").casefold(),
        item.alias,
    )))


def reduce(state: TuiState, event: Event) -> TuiState:
    if event.kind == "key":
        key = (event.key_name or "").lower()
        if key in {"ctrl-c", "q"}:
            if state.screen is Screen.DEVICES:
                return replace(state, quit_requested=True, status="Goodbye. No ring was contacted.")
            return replace(state, screen=Screen.DEVICES, status="Cancelled; no operation was run.")
        if key in {"escape", "esc"}:
            return replace(state, screen=Screen.DEVICES, status="Cancelled; no operation was run.")
        if state.screen is Screen.DEVICES and key == "r":
            generation = state.scan_generation + 1
            return replace(state, screen=Screen.SCANNING, scan_generation=generation,
                           status="Scanning… no connection has started.", body="Waiting for nearby Bluetooth advertisements…")
        if state.screen is Screen.SCANNING and key == "r":
            generation = state.scan_generation + 1
            return replace(state, scan_generation=generation,
                           status="Refreshing scan… no connection has started.")
        if state.screen is Screen.DEVICES and key == "p":
            return replace(state, screen=Screen.PICKER, focus_index=0, status="Choose a device to pair.")
        if state.screen is Screen.PICKER:
            if key in {"down", "j"} and state.candidates:
                return replace(state, focus_index=min(state.focus_index + 1, len(state.candidates) - 1))
            if key in {"up", "k"} and state.candidates:
                return replace(state, focus_index=max(state.focus_index - 1, 0))
            if key in {"enter", "return"} and state.candidates:
                return replace(state, screen=Screen.PAIR_CONFIRM, status="Confirm pairing for the selected device.")
    elif event.kind == "scan_completed":
        if state.screen is not Screen.SCANNING or event.generation != state.scan_generation:
            return state
        candidates = _sort_candidates(event.candidates)
        return replace(state, screen=Screen.DEVICES, candidates=candidates, focus_index=0,
                       status="Scan complete." if candidates else "No nearby devices found; press r to retry.",
                       body="\n".join(f"{i}. {item.display_name or 'unnamed device'} [{item.alias}]" for i, item in enumerate(candidates, 1)))
    return state


def render_model(state: TuiState) -> dict[str, object]:
    return {
        "screen": state.screen.value,
        "title": "JRING — DEVICES" if state.screen is Screen.DEVICES else f"JRING — {state.screen.value.upper()}",
        "purpose": "Nearby devices and pairing" if state.screen is Screen.DEVICES else state.status,
        "body": state.body,
        "focus_index": state.focus_index,
        "status": state.status,
        "keys": "r scan  p pair  v simulator  q quit  Ctrl-C cancel",
    }
