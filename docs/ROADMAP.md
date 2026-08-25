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
- [#16 Complete clean-room APK-to-Python BLE protocol parity](https://github.com/Pipeliner/jring-client/issues/16)
- [#17 Harden evidence scanning and private-ledger separation](https://github.com/Pipeliner/jring-client/issues/17)
- [#22 Publish an exhaustive offline protocol coverage ledger](https://github.com/Pipeliner/jring-client/issues/22)

## Vendor transport and owner hardware

- [#18 Promote read-only vendor queries through owner hardware canaries](https://github.com/Pipeliner/jring-client/issues/18)
- [#21 Build a fail-closed vendor GATT transaction engine](https://github.com/Pipeliner/jring-client/issues/21)
- [#23 Detect authorization-gated firmware without vendor cloud requests](https://github.com/Pipeliner/jring-client/issues/23)
- [#24 Verify owner-controlled vendor binding without cloud replay](https://github.com/Pipeliner/jring-client/issues/24)

## Desktop input and accessibility

- [#4 Fail-safe live sensor-to-keyboard/mouse runtime](https://github.com/Pipeliner/jring-client/issues/4)
- [#5 Accessible mappings and action inventory](https://github.com/Pipeliner/jring-client/issues/5)
- [#20 Inventory and safely expose raw and non-health capabilities](https://github.com/Pipeliner/jring-client/issues/20)
- [#25 Make simulator profiles consistent across commands](https://github.com/Pipeliner/jring-client/issues/25)
- [#30 Expose task-first non-health and HID capability UX](https://github.com/Pipeliner/jring-client/issues/30)

## High-risk and bulk capabilities

- [#19 Threat-model private-data, bulk-transfer, and destructive features](https://github.com/Pipeliner/jring-client/issues/19)

## Everyday hardware UX and automation

- [#6 Guided selection with ephemeral aliases](https://github.com/Pipeliner/jring-client/issues/6)
- [#7 Passive BlueZ operational diagnostics](https://github.com/Pipeliner/jring-client/issues/7)
- [#8 Partial Device Information states under one deadline](https://github.com/Pipeliner/jring-client/issues/8)
- [#9 Versioned JSON errors and stable exit codes](https://github.com/Pipeliner/jring-client/issues/9)
- [#26 Make doctor diagnostics portable without silent busctl dependence](https://github.com/Pipeliner/jring-client/issues/26)

## Installation portability

- [#13 Portable installation across major Linux distro families](https://github.com/Pipeliner/jring-client/issues/13)
- [#27 Provide an honest installable distribution path](https://github.com/Pipeliner/jring-client/issues/27)
- [#28 Design a verifiably offline installation path](https://github.com/Pipeliner/jring-client/issues/28)
- [#29 Split Linux prerequisites by capability and test literal recipes](https://github.com/Pipeliner/jring-client/issues/29)

## Distribution and governance

- [#10 Reproducible signed end-user release flow](https://github.com/Pipeliner/jring-client/issues/10)
- [#12 Explicit project license](https://github.com/Pipeliner/jring-client/issues/12)
- [#14 Gated PyPI Trusted Publishing](https://github.com/Pipeliner/jring-client/issues/14)
- [#15 Tested package discovery keywords and project URLs](https://github.com/Pipeliner/jring-client/issues/15)
- [#31 Improve packager and terminal discovery UX](https://github.com/Pipeliner/jring-client/issues/31)

Dependencies remain explicit: evidence handling precedes hardware event decoding;
verified neutral events precede live input; and tested package metadata and owner-controlled
release gates precede publication. Issues may refine or split their scope, but newly
discovered work must become another tracked issue instead of surviving only as a TODO
or review note.
