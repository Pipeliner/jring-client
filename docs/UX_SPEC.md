# JRing human UX specification

Status: accepted for v0.5 after adversarial review

## Human goal

A Linux user who owns a JRing should be able to understand what the client can safely
do, try it without hardware, and recover from ordinary setup errors without reading a
Python traceback. Safety and privacy must remain visible without turning routine use
into guesswork.

## Product principles

1. Lead with the task: commands read as `jring status --simulate` and
   `jring history --simulate --output history.jsonl`.
2. Default to human-readable output. Structured JSON is explicit with `--json`.
3. Errors name the remedy and do not expose internals unless a developer runs tests.
4. Discovery never selects a device and never prints a Bluetooth address.
5. A hardware write requires an explicit confirmation on the same command.
6. Output never includes an address, raw health payload, or hidden telemetry.

## Private observation

`jring observe` is a deliberate owner-investigation command, not a feature-enablement
command. It requires a mode-0600 selected-address file, a new mode-0600 private output,
one exact locally enumerated service/characteristic/instance target, a bounded deadline
and record limit, and explicit connect, notification, and observation acknowledgements.
Before connecting it states that it will not read a characteristic, write to the ring,
decode a value, emit input, upload data, open a browser, or retry. Human and JSON output
withhold raw bytes, address, target identity, and private path; completion never changes
runtime eligibility.
7. Readiness checks are passive and distinguish optional hardware setup from the
   always-available simulator path.
8. General-purpose input mappings preview by default, use a closed action vocabulary,
   and require explicit authorization before emitting operating-system input.
9. Simulation and hardware selection are mutually exclusive, and every simulated
   result carries visible, machine-readable provenance.
10. Accepted options are never ignored. Radio-active scanning and replacement of an
    existing export each require an explicit flag.
11. JSON automation receives an additive versioned envelope on every accepted JSON
    path, including failures; stderr stays empty in JSON mode.

## Acceptance scenarios

### Bare terminal home

Given no arguments and no `--json`, when a person runs `jring`, then the client exits
successfully after rendering a fixed, dependency-free terminal home. Its reading order
is: no-I/O boundary, safe simulated status command, optional passive diagnosis,
offline evidence commands, hardware preparation, unavailable capabilities, and help.
It asks no question; uses no color, cursor control, terminal-size detection, or
interactive widget; and does not parse a command, run diagnostics, construct a
transport, scan, select a ring, access the network, or emit desktop input. This is a
least-surprising terminal start screen, not a curses UI or a GUI.

Given `jring --json` with no command, the command preserves the existing schema-1 JSON
usage-error envelope and never prints the human home. Explicit commands and `--help`
are unchanged.

### First safe success

Given no ring and no optional Bluetooth dependency, when a person runs
`jring status --simulate`, then they see battery, identity, capability, and safety
information in readable text and the command exits successfully.

### Automation

Given the simulator, when a person runs `jring status --simulate --json`, then stdout
is valid JSON with stable field names, includes `schema_version`, `operation`, `source`,
and `ok`, and contains no device address.

### One standard heart-rate sample

Given no ring, `jring heart-rate --simulate` exercises the complete bounded
subscription lifecycle against the fake transport and injects the synthetic
`72 bpm` measurement only after subscription confirmation. Human output leads with
simulation provenance and says that no Bluetooth operation occurred. Schema-1 JSON
uses operation `heart_rate`, reports `synthetic`, `measurement.bpm`, a normalized
`measurement.contact_state`, `not_saved` persistence, and non-medical meaning; it
contains no address, raw bytes, or raw flags. A simulator profile remains explicit,
but `--allow-notifications` is rejected because it is a hardware-only consent.

Given an explicitly selected ring, `jring heart-rate` is rejected during argument
parsing unless `--allow-notifications` is present. This happens before construction of
the hardware transport. Help and the usage error disclose that enabling and disabling
the standard notification through BlueZ may perform standard CCCD control traffic.
The runtime validates one connection-owned, unambiguous `180d`/`2a37` notify endpoint
with one `2902` descriptor, subscribes once, accepts one valid measurement, disables
the notification, and closes the connection. It performs no characteristic read,
vendor command, retry, background stream, export, or persistence.

Human results announce hardware provenance, the one-connection observation, fitness-
only/non-medical meaning, unknown general model/firmware support, no vendor command,
and completed notification cleanup. JSON represents the same facts with stable enums.
Neither human nor JSON success is emitted until both notification
cleanup and connection-context cleanup succeed; any timeout, malformed value,
disconnect, ambiguity, overflow, cancellation, unsubscribe failure, or close failure
returns no measurement. Guided `--select --active-scan --allow-notifications` reuses
the human-only ephemeral-alias and default-no connection flow; automation uses a
mode-0600 address file.

`jring capabilities` reports standard Heart Rate metadata separately from HID:
service, measurement notify property, instance count/resolution, CCCD presence, exact
targeting readiness, and explicit `not_read`, `not_attempted`, and `not_tested` states.
Metadata inventory never starts a notification and never claims live delivery or
model/firmware compatibility.

### Automation failures

Given `--json`, when parsing, prerequisites, permissions, timeouts, protocol
compatibility, or internal execution fail, stdout contains exactly one JSON object and
stderr is empty. The object includes `schema_version`, `operation`, `source`, `ok:
false`, and an `error` object with stable `code`, `retryable`, and a sanitized human
`message`. It never includes a traceback, Bluetooth address, BlueZ path, or raw payload.

Exit meanings are stable within the current CLI major version:

| Exit | Error code | Meaning | Retryable default |
|---:|---|---|---|
| 0 | none | Operation completed | no |
| 2 | `usage` | Arguments or requested mapping are invalid | no |
| 3 | `unavailable` | A required local dependency, device, or connection is unavailable | yes |
| 4 | `timeout` | The bounded operation expired | yes |
| 5 | `protocol_incompatible` | A required service/value is absent, malformed, or unsupported | no |
| 6 | `permission_denied` | Explicit authorization or local permission is missing | no |
| 70 | `internal` | An unexpected client failure occurred | no |
| 130 | `interrupted` | The user interrupted the operation | operation-dependent |

Interruption is retryable only when the operation contract proves that no
side-effecting dispatch could have escaped. The owner-hardware canary reports it
non-retryable after possible dispatch.

Schema 1 additions are backward-compatible: existing success fields remain at their
current paths. Removing or renaming a field requires a new `schema_version`; English
messages are explanatory and are not compatibility keys.

### Offline shell completion

Given an installed package, when a user runs `jring completion bash`, then stdout
contains the parser-derived Bash completion script without scanning, connecting,
writing, opening a browser, or modifying host configuration. `jring completion
--help` names the required `bash` choice, and unsupported shells are rejected.

### Flexible option placement

Given an existing script using `jring --simulate status`, when it upgrades, then the
old placement still works; the more natural `jring status --simulate` works too.

### Recoverable setup error

Given missing hardware support or an unavailable characteristic, when a command
fails, then stderr begins with `jring: error:`, explains the issue, contains no
traceback, and the process exits non-zero.

### Deliberate write

Given a selected device, when a person requests `time-sync` without `--yes` or
`--allow-write`, then argument parsing refuses the operation before connecting.

### Predictable export

Given history records, when the output ends in `.jsonl` or `.csv`, then the client
atomically writes that exact format. Any other suffix is rejected with a clear error.

### Passive setup diagnosis

Given any supported installation, when a person runs `jring doctor`, then the client
checks Python, Linux, Bleak, BlueZ, evdev, and `/dev/uinput` readiness without
scanning, connecting, writing, or using the network. It reports simulator, BLE
hardware, and desktop-input readiness independently with concrete remedies.

The BLE section separates installed prerequisites from passive operational evidence
for the diagnostic tool, system D-Bus, BlueZ daemon, adapter presence, adapter power,
and session query permission. Human output always includes the same stable snake-case
check names used by JSON, including `diagnostic_tool` and `system_dbus`. Each check is
`available`, `unavailable`, `denied`, or `uninspected` with a reason and remedy.
Failure to inspect is never presented as absence or health. Ring compatibility remains
`not_checked`; `doctor` never proves a ring will connect.

Given that the system-bus socket exists but `busctl` is absent, `diagnostic_tool` is
`unavailable` and the D-Bus/BlueZ operational checks are `uninspected`. The remedy asks
for any package that provides `busctl`; it does not claim that D-Bus is broken or name a
distribution package manager. Given that `busctl` is present but a bounded query cannot
reach the bus, `diagnostic_tool` remains `available` while `system_dbus` is
`unavailable`. A recognized authorization denial remains a distinct
`bluez_permission: denied` result.

The standard library has no stable D-Bus client, and optional backend-private Python
interfaces are not treated as a portable diagnostic contract. When `busctl` is absent,
the client therefore reports the missing diagnostic capability rather than opening an
unreviewed fallback or inferring bus health from a socket path alone.

### Readiness automation

Given missing optional hardware prerequisites, when automation runs
`jring doctor --json`, then it receives stable structured checks and a successful exit
because diagnosis completed. With `--require-hardware`, the same report exits nonzero.
Automation can independently use `--require-input` for Linux desktop-input readiness.

### Standard HID visibility

Given a selected device advertising Bluetooth service `1812`, when a person requests
status, then the human and JSON outputs report that the standard HID service was
observed while usability remains unknown. The client does not reinterpret or log raw
HID reports.

### Read-only non-health capability inventory

Given no ring, `jring non-health-capabilities` starts with the boundary that live ring
input is unavailable, JRing is not a live HID driver, and Linux `uinput` is currently
only a simulator/future translation sink. Screen-reader order is task-first: statically
classified device actions and cumulative-step/unknown-motion candidates precede
standard HID metadata, classic profile/RFCOMM evidence, host integration, general-use
codecs, and raw non-health framing. A general-use section lists the 15 already-decoded
AI/speech, Wi-Fi, device-system, EQ/media/dial, touch, and screen-light surfaces.
Every item carries evidence, maturity, neutral meaning, privacy classes, recovered
request/callback operation names, runnable/hardware-eligibility, hardware-verification,
live, candidate, scripted-fake-decoder coverage, and input-eligibility states. All
runnable, hardware-eligible, hardware-verified, live, and input-eligible states are
false. The device-action, cumulative-step, unknown-motion, Classic info/name,
host-volume, main-chat-action, and touch-mode rows say that passive scripted fake event decoding is
covered. Unknown-motion coverage means only exact `78/00` and `78/01` private,
nine-channel callback projections with zero writes. Values are redacted; selector
meaning, axes, units, cadence, activation, sensor-event, gesture, step, button, and
input semantics are not proven. Touch-mode
coverage means only a private, neutral setting projection for exact `78/09`; it grants
no enabled/state, gesture, tap, button, sensor, input, setter-causation,
acknowledgement, terminal, live, or hardware meaning. The Wi-Fi network-name row says
only that a separate library fake can assemble caller-supplied count/fragment
responses; it performs no host or ring Wi-Fi scan. This does not make media, volume,
or shutter actions
previewable or mappable, and the separate input simulator generates only a synthetic
step event. Every operation link
must still exist in the recovered codec or callback-behavior ledger.
Main-chat-action coverage means only one private, neutral, passive candidate from exact
opcode `4E`. The fake run owns no request and the protocol relationship stays unknown;
it grants no ChatGPT/content execution or retention, acknowledgement, terminal, live,
hardware, or input meaning.
Device-action labels are source classifications only; their inventory meaning remains
`unverified_static_action_code`, and available/input-eligible state is announced before
future candidacy.
The command is local-only: it rejects simulation and device selectors and constructs
neither a BLE transport nor an input sink.

