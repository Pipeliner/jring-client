# Compatibility evidence

## How to read support claims

Documentation is not execution evidence. JRing uses three deliberately separate
levels:

- **Documented installation path:** the repository gives a package and interpreter
  recipe for that family. The recipe can still vary with a distro point release.
- **CI exercised:** a committed workflow installs and tests the package in the named
  environment. This establishes only those software checks, not Bluetooth adapter or
  ring behavior.
- **Owner hardware verified:** a privacy-reviewed owner report establishes only the
  explicitly recorded hardware dimensions.

The routine test workflow uses a GitHub-hosted Ubuntu runner with Python 3.10 and 3.13.
A separate bounded native-container workflow installs and tests Debian 13, Fedora 44,
Rocky Linux 9.6, Arch, and openSUSE Leap 15.6 userspace environments. The repository's
checks page, rather than this document, records whether a particular workflow run was
green. No distro row is a real-ring compatibility claim. No owner hardware
observations have been accepted.

| Linux family | Documented installation path | CI exercised | Owner hardware verified |
|---|---|---|---|
| Ubuntu | yes | Ubuntu runner; Python 3.10 and 3.13 | none |
| Debian | yes | Debian 13 native container smoke | none |
| Fedora | yes | Fedora 44 native container smoke | none |
| RHEL / Rocky / Alma 9 | yes; select Python 3.11 | Rocky Linux 9.6 native container smoke | none |
| Arch | yes | rolling `base` native container smoke | none |
| openSUSE Leap 15.6 | yes | native container smoke | none |
| SLES 15 | yes; official Python module required | documentation-only; not CI-exercised | none |
| NixOS | yes; nixpkgs attribute is revision-dependent | documentation-only; not CI-exercised | none |

### Interpreter choices

`pyproject.toml` declares CPython 3.10 or newer. Python 3.10 and 3.13 are the explicit
routine matrix choices. The native containers additionally exercise their packaged
interpreters: Python 3.13 on Debian, Python 3.11 on Rocky Linux and openSUSE, Fedora's
current Python, and Arch's rolling Python. Python 3.12 and later remain within the
package declaration but must not be described as CI-verified unless a workflow actually
selected that minor. Optional Bleak and evdev compatibility is additionally bounded by
the versions recorded in package metadata.

CI validates imports, unit tests, and simulated behavior. It does not grant Bluetooth
or uinput permission, activate a radio, connect a device, test a distro's service
manager, or establish that package names remain present in every point release.

### Native container smoke boundary

The `Native container smoke` workflow installs each image's compiler, Python and Linux
userspace headers, BlueZ tools, and all JRing extras. It runs pytest, passive doctor
JSON, simulated status and capabilities, and an input preview. It never requests an
active scan, address, selection, or input injection.

These are native distro userspace/package-manager checks running on a GitHub-hosted
Linux kernel. The Leap 15.6 image is only a practical openSUSE userspace proxy for the
related SLES 15 package family; it does not exercise SLES repositories, subscriptions,
support policy, or a booted SLES host. A container does not verify systemd services,
the distro kernel, a Bluetooth adapter, BlueZ D-Bus access, udev policy, `/dev/uinput`,
or a NixOS system rebuild. Faithful hosted SLES and NixOS jobs are therefore
documentation-only until an appropriate bounded runner exists.

## Privacy-safe compatibility reports

Compatibility reports are review artifacts, not telemetry. The tool never scans,
connects, reads a ring, or publishes output while generating or merging a report. A
report has no timestamp, address, account, health measurement, raw payload, serial,
distro patch version, or exact personal data.

The coarse dimensions are model family, firmware major, Linux family, Python minor,
BlueZ major, and Bleak major. Hardware evidence states are:

- `untested`: no evidence for this dimension.
- `verified`: prerequisites, connection, or standard reads were directly established.
- `advertised` / `not_advertised`: HID service metadata was observed, without a
  usability claim.
- `incompatible`: the named dimension was attempted and failed its contract.

The row summary is one of `untested`, `prerequisites_only`, `connected`,
`standard_reads_verified`, `hid_advertised`, `motion_verified`, or `incompatible`.
Synthetic CI rows are restricted to the first two and keep connection, standard reads,
HID, and motion `untested`.

## Current hardware matrix

No owner hardware observations are included in this matrix, which makes no hardware
compatibility claim.

| Source | Environment | Prerequisites | Connection | Standard reads | HID | Motion |
|---|---|---|---|---|---|---|
| Synthetic CI | Python 3.10 | untested | untested | untested | untested | untested |
| Synthetic CI | Python 3.13 | untested | untested | untested | untested | untested |

Owner hardware rows require an accepted privacy-safe evidence ID and a mode-0600 report
file. Generate and validate locally, inspect the complete JSON, then decide separately
whether to contribute it. Matrix merge is deterministic and rejects duplicate report
IDs; zero errors never changes an untested state into a compatibility claim.
