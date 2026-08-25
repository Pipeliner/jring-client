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
aliases and a possible-JRing label explicitly identified as a client-side name
heuristic, then asks a default-no confirmation before it can connect. It never
auto-selects a sole result. Discovery JSON includes the same
`likely_jring_basis=client_name_heuristic` boundary. This guided path is human-only and
does not support `--json`; scripts should keep using the mode-0600 address file.

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

Inspect the complete accounting of the recovered interface declarations—without
claiming complete decompilation, protocol parity, or hardware support—and without
Bluetooth, a ring, or optional dependencies:

```sh
jring protocol-coverage
jring protocol-coverage --json
```

The report accounts for 112 requests and 105 callbacks with zero unclassified ledger
entries: 85 offline request codecs, 26 non-runnable static behavior-evidence rows,
and one non-runnable control model. Evidence rows are not behavioral parity or callable
features. All 86 callback declarations classified as opcode-originated have offline
decoder coverage; this is not a count of distinct wire families.
Every one of those 85 request and 86 callback codec rows links to an importable Python
encoder, parser, typed factory, or stateful pipeline. The four shared `23` sensor
wrappers have exact start selectors and a common stop selector. The five raw callback
rows use callback-specific fail-closed parsers over the shared raw frame decoder, so no
codec-family binding remains unresolved.
For the 37 builder families reviewed instruction-by-instruction, a separate sanitized
ledger records byte-exact parity on the Python encoders' accepted domains: all are
fixed 20-byte, checksum-free builders; 31 use the source main queue and six the raw
queue. Only sensor-session start/stop are front-inserted. Source gates, logging, queue
draining, alarm partial-enqueue behavior, and dial-state queue clearing are explicitly
not reproduced.
The report also gives every deterministic request codec one closed request/callback
correlation row. Proven single responses, shared streams, stateful families, raw event
candidates, callback-silent failures, and explicit unknowns remain distinct. Twenty
rows still have no exact terminal relationship; local quiet is never promoted to
success, and matching requires an operation token plus connection generation.
The fake-only transaction simulator can now compose all seven query families, the
screen-light subcommand, and all eight typed settings families. A synthetic mutation
acknowledgement is parsed through the same closed correlation rules; this still creates
no client method, live adapter, write authority, retry policy, or hardware claim.
All seven personal-setting encoders can likewise compose success-only fake matchers;
their private input stays hidden and absence of a proven failure opcode remains explicit.
Eight single-frame behavior mutations are also composable with paired acknowledgements.
Alarm batches are deliberately rejected by this factory because their multi-frame,
source-sequential semantics require a separate state machine.
Seven additional no-argument main queries and the typed screen-light request use
subcommand-aware fake matchers. Streaming Wi-Fi scan is rejected rather than being
misrepresented as a singleton response.
An independent app-use view shows that the APK directly invokes 51 of 112 request
targets at 152 static call sites; 43 uninvoked SDK entries still have wire codecs, 14
are local/composite, and four are no-op stubs. It also reconciles 181 callback invoke
sites: 125 in the main response handler, six in the raw handler, and 50 elsewhere.
Those sites reach 103 of 105 declarations; two have no direct invoke. These static
counts do not prove runtime reachability.
The sanitized Binder crosswalk adds exact transaction IDs and semantic-versus-Parcel
kinds for all 217 rows. Every ID is contiguous and agrees across interface, Proxy,
Stub, and implementation; all calls are synchronous and all ordered marshalling checks
match. Each row links its existing app-use and codec status while leaving wire
relationships explicitly unclassified. Binder parity still does not establish BLE
semantics or live support.
The report distinguishes those from absent,
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
actions, the cumulative step counter, unknown motion channels, classic profile/RFCOMM
evidence, classic metadata callbacks, the host volume-state request, and raw non-health
framing. It also exposes 15 closed general-use rows for already-decoded AI/speech,
Wi-Fi, system-state, EQ/media/dial, touch, and screen-light surfaces:

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

`jring capabilities --simulate` demonstrates the versioned non-health inventory. The
offline `jring non-health-capabilities` view lists all 13 statically mapped device
actions: six input candidates and seven blocked side-effecting actions. With
the same local-only command, five supplemental evidence rows keep classic profile
attachment, an RFCOMM socket lifecycle reference, two classic metadata callbacks, and
the host volume-state request visible without claiming that any is live or
HID-compatible. The reviewed helper only constructs and closes the classic socket;
actual OTA transfer uses GATT, and no RFCOMM connect, read, or write was observed. With
the same view, 15 general-use rows link these static surfaces back to their recovered
request/callback ledger names. Network names, credentials, media references, and
AI/voice state are privacy-classified but never stored. Every row remains non-runnable,
hardware-ineligible, and hardware-unverified. With an explicitly selected device,
`jring capabilities --address-file ...` enumerates only
standard service/characteristic/descriptor metadata. It never reads a HID Report Map
or report value and never subscribes. A read property is only advertised metadata; no
value was read. Repeated HID Report characteristics remain separate numbered metadata
instances with their own Report Reference descriptor state.
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