For metadata on an explicitly selected ring, `jring capabilities --select
--active-scan` reuses the same ephemeral-alias, default-no, human-only selection flow
as status. Confirmation names the capabilities task. After confirmation it inventories
only services, characteristics, properties, and descriptors; it does not read values,
subscribe, write, persist an address, or expose an address in output.

Given a selected device or the HID simulator, when a person runs `jring capabilities`,
then the client enumerates standard GATT metadata only. Human and schema-1 JSON output
distinguish service `advertised`, characteristic `read_property_advertised` or
`advertised`, missing
`unsupported`, malformed optional descriptor metadata, `not_verified` usability, and
`not_checked` OS attachment.

Given `jring capabilities --issue-draft-url`, the client locally creates a reviewable
GitHub issue-draft URL and includes it in the matching human or JSON result. It does
not open a browser or issue a network request. The fixed draft names itself
unverified and contains only coarse inventory/metadata states plus vendor-route count;
it excludes device identifiers, targets, paths, packets, values, health information,
battery, and firmware fields. Human output tells the owner to review the draft before
opening it. A draft cannot establish compatibility, authorization, or runtime support.

The vendor section always presents exactly two rows in main-then-raw order. For each,
service and metadata inventory availability, the stable structural preflight result,
and current-snapshot transport target ownership are distinct fields. If either source
inventory is unavailable or timed out, preflight is `not_evaluated`; an empty fallback
is never mislabeled unsupported or missing. A structural success requires the exact
service-bound request/response pair, response-capable request write property, notify,
one advertised CCCD, matching current connection generation, and consistent opaque
target metadata. Both targets must independently pass `owns_target` to receive the
`current_snapshot_owned` label. Output never includes either target, an instance ID,
connection generation, backend object/path, descriptor instance ID, value, payload, or
frame. Every row remains metadata-only, non-runnable, live-ineligible,
owner-unauthorized, hardware-ineligible, and hardware-unverified.

`read_property_advertised` means only that the GATT characteristic metadata advertises
a read property; no value was read or understood. Inventory never reads the HID Report Map, captures a
report, subscribes to HID/vendor/health notifications, starts a measurement, or prints
addresses, D-Bus paths, descriptor values, report maps, or payloads. A missing or
malformed Report Reference descriptor does not hide valid HID characteristic states.
Repeated HID Report characteristics are rendered as separate numbered instances with
per-instance opaque metadata ID, property state, and Report Reference IDs/states. UUID
deduplication never hides multiplicity. Heterogeneous instances aggregate as
`multiple_mixed`; homogeneous instances use `multiple_consistent`. Report Reference
coverage distinguishes all, none, mixed, malformed, and malformed-mixed peers.
Opaque IDs are metadata-only and explicitly not targetable by current reads or
subscriptions; no backend handle or object is serialized.
No hardware motion event appears as verified until an accepted issue-#1 fixture proves
its non-health meaning.
The classic rows remain a separate section from standard HID: Android attachment
plumbing and an OTA socket helper do not prove a HID profile, while decoded classic
metadata does not prove attachment. The raw action/payload and unknown-motion rows also
state when the reviewed app callback discards its arguments, keeping SDK dispatch
distinct from app consumption.

Known vendor UUIDs are inventoried in both service and characteristic positions.
Each observation states only its location and `meaning: unknown`; a writable property
does not make a vendor operation usable. Human output says that values were not read
and writes remain disabled. If service enumeration fails but characteristic metadata
is available, those independent observations remain visible and the overall result is
`partial` rather than unsupported.

### Honest offline vendor decoding

Given a synthetic, exactly 20-byte vendor response, the offline protocol library
decodes only statically proven fields and rejects wrong lengths, unrelated opcodes, and
failure branches. Band functions are exposed as 96 indexed flags in wire order, with
app-derived names clearly distinguished from hardware verification. Bounded history
frames expose raw device epoch seconds and deterministic record spacing.
Coverage metadata separates recognized failure branches from direct callback delivery,
including the conditional byte-1 predicate on `a5`.

Offline decoders do not subscribe, write, infer that a frame ends history, adjust old
records using the host's current timezone, or reproduce the Android SDK's timeout
callbacks. Advanced sensor fields and unverified sport codes retain neutral names.
No decoded frame becomes eligible for hardware merely because the parser accepts it.
The decoder also preserves the recovered many-to-many dispatch for opcode `25`: one
synthetic frame can be decoded as multiple-sport data and can satisfy the generic
sensor-mode acknowledgement parser, without inventing a second opcode family. The
result reports the exact one-success-then-six-samples projection order.
Four-byte values on SDK paths backed by Java's signed integer parser fail closed above
`7fffffff`; ECG paths proven to use a wider parser keep the full unsigned range. A
failed sensor open or close result reports requested direction separately and leaves
actual active state unknown.
Device revision and dial-code callback strings retain exact fixed width and uppercase
hexadecimal representation; numeric properties are explicitly convenience views.
Any deliberate divergence from SDK callback behavior is labeled as hardening or
normalization: exact frame length, bounded lengths and assembly, strict text decoding,
redaction, raw timestamps, unknown local closure, and collapsed dual projections are
never called callback-equivalent.

Given a typed offline mutation request, its encoder preserves the proven 20-byte layout
while rejecting low-byte wrapping, implicit host locale/charset use, partial alarm
batches, unsafe text truncation, and unknown mode fallbacks. Frames and private values
do not appear in representations. All 26 mutation families remain static-only,
hardware-ineligible, absent from the client/transport, and unavailable as live writes;
health, reproductive, reset, identifier, and private-text operations retain their risk
boundaries.
The evidence view must identify the source language default, the alarm wrapper's
retained sequential/non-atomic pipeline, and the dial wrapper's pre-enqueue queue/state
clears. Exact wire bytes must never be presented as reproduction of those omitted
behaviors.

Given any of the 46 additional main-command codecs, the request reports a closed
operation identity plus privacy/risk or wire-parity metadata. Wi-Fi scanning is an
active network action, never a read-only query. Private phone-integration requests hide
both content and frame counts, reject ambiguous or lossy inputs, and identify omitted
timeout/local state. Notification content that depends on retained deduplication and a
generated sequence is planned only by an ephemeral-keyed, digest-retaining, bounded
offline state machine. Its output state is proposed only after atomic enqueue and does
not imply delivery; acknowledgement, planner/overlap serialization, throttling, and
atomic live delivery remain blocked. Together with the seven paired queries, six raw requests, and 26 settings
mutations, the ledger reports 85 offline request codecs.
The separate notification fake may exercise that frame plan, but its sequential fake
calls do not satisfy the planner's atomic-enqueue condition and never commit the
proposed state.

Given the complete request ledger, the other 26 SDK methods expose non-runnable static
behavior evidence—not behavioral parity—and the raw CCCD method exposes one
non-runnable control model. Local
BLE models accept no address, UUID, or payload; platform models do not perform network,
filesystem, cache, or callback registration work; OTA evidence cannot parse a binary,
open a path, contact metadata services, or write SUOTA characteristics. Thus all 112
requests are represented while every live and hardware-verified vendor count stays zero.
The OTA model also warns that the source's nominal info-only call can download and
overwrite a cache file on a fresh metadata response even when automatic start is off.

The machine-readable operation ledger accounts for all 112 SDK requests exactly once
and keeps routing separate from Python maturity. Its presence does not imply 112 useful
Bluetooth operations: local, cloud, filesystem, conversion, DFU, dynamic-GATT, and
no-op interface methods remain visibly distinct, and every live vendor state is false.
The paired callback ledger accounts for 105 declarations and separates 86 declarations
classified as opcode-originated, 14 platform/network/transport callbacks, three APK-generated local
end projections, and two declarations with no invocation site. This prevents an
interface declaration or local timer from being presented as a distinct wire family.
Immutable registries link all 85 request-codec and 86 response-decoder rows to importable
Python symbols. Direct, bound, branching, pipeline, stateful, and unresolved-family
relationships remain separate. Four shared sensor wrappers have exact selectors, and
five callback-specific raw wrappers reject every other known raw type. No codec-family
binding remains unresolved.
An independent request-routing view partitions all 112 rows into 79 deterministic main,
six deterministic raw, one shared-preflight, one caller-directed dynamic, one descriptor
control, one DFU, and 23 no-fixed-packet operations. It exposes source queue risks and
Python safety rules without becoming executable.
An app-use supplement separately partitions the same request ledger into 51 directly
invoked APK targets at 152 static sites, 43 uninvoked wire entries, 14 uninvoked
local/composite entries, and four uninvoked no-op stubs. Its callback side records 103
declarations with direct invokes and names the two without one. It preserves 181 exact
invoke sites by origin—125 main-response, six raw-response, and 50 outside those
dispatchers—without double-counting the four targets shared by main and outside code. This keeps
“available in the SDK,” “referenced by the APK,” and “runnable in Python” as separate
claims. Same-spelled request and callback rows remain separate interface roles.
For every non-codec callback, structured evidence distinguishes dispatch origin,
result meaning, silence conditions, side effects, and privacy class. UI text must call
raw-notification `true` a queue-submission acceptance rather than an enable result,
must not render OTA phase/detail as a percentage, and must describe scan identifiers as
derived fragments rather than raw advertisement data.
The Binder supplement exposes exact transaction IDs and safe semantic/Parcel kinds for
all 217 rows. IDs, interface/Proxy/Stub/implementation parity, ordered marshalling, and
synchronous call mode are mechanically checked. Boolean semantics never collapse into
their `int32` Parcel representation, and structural parity never becomes a BLE feature
or semantic-alias claim. Per-row app-use and codec statuses are linked without guessing
a wire relationship or semantic group.

