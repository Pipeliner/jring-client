# JRing Linux client design

## Scope and evidence

This client is original code informed by static inspection of the user-supplied JRing
1.9.84 XAPK. No vendor binary or decompiled source is stored here.

**Verified (high confidence):** the supplied archive SHA-256 is
`45c7f062c75d9b934d8db82d0b7d0d8dd7f40cc394bd3e625b51ae38fb4ba34f`.
It contains one base APK, 17 language splits, one density split, and one arm64 split.
The package is `com.jaga.ibraceletplus.jyring`, version 1.9.84 (182), min SDK 21,
target SDK 35. Static DEX strings identify `com.sxr.sdk.ble.keepfit`, its AIDL
service/callback models, BLE discovery/connect/read/write/notify operations, and
operations for battery, device information, time, heart rate, oxygen, temperature,
blood pressure, ECG, activity/sleep/sport history, and capability queries.

**Verified (high confidence):** UUID strings include Device Information service
`180a` and characteristics `2a23` through `2a2a` and `2a50`; Heart Rate service
`180d`, measurement `2a37`; CCCD `2902`; and vendor families `33f3`–`33f6`,
`56ff`, `57ff`, `fef5`, `ffe5`, and `ffe9` (all Bluetooth-base UUIDs).

**Verified (medium confidence):** the manifest requests Bluetooth scan/connect,
location, network, notification, phone/contact/call, media, camera, storage, and
foreground-service permissions. These describe the Android app, not permissions
required by this client. The arm64 split contains one native library. The base has
three DEX files and local web/font/audio assets.

**Verified statically (high confidence):** the embedded SDK names `56ff` as its main
service, associates `33f3`/`33f4` with its transport path and `33f5`/`33f6` with a
raw-data path, and names `ffe5`/`ffe9` as a second path. These are SDK code roles, not
claims that a selected ring exposes them or that request/response direction has been
confirmed on Linux. The client reports matching service and characteristic metadata
with `meaning: unknown`; it reads no values and performs no vendor writes.

**Verified statically (high confidence):** the recovered SDK has a global application
command queue, Android characteristic-write completion state, and local timeout paths.
Those mechanics are not an owner-authentication session and do not prove a safe retry
contract. CRC/XOR references still do not establish one checksum rule for all frames.
Consequently no guessed frame is sent to hardware. The simulator uses a documented,
client-owned envelope solely to test reassembly, event parsing, and history export.

**Unknown:** the legitimate physical owner-confirmation behavior for binding, checksum
coverage across frame families, live endpoint behavior, history acknowledgement and
pagination on real firmware, and which UUID family applies to a particular ring model.

## Architecture and safety

