# JRing roadmap

Future work is tracked in public GitHub issues rather than an unowned documentation
list. Every implementation issue carries a user job, a behavior and safety contract,
RED-first test expectations, an artifact boundary, and an explicit block condition.
The `symphony` label marks work eligible for the fail-closed issue workflow; it does not
authorize hardware access, input injection, publication, or a decision reserved for the
owner.

## Evidence and general device functionality

- [#1 Privacy-safe hardware evidence and fixtures](https://github.com/Pipeliner/jring-client/issues/1)
- [#2 Non-health services, HID descriptors, and sensor inventory](https://github.com/Pipeliner/jring-client/issues/2)
- [#3 Verified non-health motion events](https://github.com/Pipeliner/jring-client/issues/3)
- [#11 Privacy-safe real-hardware compatibility matrix](https://github.com/Pipeliner/jring-client/issues/11)

## Desktop input and accessibility

- [#4 Fail-safe live sensor-to-keyboard/mouse runtime](https://github.com/Pipeliner/jring-client/issues/4)
- [#5 Accessible mappings and action inventory](https://github.com/Pipeliner/jring-client/issues/5)

## Everyday hardware UX and automation

- [#6 Guided selection with ephemeral aliases](https://github.com/Pipeliner/jring-client/issues/6)
- [#7 Passive BlueZ operational diagnostics](https://github.com/Pipeliner/jring-client/issues/7)
- [#8 Partial Device Information states under one deadline](https://github.com/Pipeliner/jring-client/issues/8)
- [#9 Versioned JSON errors and stable exit codes](https://github.com/Pipeliner/jring-client/issues/9)

## Installation portability

- [#13 Portable installation across major Linux distro families](https://github.com/Pipeliner/jring-client/issues/13)

## Distribution and governance

- [#10 Reproducible signed end-user release flow](https://github.com/Pipeliner/jring-client/issues/10)
- [#12 Explicit project license](https://github.com/Pipeliner/jring-client/issues/12)
- [#14 Gated PyPI Trusted Publishing](https://github.com/Pipeliner/jring-client/issues/14)
- [#15 Tested package discovery keywords and project URLs](https://github.com/Pipeliner/jring-client/issues/15)

Dependencies remain explicit: evidence handling precedes hardware event decoding;
verified neutral events precede live input; and tested package metadata and owner-controlled
release gates precede publication. Issues may refine or split their scope, but newly
discovered work must become another tracked issue instead of surviving only as a TODO
or review note.