Raw AI/audio/image codecs remain offline and are never subscribed by ordinary client
commands. Synthetic payload projection zero-fills a declared short tail, ignores extra
bytes, enforces configured bounds, and omits data bytes from representations. Generic
and typed callback emission are reported separately; no cross-frame assembler is
invented. A raw request
constructor cannot make a live write; raw notification disable is not implemented from
the APK because its descriptor state machine is statically unsafe. The offline control
model records requested MTU/delay, local notification actions, always-enable CCCD
values, and the immediate queue-result callback without an executable method. It
therefore makes the recovered enable-on-disable defect visible without making it usable.

Given `jring protocol-coverage`, a person receives a local-only summary of all request
and callback entries, offline codec counts, route/source totals, and zero live or
hardware-verified vendor operations. Before any counts, human output says complete
APK-to-Python Bluetooth capability parity is not established. JSON exposes the same
top-level verdict while `ok: true` means only that report generation succeeded. Four
independent dimensions keep recovered-AIDL row accounting separate from source
semantics, live vendor availability, and hardware verification; no percentage or
unknown-firmware capability denominator is invented. The report includes a schema-1
guidance object and a matching human-first section: local evidence inspection and the
simulator are safe to explore, while live vendor Bluetooth, hardware-verified vendor
behavior, and host input from ring events remain unavailable. The fixed next safe
action is `jring doctor`, which checks local prerequisites without selecting or
contacting a ring. This recommendation does not imply ring compatibility or authorize
Bluetooth access.

The report includes a schema-1
operation registry with all 112 request rows: 103 are ring-facing, nine are explicitly
non-ring platform behavior, 101 remain `offline_only`, and generic `setUuid` plus
`writeCharacteristic` are `unsafe`. Every row exposes sanitized capability, route,
endpoint, request/terminal evidence, privacy, idempotence, consent, status, and
firmware/evidence state while retaining zero live eligibility and zero hardware
verification. The 103-row denominator is limited to the recovered request surface;
it does not claim unknown firmware support. Correlation reporting
distinguishes zero rows remaining in the generic topology bucket from all 58 rows carrying
explicit caveats and enumerates every terminal rule: 36 single matched responses, 29
with no proven terminal, 17 per-frame-only, two
local-quiet-unknown, and one metadata-or-marker-else-local-quiet-unknown. It never
presents that smaller relationship-gap count as terminal completeness. A
directly adjacent sentence explains that zero generic rows means more-specific static
classification only and establishes no response semantics, live availability, or
hardware support. A separately labeled supplemental section reports
recovered session transitions, adversarial races, and source-labeled binding reactions;
it explicitly says these are not interface entries and therefore never inflates the
112-request or 105-callback ledgers. The same supplement begins with `Static source
recovery completeness: not established`, then reports the structured-run, emitted-stub,
marker, scoped-denominator, warning, and fallback-pass facts one per line. It says the
counts are different measurements and names complete semantic source review, complete
smali/instruction review, and complete DEX coverage as unperformed or unclaimed. Every
scoped zero is paired with its outputs-scanned denominator and the final hardware count
remains zero. The artifact supplement also reports all three packaged DEX units as
scope-classified:
one owned application/embedded-SDK unit and two without owned scope. It says in the
same line that complete instruction review is not established, so inventory coverage
cannot be read as semantic recovery. A following owned-scope warning audit names the
11 application and 21
embedded-SDK file population, their 29 and 62 warning occurrences, two same-tool surface
corroborations, one historical comparison divergence, and separate risk-first counts for
contradicted, inconclusive, confirmed, and not-performed instruction reviews.
It separately says five dependency files are excluded and that transitive Bluetooth
coverage is not exhaustive. A file count is never substituted for a warning-site count,
fallback file presence never proves a method body, and same-tool agreement is never
called validation or resolution. Instruction confirmation exposes no private artifact,
DEX, descriptor, prototype, offset, fingerprint, source, or disassembly identity. It
does not change static source completeness, semantic correctness, runnable state,
hardware eligibility, or the zero hardware-verified count.
A following whole-artifact supplement begins with `Artifact-surface completeness: not
established`. It reports exact AIDL-to-ledger parity, an exclusive owned-method
classification, dynamic-receiver mismatches, unresolved native declarations, and the
inconclusive dial-activation result. It never turns method, resource-keyword, Binder, or
native-declaration counts into capabilities. All private digests, DEX ordinals,
descriptors, prototypes, component/action names, code spans, native filenames, and
resource identities stay outside human and JSON output. The aggregate may say that all
owned-scope Android Bluetooth direct-instruction references are classified while the
older broad source-reference counts are non-exhaustive. It reports 236 referencing
methods across 63 classes and zero unclassified, immediately followed by the boundary
that semantics, transitive dependencies, runtime behavior, and hardware status remain
unestablished. Direct-reference absence is never rendered as unsupported. The aggregate
may also say that all
11 owned reflective calls resolve to constant Android helper categories, the reviewed
Binder/resource/navigation routes have no standalone-dial activation edge, and all
three packaged JNI roots perform image/wallpaper work without a rooted Bluetooth edge.
It still keeps runtime-generated, external-native, and exhaustive activation
inconclusive. The remaining 16 non-opcode callbacks are separately classified as 14
closed behavior surfaces and two declarations without observed dispatch, leaving zero
silently unclassified callback rows while exposing no callback values.
`--json` returns every ledger entry and the closed, non-runnable evidence supplements in
a schema-1 success envelope without frame bytes, private locators, logs, or source. The command
constructs no transport and rejects simulation, address, and timeout options because
none apply.

Offline acknowledgement parsing is operation-specific. A response for one known
operation cannot complete another, success-only branches do not gain invented failure
codes, notification content requires its outbound marker, and a bytecode-disproved ECG
failure collision is not reproduced.

Offline stream parsers expose only bounded numeric fields and raw device timestamps.
They do not start a sensor, subscribe, convert values to medical conclusions, or imply
hardware support. Packed ECG frames are decoded as unsigned 12-bit samples without
physiological labels.

Given one offline history transaction, the decoder accepts only that transaction's
proven opcode family, rejects unrelated frames without refreshing a deadline, and
closes exactly once. Explicit wire terminals and recovered device-metadata completion
are distinct from local idle/overall timeouts; local quiet has unknown completeness.
Deadline callbacks carry a session and generation guard, and timestamps stay raw rather
than being shifted through the host timezone. No raw frame, timestamp, or measurement
appears in object representations.

Given an exact fake shared-day or raw-event collection, memory, setup stages, the whole
attempt, and cleanup are bounded. A second concurrent attempt is rejected before it
touches the transport; cancellation still cleans up; retained callbacks become inert;
and overflow, overall timeout, or cleanup failure abort without a success claim. If a
write began but did not return, the result says delivery is uncertain.

Given an exact fake `getDataByDay` request, type-specific frames produce the recovered
`onGetDataByDay` multiplicity. Detail `ff` reports a confirmed wire terminal; the
F0/AA/A0 predicate reports confirmed device metadata. Proven failure frames report a
failed end. Local quiet after data may reproduce one local end projection but remains
unknown, while frame limits and unrelated traffic cannot invent completion. Matching
malformed input and queue overflow abort, and all stored parsed values stay redacted.
Every transport stage is bounded, one collector cannot run concurrently, and retained
old callbacks cannot enter a reused attempt. Plain-language guidance says both that the
run was synthetic and whether locally stopped or aborted values may be incomplete.

Given an exact fake Wi-Fi scan request, the advertised count and complete assembled
entries reproduce their callback counts without performing host networking. Count
equality is a local diagnostic, not a terminal; quiet and limits remain unknown.
Invalid text, fragment-order errors, overflow, disconnect, or transport failure abort.
Stages and cleanup are bounded, cancellation cleans up, concurrent use is rejected,
and private SSIDs appear only through an explicitly named local-test accessor. A
returned fake write call means only that the fake call completed: protocol delivery,
application acknowledgement, and a wire terminal remain unknown or false. Names,
signal values, and fragment identifiers do not appear in representations or ordinary
dataclass serialization. The result also states that no host network was accessed or
modified and grants no live, owner, hardware, or input authority. Notifications before
actual fake write invocation are discarded. One immutable deadline covers setup,
write, and observation; an invoked call that does not return is uncertain and taints
reuse, as does cleanup failure.
Selectorless shared `54` traffic cannot be attributed to Wi-Fi and is unrelated;
length-invalid matching count/fragment traffic aborts.

Given an exact typed alarm batch and the scripted fake transport, the dedicated
simulator validates the complete request before connecting and writes its base/content
frames in the recovered encoder's order on the accepted Python domain. Exact `0d`/`8d`
callbacks are labeled uncorrelated per-frame observations because the recovered
projection exposes no proven alarm, chunk, batch, request, or terminal identity; body
bytes remain uninterpreted, and `1c` or other traffic is unrelated. Privacy-safe
success/failure counts preserve callback multiplicity without claiming causation. A
failure stops only future synthetic writes and prevents reuse, while earlier calls are
not rolled back. Returned calls, callback counts, local quiet, and observation limits
never mean batch success. A limit reached after the complete plan is unknown; a limit
that locally stops a partial plan is aborted, while a separate field confirms whether
every invoked fake call returned. Malformed matching callbacks, callback overflow,
disconnect after dispatch, and post-write cleanup failure remain uncertain without
claiming transport-call uncertainty. One overall deadline bounds setup, writes, and observation;
unsubscribe and close are then independently bounded during cleanup. An invoked call
without a confirmed return is uncertain. Results
retain no request, frames, acknowledgement objects, private content, or schedule and
state that no ring or OS input was touched.

Given an exact notification planner state, request, and scripted fake transport, the
notification batch simulator reconstructs the private inputs before acquiring the fake
lease, subscribes on the resolved current-generation MAIN route, and invokes the exact
header, title, and content frames in planner order. A deduplicated plan performs no
connection, subscription, write, or state commit. For a planned batch, an exact `12`
callback is correlated only to a marker whose frame has already been invoked in this
attempt. That observation is per-frame only: even every marker being observed cannot
mean ring delivery, display change, batch acknowledgement, terminal completion, or
planner-state commit. The remaining `12` body bytes are uninterpreted. A future marker
is unowned diagnostic traffic and is discarded without buffering, later correlation,
quiet extension, abort, or taint.

An exact `92` callback is an unmarked failure-shaped projection whose body is also
uninterpreted. It cannot name a frame or prove batch failure or completion. The fake
stops not-yet-invoked writes, leaves returned earlier calls untouched, and taints reuse;
this is a conservative simulator policy, not recovered source queue behavior. Direct
sequential fake calls likewise do not reproduce source queue acceptance, atomic enqueue
or delivery, caller throttling, planner/overlap serialization, or the source's global
callback-overlap race. Quiet, marker multiplicity or coverage, returned calls, and local
limits remain unknown. Setup, writes, observation, cancellation, and cleanup stay
bounded and generation-owned, with no automatic retry after uncertainty.

