# JRing client

This is an offline-first Python 3 Linux client for explicitly selected JRing BLE
devices. It performs safe standard Bluetooth GATT reads and one bounded standard
heart-rate notification today, and provides a tested simulator. Vendor writes and hardware history remain disabled until packet captures
from the owner's selected ring establish the protocol exactly.

## Install and run

From a clone, create an isolated environment. `python3` is used for bootstrapping on
Linux distributions that do not provide a `python` command:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
jring
jring doctor
jring non-health-capabilities
jring protocol-coverage
jring status --simulate
jring heart-rate --simulate
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
jring heart-rate --address-file ~/.config/jring/address --allow-notifications
jring time-sync --address-file ~/.config/jring/address --yes
```

The legacy `--address` option remains available, but it exposes the identifier in
shell history and process listings. Neither discovery result aliases nor addresses are
persisted by the client, and discovery never auto-selects a device.

For an interactive status or metadata-only capability check without putting an address
in argv or a file, use:

```sh
jring status --select --active-scan
jring capabilities --select --active-scan
jring heart-rate --select --active-scan --allow-notifications
```

The scan and connection are separate consent steps. The command shows temporary
aliases and a possible-JRing label explicitly identified as a client-side name
heuristic, then asks a default-no confirmation before it can connect. It never
auto-selects a sole result. Discovery JSON includes the same
`likely_jring_basis=client_name_heuristic` boundary. This guided path is human-only and
does not support `--json`; scripts should keep using the mode-0600 address file.
The capabilities path reads service/characteristic metadata only; it never reads
values, subscribes, or writes. It evaluates fixed main/raw vendor route structure and
current-snapshot target ownership without exposing target identities. Structural
readiness grants no live eligibility, owner authorization, or hardware support.

For a bounded owner investigation of one notify-capable metadata row, keep the address
and capture outside the repository and choose the exact service, characteristic, and
instance from the explicitly opted-in, metadata-only selector manifest
(`jring capabilities ... --include-observation-targets --json`):

```sh
jring capabilities --address-file ~/.config/jring/address \
  --include-observation-targets --json \
  | jq -r '.observation_targets[] | [.service_uuid, .characteristic_uuid, .instance_id] | @tsv'
jring observe --address-file ~/.config/jring/address \
  --private-output ~/.config/jring/observation.json \
  --service-uuid SERVICE --characteristic-uuid CHARACTERISTIC --instance-id INSTANCE \
  --max-records 8 --allow-connect --allow-notifications --allow-observation