`jring.protocol` contains strict typed parsers and the simulator-only envelope.
`jring.vendor_protocol` contains pure offline encoders for statically proven query
layouts plus strict offline response decoders. Its request objects cannot claim
hardware eligibility and are not accepted by any client transmission API. Decoder
objects omit device identifiers and raw bytes; ambiguous fields retain neutral names.
`jring.vendor_history` adds a pure per-request state machine for recovered history
frames. It uses finite monotonic deadlines, distinguishes wire/device/local closure,
and never turns an idle timeout into confirmed completeness or retains a raw frame.
`jring.non_health` is an immutable, local-only evidence inventory. Its closed
general-use rows link sanitized operation names to the recovered request and callback
ledgers and classify privacy without retaining values. It exposes no frame, transport,
parser, input sink, or authority to promote a static candidate.
`jring.vendor_transport` is likewise pure: it models one typed vendor transaction,
keeps notification-subscription readiness, modeled characteristic-write outcomes, and
application responses distinct, provides generation tokens for a coordinator to bind,
and classifies an unknown post-dispatch write outcome as uncertain. Subscription
readiness means only that the transport's high-level activation call completed; it
does not claim an explicit CCCD write or peripheral descriptor acknowledgement. The
model has no BLE/client import and cannot make an operation hardware-eligible.
`jring.vendor_runtime_fake` and `jring.vendor_runtime_simulator` exercise that ordering
against one exact scripted in-memory transport. The coordinator refuses subclasses and
real transports, performs route preflight, calls only the explicit response-write
boundary, binds callbacks to a connection generation, buffers response-before-write
races, and poisons reuse after uncertain delivery or cleanup. It is synthetic test
infrastructure—not a `JRingClient` feature or evidence of device support.
`jring.vendor_behavior_settings`, `jring.vendor_settings`, and
`jring.vendor_personal_settings` hold closed, strict synthetic mutation encoders. They
preserve proven valid layouts while rejecting SDK wrapping, implicit encodings,
partial batches, retries, and queue side effects; sensitive fields and frames stay out
of representations.
`jring.vendor_main_commands`, `jring.vendor_commands`, and
`jring.vendor_phone_integration` extend that offline boundary to queries, host-state
projections, network actions, sensor controls, and private fragmented transfers.
Operations expose explicit privacy/risk metadata, `scanWifi` is an active network
action rather than a read-only query, and phone-integration parity is wire-frames-only.
`jring.vendor_notify` adds an ephemeral-keyed, digest-only planner state with exact
bounded notification fragmentation. Planning returns a proposed state transition only;
it cannot commit delivery. Live acknowledgement, planner/overlap serialization,
throttling, and atomic delivery remain blockers.
`jring.vendor_local_operations`, `jring.vendor_platform_surface`, and
`jring.vendor_ota_evidence` are immutable behavior inventories. They accept no runtime
address, UUID, payload, path, or network input and expose no execute method. Dynamic
arbitrary writes and destructive SUOTA are documented without recreating their authority.
The SUOTA model's closed UUID-role inventory is capability metadata only: six required
transfer/status roles and four optional metadata roles remain non-runnable and
hardware-ineligible.
`jring.transport` defines a small async BLE interface and a fake implementation.
`jring.client` owns timeouts, bounded reconnect backoff, capability detection,
standard GATT reads, subscriptions, cancellation, and clean shutdown. `jring.bleak`
loads Bleak lazily. `jring.cli` requires either same-process confirmed selection or an
exact address for hardware access, plus an additional confirmation flag for the only
write (standard Current Time service).

Discovery is an explicitly authorized active BLE scan because the supported Bleak
backend sends scan requests. It prints redacted aliases, never addresses, and never
connects. Connection prefers a mode-0600 `--address-file`; legacy `--address` remains
available with a shell-history/process-list warning. Vendor writes, pairing,
firmware/DFU, destructive history operations, cloud access, and telemetry are absent.
The recovered vendor cloud checks, Android bonding, BLE binding mutation, and startup
device-time mutation are separate state machines; none is inferred or run implicitly.

The word “session” is not used as a catch-all authorization state. Five domains remain
separate in the design:

1. developer-cloud SDK validation, which is asynchronous application licensing;
2. device-cloud gear policy, which starts after the recovered SDK has exposed BLE
   readiness and can later disconnect it;
3. the explicit `4b` application binding exchange;
4. Android OS bonding for optional classic-Bluetooth behavior; and
5. the local command transaction from subscription activation through write outcome
   to a matched application response.

Recovered startup ordering is also not copied as a safety contract. The SDK exposes
its connected state after notification setup is submitted, before a descriptor callback,
then starts device-cloud policy. Its descriptor callback schedules an implicit device-time
write. A Python live bridge must instead expose `connected`, `endpoints_checked`,
`subscription_activated`, `write_outcome`, and `response_matched` as distinct evidence.
High-level notification activation is never described as a peripheral CCCD
acknowledgement. Cloud denial, local binding, and Android bond state cannot promote any
of those transport facts.

Decompiler recovery is represented by aggregate-only, closed static evidence. Run-level
failure telemetry, emitted failed-method stubs, marker occurrences, warning-bearing
files, and package-scope denominators remain separate measurements. A completed
fallback-mode output pass does not become complete semantic review, complete smali
review, complete DEX coverage, protocol parity, or hardware support. The public model
contains no rendered source, class or method locator, stack trace, log, bytecode, or
private artifact path.

Warning triage is a narrower supplemental graph. It distinguishes file population,
warning occurrences, method sites, domain consequence, counterpart availability,
same-tool surface corroboration, divergence, and independent instruction review. Two
JADX modes agreeing never becomes equivalence; a fallback file never proves that one
warned method body exists. Warning-bearing dependency and transitive call paths remain
outside the owned-scope population, so the graph cannot claim exhaustive Bluetooth
dependency coverage.