The result retains no notification text, ID, category, UID, digest, marker identity,
frame, or frame count and grants no live, owner, hardware, or input authority. The exact
scripted transport deliberately retains private write calls through test-only access;
that storage is disclosed and is never serialized as the result. `setNotify` remains an
ambiguous/batched per-frame eligibility row outside the singleton success engine, so
coverage totals and all live/hardware counts remain unchanged.
Structured output labels the disposition `offline_planner_only` and transport
`exact_scripted_fake_only`. It reports `planned_batch` versus `none_deduplicated`, and
the private-test-frame storage flag snapshots the scripted transport's actual retained
calls, including earlier attempts, until `clear_sensitive_test_state()` is called.
`test_retained_frame_warning_reflects_transport_storage_across_attempts` verifies the
planned, deduplicated, and explicitly cleared states.
The result-retention and source-global-overlap-race reproduction flags remain false;
single-batch serialization describes this simulator only, not recovered source safety.

Given an exact fake ECG-history request, one descriptor must precede arrival-ordered
event and sample callbacks, and each packed sample frame projects one callback carrying
twelve values. The
“start/end” callback name is not treated as evidence that an event ends the stream:
quiet and caller limits remain unknown, and this collector has no success or confirmed
state. Duplicate or missing descriptor ordering, matching malformed frames, overflow,
disconnect, and setup or cleanup failures abort. Live ECG traffic cannot refresh the
history deadline, while samples, metadata fields, and device timestamps remain hidden
from representations and are available only to focused synthetic tests. Aborted
streams explicitly instruct callers to discard any partial parsed values.
Setup/write/cleanup deadlines, cancellation cleanup, single-flight rejection, inert old
callbacks, and drained queues keep repeated fake attempts bounded and isolated.

Given the offline vendor transaction model, no write intent exists before matching
generation-bound notification-subscription readiness. That readiness does not claim a
direct CCCD acknowledgement. A write intent is not an application success: an explicit
acknowledged modeled write outcome must precede a strict typed response parse, while an
unknown write outcome requires confirmed disconnect before reuse. One enqueue-time
deadline covers every phase, unrelated frames never extend it, and the engine provides
generation tokens that a coordinator must bind to callbacks. A timeout, cancel,
disconnect, malformed response, or unknown post-dispatch outcome reports uncertain
delivery and is never replayed. This
model has no hardware transport/client integration and all objects remain static-only
and hardware-ineligible.

Given the strict future-adapter transaction engine, `connected` never means vendor
ready. The exact primary descriptor action must have both a recorded dispatch and a
successful platform callback. Primary setup failure remains visible without a queued
operation. Optional RAW setup can become `ready_degraded` only after primary success
and a definite optional failure; it names `raw_notifications` as unavailable. Optional
dispatch uncertainty requires reconnect. A callback at the exact deadline loses to
timeout, and an old connection's callback or disconnect is reported only as
`stale_callback_ignored`.

Human guidance leads with whether a command was sent. Pre-dispatch failures say “No
command was sent; reconnect and retry setup.” Possible post-dispatch failures say “The
command may have been sent; reconnect, do not repeat it, and verify the outcome before
starting a new attempt.” Machine output keeps connection phase, operation stage,
completeness, replay prohibition, and recovery separate. Assistive input is disarmed
on any required-capability loss and never catches up events after reconnect.

Given the fake-only vendor coordinator, only the exact scripted transport type is
accepted. The shared pure route resolver accepts only the closed main and raw pairs,
requires one connection-scoped target per endpoint, and rejects duplicate UUIDs across
the complete metadata snapshot, inconsistent target fields, missing response-capable
write/notify properties, and absent or repeated CCCD metadata. The exact scripted fake
then separately proves object identity and current-snapshot ownership, so reconstructed,
stale, or otherwise unowned targets fail before fake I/O. Route ambiguity, missing
properties, or setup failure sends no vendor command. Every fake coordinator uses the
resolved fake targets rather than UUID-only I/O. Bleak exposes no target I/O and keeps
vendor writes disabled; its standard Current Time write is service-bound, unambiguous,
writable, and payload-validated. A callback received during the response-write await is
buffered and cannot
complete the operation until that write returns; a write exception, disconnect,
timeout, cancellation, malformed response, queue overflow, or cleanup failure never
retries and poisons unsafe reuse. Results use plain language: “no vendor command was
sent” for an aborted attempt, and “may have received / was not repeated / create a new
simulator” for an uncertain attempt. Every result remains synthetic and
hardware-unverified, and neither Bleak nor `JRingClient` accepts this coordinator.
For the device-system fake transaction, human and JSON inventory distinguish passive
decoder coverage from an operation-bound scripted transaction that performs one write.
Exact canonical `54/11` is written once and only exact post-entry `54/12` may match.
The callback code is private and neutral. “Succeeded” means only a matched scripted
response; it is not current device state, Bluetooth readiness/connection,
battery/power, firmware health, owner binding, a live ring, hardware verification, or
input. Parsed values are absent from ordinary dataclass/JSON serialization.
All typed inputs admitted to this fake coordinator preserve the exact validated request
shape through an identity-bound, non-serialized seal. Changed fields or hidden frames
fail before operation creation, and instance-shadowed accessors cannot replace bytes;
copy and deepcopy retain the same sealed request. Unrelated short notifications and
selectorless shared opcodes remain unrelated rather than producing alarming malformed
results. EQ SET-kind cannot close GET, and heart-session start/stop preserve distinct
synthetic success and failure branches. These are offline correlation guarantees only.

Fake-singleton eligibility is a separate closed denominator over all 85 deterministic
requests. Human coverage reports 36 statically matched-terminal rows, 11 typed projections,
six ambiguous or batched per-frame rows, 29 rows with no proven terminal, and three
locally/marker-bounded streams. Only the 36 can enter the success-returning fake engine;
all rows remain explicitly live-ineligible, owner-unauthorized, and hardware-ineligible.
The attractive presence of a typed callback, opcode match, or parsed value never turns
the other groups into acknowledgement or transaction success.

Identifier-bearing device responses are redacted or hidden by construction. Binding
fields remain unnamed, factory bytes require an explicit local-use accessor, all 15 EQ
wire values are preserved while the APK's callback bug is explicit, and parsing a dial
or file-state response does not enable dial transfer, filesystem access, factory mode,
or binding.

### Explicit simulator profiles

The simulator has two explicit profiles. `basic` is the default and advertises no
standard HID service. `hid` contains the same basic status values plus synthetic
standard HID service, characteristic, and descriptor metadata. It never supplies a
Report Map value, HID report, verified event, or operating-system attachment.

Given `--simulate` without a profile, status and capabilities both select `basic` and
report the same HID service state. Given `--simulate --simulate-profile hid`, both
select `hid` and report the same advertised state. Human output names the selected
profile directly after the simulation banner; JSON includes `simulator_profile` next
to `source`. A profile option without `--simulate` is a usage error, and profile
selection never constructs a hardware transport.

`input-actions` lists both profiles before the event vocabulary. Input preview and
emission also report their selected profile, while making clear that the synthetic
`step` event is unchanged and does not become a HID report merely because the `hid`
metadata profile was selected.

### Safe step-to-input preview

Given no ring, when a person runs
`jring input --simulate --map step=click:left`, then the client exercises a simulated
step, describes the mouse click it would emit, and produces no operating-system input.
The simulated step comes from a closed internal pair of 20-byte vendor cumulative-step
frames: the first establishes a baseline and one exact increment produces one preview
candidate. Human and JSON output label this source synthetic, cumulative, live
unavailable, and hardware-unverified. Neither frame, count, time, generation, address,
path, nor target is shown or accepted from the command line.

Static APK evidence distinguishes two non-health event families without making either
live: discrete device actions and a cumulative step counter. Offline action decoding
lists all 13 mapped actions exactly once. It labels six media, volume, and shutter codes
as possible future input candidates, while seven find-phone, call, location,
camera-lifecycle, and time-write actions remain visibly blocked and side-effecting.
Descriptions name the APK's actual host effects: maximum-volume find-phone playback
with scheduled reset, camera shutter/open/close, call answer/end, conditional
location/weather refresh, media play/pause/next/previous, time synchronization, and
host media-volume changes. These are proprietary vendor-callback reactions, not HID
reports, and the inventory executes none of them.
Unknown action codes are never candidates. A live cumulative counter is not interpreted
as a click: connection baselines, resets, batching, debounce, and rate limits require
owner-hardware evidence first. The closed synthetic pair above demonstrates policy and
mapping UX only; it establishes no physical step or gesture meaning.

Given the exact scripted MAIN fake, passive event collection subscribes without any
write and accepts only `06`/`22` device actions, `51` cumulative steps, `45/00`
Classic info, `45/01` redacted Classic name, `45/02` redacted App-ID, `49`
host-volume requests, exact `78/00` and `78/01` private unknown-motion callback
projections, exact `4E` private passive chat-action candidates, and the exact `78/09`
touch-mode setting projection. App-ID
stays an uncorrelated callback event and cannot establish setter causation, identifier
equality, acknowledgement, or a terminal. Selectorless and unknown `45` traffic is
unrelated. Every other `78` selector is unrelated. Motion values remain redacted and
neutral; they are not axes, gestures, live sensor events, or input actions, and the
inbound selectors do not prove setter causation, acknowledgement, or enabled/disabled
state.
Exact `4E` duplicates remain separate observations. This fake run owns no request;
the protocol relationship stays unknown. They are not acknowledgements, terminals,
ChatGPT/content execution or retention, or input. `4F` and `54` remain unrelated to
that event kind.
Quiet and limits remain unknown; every
matching malformed frame, overflow, deadline, disconnect, or cleanup failure aborts.
Values remain redacted. The private touch value is neutral, not enabled/state, a
gesture, tap, button, sensor sample, or input event. Its setter has zero observed app
invokes, and passive decoding proves no setter causation, acknowledgement, terminal,
live behavior, or hardware support. No event is hardware- or input-eligible. A shared
fake-transport lease rejects caller-preconnected transports and competing coordinators
before I/O; cleanup therefore never closes a connection owned outside the attempt.
Classic metadata never claims profile attachment, bonding, RFCOMM, HID, or live
support. Ordinary structured output omits the decoded-value and event storage entirely
while including fixed zero-write, no-setter, no-ring, no-gesture,
no-sensor-promotion, no-terminal, no-hardware, and no-input fields; private values
remain available only through explicit
synthetic test accessors.
Cancellation during unsubscribe or close preserves a separately bounded cleanup attempt
before cancellation is re-raised, and callbacks are inert before cleanup begins.