jring review-observation --private-input ~/.config/jring/observation.json
```

`observe` makes one bounded connection and notification subscription, then writes only
a new mode-0600 private record. It never reads a characteristic, writes a vendor value,
decodes a frame, enables an input action, uploads, opens a browser, or retries.
`review-observation` is offline-only and displays only capture state and count; it
never renders a captured frame, address, target identity, or private path. An
observation is not proof of protocol meaning, compatibility, or runtime authorization.

The selector manifest contains only service UUID, characteristic UUID, and a
connection-scoped instance ID for notify endpoints with exactly one advertised CCCD.
It is omitted by default and contains no characteristic values, addresses, paths, or
connection generations.

To prepare a reviewable public handoff after a metadata-only probe, add
`--issue-draft-url` to `capabilities`. The client creates a GitHub issue-draft URL
locally; it does not open a browser or make a network request. Its prefilled text is
limited to coarse inventory states and a route count. Review it before opening it—raw
packets, addresses, values, health data, private paths, and firmware details are never
included.

`jring heart-rate` collects exactly one standard Bluetooth Heart Rate Measurement and
then disables its notification before displaying a result. Hardware use requires
`--allow-notifications` before a transport is constructed because BlueZ may perform
standard CCCD control traffic while enabling or disabling the notification. The
client sends no vendor characteristic command, saves no measurement, omits raw bytes
and the device address, and does not turn an advertisement or one valid sample into a
broad model/firmware compatibility claim. Output is fitness information only, not
medical advice. Use `jring heart-rate --simulate` for the synthetic 72 bpm sample;
simulation rejects the hardware-only consent flag and performs no Bluetooth operation.

Human-readable output is the default. Add `--json` to `status`, `heart-rate`,
`capabilities`, or `discover` for
automation. Both task-first options (`jring status --simulate`) and the original
global-first form (`jring --simulate status`) are supported.
Simulated human output clearly states that no ring was contacted; structured results
and exports include source and schema provenance.

## Comparative research, alternatives, and data sources

Start with the [external JRing / 56ff prior-art ledger](docs/EXTERNAL_JRING_PRIOR_ART.md).
It links the public [PulseLoop iOS](https://github.com/saksham2001/PulseLoopiOS) and
[PulseLoop Android](https://github.com/foureight84/PulseLoopAndroid) implementations,
an [independent JRing capture write-up](https://jw-tech.fr/en/blog/smart-ring-reverse-engineering),
and SR08 retail/manual material. These sources are useful comparative evidence for
forming reconciliation candidates. An implementation may inform an explicitly
unverified offline decoder or owner-consented probe candidate, but is not verification
or runtime authorization: a model name, frame resemblance, or third-party claim never
marks a JRing capability supported, hardware-verified, or safe to replay.

For adjacent tools or a different companion-app approach, see
[BlueZ](https://www.bluez.org/) and [Gadgetbridge](https://gadgetbridge.org/). They are
alternatives to evaluate on their own terms; this project does not claim they support a
selected JRing or share its protocol. The authoritative sources for JRing behavior stay
separate: the clean-room recovered scope, the public prior-art ledger, and
owner-authorized private evidence. Each external claim must be independently reconciled
before it can affect a specification, and owner-hardware evidence is still required
before a live capability can be considered.

JSON successes include `schema_version`, `operation`, `source`, and `ok`. JSON failures
write one redacted envelope to stdout and nothing to stderr. Stable failure exits are
2 for usage, 3 for unavailable prerequisites/device, 4 for timeout, 5 for protocol
incompatibility, 6 for permission, 70 for an unexpected internal failure, and 130 for
interruption. Scripts should branch on the error `code`, not its explanatory message.

Contributions are welcome, but raw Bluetooth captures, app archives, device addresses,
account details, timestamps, health values, and vendor payload dumps do not belong in
GitHub issues or commits. Read [CONTRIBUTING.md](CONTRIBUTING.md) for the local
fail-closed evidence workflow and [SECURITY.md](SECURITY.md) for private reporting.
Schema-2 public candidates currently cover only one sealed vendor-main device-info
canary shape; validation does not enable it, authorize hardware, or establish support.
The local validator also accepts a separate owner-only, self-declared schema-2
historical observation for that one operation. It withholds identifiers and device
context and must remain outside Git at mode 0600 or read-only 0400; validation performs
no Bluetooth action, and derivation/publication are refused. This is a privacy and
consistency boundary, not Bluetooth parity or a reusable consent token.

The separate owner-hardware transport canary is specified in
[OWNER_HARDWARE_EVIDENCE.md](docs/OWNER_HARDWARE_EVIDENCE.md). It supports fresh guided
selection, creates one new private mode-0600 record, and requires independent
connection, notification, and write authorization. Its response value is discarded:
even a matched terminal proves transport correlation only, not device-information
contents, firmware support, vendor authorization, or live runtime eligibility. Offline
review and sanitized public-row derivation are separate commands and perform no
Bluetooth I/O. An interrupted canary is non-retryable: its write may already have
escaped, so inspect the requested private record before considering another manual
attempt. Human review previews every field eligible for the public row before a
separate derivation step. The versioned public artifact labels its model and firmware
scope owner-declared and carries explicit false runtime and repeat authority; neither
`promote` nor `candidate_success` enables an operation.

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

The report answers the overall question first: complete APK-to-Python Bluetooth
capability parity is not established. It then separates complete accounting within the
known AIDL declaration scope from incomplete source semantics, live vendor availability,
and hardware verification. JSON command success likewise remains distinct from the
top-level `bluetooth_capability_parity` verdict.

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
The artifact supplement now keeps the older broad Android Bluetooth source-reference
counts explicitly non-exhaustive and publishes a separate direct-instruction inventory
for the complete owned application/SDK scope. That inventory classifies 236 referencing
methods across 63 classes with zero unclassified, including GATT lifecycle, reads and
writes, descriptor/notification setup, MTU, connection priority, RSSI, discovery,
legacy/modern scanning, bonding, classic profiles/RFCOMM, and adapter power. This is
reference classification—not semantic, dependency/transitive, runtime, or hardware
completion.
The report also gives every deterministic request codec one request/callback
correlation row. Proven single responses, shared streams, stateful families, raw event
candidates, callback-silent failures, and explicit unknowns remain distinct. No row
remains in the generic topology bucket, but 58 of 85 retain at least one explicit
caveat. That zero means only that every row has a more specific static classification;
it does not establish response semantics, live availability, or hardware support. The
contact-fingerprint request and notification share an exact `46`
four-byte shape but remain an unproven event relationship, not an acknowledgement. The
phone-volume path
is modeled as an inbound device request followed by an outbound host-state projection,
never as an acknowledgement. The SMS-send path likewise has only an inbound `4d/06`
event and an outbound `4d/07` acknowledgement candidate: value propagation, ordering,
failure, and terminal behavior remain unproven.
Weather refresh, motion delivery, ChatGPT action, and fragmented chat content now have
explicit non-terminal event/shared-topology candidate rows too; none claims request
ownership, causality, acknowledgement, or hardware support. Terminal rules comprise 36
single matched responses, 29 with no proven terminal, 17 per-frame only, two
local-quiet-unknown, and one metadata-or-marker-else-local-quiet-unknown.
Four private E-card/SMS sync rows now preserve only their shared inbound-update and
outbound-batch topology. Content, opaque fingerprints, branch selection, ordering,
completion, and local data access remain redacted or unproven.
Contact-content has only a conditional reverse-direction sync candidate: a fingerprint
notification may cause a local mismatch branch to reload private contacts and send a
fingerprint plus content batches, while local contact changes can send the same outbound
sequence without a notification. No acknowledgement, response, terminal, private-store
reproduction, or runtime is established.
The three formerly generic rows now record a narrower bounded fact: the reviewed
dispatcher exposes no eligible callback for the exact phone-call-state, AI-language,
or app-state discriminator. Responses on another discriminator, delivery, device side
effects, failure, and terminal behavior remain unproven; quiet is never success.
App-ID now has only a cross-opcode notification candidate, while the shared Phone-MAC
opcode is recorded as an unrelated host-volume collision with no eligible callback.
Two private network-configuration rows retain only a disjoint Wi-Fi state-event
candidate, and the media-FTP completion-named call retains only a source-local
terminal-shaped projection shared by success and exhausted failure. None establishes
identifier equality, credential use, connection, transfer, acknowledgement, runtime,
or hardware support.
Local quiet is never promoted to success, and matching requires an operation token
plus connection generation.
The fake-only singleton transaction simulator composes four static query families, the
screen-light subcommand, and six typed settings families with statically matched terminals.
Its operation-bound device-system path performs one exact synthetic `54/11` query
write and closes only on an exact post-entry `54/12` fake response. The private neutral
callback code is excluded from structured output. Fake success is not current device
state, Bluetooth readiness/connection, battery/power, firmware health, owner binding,
live support, or hardware verification.
The two shared sensor-session setting shapes are rejected because their per-frame
projection is ambiguous across four interface wrappers and a shared opcode. The other three static
queries use the separate shared-day history collector because their first matching
frame is not a proven terminal. A synthetic mutation
acknowledgement is parsed through the same closed correlation rules; this still creates
no client method, live adapter, write authority, retry policy, or hardware claim.
Closed request bytes are reconstructed before execution, and notification ownership
starts only when the fake write coroutine actually enters; an expired pre-entry call
or a pre-entry disconnect/cancellation performs no write and owns no response.
Every accepted settings, personal, behavior, command, and phone request also retains
an identity-bound copy of its originally validated execution shape. Post-construction
field or frame changes are rejected before an operation exists; shallow and deep copies
retain the same sealed shape. Response ownership checks opcode and any required branch
discriminator before length: truncated unrelated traffic stays unrelated, EQ SET-kind
traffic cannot close an EQ GET query, and heart-session start and stop keep distinct
`14/94` and `15/95` terminals.
All seven personal-setting encoders can likewise compose success-only fake matchers;
their private input stays hidden and absence of a proven failure opcode remains explicit.
Eight single-frame behavior mutations are also composable with paired acknowledgements.
Alarm batches are deliberately rejected by this factory because their multi-frame,
source-sequential semantics require a separate state machine.
A dedicated fake-only alarm batch simulator preserves the exact base/content frame
order without exposing a live client method. Exact `0d`/`8d` callbacks are recorded
only as uncorrelated per-frame observations: the recovered projection exposes no
proven alarm ID, chunk ID, batch ID, or terminal marker, and the remaining body is
uninterpreted. Privacy-safe callback multiplicity is preserved, but returned fake
calls, callback counts, local quiet, and observation limits never establish batch
success. An observed failure stops only future synthetic writes and taints reuse; no
alarm data is retained in the result.
A separate fake-only notification batch simulator composes the existing bounded
notification planner with the scripted MAIN route. It issues the planner's header,
title, and content frames as ordered sequential fake calls. An exact `12` callback is
associated only with a marker whose frame has already been invoked in that attempt;
this is a per-frame callback observation, not proof of display, delivery, whole-batch
acknowledgement, or a terminal. A future marker is unowned diagnostic traffic: it is
not buffered or later correlated and does not extend quiet, abort, or taint the attempt.
The `92` projection has no proven marker or body semantics, so it cannot identify a
failed frame. The simulator conservatively stops only not-yet-invoked fake writes and
taints reuse without rolling back earlier calls or claiming batch failure.
Returned calls, marker coverage, quiet, and limits never commit the planner's proposed
UID/deduplication state. Caller throttling, source global-overlap behavior, atomic
enqueue/delivery, and source queue acceptance are not reproduced. Results retain no
notification data or frame shape, although the explicit scripted-test transport keeps
private frame calls for focused test inspection. This adds no client method, live
vendor write authority, owner authorization, hardware verification, or input path.
All fake transaction and stream coordinators now share one pure main/raw GATT resolver.
It checks that connection-scoped characteristic metadata is structurally consistent
and refuses UUID ambiguity, missing response-write/notify properties, and CCCD metadata
gaps. Each exact fake coordinator then separately verifies that the resolved targets
belong to its current transport snapshot before synthetic I/O. Bleak retains an opaque
target-to-characteristic map only for current-identity checks and exposes no live target
I/O; its direct write boundary accepts only the guarded standard Current Time
characteristic when exactly one writable instance exists under the Current Time
service and the payload is canonical. Vendor writes and hardware eligibility remain
zero.
Seven additional no-argument main queries and the typed screen-light request use
subcommand-aware fake matchers. Streaming Wi-Fi scan is rejected rather than being
misrepresented as a singleton response.
Three typed command encoder variants—device time plus heart-rate start and stop—compose
because their interface rows have statically matched terminals. Nine typed command
value/event projections and two phone projections no longer become transaction
success; six other command families with no exact response relationship remain
rejected. Only the user-info phone integration has a singleton matched terminal.
Other private sync/content families remain rejected until their streaming or causal
terminal rules are proven.
Across all 85 deterministic requests, a closed fake-singleton eligibility ledger now separates
36 singleton matched terminals, 11 typed non-terminal projections, six ambiguous or
batched per-frame routes, 29 with no proven terminal, and three locally/marker-bounded
streams. Only the first group can enter the success-returning fake engine; this grants
no live, owner-authorized, or hardware eligibility.
Dedicated alarm and notification batch simulators do not change that crosswalk.
`setNotify` remains one of the six ambiguous/batched per-frame rows: its invoked-marker
relationship is not a whole-batch terminal, and every live and hardware count remains
zero.
The scripted fake now has a distinct raw `33f5`/`33f6` route and bounded event
collector. It can write a closed raw command and parse typed raw notifications, but
always reports unknown completeness: an event is not an acknowledgement, reaching an
event limit is not success, and local quiet is not a terminal. Queue size, setup,
overall collection, and cleanup are bounded; concurrent use is rejected and stale
callbacks are made inert before reuse.
Shared multi-sport, oxygen-day, and advanced-sensor-day responses now have a separate
fake history collector. It preserves per-frame callback multiplicities, conditional
multi-sport failure, unrelated-event isolation, and unknown completion at both local
quiet and caller limits; it never emits a synthetic wire-end event.
After accepted oxygen or advanced-sensor data followed by local quiet, it does reproduce
the source's single local end projection with a hidden last-sample timestamp, while
leaving completeness unknown. This collector applies the same bounded-stage,
bounded-queue, single-flight, cancellation-cleanup, and stale-callback rules.

The internal streaming simulators are deliberately separate from the live client:

| Fake-only collector | What it can reproduce | Honest stopping state |
|---|---|---|
| Generic day history | Typed sample/end callback multiplicity | Wire/metadata completion only when explicit; otherwise unknown or aborted |
| Wi-Fi network-name response stream | Advertised count and locally assembled SSID callbacks | Fake-call return leaves protocol completion unknown; uncertain calls taint reuse |
| ECG history | Metadata, event, and one packed-sample callback per frame | No proven terminal; quiet/limit remain unknown |

They accept only the scripted fake transport, retain no raw notification frames after
cleanup, and never contact a Linux Bluetooth device. Private Wi-Fi/health values are
available only through explicitly named local-test accessors and never appear in result
representations or ordinary dataclass serialization.
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

That inventory now labels the device-action, cumulative-step, unknown-motion, Classic
info/name, host-volume, main-chat-action, Wi-Fi callback-code, and touch-mode rows whose passive MAIN
notifications can be exercised
with the exact scripted fake. The same internal collector also exercises the exact
redacted App-ID event at `45/02` without adding a human capability row. The fake
subscribes to its instance-bound synthetic response target and performs zero writes.
It accepts `78/00` and `78/01` only as private, neutral nine-channel callback
projections and `78/09` only as a neutral, private touch-mode setting projection;
every other `78` selector remains unrelated. The motion values are redacted and do
not prove selector meaning, axes, units, cadence, activation, a live sensor event,
gesture, step, button, or input action. The corresponding setter has no observed app
invoke, so inbound `00`/`01` is not an acknowledgement or enabled/disabled state.
The touch value is not an enabled flag, device
state, gesture, tap, button, sensor sample, or input event. The bundled
`setTouchMode` entry has zero observed app invokes, so the projection proves no setter
causation, acknowledgement, terminal, live behavior, or hardware support. Decoded
values remain redacted and hardware- and input-ineligible. App-ID is likewise only an
uncorrelated callback event: it does not prove setter causation, identifier equality,
acknowledgement, or a terminal.
Exact opcode `4E` is separately retained only as a private, neutral chat action-code
candidate. This zero-write fake run owns no request, while the protocol relationship
to nearby request families remains unknown. It does not execute ChatGPT; parse or
retain prompt, response, text, audio, image, or other content; acknowledge a request;
establish a terminal; or create input.
Exact `54/04` is separately projected as one private, neutral Wi-Fi callback state-code
candidate. Address material is discarded, and the fake performs no write, credential
processing, host/ring networking, or radio change. The code does not report whether
Wi-Fi is enabled, connected, joined, current, or internet-reachable; it is not an
acknowledgement, terminal, live behavior, hardware verification, or input.
It is a library test surface, not a live-ring or Classic-attachment command.

The Wi-Fi network-name inventory row separately identifies the existing library-only
fake response assembler. It invokes one exact request only on the scripted fake, never
starts a host or ring Wi-Fi scan, hides private names and fragment metadata from normal
serialization, and treats a returned fake write call, advertised-count equality, local
quiet, and caller limits as unknown protocol completion. It adds no CLI run command,
network authority, live Bluetooth path, or input eligibility.

A separate library-only fake coordinator exercises the proven host-volume reverse
pipeline: one exact fake `49` request can cause one closed projection of explicitly
caller-supplied offline values on the same fake connection. It never reads or changes
desktop audio, never accepts a generic payload, never retries an uncertain write, and
never claims that the returned fake transport call is an application acknowledgement
or protocol terminal. The passive collector remains strictly zero-write; neither path
is exposed as a CLI or live Bluetooth feature.

Separately, the input simulator generates a closed pair of synthetic cumulative-step
frames, decodes them through the recovered `51` parser, baselines the first value, and
accepts one exact increment as a neutral `step` preview. It does not consume passive
MAIN events or accept counter/frame input from the command line. The experimental
counter candidate is not directly dispatchable; only this closed synthetic fixture is
promoted into the existing allowlisted simulator event. That event can preview a
keyboard key or mouse click, but media, volume, and shutter actions cannot yet be
previewed or mapped. Preview is the default and never emits operating-system input:

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

JRing is not a live HID driver. Linux `uinput` is used only for an explicitly approved
simulated event today and is a future translation sink for hardware events only after
those events are owner-verified.

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
hardware-ineligible, and hardware-unverified; a separate
`scripted_fake_decoder_available` field identifies decoder coverage exercised only by
the passive scripted fake. With an explicitly selected device,
`jring capabilities --address-file ...` enumerates only
standard service/characteristic/descriptor metadata. It never reads a HID Report Map
or report value and never subscribes. A read property is only advertised metadata; no
value was read. Repeated HID Report characteristics remain separate numbered metadata
instances with their own Report Reference descriptor state.
HID usability and operating-system attachment remain unverified/not checked.
The same snapshot produces exactly two sanitized vendor-route rows, main then raw.
Each keeps service/metadata availability, structural preflight, and transport target
ownership separate; no characteristic value, target ID, generation, subscription, or
write is exposed or attempted.

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
The APK-first source contract is the complete, evidence-graded
[clean-room functionality specification](docs/APK_FUNCTIONAL_SPEC.md), with linked
request, callback, transport, session, OTA, UI, and data appendices. It describes the
reviewed Android build rather than simulator behavior or a claim of hardware parity.
The cross-persona [adversarial UX review](docs/ADVERSARIAL_UX_REVIEW.md) records the
v0.5 trust repairs and the gates that remain before live sensor-to-input bridging.
All deferred work, including non-health HID/sensor functionality, is owned by the
[JTBD/SDD/TDD roadmap](docs/ROADMAP.md) and its linked GitHub issues.

## License

JRing Client is distributed under the [MIT License](LICENSE).
