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
    operation: str | None = None
    outcome: str | None = None

    @classmethod
    def key(cls, key_name: str) -> "Event":
        return cls("key", key_name=key_name)

    @classmethod
    def scan_completed(cls, generation: int, candidates: Iterable[SelectionCandidate]) -> "Event":
        return cls("scan_completed", generation=generation, candidates=tuple(candidates))

    @classmethod
    def task_completed(cls, generation: int, operation: str, outcome: str) -> "Event":
        return cls("task_completed", generation=generation, operation=operation, outcome=outcome)


@dataclass(frozen=True)
class TuiState:
    screen: Screen
    candidates: tuple[SelectionCandidate, ...] = ()
    focus_index: int = 0
    scan_generation: int = 0
    quit_requested: bool = False
    status: str = "Ready. No Bluetooth operation has started."
    body: str = "Press r to scan nearby devices, p to pair, or v for the offline simulator."
    selected_candidate: SelectionCandidate | None = None
    address_file: str | None = None
    operation_kind: str | None = None
    side_effect_possible: bool = False

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
            possible = state.screen is Screen.TASK_RUNNING and state.side_effect_possible
            return replace(state, screen=Screen.RESULT, side_effect_possible=possible,
                           status="Cancelled; outcome is uncertain because the operation may have started." if possible else "Cancelled; no operation was run.")
        if key in {"escape", "esc"}:
            if state.screen is Screen.TASK_RUNNING:
                return replace(state, screen=Screen.RESULT, side_effect_possible=True,
                               status="Cancelled; outcome is uncertain because the operation may have started.")
            generation = state.scan_generation + 1 if state.screen in {Screen.SCANNING, Screen.PICKER} else state.scan_generation
            return replace(state, screen=Screen.DEVICES, scan_generation=generation, status="Cancelled; no operation was run.")
        if state.screen is Screen.DEVICES and key == "r":
            generation = state.scan_generation + 1
            return replace(state, screen=Screen.SCANNING, scan_generation=generation,
                           status="Scanning… no connection has started.", body="Waiting for nearby Bluetooth advertisements…")
        if state.screen is Screen.SCANNING and key == "r":
            generation = state.scan_generation + 1
            return replace(state, scan_generation=generation,
                           status="Refreshing scan… no connection has started.")
        if state.screen is Screen.PICKER and key == "r":
            generation = state.scan_generation + 1
            return replace(state, scan_generation=generation,
                           status="Refreshing device list…", body="Waiting for nearby Bluetooth advertisements…")
        if state.screen in {Screen.ERROR, Screen.RESULT} and key == "r":
            generation = state.scan_generation + 1
            return replace(state, screen=Screen.SCANNING, scan_generation=generation,
                           status="Scanning… no connection has started.", body="Waiting for nearby Bluetooth advertisements…")
        if state.screen is Screen.DEVICES and key == "p":
            generation = state.scan_generation + 1 if not state.candidates else state.scan_generation
            return replace(state, screen=Screen.PICKER, focus_index=0, scan_generation=generation,
                           status="Choose a device to pair." if state.candidates else "Scanning for devices to pair…",
                           body="Waiting for nearby Bluetooth advertisements…" if not state.candidates else state.body)
        if state.screen is Screen.PICKER:
            if key in {"down", "j"} and state.candidates:
                return replace(state, focus_index=min(state.focus_index + 1, len(state.candidates) - 1))
            if key in {"up", "k"} and state.candidates:
                return replace(state, focus_index=max(state.focus_index - 1, 0))
            if key in {"enter", "return"} and state.candidates:
                selected = state.candidates[state.focus_index]
                return replace(state, screen=Screen.PAIR_CONFIRM, selected_candidate=selected,
                               status="Confirm pairing for the selected device.", body=f"Selected: {selected.display_name or 'unnamed device'} [{selected.alias}]\nAdvertisements can be stale. Pairing will perform one Bluetooth operation.")
        if state.screen is Screen.PAIR_CONFIRM and key in {"confirm-pair", "pair"}:
            return replace(state, screen=Screen.TASK_RUNNING, operation_kind="pair",
                           side_effect_possible=True, status="Pairing…", body="One BlueZ pairing operation is running.")
        if state.screen is Screen.TRUST_CONFIRM and key in {"confirm-trust", "trust"}:
            return replace(state, screen=Screen.TASK_RUNNING, operation_kind="trust",
                           side_effect_possible=True, status="Trusting…", body="One BlueZ trust operation is running.")
    elif event.kind == "scan_completed":
        if state.screen not in {Screen.SCANNING, Screen.PICKER} or event.generation != state.scan_generation:
            return state
        candidates = _sort_candidates(event.candidates)
        screen = Screen.PICKER if state.screen is Screen.PICKER else Screen.DEVICES
        return replace(state, screen=screen, candidates=candidates, focus_index=0,
                       status="Scan complete." if candidates else "No nearby devices found; press r to retry.",
                       body="\n".join(f"{i}. {item.display_name or 'unnamed device'} [{item.alias}]" for i, item in enumerate(candidates, 1)))
    elif event.kind == "task_completed":
        if state.screen is not Screen.TASK_RUNNING or event.generation != state.scan_generation:
            return state
        outcome = event.outcome or "unknown"
        if event.operation == "pair" and outcome in {"paired", "already_paired"}:
            return replace(state, screen=Screen.TRUST_CONFIRM, operation_kind=None, side_effect_possible=False,
                           status="Pairing succeeded. Trust this device?", body="Trust is separate and defaults to No. Press t to trust, or n to finish.")
        return replace(state, screen=Screen.RESULT, operation_kind=None, side_effect_possible=False,
                       status=f"{event.operation or 'Task'} result: {outcome}.", body="Press r to retry or Escape to return.")
    return state


def render_model(state: TuiState) -> dict[str, object]:
    body = state.body
    if state.screen is Screen.PICKER and state.candidates:
        rows = []
        for index, item in enumerate(state.candidates, 1):
            marker = ">" if index - 1 == state.focus_index else " "
            rows.append(f"{marker} {index}. {item.display_name or 'unnamed device'} [{item.alias}]")
        body = "Names are advertisement labels, not identity proof; results can be stale.\n\n" + "\n".join(rows)
    if state.screen is Screen.PAIR_CONFIRM:
        keys = "Enter/y pair  Esc cancel"
    elif state.screen is Screen.TRUST_CONFIRM:
        keys = "t trust  n skip  Esc cancel"
    elif state.screen is Screen.PICKER:
        keys = "↑/↓ or j/k move  Enter select  r rescan  Esc cancel"
    else:
        keys = "r scan  p pair  s status  c capabilities  d doctor  i inputs  v simulator  q quit  Ctrl-C cancel"
    return {
        "screen": state.screen.value,
        "title": "JRING — DEVICES" if state.screen is Screen.DEVICES else f"JRING — {state.screen.value.upper()}",
        "purpose": "Nearby devices and pairing" if state.screen is Screen.DEVICES else state.status,
        "body": body,
        "focus_index": state.focus_index,
        "status": state.status,
        "keys": keys,
    }