Given the separate exact scripted host-volume coordinator and a closed request with
explicitly caller-supplied offline values, one valid `49` request may produce one
targeted fake write. Output must say that the fake write call returned while protocol
completeness remains unknown; it must
never say the device accepted, applied, acknowledged, or completed the projection.
The result contains no volume values, inbound body, frame, endpoint, or exception
detail and states that host audio was neither read nor modified. Quiet causes zero
writes, possible post-invocation dispatch is uncertain and tainted, and the same
coordinator cannot retry. This library-only path is distinct from volume-up/down input
candidates and grants no CLI, live Bluetooth, owner, hardware, or input authority.

The offline `ExperimentalStepCounterAdapter` demonstrates that safety contract with
synthetic counters. It ignores the first value of each increasing connection
generation, stale generations, duplicates, reset/wrap values, and every multi-step
jump. Only a decrease enters a visible rebaseline-required state, and later increments
remain silent until the caller explicitly accepts a same-generation baseline. Its
global minimum interval survives reconnect and rebaseline. An exact isolated increment
returns a closed preview candidate, not a dispatchable sensor event. The no-argument
synthetic bridge alone promotes its fixed baseline/+1 demonstration to the simulator
event. Both are hardware-ineligible and have no BLE source or input sink.

### Discoverable and accessible input vocabulary

Given no ring and no optional input package, when a person runs `jring input-actions`,
then keyboard and mouse actions appear in a stable screen-reader order using plain
text. Primary and secondary mouse actions also show their left and right labels. The
output says that `step` is simulated and that no hardware gesture has been verified,
so it does not imply that stepping is the only future interaction.

Given `--json`, the same command returns the complete closed allowlist in a schema-1
success envelope. `primary`/`left` and `secondary`/`right` are deterministic aliases;
using either label exposes only that selected kernel button capability.

### Deliberate input injection

Given a valid simulated mapping, when a person adds `--allow-input`, then exactly one
allowlisted keyboard or mouse action is emitted through Linux `uinput`. Shell commands,
paths, arbitrary key codes, and unsupported sensor event names are rejected before a
sink is opened. Hardware motion input remains unavailable until verified.

### Radio intent is explicit

Given any command marked simulated, it performs no Bluetooth scan or connection.
`discover` rejects `--simulate`, and a real discovery requires `--active-scan` with
copy explaining that the radio sends scan requests but never connects.

### Source intent and provenance

`--simulate` and hardware selection are mutually exclusive. Human simulated results
lead with `SIMULATION — no ring contacted`; JSON includes `schema_version` and
`source`, and exported rows include `source` plus `synthetic`.

### Honest partial status

Given a ring without the optional Battery characteristic, status still reports device
information and advertised services. Human wording says a service was advertised and
not tested; JSON marks battery availability independently.

Given optional Device Information reads that are mixed valid, unavailable, malformed,
and slow, status finishes within one field-collection deadline and preserves every
completed independent result. Each field reports exactly one of `available`,
`unavailable`, `malformed`, `timed_out`, or `not_advertised`. Service-inventory failure
is also explicit and never turns an unknown HID/heart-rate state into `not advertised`.

Schema 1 retains the existing `device_info`, `battery_percent`, `battery_available`,
and capability booleans. It additively exposes `device_info_states`, `battery_state`,
and capability `inventory_state`; automation may adopt these without losing the old
value paths.

### Supported Bleak connection contract

Given a supported Bleak 1.x client whose successful `connect()` completes with no
return value, the transport treats completion plus `is_connected` as success. A
successful adapter connection is never converted into a client error.

### Option meaning is enforced

Options that do not apply to a subcommand fail during parsing. Timeouts are finite and
between zero and 30 seconds. Any accepted `--json` success writes only valid JSON to
stdout; commands without a JSON contract reject the option.

When a hardware-capable command has no device source, its error is a recovery path,
not merely a list of flags: it names the preferred private `--address-file` selector,
points every first-time user to `jring status --simulate`, and recommends `jring doctor`
before hardware. The simulator suggestion is intentionally the safe status preview,
rather than a claim that every command has a simulator mode or that the selected ring
is compatible.

### Private and sanitized selection

A person may put an exact address in a mode-0600 file and pass `--address-file` so the
identifier is absent from argv. Conflicting source selectors fail before transport
construction. Expected and unexpected CLI errors redact MAC-like identifiers, long
payload hex, and BlueZ D-Bus paths and never show a traceback.

### Guided same-process selection

Given a terminal user who runs `jring status --select --active-scan`, the client first
states that an active scan sends radio requests and has not connected. Results use
per-process aliases plus only a possible-JRing classification and coarse signal
strength. The classification is explicitly labeled as a client-side name heuristic,
not device identity evidence.
Names and addresses never appear.

Choosing a numbered alias does not connect. The client repeats the alias and asks a
separate default-no question before constructing a transport. A negative answer,
end-of-input, invalid selection, zero results, or ambiguous input makes no connection.
One result is never selected automatically.

Guided selection requires an interactive terminal and is same-process. It rejects `--json`, simulation,
address selectors, and missing `--active-scan`; automation continues to use a
mode-0600 `--address-file`. Aliases and the private address-to-alias association are
neither persisted nor exposed by public results or object representations.

### Privacy-safe evidence contribution

Given a contributor with locally authorized evidence, when they validate a manifest,
then missing provenance, publication consent, coarse device context, redaction
declarations, coverage, or confidence fails closed. Addresses, BlueZ paths, account
identifiers, precise timestamps, health fields, raw payload fields, and long hex are
rejected without the diagnostic repeating the sensitive value.

Given a fully synthetic safe manifest, `derive` emits the smallest deterministic JSON
fixture to stdout. It omits administrative consent and collection details, preserves
explicit synthetic provenance, and includes only facts named by coverage. Nothing is
uploaded or written automatically. The contributor manually reviews the output before
publication and uses the private security channel for sensitive reports.

An owner-authorized manifest is private input, not a commit-ready public artifact.
Local validation requires mode 0600 or read-only 0400; repository scanning rejects it at any mode. The
scan inspects every repository file and rejects disguised capture, archive, Android,
native, decompiler, and smali material without echoing a filename or rejected content.

A separate private schema-2 observation may describe one historical device-info
attempt. `validate` says exactly that local validation passed, validation itself
performed no Bluetooth operation, and the object is not publishable. It accepts coherent failure and uncertainty
rather than coercing them into success or unsupported hardware. `derive` fails with
`private_evidence`, writes no JSON to stdout, and exposes no evidence ID or path. This
object is not a pre-run plan, reusable permission, authenticated result, public claim,
runtime registry entry, or model/firmware support statement.

The record labels itself self-declared, withholds its evidence ID and device context,
and distinguishes failed from outcome-unknown connection attempts. After possible
dispatch, terminal absence names a bounded reason but remains uncertain. A current-
generation terminal is accepted only after write completion; notification and
unsubscribe completion describe high-level transport calls, never direct CCCD
acknowledgement. Cleanup order is explicit, and failed/unknown cleanup blocks success.

A schema-2 device-info candidate is a different public artifact. Its human meaning is
“ready for protocol/privacy/runtime review,” never “ready to run.” Validation accepts
only one fixed operation shape and explicitly shows that the prospective canary needs
notification activation and one vendor GATT write. The candidate cannot contain an
address, identifier, timestamp, raw frame, arbitrary endpoint, free-form fact,
confidence, or success field. The derived fixture omits publication administration and
the private evidence reference while retaining all denied effects and six false
authority flags. Public-derived identifiers and model/firmware context are fixed to
withheld values in this first schema. Repository scanning requires an exact
claim/fixture pair anywhere in the repository and compares JSON types strictly; a
private schema-1 ledger is neither required nor commit-eligible. Release and PyPI
artifact builds run the same scan before packaging.

### Honest compatibility matrix

The owner-hardware transport canary is a distinct, default-no workflow. Human execution
shows the declared coarse scope and complete connection/subscription/write disclosure
before transport construction. A positive-duration quiet window precedes the one
vendor write. Result copy leads with whether dispatch was absent or may have escaped,
whether a terminal matched, whether cleanup was confirmed, and whether the new private
record exists. The complete fixed order is primary attempt, write dispatch, response
terminal, cleanup, evidence commit, then status-specific recovery. It never calls the
response a verified device-information value or describes a matched response as a
property of ATT write completion. Cleanup uncertainty and evidence-commit failure are
separate states and do not replace the primary attempt status.

Interruption preserves exit 130 but is non-retryable for this canary because a write
may have escaped. Human and JSON output say not to replay automatically and direct the
owner to inspect the requested private record, if created, before considering a new
manually authorized attempt. A failed private commit never recommends reviewing a
nonexistent record.

`review-owner-evidence` restrictively loads one private mode-0600 record, performs no
Bluetooth I/O, and can first preview every prospective public field, including the
owner-declared scope and coarse Linux/Python/BlueZ/Bleak dimensions, without writing.
After inspection, explicit promote/reject authority can create one private review
receipt. It creates no public artifact. `derive-owner-evidence` is a separate action
that requires the bound receipt and an explicit public-creation flag. It creates a new
sanitized file without overwrite and states
that the runtime registry is unchanged. The detached artifact includes a schema
version, closed record type, an owner-declared scope marker, and explicit false runtime
and repeat authority. JSON failures retain the standard error envelope and use
evidence-specific, non-retryable codes. Paths, addresses, target identities, frames,
response values, and exception text remain absent.

Given synthetic CI evidence only, when a maintainer builds the matrix, then the row may
report local prerequisites and simulator checks but every hardware dimension remains
`untested`; the matrix state is `synthetic_only`, never compatible. Owner hardware
reports require a separately authorized evidence identifier and private mode-0600 input.

Reports use only coarse model/firmware/environment families and explicit dimension
states. Validation rejects identifiers, precise timestamps, health/raw fields, unknown
states, impossible progressions, and duplicate report IDs without echoing unsafe
values. Deterministic merge output names its synthetic/owner counts and every tested or
untested dimension; generation and merge print reviewable JSON and never publish it.

### Verified install artifact

Given a clean commit or matching version tag, the release-artifact workflow uses pinned
build tools to build twice under one source epoch, normalizes archive metadata, and
requires byte-identical outputs. Inspection checks package metadata, safe paths,
declared source members, and required review policy/tool files before checksumming.

The built wheel is installed outside the checkout and runs `doctor`, simulated status,
and simulated capabilities. The workflow creates a provenance attestation and a
short-lived CI artifact only. It has no package-index upload, GitHub-release creation,
contents-write permission, or signing secret. Installation documentation covers
checksum verification, pipx/uv-tool install, upgrade, and uninstall.

The source metadata claims Console on POSIX Linux and only the fixed CPython minors
exercised by committed CI: 3.10, 3.11, and 3.13. It does not promote rolling distro
interpreters, documentation-only distributions, or an accepted `requires-python`
range into fixed-minor test evidence. The SPDX MIT expression remains authoritative;
the legacy MIT classifier is omitted because the pinned backend rejects combining it
with the modern license expression.

