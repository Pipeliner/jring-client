# JRing client

This is an offline-first Python 3 Linux client for explicitly selected JRing BLE
devices. It performs safe standard Bluetooth GATT reads today and provides a tested
simulator. Vendor writes and hardware history remain disabled until packet captures
from the owner's selected ring establish the protocol exactly.

## Install and run

From a clone, create an isolated environment. `python3` is used for bootstrapping on
Linux distributions that do not provide a `python` command:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
jring doctor
jring non-health-capabilities
jring protocol-coverage
jring status --simulate
jring capabilities --simulate
jring history --simulate --output history.jsonl
jring input --simulate --map step=click:left
```

`--simulate` uses the named `basic` profile everywhere: it has standard status data
and does not advertise HID. To inspect a synthetic, metadata-only HID inventory, name
the `hid` profile explicitly in either supported option position:

```sh
jring capabilities --simulate --simulate-profile hid
jring --simulate --simulate-profile hid status
```

Human and JSON results name the selected profile. The HID profile never reads or
emits HID reports and does not claim operating-system attachment.

For hardware, install the optional Bleak dependency. Discovery is an active radio scan:
`--active-scan` explicitly acknowledges that BLE scan requests are transmitted. It
redacts addresses and never connects.

```sh
python -m pip install -e '.[ble]'
jring discover --active-scan
```

Use BlueZ locally to identify your ring, then put its exact address on one line in a
private file. The client rejects files accessible by another user:

```sh
mkdir -p ~/.config/jring
chmod 700 ~/.config/jring
# Add the exact address with your editor, then:
chmod 600 ~/.config/jring/address
jring status --address-file ~/.config/jring/address
jring time-sync --address-file ~/.config/jring/address --yes
```

The legacy `--address` option remains available, but it exposes the identifier in
shell history and process listings. Neither discovery result aliases nor addresses are
persisted by the client, and discovery never auto-selects a device.

For an interactive status check without putting an address in argv or a file, use:

```sh
jring status --select --active-scan
```

The scan and connection are separate consent steps. The command shows temporary
aliases and coarse identity cues, then asks a default-no confirmation before it can
connect. It never auto-selects a sole result. This guided path is human-only and does
not support `--json`; scripts should keep using the mode-0600 address file.

Human-readable output is the default. Add `--json` to `status` or `discover` for
automation. Both task-first options (`jring status --simulate`) and the original
global-first form (`jring --simulate status`) are supported.
Simulated human output clearly states that no ring was contacted; structured results
and exports include source and schema provenance.

JSON successes include `schema_version`, `operation`, `source`, and `ok`. JSON failures
write one redacted envelope to stdout and nothing to stderr. Stable failure exits are
2 for usage, 3 for unavailable prerequisites/device, 4 for timeout, 5 for protocol
incompatibility, 6 for permission, 70 for an unexpected internal failure, and 130 for
interruption. Scripts should branch on the error `code`, not its explanatory message.

Contributions are welcome, but raw Bluetooth captures, app archives, device addresses,
account details, timestamps, health values, and vendor payload dumps do not belong in
GitHub issues or commits. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the local
fail-closed evidence workflow and [SECURITY.md](SECURITY.md) for private reporting.

Maintainers can generate a hardware-independent compatibility row and deterministically
merge reviewed reports without publishing them:

```sh
python3 scripts/compatibility_matrix.py generate-synthetic
python3 scripts/compatibility_matrix.py merge report-a.json report-b.json
```

Synthetic success verifies only named local checks; all hardware dimensions remain
`untested`. See [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) for the schema and the
owner-evidence gate.

For reviewed CI artifacts, checksum verification, isolated `pipx`/`uv tool` install,
upgrade, and uninstall instructions, see [docs/INSTALL.md](docs/INSTALL.md). The
repository does not currently publish to a package index or create GitHub releases.
The tokenless, owner-gated release design and remaining PyPI trust step are documented
in [docs/PUBLISHING.md](docs/PUBLISHING.md).

Inspect the complete static interface accounting without Bluetooth, a ring, or optional
dependencies:

```sh
jring protocol-coverage
jring protocol-coverage --json
```

The report accounts for 112 requests and 105 callbacks, including 39 offline request
codecs and all 86 wire callback codecs. It distinguishes those from absent,
APK-generated, and non-Bluetooth behavior, and always reports zero live or
hardware-verified vendor operations. It contains no payload bytes and grants no write
authority.

Run `jring doctor` before touching hardware. It passively checks Python, Linux, Bleak,
BlueZ, evdev, and `/dev/uinput`, explains exactly what is missing, and reports
simulator, BLE-hardware, and desktop-input readiness independently. It does not scan,
connect, write, or use the network. Automation can use
`jring doctor --json --require-hardware` when missing BLE prerequisites should produce
a nonzero exit status. Use `--require-input` to require evdev and writable `uinput`
instead.

## Use a sensor event as desktop input

Live ring input is not available yet. Inspect the local evidence and candidate boundary
without Bluetooth first; this includes standard HID metadata, media/volume/shutter
actions, the cumulative step counter, unknown motion channels, and raw non-health
framing:

```sh
jring non-health-capabilities
jring non-health-capabilities --json
```

The simulator can then exercise a non-health `step` event as an allowlisted keyboard
key or mouse click. Preview is the default and never emits operating-system input:

```sh
jring input-actions
jring input-actions --json
jring capabilities --simulate
jring capabilities --simulate --simulate-profile hid
jring input --simulate --map step=key:space
jring input --simulate --map step=click:primary
```

`input-actions` is entirely local and lists both simulator profiles plus the complete
action vocabulary without Bluetooth, `evdev`, or `/dev/uinput`. Its plain-text order
is suitable for screen readers. It labels the mouse actions as primary (left),
secondary (right), and middle, and states that `step` is currently a simulator
event—not a required physical gesture.

To deliberately inject one simulated event through Linux `uinput`, install the input
extra and add the confirmation flag:

```sh
python -m pip install -e '.[input]'
jring input --simulate --map step=key:space --allow-input
```

Named keys are `space`, `enter`, `escape`, the four arrows, `page-up`, and
`page-down`; mouse clicks are `primary` (`left`), `secondary` (`right`), and `middle`.
Each alias selects the same action, and the temporary Linux input device advertises
only the selected key or button. Arbitrary key codes and
shell commands are rejected. Status can report that a standard Bluetooth HID service
was advertised, but service presence alone does not prove that HID reports work or an
operating-system input device exists.

Hardware JRing motion events are not enabled yet: the vendor event frames are not
verified. This boundary prevents a guessed packet or misclassified health payload from
generating desktop input.

`jring capabilities --simulate` demonstrates the versioned non-health inventory. With
an explicitly selected device, `jring capabilities --address-file ...` enumerates only
standard service/characteristic/descriptor metadata. It never reads a HID Report Map
or report value and never subscribes. `readable` describes an advertised GATT property;
HID usability and operating-system attachment remain unverified/not checked.

`time-sync` is the sole hardware write and targets the standard Bluetooth Current Time
characteristic. Some rings may not expose it; failure is safe. History export accepts
`.csv` or `.jsonl` and refuses to replace an existing file unless `--force` is given.
Hardware history deliberately reports
"not verified" rather than guessing a vendor command.

## Least-privilege BlueZ setup

Run `bluetoothd` through your distribution's normal service management. Prefer a local
desktop/logind session, where BlueZ's D-Bus policy grants Bluetooth access. Do not run
the client as root and do not make the system D-Bus socket world-writable. If a headless
service is required, create a dedicated unprivileged user and a narrowly scoped polkit
rule granting only BlueZ scan/connect/GATT operations; exact policy syntax varies by
distribution. Do not grant network, serial-port, storage, or sudo access to this client.

Pair through the normal BlueZ UI or `bluetoothctl` only if the selected ring requires
it. This client does not automate trust or pairing. Disable Bluetooth when not in use.

## Privacy and threat model

BLE advertisements expose proximity and may expose a stable address. Health readings
and exported history are sensitive. Discovery output must use per-process aliases;
diagnostics omit raw payloads and addresses. Exports remain local, are written
atomically with restrictive permissions, and should be stored on encrypted media.

The client assumes the local user, Python environment, BlueZ, and kernel are trusted.
It defends against malformed/truncated BLE values, accidental selection, unbounded
waits/retries, guessed vendor writes, telemetry, and accidental identifier logging. It
does not defend against a compromised host, malicious Bluetooth stack, radio tracking,
or a device presenting false measurements. Measurements are not medical advice.

No cloud API, authentication bypass, account impersonation, firmware flashing, DFU,
contact/notification upload, or telemetry is implemented.

## Validation

Run all repository tests with:

```sh
python -m pip install -e '.[ble,dev]'
python -m pytest
```

The optional hardware test is skipped unless both `JRING_HARDWARE_TEST=1` and an exact
`JRING_DEVICE_ADDRESS` are supplied. It is currently only an opt-in guard because no
ring was available during development. See [DESIGN.md](docs/DESIGN.md) for evidence,
confidence levels, architecture, acceptance criteria, and exact gaps. Human-facing
behavior and its test map live in [UX_SPEC.md](docs/UX_SPEC.md).
The cross-persona [adversarial UX review](docs/ADVERSARIAL_UX_REVIEW.md) records the
v0.5 trust repairs and the gates that remain before live sensor-to-input bridging.
All deferred work, including non-health HID/sensor functionality, is owned by the
[JTBD/SDD/TDD roadmap](docs/ROADMAP.md) and its linked GitHub issues.

## License

JRing Client is distributed under the [MIT License](LICENSE).
