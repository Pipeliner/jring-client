# JRing TUI — interaction model and software design

Status: implementation in progress; reducer/runtime slices are landed, conformance work remains

## Evidence and design choice

The current curses loop mixes rendering, blocking BLE work, and line prompts.
That is the source of progress text leaking outside the TUI, awkward cancellation,
and focus loss. Python’s curses guide describes a non-blocking `getch` loop and
explicit resize handling; mature TUI frameworks model screens/widgets, focus,
and events rather than shell prompts. See the [Python curses guide](https://docs.python.org/3/howto/curses.html),
[Textual screens](https://textual.textualize.io/guide/screens/),
[Textual focus/key bindings](https://github.com/Textualize/textual/blob/main/docs/guide/widgets.md),
and [prompt-toolkit Application/event-loop reference](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/reference.html).

We will use an event-driven state machine behind a renderer boundary. The first
implementation may remain stdlib-only, but it must preserve these architectural
properties; switching to Textual or prompt-toolkit later must not change the
interaction contract.

### Renderer decision gate

The preferred renderer for the complete TUI is Textual, subject to issue #68’s
packaging check. Its documented screen stack, focusable widgets, async app model,
pilot key/resize testing, and worker support map directly to this contract. A
stdlib-curses implementation is acceptable only if it provides equivalent
screen/focus/reducer separation and headless tests; retaining the current
blocking redraw loop is explicitly rejected. prompt-toolkit remains a viable
alternative if its application/event-loop model and widget coverage pass the
same acceptance matrix.

## JTBD scenarios

| User job | Default path | Completion signal |
| --- | --- | --- |
| “Show me what is nearby” | Open TUI → Devices → `r` | Named, sorted rows or actionable empty/error state |
| “Pair my ring quickly” | Devices → `p` → scan → select → Pair → optional Trust | Result screen states outcome and next action |
| “Use my configured ring” | Devices → select saved device → Status/Capabilities | Current device and operation state are visible |
| “I have no hardware” | Devices → `v` Simulator | Offline provenance is prominent; no radio call |
| “Something failed” | Result panel → `r` retry or `Esc` back | Cause, remedy, and side-effect status are explicit |
| “I pressed Ctrl-C” | Any screen/modal | Modal cancels or root exits cleanly; no traceback |

## Screen/state model

```
DEVICES ──r──> SCANNING ──> DEVICES(results)
   │              └──────> ERROR(retry/back)
   p
   └──────> PICKER ──> PAIR_CONFIRM ──> TRUST_CONFIRM ──> RESULT
   s/c/d/i/v ──> TASK_RUNNING ──> RESULT ──> DEVICES
```

Each screen owns a title, purpose line, content region, status line, and key
legend. Focus is visible without color. Long content scrolls. Resize events
recompute layout and never crash. Simulator is a sibling task, never an error
fallback for missing hardware.

## Event and task model

- A single UI event loop receives key, resize, timer, scan-result, task-result,
  and cancellation events.
- BLE and subprocess work runs in bounded background tasks; render never waits
  synchronously on them. Progress is state, not `print()`.
- `r` starts one bounded scan and immediately renders `SCANNING`.
- `p` uses fresh device results or starts a scan within the picker.
- Every task carries a generation/token; stale results cannot overwrite the
  current screen.
- Ctrl-C, Escape, and `q` are first-class events. Cancellation is idempotent;
  cleanup is bounded; no automatic retry occurs.
- Exceptions become sanitized result events. Raw exceptions, addresses, and
  payloads never reach the renderer.

### Normative reducer vocabulary

The headless model exposes a pure reducer (or equivalent) over these stable
states: `DEVICES`, `SCANNING`, `PICKER`, `PAIR_CONFIRM`, `TRUST_CONFIRM`,
`TASK_RUNNING`, `RESULT`, and `ERROR`. Events include `KEY`, `RESIZE`,
`SCAN_STARTED`, `SCAN_COMPLETED`, `TASK_COMPLETED`, `TASK_FAILED`,
`CANCELLED`, and `TICK`; implementations may add internal events but must not
make renderer code responsible for state transitions. Each rendered model must
contain `screen`, `title`, `purpose`, `body`, `focus_index`, `status`, and
`keys`. This vocabulary is the contract tested by TDD and is independent of
whether the renderer uses curses, Textual, or prompt-toolkit.

### Pairing and cancellation result contract

The reducer retains `selected_candidate`, `address_file`, `operation_kind`, and
`side_effect_possible` independently of rendered text. Pairing is two operations:
`PAIR_CONFIRM` authorizes one pair call; only a `PAIR_RESULT` of `paired` or
`already_paired` may transition to `TRUST_CONFIRM`; `TRUST_CONFIRM` authorizes
one trust call and never repeats pairing. Rejected, unavailable, timed-out, or
uncertain pairing ends in a result/error state with trust unavailable.

Cancellation has three outcomes: before worker dispatch, `cancelled` with
`side_effect_possible=false`; after dispatch but before a result, `uncertain`
with `side_effect_possible=true`; after a completed result, ordinary result
handling wins. No cancelled/uncertain operation is retried automatically, and
stale result events (wrong generation) are ignored. The renderer states which
outcome occurred.

## Devices view

Devices is the default screen on every launch, even when an address file exists.
Opening the TUI performs no radio operation. The initial empty state explains
`r` scan, `p` pair, and `v` simulator. A configured device is labelled configured
but does not replace the nearby-device view.

Rows show advertised Bluetooth name (or “unnamed device”), privacy-safe alias,
JRing-name heuristic, signal strength, and freshness. Names are labels, not
identity proof; stale/incomplete results are disclosed. Sort by likely JRing,
RSSI descending, case-folded name, then alias. Raw addresses are never rendered.

## Pairing/trust modal

1. `p` enters an in-TUI scanning/picker screen; no stdout progress or terminal
   mode switch occurs.
2. Up/down and `j`/`k` move focus; Enter selects; number keys 1–9 are shortcuts;
   Escape/Ctrl-C cancel.
3. Pair confirmation names the selected label and warns that advertisements can
   be stale. The default is cancel; explicit `PAIR` text or a clearly labelled
   confirm key is required.
4. Address-file path is an in-TUI editable field. Atomic creation requires a
   user-owned regular mode-0600 file and refuses symlinks/unsafe existing files.
5. Trust is a separate modal, default No, shown only after pair success or
   already-paired. Pair and trust have separate tokens/results.
6. Result screen reports paired/trusted/cancelled/uncertain, file-write status,
   remedy, and next key.

## Other tasks

Status/Capabilities use an in-TUI configured-file field and never silently scan.
Doctor/Input Actions are local bounded tasks with scrollable output. Simulator is
explicit (`v`) and labelled “offline simulator — no ring contacted”. Hardware
connection failures say “could not connect”, explain stale results/retry, and do
not show traceback or raw BlueZ output.

## Accessibility and terminal behavior

- Reading order is task-first; no color-only meaning, spinner, or hidden hotkey.
- Minimum supported terminal is 80×24; clipping/wrapping is safe and announced.
- Unicode advertisement names are sanitized to one line.
- Ctrl-C works at root, during scan, in picker, in editable fields, and on result.
- Plain fallback exists only when curses cannot initialize and preserves labels,
  ordering, and safety language.
- Supported release targets provide curses for the interactive `jring tui` path.
  Importing or installing the package remains safe on minimal Python builds without
  the module; those use the plain fallback and keep all CLI commands available.

## Acceptance/TDD matrix

| Given | Event | Must observe |
| --- | --- | --- |
| fresh launch | none | Devices screen; no BLE call; no simulator |
| Devices | `r` | in-TUI SCANNING, then sorted names or actionable error |
| any screen | Ctrl-C | clean cancel/quit; no traceback |
| Devices | `p` | in-TUI picker; no stdout leakage or terminal mode switch |
| picker | arrows/Enter | visible focus and selection; no connection yet |
| picker | Escape/Ctrl-C | modal closes; no file/pair/trust |
| selected row | cancel confirmation | no pair call |
| selected row | confirm | exactly one pair call |
| pair success | default Trust | no trust call |
| pair success | explicit Trust | exactly one separate trust call |
| scan results | sort/render | JRing-first, RSSI/name ordering; names visible |
| task failure | result | remedy, retry/back action, no raw error/address |
| resize/80×24 | redraw | no crash; title/focus/footer remain visible |
| simulator | `v` | explicit offline provenance; no BLE call |
