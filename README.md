# JRing client

This is an offline-first Python 3 Linux client for explicitly selected JRing BLE
devices. It performs safe standard Bluetooth GATT reads today and provides a tested
simulator. Vendor writes and hardware history remain disabled until packet captures
from the owner's selected ring establish the protocol exactly.

## Install and run

Use a virtual environment. For simulation, the base project is sufficient:

```sh
python -m pip install -e .
jring status --simulate
jring history --simulate --output history.jsonl
```

For hardware, install the optional Bleak dependency, then select the ring by its exact
address. The CLI never connects to a discovery result automatically.

```sh
python -m pip install -e '.[ble]'
jring discover
jring status --address AA:BB:CC:DD:EE:FF
jring time-sync --address AA:BB:CC:DD:EE:FF --yes
```

`discover` passively lists per-run aliases, coarse name matches, RSSI, and advertised
service UUIDs. It neither reveals addresses nor selects/connects a device. Use BlueZ
tools locally to obtain and explicitly pass the intended ring address.

Human-readable output is the default. Add `--json` to `status` or `discover` for
automation. Both task-first options (`jring status --simulate`) and the original
global-first form (`jring --simulate status`) are supported.

`time-sync` is the sole hardware write and targets the standard Bluetooth Current Time
characteristic. Some rings may not expose it; failure is safe. History export accepts
`.csv` or `.jsonl`. Hardware history deliberately reports
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
diagnostics omit raw payloads and addresses. Exports remain local, are atomically
replaced, and should be stored on encrypted media with restrictive permissions.

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
python -m pip install -e '.[dev]'
python -m pytest
```

The optional hardware test is skipped unless both `JRING_HARDWARE_TEST=1` and an exact
`JRING_DEVICE_ADDRESS` are supplied. It is currently only an opt-in guard because no
ring was available during development. See [DESIGN.md](docs/DESIGN.md) for evidence,
confidence levels, architecture, acceptance criteria, and exact gaps. Human-facing
behavior and its test map live in [UX_SPEC.md](docs/UX_SPEC.md).