Given a reviewed source tree and local wheelhouse containing every exact pin from
`requirements/release.txt`, a fresh virtual environment installs the frontend with
`--no-index --find-links`, and the default isolated PEP 517 backend resolves from the
same wheelhouse under `PIP_NO_INDEX=1`. The build produces one wheel and one source
archive without changing system Python.

Given any change to the authoritative parser, `generate_cli_artifacts.py --check`
byte-compares deterministic Bash completion and man-page resources. Visible options,
aliases, choices, required values, file values, and parser command order stay scoped to
their parser context; suppressed compatibility arguments remain absent. The manual
states the offline/no-contact safety boundary before its catalog. Generation reads no
environment value, address, capture, Bluetooth state, shell history, or runtime device
state. These files ship as inert wheel resources: package installation neither edits a
shell configuration nor installs them into host completion or manual directories.

### Non-destructive export

History refuses to replace an existing destination unless `--force` is explicit.
Both paths remain atomic and restrictive, and simulated rows keep provenance.

## Test map

| Scenario | Executable evidence |
|---|---|
| First safe success | `test_human_status_is_readable` |
| Automation | `test_json_status_is_stable_and_private` |
| One standard heart-rate sample | `test_simulated_heart_rate_is_one_synthetic_private_sample`, `test_simulated_heart_rate_json_is_stable_and_private`, `test_hardware_heart_rate_requires_consent_before_transport`, `test_hardware_heart_rate_discloses_bounded_standard_notification`, `test_heart_rate_emits_no_measurement_when_context_close_fails`, `test_guided_heart_rate_reuses_private_default_no_selection`, `test_exact_standard_target_yields_one_sample_then_cleans_up`, `test_capability_inventory_reports_structural_heart_rate_readiness_without_io` |
| Automation failures | `test_json_failures_have_stable_envelopes_and_exit_codes`, `test_json_usage_error_has_no_stderr`, `test_json_error_redaction` |
| Flexible option placement | `test_global_option_placement_remains_compatible` |
| Recoverable setup error | `test_expected_error_is_actionable_without_traceback` |
| Deliberate write | `test_time_sync_requires_explicit_confirmation` |
| Predictable export | `test_history_export_rejects_ambiguous_suffix` |
| Passive setup diagnosis | `test_doctor_explains_hardware_setup_without_failing`, `test_bluez_layers_remain_distinct`, `test_missing_busctl_is_a_named_diagnostic_gap_not_a_dbus_failure`, `test_present_busctl_can_report_broken_dbus_separately`, `test_passive_bluez_probe_uses_only_read_queries` |
| Readiness automation | `test_doctor_json_can_strictly_require_hardware` |
| Standard HID visibility | `test_standard_hid_service_is_reported` |
| Read-only capability inventory | `test_hid_advertisement_is_not_called_usable`, `test_standard_hid_metadata_has_explicit_states`, `test_malformed_optional_descriptor_preserves_inventory`, `test_capability_inventory_performs_no_reads_or_subscriptions`, `test_vendor_route_readiness_uses_metadata_and_current_target_ownership_only`, `test_timed_out_vendor_metadata_is_not_misreported_as_missing_endpoints`, `test_timed_out_service_inventory_does_not_run_vendor_preflight`, `test_stale_vendor_targets_fail_generation_before_ownership`, `test_malformed_vendor_metadata_is_sanitized_instead_of_raising`, `test_cli_capability_inventory_is_private` |
| Honest offline vendor decoding | `test_band_functions_expand_twelve_bytes_lsb_first`, `test_multi_sport_day_decodes_six_packed_records`, `test_multi_sport_frame_also_reports_generic_sensor_mode_success`, `test_oxygen_day_decodes_fifteen_one_minute_samples_without_guessing_end`, `test_advanced_sensor_day_preserves_three_neutral_five_byte_records` |
| Complete request accounting | `test_static_vendor_operation_coverage_accounts_for_all_112_requests_once`, `test_only_seven_operations_have_offline_request_and_response_codecs`, `test_static_coverage_never_promotes_an_operation_to_hardware` |
| APK-owned interface use | `test_every_request_has_one_exact_app_use_classification`, `test_direct_app_use_counts_are_occurrences_not_distinct_methods`, `test_every_callback_has_exact_invoke_origin_counts_or_is_unobserved`, `test_callback_origin_counts_preserve_overlap_and_repeated_invokes` |
| Exact Binder parity | `test_request_and_callback_binder_surfaces_have_exact_contiguous_parity`, `test_every_binder_transaction_is_synchronous_and_parcel_order_matches`, `test_semantic_boolean_kinds_remain_distinct_from_parcel_int32`, `test_binder_rows_link_app_use_and_codec_status_without_inference`, `test_binder_evidence_is_closed_sanitized_and_non_runnable` |
| Strict offline mutation encoders | `test_twenty_six_mutations_have_offline_codecs_without_live_eligibility`, `test_device_settings_preserve_the_exact_profile_layout_and_inverted_calling_bit`, `test_alarm_batch_builds_base_and_exact_content_chunks_without_state`, `test_request_bytes_and_sensitive_inputs_are_structurally_hidden`, `test_requests_are_closed_offline_private_and_never_hardware_eligible`, `test_safety_metadata_refuses_unsafe_apk_runtime_behaviors` |
| Additional main-command codecs | `test_forty_six_additional_main_requests_have_offline_codecs`, `test_wifi_scan_is_an_active_network_action_not_a_read_only_query`, `test_every_main_operation_has_closed_privacy_and_risk_metadata`, `test_ai_language_is_opaque_explicit_utf8_and_never_uses_host_locale`, `test_private_text_rejects_controls_formatting_and_malformed_unicode`, `test_plans_exact_header_title_and_content_frames_without_live_side_effects` |
| Complete non-runnable behavior surface | `test_twenty_six_non_codec_requests_have_closed_behavior_evidence`, `test_all_fourteen_local_ble_or_dynamic_gatt_requests_are_accounted_once`, `test_ten_non_bluetooth_requests_are_closed_and_accounted_once`, `test_get_ota_info_models_exact_main_request_without_exposing_a_frame`, `test_start_file_ota_is_descriptive_only_and_lists_dangerous_side_effects` |
| Complete callback accounting | `test_static_vendor_callback_coverage_accounts_for_all_105_callbacks_once`, `test_callback_coverage_distinguishes_unused_and_non_opcode_sources`, `test_all_eighty_six_opcode_originated_declarations_have_response_codecs`, `test_three_apk_generated_end_callbacks_are_local_projections_not_wire_codecs` |
| Codec registry traceability | `test_request_registry_exactly_matches_all_eighty_five_codec_rows`, `test_callback_registry_exactly_matches_all_eighty_six_decoder_rows`, `test_every_registry_target_resolves_to_callable_code`, `test_shared_and_stateful_codecs_are_not_misrepresented_as_direct`, `test_coverage_rows_link_back_to_registry_entries` |
| Request packet routing | `test_all_112_requests_have_one_mutually_exclusive_packet_route`, `test_main_raw_and_exception_routes_have_exact_roles`, `test_routing_counts_do_not_authorize_live_queue_reproduction`, `test_request_routing_evidence_is_closed_and_sanitized` |
| Static session sequencing and race evidence | `test_session_evidence_is_a_closed_immutable_singleton`, `test_session_graph_has_closed_unique_codes_and_only_known_interface_links`, `test_source_connected_is_dispatch_acceptance_not_descriptor_acknowledgement`, `test_device_policy_occurs_after_connected_and_does_not_become_owner_authority`, `test_all_adversarial_session_races_have_python_safety_rules` |
| Honest aggregate decompilation evidence | `test_primary_run_and_emitted_markers_remain_different_observables`, `test_zero_scoped_markers_have_nonzero_scanned_denominators`, `test_warning_scope_is_visible_without_becoming_a_hard_failure_or_success_claim`, `test_fallback_pass_is_complete_output_generation_not_semantic_or_smali_review`, `test_decompilation_evidence_never_promotes_runtime_or_hardware_maturity`, `test_protocol_coverage_human_summary_is_offline_and_honest`, `test_protocol_coverage_json_accounts_for_every_entry` |
| Scoped warning and instruction review without false resolution | `test_warning_audit_accounts_for_owned_scope_without_inflating_interfaces`, `test_application_warning_partition_keeps_risk_exclusion_and_sites_distinct`, `test_sdk_warning_partition_preserves_kind_and_consequence_axes`, `test_same_tool_dispatch_surface_corroboration_does_not_validate_branches`, `test_instruction_review_resolves_selector_and_receiver_control_flow_only`, `test_progress_named_handoff_is_not_relabelled_as_numeric_ota_progress`, `test_ota_patch_and_dormant_dial_transfer_stay_separate_and_non_runnable`, `test_warning_evidence_is_closed_aggregate_only_and_without_authority`, `test_instruction_review_tightens_local_ota_flow_without_authorizing_it` |
| Whole-artifact parity without method-count inflation | `test_all_dex_interface_declarations_exactly_match_public_ledgers`, `test_call_and_dispatch_links_are_evidence_not_new_interface_rows`, `test_exclusive_owned_method_classification_reconciles_without_inflating_ledgers`, `test_android_bluetooth_references_stay_platform_plumbing_categories` |
| Manifest, receiver, resource, native, and dynamic activation honesty | `test_manifest_surface_separates_declared_features_from_dynamic_receivers`, `test_dynamic_receiver_mismatches_are_blockers_not_capabilities`, `test_resource_keyword_counts_never_become_capability_counts`, `test_native_false_positive_is_corrected_without_claiming_native_absence`, `test_dynamic_dial_activation_remains_inconclusive_across_all_surfaces`, `test_artifact_evidence_is_closed_sanitized_and_without_runtime_authority` |
| Offline device/config decoding | `test_device_code_discards_all_identifier_bytes`, `test_device_dial_decodes_every_field_in_the_twenty_byte_layout`, `test_eq_info_decodes_signed_values_and_requires_expected_kind`, `test_factory_test_bytes_are_hidden_and_byte_19_is_not_claimed` |
| Offline sensor and ECG decoding | `test_sensor_measurement_state_distinguishes_open_close_and_failure`, `test_sdk_integer_parse_fields_reject_values_above_signed_ceiling`, `test_sdk_integer_parse_ceiling_is_inclusive_but_ecg_long_path_stays_unsigned`, `test_live_sensor_values_preserve_eight_neutral_bytes`, `test_ecg_values_unpack_six_groups_into_twelve_unsigned_values`, `test_ecg_history_info_and_start_end_use_exact_little_endian_fields` |
| Operation-specific acknowledgements | `test_vendor_ack_decodes_operation_specific_success_and_failure`, `test_vendor_success_only_ack_rejects_guessed_failure_branch`, `test_notify_ack_requires_the_outbound_marker_for_success`, `test_ecg_mode_ack_keeps_response_mode_without_inventing_failure_opcode` |
| Local protocol coverage UX | `test_protocol_coverage_human_summary_is_offline_and_honest`, `test_protocol_coverage_json_accounts_for_every_entry`, `test_protocol_coverage_exposes_closed_operation_registry_denominator`, `test_protocol_coverage_never_constructs_a_transport` |
| Normalized event/result contract | `test_ring_event_schema_is_stable_metadata_only_and_round_trips`, `test_event_relationship_cannot_invent_source_causality`, `test_event_order_guard_requires_contiguous_stream_and_atomic_rejections`, `test_operation_result_states_preserve_dispatch_effect_and_recovery`, `test_operation_result_has_stable_golden_json_and_independent_clock_domains`, `test_matched_failure_terminal_is_preserved_without_claiming_success`, `test_conditional_terminal_requires_marker_or_metadata_not_quiet_or_generic_match`, `test_operation_without_failure_evidence_cannot_invent_a_failure_terminal`, `test_result_order_guard_never_regresses_accepted_dispatch`, `test_result_order_guard_preserves_a_matched_response_through_cleanup_failure`, `test_result_order_guard_allows_uncertain_as_first_and_terminal_attempt_state`, `test_accepted_can_become_uncertain_only_after_stage_progress_without_dispatch_regression`, `test_contracts_close_construction_extra_fields_and_private_echoes`, `test_process_local_seal_rejects_declared_field_mutation_and_copy_is_identity` |
| Closed live-operation registry | `test_registry_accounts_for_all_112_requests_once_with_closed_terminal_status`, `test_registry_classifies_non_ring_and_generic_transport_without_a_fallback`, `test_registry_preserves_route_endpoint_and_response_terminal_evidence`, `test_registry_has_exact_capability_privacy_idempotence_and_consent_types`, `test_registry_is_immutable_sanitized_and_cannot_construct_runtime_authority`, `test_registry_lookup_is_exact_and_rejects_unknown_names_without_echo` |
| Offline raw channel | `test_static_raw_requests_share_the_exact_twenty_byte_envelope`, `test_raw_payload_notification_is_bounded_and_hidden_from_repr`, `test_raw_payload_projection_zero_fills_short_and_ignores_extra`, `test_raw_generic_callback_and_typed_projection_are_separate`, `test_raw_notification_control_is_evidence_not_a_runnable_plan` |
| Offline non-health event classification | `test_device_action_decoder_classifies_input_candidates_and_side_effects`, `test_weather_action_opcode_uses_its_static_action_without_payload_guessing`, `test_step_counter_is_cumulative_and_not_a_verified_button_event`, `test_experimental_step_counter_never_replays_batches_resets_or_reconnects` |
| Zero-write passive MAIN event simulation | `test_collects_only_closed_passive_main_events_without_any_write`, `test_collects_redacted_classic_info_and_name_without_attachment_or_write`, `test_collects_redacted_app_id_without_correlating_setter_or_writing`, `test_unknown_45_selectors_count_as_unrelated`, `test_selectorless_45_cannot_be_attributed_to_classic_and_does_not_rollback`, `test_overlong_matching_45_event_aborts_without_private_projection`, `test_malformed_app_id_rolls_back_a_prior_valid_event`, `test_collects_exact_chat_action_as_passive_private_projection_without_write`, `test_main_chat_action_projection_is_decoder_owned_immutable_and_bounded`, `test_duplicate_chat_actions_remain_nonterminal_passive_per_frame_projections`, `test_malformed_exact_chat_action_rolls_back_prior_event`, `test_chat_content_and_ai_state_opcodes_are_unrelated_to_chat_action`, `test_collects_exact_wifi_callback_code_without_network_or_write`, `test_wifi_callback_projection_is_decoder_owned_immutable_and_bounded`, `test_other_54_selectors_remain_unrelated_to_wifi_callback`, `test_selectorless_54_is_unrelated_and_does_not_rollback_wifi_projection`, `test_malformed_exact_wifi_callback_rolls_back_prior_event`, `test_duplicate_wifi_callback_codes_remain_nonterminal_passive_events`, `test_collects_exact_touch_mode_as_neutral_passive_projection_without_any_write`, `test_collects_exact_unknown_motion_channel_projection_without_write_or_input`, `test_motion_projection_redacts_private_values_across_copy_and_serialization`, `test_mixed_touch_and_unknown_motion_projections_keep_distinct_semantics`, `test_other_78_selectors_are_unrelated_without_becoming_motion`, `test_malformed_exact_motion_selector_rolls_back_prior_event`, `test_selectorless_78_does_not_rollback_a_prior_touch_projection`, `test_malformed_exact_touch_selector_rolls_back_prior_event`, `test_queue_overflow_aborts_and_discards_partial_projection`, `test_preconnected_transport_is_rejected_without_closing_caller_connection`, `test_transport_lease_blocks_a_different_fake_coordinator_without_interference`, `test_cancellation_cleans_up_releases_single_flight_and_stales_callback`, `test_cancellation_during_postevent_unsubscribe_finishes_bounded_close`, `test_cancellation_during_preflight_close_remains_bounded` |
| Fake-only Wi-Fi network-name response assembly | `test_fake_wifi_runtime_has_no_host_network_or_distro_service_imports`, `test_advertised_count_is_diagnostic_unknown_not_wire_completion`, `test_zero_advertised_count_stays_unknown_and_does_not_invent_ssid_callback`, `test_selectorless_shared_54_is_unrelated_and_does_not_rollback_count`, `test_prewrite_notifications_are_not_owned_by_the_scan_attempt`, `test_invalid_utf8_completed_entry_is_malformed_and_never_projected`, `test_delayed_queue_overflow_cannot_be_masked_by_the_frame_limit`, `test_invoked_write_failure_is_uncertain_tainted_and_not_reusable`, `test_disconnect_during_invoked_write_is_uncertain_and_taints_reuse`, `test_prewrite_cleanup_failure_is_aborted_but_taints_reuse`, `test_overall_deadline_covers_an_invoked_blocked_write`, `test_cleanup_deactivates_callback_drains_queue_and_bounds_large_frames`, `test_cancellation_during_write_cleans_up_once_and_taints_reuse`, `test_cancellation_during_postwrite_unsubscribe_finishes_close_and_taints`, `test_cancellation_during_prewrite_close_is_bounded_and_taints` |
| Fake-only ordered alarm batch simulation | `test_fake_alarm_runtime_has_no_live_bluetooth_host_or_input_imports`, `test_exact_alarm_frames_write_in_order_but_never_establish_batch_success`, `test_uncorrelated_failure_shaped_callback_stops_only_future_fake_writes`, `test_late_failure_does_not_claim_that_nonexistent_writes_were_stopped`, `test_callback_multiplicity_is_preserved_without_inventing_correlation`, `test_failure_observation_stops_counting_at_the_caller_limit`, `test_multiple_owned_failure_callbacks_preserve_multiplicity_before_stop`, `test_failure_remains_primary_when_unrelated_frame_reaches_limit`, `test_delayed_failure_burst_cannot_overshoot_observation_limit`, `test_forged_empty_exact_batch_is_revalidated_before_connect`, `test_forged_nested_alarm_values_are_revalidated_before_connect`, `test_setup_failures_report_exact_stage_without_leaking_details`, `test_callback_burst_is_classified_as_queue_overflow_not_write_failure`, `test_prewrite_alarm_callback_is_unowned_and_cannot_stop_dispatch`, `test_inbound_content_opcode_is_unrelated_not_a_matching_alarm_callback`, `test_observation_limit_after_all_writes_is_unknown_not_success`, `test_mid_plan_observation_limit_is_local_abort_without_call_uncertainty`, `test_invoked_write_timeout_is_uncertain_and_distinct_from_setup_timeout`, `test_overall_observation_deadline_after_returned_writes_stays_unknown`, `test_partial_plan_overall_timeout_taints_reuse_without_call_uncertainty`, `test_malformed_matching_callback_after_dispatch_is_uncertain_and_tainted`, `test_invoked_write_failure_is_uncertain_tainted_and_never_retried`, `test_owned_failure_callback_survives_write_error_without_false_stop_causality`, `test_owned_failure_callback_survives_blocked_write_timeout`, `test_successful_write_return_is_preserved_when_disconnect_finishes_together`, `test_disconnect_caused_write_exception_is_classified_as_disconnect`, `test_owned_observation_is_counted_when_disconnect_finishes_together`, `test_exact_types_and_preconnected_transport_fail_before_fake_io`, `test_cancellation_during_invoked_write_taints_and_finishes_cleanup`, `test_cleanup_failure_uses_pre_and_post_write_uncertainty_boundary` |
| Fake-only marker-correlated notification batch simulation | `test_fake_notify_runtime_has_no_live_host_network_or_input_imports`, `test_exact_marker_bound_notify_frames_never_establish_batch_delivery_or_commit_state`, `test_deduplicated_plan_performs_zero_transport_io_and_commits_nothing`, `test_future_marker_is_unowned_diagnostic_and_never_acknowledges_a_later_frame`, `test_future_marker_ownership_is_fixed_at_arrival_not_when_queue_is_drained`, `test_prewrite_success_and_failure_callbacks_are_unowned`, `test_duplicate_owned_marker_is_diagnostic_not_batch_completion`, `test_quiet_without_callbacks_and_complete_marker_limit_both_stay_unknown`, `test_mid_plan_observation_limit_aborts_and_blocks_reuse_without_call_uncertainty`, `test_unmarked_failure_stops_only_not_yet_invoked_fake_writes`, `test_multiple_unmarked_failures_are_reported_without_an_exact_count`, `test_failure_remains_primary_at_limit_with_a_future_marker_also_observed`, `test_late_unmarked_failure_does_not_claim_that_writes_were_stopped`, `test_malformed_matching_callback_after_dispatch_is_uncertain`, `test_callback_burst_is_bounded_and_classified_as_overflow`, `test_write_error_preserves_owned_failure_without_false_stop_causality`, `test_blocked_write_timeout_preserves_owned_failure_and_primary_reason`, `test_successful_write_return_is_preserved_when_disconnect_finishes_together`, `test_disconnect_caused_write_exception_is_classified_as_disconnect`, `test_structurally_ambiguous_or_missing_cccd_route_never_subscribes_or_writes`, `test_targeted_subscription_is_confirmed_before_writes_and_identity_is_reused`, `test_stale_callback_from_prior_connection_generation_is_ignored`, `test_exact_types_preconnected_and_forged_inputs_fail_before_fake_io`, `test_cancellation_during_invoked_write_taints_and_finishes_cleanup`, `test_cleanup_failure_uses_pre_and_post_write_uncertainty_boundary`, `test_guidance_leads_with_primary_reason` |
| Fake-only host-volume reverse pipeline | `test_exact_device_request_projects_one_closed_response_without_claiming_ack`, `test_write_failure_is_uncertain_and_never_retried`, `test_disconnect_after_write_invocation_is_uncertain_without_retry`, `test_inbound_body_is_discarded_and_duplicate_request_cannot_change_projection`, `test_early_request_is_discarded_if_subscription_never_confirms`, `test_cancellation_after_write_invocation_taints_and_cleans_up`, `test_stale_callback_and_busy_or_wrong_types_cannot_project` |
| Task-first non-health inventory | `test_non_health_inventory_exposes_evidence_maturity_and_live_boundaries`, `test_all_thirteen_statically_mapped_device_actions_are_discoverable_once`, `test_non_health_capabilities_are_local_task_first_and_screen_reader_ordered`, `test_non_health_capabilities_json_has_stable_local_taxonomy`, `test_non_health_capabilities_rejects_unrelated_runtime_selectors`, `test_guided_capabilities_selects_ephemerally_and_reads_metadata_only`, `test_guided_capabilities_default_no_never_constructs_transport` |
| Owned-scope Android Bluetooth instruction inventory | `test_owned_scope_direct_instruction_aggregates_are_closed_and_reconciled`, `test_direct_instruction_family_counts_are_overlapping_not_old_reference_counts`, `test_direct_instruction_category_rows_preserve_fine_counts_and_absence_boundary` |
| Repeated HID Report metadata | `test_repeated_hid_reports_preserve_instance_and_descriptor_metadata`, `test_repeated_hid_aggregate_is_order_independent_and_preserves_malformed_peer`, `test_bleak_gatt_inventory_enumerates_metadata_without_reading_values`, `test_cli_capability_inventory_human_copy_is_honest` |
| Fail-closed offline vendor transaction | `test_notification_subscription_confirmation_is_required_before_any_write_intent`, `test_late_subscription_confirmation_from_old_connection_cannot_ready_a_reconnect`, `test_unknown_write_outcome_is_uncertain_and_blocks_work_until_disconnect`, `test_notification_cannot_complete_before_characteristic_write_confirmation`, `test_success_requires_the_closed_operation_specific_parser`, `test_unrelated_frames_never_refresh_the_immutable_deadline`, `test_disconnect_closes_once_and_clears_every_pending_layer`, `test_operation_constructor_is_closed_over_typed_static_requests` |
| Fake-only race coordinator | `test_success_discards_early_frames_and_processes_write_hook_frame_after_ack`, `test_success_result_keeps_parsed_value_out_of_structured_serialization`, `test_device_system_query_owns_only_exact_postwrite_54_12_response`, `test_opaque_typed_request_mutation_is_rejected_before_operation_creation`, `test_valid_behavior_field_change_cannot_replace_original_validated_frame`, `test_sealed_typed_request_copy_and_deepcopy_preserve_execution_identity`, `test_eq_query_ignores_set_kind_before_matching_get_kind`, `test_selectorless_shared_opcode_is_unrelated_before_exact_branch`, `test_truncated_unrelated_opcode_does_not_poison_matching_query`, `test_heart_rate_start_stop_runtime_owns_only_its_exact_branch`, `test_heart_rate_start_stop_runtime_preserves_distinct_failure_branch`, `test_mutated_closed_operation_is_rejected_before_fake_io`, `test_deadline_before_actual_write_entry_is_aborted_and_owns_no_response`, `test_disconnect_before_actual_write_entry_is_aborted_without_dispatch`, `test_cancellation_before_actual_write_entry_is_aborted_without_dispatch`, `test_malformed_exact_device_system_response_is_uncertain_and_redacted`, `test_main_command_factory_rejects_an_instance_shadowed_request_frame`, `test_preflight_requires_one_unambiguous_response_write_and_notify_cccd`, `test_write_error_after_invocation_is_uncertain_tainted_and_never_retried`, `test_retained_callback_from_old_generation_is_ignored`, `test_unsubscribe_failure_after_write_makes_cleanup_uncertain_and_taints` |
| Instance-safe vendor route preparation | `test_closed_main_and_raw_routes_resolve_connection_scoped_targets`, `test_endpoint_absence_ambiguity_and_wrong_service_fail_closed`, `test_connection_scoped_target_identity_is_required`, `test_connection_scoped_targets_map_exact_characteristic_objects_without_io`, `test_forged_targets_fail_but_unchanged_reinventory_reuses_target`, `test_structurally_consistent_but_unowned_targets_fail_before_fake_io`, `test_bleak_exposes_target_ownership_but_no_live_target_io`, `test_current_time_write_rejects_wrong_ambiguous_nonwritable_or_malformed_route`, `test_failed_candidate_disconnect_cannot_alias_successful_retry`, `test_failed_connected_candidate_is_never_promoted_to_live_io`, `test_hardware_io_is_rejected_while_connecting_closing_or_disconnected`, `test_successful_bleak_snapshot_omission_revokes_removed_target_without_growth` |
| Safe step-to-input preview | `test_synthetic_vendor_step_bridge_uses_decoder_baseline_and_exact_increment`, `test_vendor_step_preview_exposes_no_frame_counter_or_runtime_identity`, `test_step_counter_stale_generation_cannot_replace_current_baseline`, `test_reconnect_and_rebaseline_cannot_bypass_global_rate_limit`, `test_step_counter_candidate_cannot_be_dispatched_as_a_sensor_event`, `test_step_mapping_previews_without_emitting_input`, `test_step_preview_uses_closed_vendor_bridge_without_external_capabilities`, `test_vendor_step_preview_json_is_synthetic_private_and_unverified` |
| Explicit simulator profiles | `test_simulator_profile_preserves_global_and_task_first_forms`, `test_simulator_profile_requires_simulation`, `test_simulator_profile_is_consistent_between_status_and_capabilities`, `test_input_profile_is_explicit_in_human_and_json_output`, `test_simulator_profiles_are_discoverable_in_help` |
| Deliberate input injection | `test_input_injection_requires_opt_in`, `test_shell_mapping_is_rejected` |
| Accessible action discovery | `test_input_action_inventory_is_complete_and_stable`, `test_input_actions_are_screen_reader_ordered`, `test_mouse_aliases_are_deterministic` |
| Least-privilege input device | `test_uinput_exposes_only_selected_capabilities`, `test_unsupported_action_fails_before_uinput_import` |
| Radio intent is explicit | `test_discovery_requires_explicit_active_scan`, `test_simulated_discovery_never_scans` |
| Source intent and provenance | `test_source_modes_are_exclusive`, `test_simulated_status_has_provenance` |
| Honest partial status | `test_missing_battery_still_reports_hid`, `test_status_reports_each_optional_field_state`, `test_status_uses_one_deadline_for_all_optional_fields`, `test_cli_exposes_partial_status_states` |
| Supported Bleak connection contract | `test_bleak_one_x_none_return_is_a_successful_connection` |
| Option meaning is enforced | `test_non_applicable_global_options_are_rejected`, `test_timeout_must_be_finite_and_bounded` |
| Private and sanitized selection | `test_address_file_must_be_private`, `test_cli_errors_redact_identifiers` |
| Guided same-process selection | `test_guided_status_selects_only_after_confirmation`, `test_guided_selection_never_autoconnects`, `test_guided_selection_zero_or_invalid_results_do_not_connect`, `test_aliases_change_between_process_seeds` |
| Privacy-safe evidence | `test_unsafe_evidence_is_rejected_without_echo`, `test_manifest_requires_provenance_consent_coverage_and_redactions`, `test_safe_synthetic_manifest_derives_deterministically`, `test_private_device_info_cli_validates_locally_but_never_derives`, `test_artifact_loader_rejects_links_non_files_and_oversize_growth`, `test_repository_scan_quarantines_private_device_info_at_any_json_name`, `test_repository_evidence_scan_rejects_raw_artifacts` |
| Honest compatibility | `test_compatibility_report_rejects_sensitive_values_without_echo`, `test_untested_dimensions_cannot_claim_compatibility`, `test_synthetic_reports_merge_deterministically`, `test_zero_failure_synthetic_report_names_hardware_as_untested` |
| Owner-hardware canary and review | `test_production_bleak_path_uses_exact_main_targets_barrier_and_cleanup`, `test_private_output_is_created_exclusively_with_mode_0600`, `test_bad_integrity_device_info_is_protocol_incompatible_not_success`, `test_terminal_before_att_write_completion_is_quarantined`, `test_cleanup_awaits_are_bounded_by_the_overall_deadline`, `test_cancellation_after_write_dispatch_records_uncertain_after_one_cleanup`, `test_notification_queue_is_finite_under_unrelated_callback_flood`, `test_private_schema_rejects_exact_type_and_cross_field_incoherence`, `test_cli_owner_evidence_canary_is_task_first_explicit_and_private`, `test_cli_review_and_public_derivation_are_separate_offline_no_overwrite_steps`, `test_cli_address_file_failure_redacts_private_path` |
| Offline authorization-gate foundation | `test_synthetic_or_non_specific_evidence_can_only_be_ambiguous`, `test_offline_and_timeout_remain_distinct_without_authority`, `test_expected_scope_mismatch_is_a_value_free_error_not_a_verdict`, `test_human_output_is_conclusion_first_fixed_order_and_no_bypass_copy`, `test_classifier_import_and_execution_have_no_network_or_bluetooth_capability` |
| Verified install artifact | `test_project_version_agrees_with_runtime`, `test_artifact_inspection_and_checksums_are_deterministic`, `test_sdist_normalization_removes_build_time_variance`, `test_release_workflow_is_pinned_and_has_no_publish_step`, `test_install_documentation_covers_lifecycle_and_verification`, `test_build_inputs_are_complete_and_exactly_pinned`, `test_release_workflow_proves_an_isolated_no_index_build_from_pinned_inputs` |
| Parser-derived terminal help | `test_surface_exactly_tracks_visible_parser_contexts_aliases_and_choices`, `test_checked_in_artifacts_are_exact_parser_derived_bytes`, `test_generation_is_reproducible_private_and_host_independent`, `test_manual_leads_with_safety_and_covers_every_parser_item_once`, `test_roff_renderer_neutralizes_macro_and_control_injection`, `test_bash_completion_sources_and_preserves_command_scope`, `test_bash_completion_handles_required_positional_shell_choice`, `test_completion_command_prints_packaged_bash_script`, `test_completion_help_names_required_shell` |
| Non-destructive export | `test_history_export_requires_force_to_replace` |

## Deliberate non-goals

The CLI will not auto-connect from scan results, persist addresses, automate pairing,
guess vendor packets, execute mapped shell commands, upload data, or label measurements as medical conclusions.
Guided selection does not extend to writes or automation; those continue to require
their existing explicit contracts.