Targeted instruction review uses a private append-only provenance ledger. Each entry
binds its bounded predicate to the artifact and DEX digest, exact method prototype,
reproducible method/span fingerprint, and relevant switch, fallthrough, width, operand,
and exception edges. None of those private identities enter the package or CLI. The
public closed aggregate exposes only result state, intra/interprocedural or corpus-search
scope, reviewed-span count, sanitized observation, and limitations. A confirmed local
fact cannot promote semantic completeness or hardware maturity; a whole-corpus direct
reference absence remains inconclusive about reflection, JNI, native, or dynamic entry.

The main dispatcher has an additional closed structural crosswalk. It keeps callback
targets, syntactic and reachable invoke counts, recognized top-level opcode values, and
shadowed/no-callback branches separate. It is non-runnable and carries no frames,
private locators, source text, units, or physical meanings. A numeric opcode relationship
does not imply a distinct wire family or one callback per frame.

Whole-artifact surface evidence is another non-interface supplement. A private,
digest-bound audit reconciles all three DEX units, the AIDL declaration and
implementation sets, owned call/dispatch sites, direct Android Bluetooth helpers,
manifest components, dynamic receivers, decoded-resource names, split packaging, JNI
exports, reflection, and Binder. The public aggregate retains only sanitized counts,
closed categories, mismatches, and limitations. Its method categories are mutually
exclusive, while the direct Android API family counts are a separately labeled
non-interface view. Neither count is added to the 112/105 ledgers.
The public aggregate makes the packaged-unit partition explicit: all three units are
scope-classified, one contains the owned application/embedded-SDK population, and two
contain no owned-scope population. This inventory reconciliation is deliberately
separate from semantic, smali, and instruction completeness, which remain unestablished.

The 16 callbacks outside the wire-opcode decoder have a separate closed behavior
surface. Fourteen observed Android, network, OTA, scan, and transport dispatches are
classified without reproducing their side effects or data. Two declarations with no
observed dispatch remain declaration evidence. Raw GATT values, scan identifiers,
network material, cloud content, and file references are privacy classes only; the
aggregate stores no corresponding values. This makes callback accounting complete
without making any callback runnable or hardware-eligible.

Codec coverage is backed by immutable row-to-code registries rather than name-set
membership alone. All 85 request codec rows and 86 response decoder rows resolve to one
or more importable Python symbols. Locator kinds preserve direct callables, enum-bound
callables, typed and branching factories, pipelines, stateful assemblers, and shared
families whose row binding is still unresolved. Resolution imports symbols but never
invokes codecs, accepts payloads, or constructs Bluetooth.

Request routing is a second 112-row, mutually exclusive evidence view. Seventy-nine
deterministic layouts enter the source main queue and six enter its raw queue. One
shared OTA preflight has an identifiable main layout but is not a standalone codec; one
caller-directed write, one raw descriptor control, one internal DFU flow, and 23
no-fixed-packet operations stay separate. Queue roles describe static plumbing only.
Mutable policy status, connection gates, history/silence filters, one global pending
payload, ignored write-callback status, and unknown dispatch outcomes prevent this model
from authorizing a live queue implementation or automatic retry.

A narrower builder-parity ledger closes 37 independently reviewed builder families.
It records the Python symbol, accepted-domain differences, fixed length, checksum
absence, endpoint role, queue item type, and insertion position without storing sample
values. Thirty-one families route through the source main queue and six through its raw
queue; only the shared sensor start/stop builder is front-inserted. The ledger keeps
alarm batching and dial-state queue mutation divergences explicit and remains static,
non-callable, and hardware-ineligible.

Request/callback correlation is a third view over the 85 deterministic request codecs.
Each request has exactly one closed row, including 19 explicitly unresolved rows and
zero unspecified rows. The model preserves endpoint role, opcode/subcommand or marker
predicates, ordered callback projections, multiplicity, direct versus silent failure,
and terminal rules. Raw typed notifications remain event candidates rather than
acknowledgements. The phone-volume callback is an inbound request that causes an
outbound host-state projection; its shared opcode is not treated as an acknowledgement.
Local idle never means success, unrelated events never extend a
deadline, and an uncertain accepted write is never automatically retried.

