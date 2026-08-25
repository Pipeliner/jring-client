# JRing implementation roadmap

The public tracker is the executable roadmap. [Issue #16](https://github.com/Pipeliner/jring-client/issues/16)
is the completion epic; its checklist and the milestones below are the only completion
graph. Every implementation issue contains a JTBD outcome, SDD behavior/safety
contract, RED-first TDD evidence, allowed artifacts, dependencies, and a definition of
done. The `symphony` label makes a task eligible for the fail-closed continuation loop;
it does not itself authorize hardware, input, private evidence, writes, publication, or
package release.

Complete ring-facing parity requires every recovered ring-facing row to finish as
`hardware_verified`, `proven_unavailable`, `blocked_vendor_authorization`, or `unsafe`
for a named supported model/firmware scope. Non-ring-facing APK plumbing must be
`excluded_non_ring`. An `offline_only` codec, static UUID/opcode, simulator result, or
untested firmware cannot close the epic.

## M0 — Evidence and operation contracts

- [#17 Evidence scanning and private/public ledgers](https://github.com/Pipeliner/jring-client/issues/17)
- [#22 Exhaustive offline protocol coverage ledger](https://github.com/Pipeliner/jring-client/issues/22)
- [#32 Versioned live operation registry](https://github.com/Pipeliner/jring-client/issues/32)
- [#33 Normalized event and operation-result contracts](https://github.com/Pipeliner/jring-client/issues/33)

This milestone establishes the closed schemas that prevent static evidence from
becoming live authority. Every later runtime consumes exact registered types.

## M1 — Safe owner-hardware runtime

- [#21 Fail-closed vendor transaction engine](https://github.com/Pipeliner/jring-client/issues/21)
- [#23 Local detection of vendor-authorization gates](https://github.com/Pipeliner/jring-client/issues/23)
- [#34 Owner-hardware evidence runner and compatibility ledger](https://github.com/Pipeliner/jring-client/issues/34)
- [#35 Generation-bound live vendor event engine](https://github.com/Pipeliner/jring-client/issues/35)

This milestone supplies exact endpoint ownership, operation-specific matching,
generation safety, bounded cleanup, and private-to-public evidence promotion. Owner
authorization permits planned hardware tests, but every run still requires explicit
selection and fresh operation-specific consent.

## M2 — Read-only data and events

- [#3 Verified neutral motion events](https://github.com/Pipeliner/jring-client/issues/3)
- [#18 Read-only vendor query families](https://github.com/Pipeliner/jring-client/issues/18)
- [#20 Raw and non-health observation](https://github.com/Pipeliner/jring-client/issues/20)
- [#36 Live fitness and sensor readings](https://github.com/Pipeliner/jring-client/issues/36)
- [#37 Activity and sensor history synchronization/export](https://github.com/Pipeliner/jring-client/issues/37)

Read-only work promotes one firmware-scoped family at a time. Unknown motion stays
neutral, raw/audio activation remains gated by its threat model, and history silence
never becomes device-confirmed completion.

## M3 — Configuration and host integration

- [#38 Reviewed device settings](https://github.com/Pipeliner/jring-client/issues/38)
- [#39 Schedules and reminders without false batch success](https://github.com/Pipeliner/jring-client/issues/39)
- [#40 Private-content synchronization from local sources](https://github.com/Pipeliner/jring-client/issues/40)
- [#41 Host-action events and MPRIS media control](https://github.com/Pipeliner/jring-client/issues/41)

These tasks implement named operations only. They never expose arbitrary payloads,
reuse vendor services, retry uncertain writes, or infer whole-batch delivery from
per-frame/local callbacks.

## M4 — Linux remote and accessibility

- [#4 Fail-safe live sensor-to-keyboard/mouse runtime](https://github.com/Pipeliner/jring-client/issues/4)
- [#30 Task-first non-health/HID capability UX](https://github.com/Pipeliner/jring-client/issues/30)
- [#42 Stable Python and JSON Lines event API](https://github.com/Pipeliner/jring-client/issues/42)
- [#43 Permission-checked XDG TOML mapping profiles](https://github.com/Pipeliner/jring-client/issues/43)

Core first-party adapters are local JSON Lines, MPRIS, and allowlisted `uinput`.
Profiles contain no authority or arbitrary code. MQTT, D-Bus, OSC, MIDI, and arbitrary
shell execution remain external consumers rather than built-in integrations.

## M5 — Binding, bulk transfer, and OTA

- [#19 High-risk/private/bulk threat model](https://github.com/Pipeliner/jring-client/issues/19)
- [#24 Owner-controlled vendor binding](https://github.com/Pipeliner/jring-client/issues/24)
- [#44 Wi-Fi/AP, FTP, and device-file workflows](https://github.com/Pipeliner/jring-client/issues/44)
- [#45 Dial and wallpaper transfer](https://github.com/Pipeliner/jring-client/issues/45)
- [#46 Model- and recovery-gated factory/service operations](https://github.com/Pipeliner/jring-client/issues/46)
- [#47 Recovery-aware SUOTA firmware updates](https://github.com/Pipeliner/jring-client/issues/47)

Each mutation boundary has separate disclosure and consent. Destructive operations
require independently tested recovery, never auto-retry, and never infer completion
from an uncorrelated status or disconnect.

## M6 — Distribution and 1.0 closure

- [#14 Gated PyPI Trusted Publishing](https://github.com/Pipeliner/jring-client/issues/14)
- [#25 Minimal simulator consistency regression](https://github.com/Pipeliner/jring-client/issues/25)
- [#26 Portable passive diagnostics](https://github.com/Pipeliner/jring-client/issues/26)
- [#27 Honest installable distribution](https://github.com/Pipeliner/jring-client/issues/27)
- [#28 Verifiably offline installation](https://github.com/Pipeliner/jring-client/issues/28)
- [#29 Capability-tiered Linux prerequisites](https://github.com/Pipeliner/jring-client/issues/29)
- [#31 Packager, Bash completion, and manual UX](https://github.com/Pipeliner/jring-client/issues/31)
- [#48 1.0 ring-facing parity audit and release acceptance](https://github.com/Pipeliner/jring-client/issues/48)

Simulator work is last and limited to existing regression consistency. Fish completion
remains out of scope.
PyPI, protected-environment approval, tagging, and release publication retain their
separate owner-controlled gates even after the implementation suite passes.

## Closed foundations

Issues [#1](https://github.com/Pipeliner/jring-client/issues/1),
[#2](https://github.com/Pipeliner/jring-client/issues/2),
[#5](https://github.com/Pipeliner/jring-client/issues/5)–[#13](https://github.com/Pipeliner/jring-client/issues/13),
and [#15](https://github.com/Pipeliner/jring-client/issues/15) established evidence
handling, initial inventories, accessibility mappings, selection, diagnostics, JSON
errors, release foundations, compatibility structure, licensing, distro guidance, and
package discovery metadata. A closed foundation is not a live protocol or firmware
compatibility claim.

The repository-owned [Symphony workflow](../WORKFLOW.md) defines RED-first execution,
dual-environment verification, adversarial UX review, commit/push behavior, sanitized
workpads, and continuation. Newly discovered work must become a fully specified linked
issue rather than an unowned TODO.
