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
jring status --simulate
jring history --simulate --output history.jsonl
jring input --simulate --map step=click:left
```

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

Run `jring doctor` before touching hardware. It passively checks Python, Linux, Bleak,
BlueZ, evdev, and `/dev/uinput`, explains exactly what is missing, and reports
simulator, BLE-hardware, and desktop-input readiness independently. It does not scan,
connect, write, or use the network. Automation can use
`jring doctor --json --require-hardware` when missing BLE prerequisites should produce
a nonzero exit status. Use `--require-input` to require evdev and writable `uinput`
instead.

## Use a sensor event as desktop input

The simulator can exercise a non-health `step` event as an allowlisted keyboard key or
mouse click. Preview is the default and never emits operating-system input:

```sh
jring input --simulate --map step=key:space
jring input --simulate --map step=click:left
```

To deliberately inject one simulated event through Linux `uinput`, install the input
extra and add the confirmation flag:

```sh
python -m pip install -e '.[input]'
jring input --simulate --map step=key:space --allow-input
```

Named keys are `space`, `enter`, `escape`, the four arrows, `page-up`, and
`page-down`; mouse clicks are `left`, `right`, and `middle`. Arbitrary key codes and
shell commands are rejected. Status can report that a standard Bluetooth HID service
was advertised, but service presence alone does not prove that HID reports work or an
operating-system input device exists.

Hardware JRing motion events are not enabled yet: the vendor event frames are not
verified. This boundary prevents a guessed packet or misclassified health payload from
generating desktop input.

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