The exact-type fake runtime accepts closed operation factories for the seven static
query encoders, all eight typed setting encoders, and all seven personal-setting
encoders, plus eight single-frame behavior requests and the independently closed
screen-light route. Composition validates the
fixed request opcode, binds the operation-specific acknowledgement parser, and
preserves direct failure opcodes where present. It
cannot accept arbitrary messages or transports, and every result remains simulation
only and hardware-ineligible.
Alarm batching is rejected rather than flattened: its base/content messages,
per-alarm acknowledgements, and source non-atomic enqueue behavior need a dedicated
batch state machine.
Seven no-argument main queries and the typed screen-light request also compose through
closed response bindings. Multiplexed `54`/`78` families require exact subcommands;
the EQ route preserves its get-kind discriminator. Wi-Fi scan is rejected because its
count and fragment assembly have no proven whole-scan terminal.
Twelve strict command encoders have exact response bindings and therefore compose into
the fake engine; six without a closed correlation fail at the factory boundary. Health,
binding, and factory-mode risk labels do not change this rule or make an operation live.
The phone-integration boundary similarly permits only three exact single-frame routes:
user-info acknowledgement, Wi-Fi AP state, and worship-info projection. Private sync,
content, credential, and external-pipeline requests stay outside the singleton engine.

Raw simulation uses separate fake metadata for TX `33f5` and RX `33f6`; the main fake
route fails raw preflight. The bounded collector subscribes before an optional closed
raw write, parses only typed notifications, and cleans up deterministically. Results
have only `unknown` or `aborted` completeness—never success—because no raw request/event
pairing, acknowledgement bit, transaction identifier, or wire terminal is proven.

The shared day-history collector is likewise separate from the singleton transaction
engine. It accepts only the three closed day-query objects, counts `25` as one generic
sensor projection plus six multi-sport samples, `40` as fifteen generic and fifteen
oxygen projections, and `55` as three generic and three advanced-sensor projections.
Unrelated frames do not refresh its quiet deadline. Caller limits and quiet both end
with unknown completeness; only the conditional `a5/ff` branch is a delivered failure.
Accepted oxygen/advanced data followed by quiet adds one source-shaped local end
projection carrying the hidden last specialized timestamp. Frame limits, failure,
disconnect, malformed input, and cleanup failure never add that projection.

The generic `getDataByDay` collector is a separate fake-only state machine accepting
only an exact `DayDataRequest`. It reproduces the type-1, type-2, type-12, and type-13
sample callback counts and the three proven failure/end branches. Detail `ff` is the
only direct wire terminal; the recovered F0/AA/A0 predicate is confirmed device
metadata, not a wire terminal. Local quiet may project the source-shaped end callback
after accepted data but remains incomplete/unknown, while a caller frame limit never
fabricates an end callback. Matching malformed frames and bounded-queue overflow abort.
Every setup/write/cleanup stage has a finite deadline, concurrent use is rejected, old
retained callbacks are inert, queued frames are drained, and frame limits are capped.
Type-13 frames preserve both generic and specialized oxygen multiplicity; local end
arguments stay available only through an explicitly named redacted test accessor.

Artifact review also uses fail-closed negative evidence. No direct constructor, native
identifier, or common owned dynamic-class-construction API does not prove runtime
dormancy. A bounded review resolves all 11 invocation sites in the five owned reflective
files to constant Android bond, telephony, classic-profile, or GATT-cache targets and
excludes the separate dial-transfer object from those receiver/argument flows. A bounded
Binder/resource/navigation trace also finds no static activation edge: the app-owned
launches use app-owned flows, relevant Binder requests have no app-side invocation, and
the app directly binds its private BLE service, whose inherited service path constructs
the generic OTA object. All three packaged JNI roots and
their bounded transitive call graph perform image/wallpaper work without a rooted
Bluetooth or dial-transfer edge. Unmatched declarations, whole-ELF instructions, and
runtime-generated or external binding still keep overall activation inconclusive and
complete artifact coverage false. Android receiver registration defects
remain source-app observations; JRing does not recreate their exported or mismatched
broadcast behavior.

`status --select --active-scan` retains the scan's private address association only in
an in-process selection candidate whose representation and public summary omit it.
Aliases use a new cryptographic salt for each discovery call. A numbered choice is
followed by a distinct default-no connection confirmation before `BleakTransport` is
constructed. The possible-JRing flag is only a client-side advertised-name substring
heuristic and is labeled as such in human and discovery JSON output. This interactive
path has no JSON mode; non-interactive callers use the private address-file contract.
Diagnostics hash addresses with a per-process salt and omit raw health payloads.
Readiness uses a bounded, read-only system D-Bus query for BlueZ daemon ownership,
enumerates only local `hciN` adapter names from sysfs, and reads only each adapter's
boolean `Powered` property. It never requests paired-device objects, starts discovery,
connects, sets power, or edits policy. Unparseable or denied evidence becomes
`uninspected` or `denied`, never a guessed healthy or absent state.
`busctl` availability is a separate `diagnostic_tool` check. A missing executable does
not become a D-Bus repair diagnosis, and no backend-private optional Python D-Bus API is
used as an implicit fallback.

