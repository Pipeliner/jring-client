# TUI pairing picker — SDD

Status: proposed implementation contract (2026-08-26)

## Job to be done

When a person wants to pair a nearby ring, they should be able to identify it
from the TUI without first finding a Bluetooth address or writing shell commands.
The flow must remain understandable to a hurried user and must not silently pair
or trust a device.

## User flow

1. Choose **Pair** (`p`) from either TUI frontend.
2. The client performs one explicitly initiated BLE scan and displays a numbered
   list. Each row contains the advertised Bluetooth name (or “unnamed device”),
   a privacy-safe alias, JRing-name heuristic, and signal strength; raw addresses
   are never printed. Likely JRing devices appear first, then stronger signals,
   then stable alphabetical names.
3. Choose a row or cancel. Invalid input does no work and returns to the menu.
4. Choose the destination address-file path (defaulting to the current path or
   `~/.config/jring/address`). The selected address is written only to a
   user-owned mode-0600 regular file.
5. Type `PAIR` to authorize exactly one BlueZ pairing operation.
6. After pairing, answer a separate `y/yes` prompt to authorize `trust`; the
   default is no. Pairing and trust are never conflated.

The curses frontend keeps this picker inside the TUI: it renders the numbered
rows and accepts a number/arrow selection without dropping to a shell-style
prompt or terminating curses. The plain fallback uses line input.

## Curses interaction contract

- The default curses view is **Devices**, whether or not an address file is
  already configured. It explains how to scan and never shows a simulator as
  the first view.
- All scan, selection, path, pairing, and trust prompts are rendered inside
  curses; curses is not ended for `input()` or a shell-style prompt.
- Ctrl-C, Escape, and `q` cancel the current picker/prompt or quit safely. They
  never leave a half-authorized pairing operation running.
- Opening the TUI does not perform a radio scan. The user presses `r` (refresh)
  from Devices to initiate one, so “no implicit scan” remains true.

## Invariants

- Scan happens only after selecting Pair; no TUI startup scan occurs.
- Scan, selection, and file creation do not connect to the device.
- The picker never displays or logs a raw Bluetooth address.
- Advertised names are user-facing labels, not proof of identity; the UI says so.
- Discovery results can be stale or incomplete. A failed subsequent connection
  is explained as “not connected” with retry guidance, not as an unexplained
  traceback.
- Cancel, empty results, scan failure, invalid selection, unsafe path, or a
  non-literal pairing confirmation must perform no pairing/trust operation.
- Existing address-file validation remains authoritative for all hardware use.
- A scan result is ephemeral; the stored file is the explicit hand-off to later
  status/capability commands.
- Curses mode must not exit to the terminal merely to choose a device.

## TDD matrix

| Case | Expected behavior |
| --- | --- |
| one or more devices | numbered picker is shown; selected alias is displayed |
| named devices | Bluetooth name is shown and likely JRing devices sort first |
| `q` or interrupt | no file, pairing, or trust operation |
| invalid number | explanatory cancellation; no operation |
| empty scan | retry guidance; no operation |
| scan exception | sanitized error; no operation |
| valid selection + `PAIR` | one `pair` command receives the selected address-file |
| valid selection + no trust | no `trust` command |
| valid selection + `y` trust | separate `trust` command is authorized |
| unsafe address path | no pairing/trust command |