`jring.input` maps typed logical sensor events to a closed set of named keyboard and
mouse actions. Preview is the default. Linux `uinput` is loaded lazily and requires an
explicit CLI authorization flag. Shell commands and arbitrary codes are not part of
the model. A local action inventory is generated from the same definitions used by
the parser. Primary/left and secondary/right are aliases of identical actions. A
created `uinput` device advertises only the code selected by its validated mapping.
Standard HID service `1812` is detected as a capability only; raw HID
reports are neither parsed nor logged. Simulated `step` is the only motion source until
hardware event frames are verified.
The local non-health inventory separately exposes classic profile attachment, an
RFCOMM socket lifecycle reference, two classic metadata callbacks, and the host
volume-state request. Static evidence contains socket construction and close only;
actual OTA transfer uses GATT, with no observed RFCOMM connect, read, or write.
These rows share no activation path with HID and remain non-live, non-input-eligible
evidence.

`JRingClient.capability_inventory` concurrently requests service UUIDs and static GATT
metadata under one deadline. The transport returns only characteristic properties and
descriptor UUIDs; no characteristic or descriptor value is read. Known standard HID
metadata is converted into explicit evidence states, while report contents, OS
attachment, usability, and hardware motion remain unverified.

The same inventory preserves role-neutral observations of statically known vendor
UUIDs wherever they appear as a service or characteristic. Characteristic-only
evidence is no longer lost or mislabeled as a service. A vendor UUID's presence and
properties never infer health, motion, HID, history, or command semantics.

The repository-local compatibility tool validates coarse, versioned reports using the
same fail-closed sensitive-content checks as evidence manifests. It performs no device
operation and merges rows deterministically. Synthetic and owner evidence remain
separate, and no computation promotes `untested` into a compatibility claim.

Release preparation uses an isolated workflow with immutable action SHAs and exact
Python build-tool versions. Wheels must already be reproducible; source archives are
normalized to sorted members, the commit epoch, numeric ownership, and a deterministic
gzip header before two builds are compared. Inspection and clean install smoke tests
precede checksums, provenance attestation, and temporary CI artifact upload. There is
no publishing step or repository-contents write permission.

## Acceptance criteria

- Import and simulator tests work without Bleak or hardware.
- Parsers reject truncated, oversized, malformed, and bad-checksum simulator data.
- Discovery alone cannot connect; guided selection requires explicit scan and
  connection consent, while other hardware access requires an explicit address.
- Safe standard battery/device-info reads are bounded by timeouts.
- Time sync is opt-in and requires `--allow-write`; vendor writes are impossible.
- Live standard heart-rate notifications can be consumed and cancelled cleanly.
- Simulated history can be paginated and exported as JSONL/CSV with atomic replace.
- Reconnect attempts are bounded, cancellable, and use capped exponential backoff.
- Diagnostics redact addresses and never log payloads by default.
- Standard HID service presence is reported as observed, with usability unknown and
  without capturing reports.
- Standard HID metadata inventory never reads or subscribes and preserves independent
  characteristic states when optional descriptor metadata is missing or malformed.
- Vendor UUID inventory covers service and characteristic positions, labels meanings
  unknown, and cannot read, subscribe, pair, or write.
- Static vendor request vectors are exact, bounded, synthetic, and transport-disconnected;
  they always report `static_apk_only` and `hardware_eligible: false`.
- Static response decoders require exact lengths/opcodes, expose integrity state, and
  structurally discard the device-info identifier instead of redacting it after parsing.
- Status collects battery, Device Information, and service inventory concurrently under
  one bounded deadline. Additive per-field states distinguish absence, malformed data,
  timeouts, and a service that was not advertised without exposing raw values.
- Sensor-to-input mappings preview by default and reject arbitrary actions.
- Input injection is explicit, bounded to one simulated event, and closes `uinput`.
- Input actions are locally discoverable, accessible in terminology and ordering, and
  restrict the kernel device to selected capabilities.
- Unit, simulated integration, and CLI tests pass without a ring; hardware tests skip.
