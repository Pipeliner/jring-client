# Protocol evidence ledger

The research input was verified before extraction and all extraction occurred outside
Git in the task temporary directory. This ledger is a concise factual inventory, not
decompiled vendor material.

| Area | Evidence | Confidence | Client status |
|---|---|---:|---|
| Archive | Base APK; ko, vi, zh, de, hi, my, fr, it, ja, pt, ru, th, tr, es, in, en, ar language splits; xhdpi and arm64 splits | High | Documented |
| Package | JRing 1.9.84/182, package `com.jaga.ibraceletplus.jyring` | High | Documented |
| BLE SDK | `com.sxr.sdk.ble.keepfit` service, AIDL client/options/profiles/callbacks | High | Architecture informed only |
| Standard GATT | Device Info `180a`/`2a23`–`2a2a`,`2a50`; Heart Rate `180d`/`2a37`; CCCD `2902` | High | Device text and HR parsers |
| Standard HID | HID service `1812` and assigned characteristic/descriptor UUID meanings are standards-based compatibility checks, not observed vendor evidence | Low for JRing presence | Enumerate metadata only; no values or reports |
| Vendor GATT | SDK constants place `56ff` as a service with `33f3`/`33f4` transport characteristics and `33f5`/`33f6` raw-data characteristics; `ffe5`/`ffe9` form a second path; `57ff` and `fef5` also occur | High static roles; unverified on hardware | Service/characteristic metadata only |
| Battery | SDK methods/callbacks and Android UI actions mention battery | High capability; unknown UUID | Standard `2a19` safe read |
| Device info | SDK get-device-info operations and standard DIS UUIDs | High | Safe reads |
| Time | get/set device-time operations | Exact static opcode-`01` request codec; live behavior unverified | Offline codec plus guarded standard CTS read |
| Live events | HR, oxygen, blood pressure, temperature, ECG, sensor/sport callbacks | Strict static response codecs for recovered families; live direction and firmware behavior unverified | Offline response codecs; standard HR only on hardware |
| History | by-day, oxygen offline, sensor offline, multiple sport, ECG history operations | Strict static codecs for recovered families; pagination and acknowledgement remain unresolved | Offline codec/simulator/export only |
| Control domains | developer-cloud validation, device-cloud policy, `4b` binding, Android bonding, and command-transaction timeouts are separate flows | High static separation; live owner flow unverified | No cloud replay, implicit binding, bonding, or live vendor transaction |
| Integrity | Family-specific checksums plus unresolved CRC/XOR references | High where a strict codec exists; no universal rule inferred | Offline strict codecs only; no hardware eligibility |
| Other | alarms, sedentary/sleep, user profile, goals, notifications, contacts, weather, dials/OTA, Wi-Fi/AI | High API surface | Parity tracked; intentionally not transmitted |
| Native | One arm64 native library in ABI split | High | Not redistributed or invoked |

Standard Bluetooth UUID semantics come from the Bluetooth SIG assignments; their
presence proves code support, not that every JRing model exposes each characteristic.
The Battery Service UUID was not observed in the extracted string set and is therefore
a standards-based compatibility attempt, not vendor verification.

## Static parity boundary

A second, owner-authorized clean-room pass used JADX 1.5.6 on the same digest-verified
archive in a mode-0700 temporary directory. Its structured pass processed 6,705 class
units and emitted 10,185 Java renderings. The run reported 89 failures; an exhaustive
rendered-output audit separately found 88 failed-method stubs in 52 files and 87
error-or-incorrect-code markers. These are different observables and no one-to-one
mapping or inferred difference is claimed.

All 52 hard-failure files were classified as third-party dependencies. Zero recognized
hard-failure files occurred among the 268 application outputs or 47 embedded BLE-SDK
outputs, and none of the hard-failure files directly referenced Bluetooth, GATT, HID,
or the embedded SDK. Warning-only output remains material: 23 application files and 21
embedded-SDK files contain warnings, including Bluetooth-related code. Marker absence
therefore does not establish correct control flow or semantic parity.

A fresh fallback-mode pass completed normally over 6,705 units, emitted 10,267 Java
outputs, retained the same 268 application and 47 embedded-SDK output counts, and had
zero recognized hard-failure markers. Its console did not provide a numeric run-failure
count, so that value remains unavailable rather than being changed to zero. This proves
fallback output availability only: complete semantic source review, complete smali
review, exhaustive DEX instruction coverage, native/resource/reflection coverage, and
hardware behavior remain not established. None of the APK, DEX, rendered source, logs,
assets, or native code is part of this repository.

The SDK interface exposes more than one hundred entry points and corresponding event
callbacks. The public capability groups are:

| Group | Static operation surface | Python/hardware state |
|---|---|---|
| Transport | scan, connect/disconnect, service/characteristic access, notification control, RSSI | Explicit selection and passive metadata supported; vendor values untouched |
| Device queries | battery, device info/code/state/function, time, screen/touch/mode, dial/file/media/EQ/Wi-Fi state | Standard GATT subset only |
| Activity/history | current sport, by-day activity, multi-sport, advanced sensor, oxygen and ECG history | Simulator export only |
| Live sensors | heart rate, oxygen, blood pressure, temperature, ECG, G-sensor/raw sensor | Standard HR library API only; no vendor subscription |
| Personalization | goal, profile, alarms, reminders, sleep/idle, language, display, anti-lost, vibration | Static surface tracked; vendor transmission disabled |
| Phone integration | notifications, contacts, call/media state, volume, weather, messages and cards | Static surface tracked; private data never sent |
| Control domains | cloud validation/policy, explicit binding, Android bonding, and command-transaction state | Separately modeled; no bypass, replay, or inferred equivalence |
| Bulk/high risk | dials, wallpapers, files, FTP, OTA/DFU, factory test, Wi-Fi and AI/audio features | Deferred and separately threat-modelled |

Static analysis can establish endpoint labels, candidate opcodes, fixed frame widths,
and parser branches. It cannot by itself establish which firmware exposes an endpoint,
legitimate owner authentication, a write's complete side effects, or response timing.
Those distinctions are tracked in issue #16. A vendor encoder may be tested offline,
but it cannot reach `BleTransport.write` until every byte is classified and a bounded
owner-ring canary independently confirms that exact operation.

## Offline static request vectors

`jring.vendor_protocol` independently encodes the lowest-ambiguity query frames found
in the static SDK path. Each is exactly 20 bytes, zero-filled after the declared
fields, and targets the SDK's `33f3` write characteristic. The module has no transport
integration; every result is permanently marked `static_apk_only` and
`hardware_eligible: false`.

| Operation | Opcode | Declared fields | Decoder/hardware status |
|---|---:|---|---|
| Current sport query | `03` | none | Static response decoder; hardware unverified |
| Battery query | `0b` | none | Static response decoder; hardware unverified |
| Device information query | `0c` | none | Static response decoder with identifier redaction; hardware unverified |
| Band-function query | `20` | none | Static 96-flag response decoder; hardware unverified |
| Multiple-sport day query | `25` | unsigned one-byte day offset | Static packed-record decoder; hardware unverified |
| Oxygen day query | `40` | unsigned one-byte day offset | Static bounded-record decoder; hardware unverified |
| Advanced-sensor day query | `55` | unsigned one-byte day offset | Static neutral-field decoder; hardware unverified |

These are protocol facts and synthetic golden vectors, not captured owner frames.
Health-related names describe the SDK operation; the repository contains no owner
measurement or raw capture. An opcode match alone cannot activate a live operation.
`static_protocol_coverage()` provides the same seven-entry inventory to Python callers,
including request/response endpoints, known success and failure opcodes, static-only
maturity, and an unconditionally false hardware-eligibility flag.

The first strict response decoders cover:

- `0b`: battery percentage plus an opaque one-byte state code. The state is not
  relabeled as charging until hardware evidence confirms its meaning.
- `03`: a little-endian activity summary containing device epoch, steps, distance,
  calories, and one still-unknown 24-bit value.
- `13`: a second current-sport layout with device epoch and three neutral 32-bit
  fields whose meanings remain unverified.
- `0c`: device type and two revision values plus seeded CRC-32 over bytes 1–15.
  The six-byte device identifier at bytes 3–8 is intentionally discarded and cannot
  appear in the returned object or its representation.

Failure opcodes (`8b`, `83`, and `8c` for these families), wrong opcodes, wrong frame
lengths, and impossible battery percentages fail closed. Device-info CRC failure is
represented explicitly; it never silently promotes the revision fields to trusted.

The remaining four static response decoders cover:

- `20`: twelve bytes expanded byte-major and least-significant-bit first into 96
  capability flags. A small app-derived name table is metadata, not a claim that the
  selected firmware supports or safely exposes a feature.
- `25`: six one-minute records whose type codes are split across record bytes and
  three trailing nibble packs. The 12-bit value remains neutral.
- `40`: fifteen one-byte records at one-minute intervals.
- `55`: three five-byte records at 15-minute intervals. All five fields remain
  neutral because application labels are not firmware verification.

All history timestamps are returned as raw device epoch seconds. The vendor SDK
adjusts records using the host's current timezone offset, which is not reliable for
historical daylight-saving boundaries. The clean-room decoders do not apply that
policy. They also always report `end_of_history: false`: static evidence shows only
two-second inactivity timers and inconsistent or duplicate inferred endings, not a
reliable success marker on the wire.

The interface inventory contains 112 request methods and 105 callback declarations.
The mutually exclusive request ledger records 79 direct main-channel methods, one
main-then-cloud operation, six raw commands, one raw-notification control, 14 local BLE
or dynamic-GATT methods, three cloud/cache methods, one phone-network method, two local
filesystem/conversion methods, one DFU method, and four no-op stubs. Thus 80 wrappers
transitively reach the main queue, but the composite OTA-info operation is not counted
twice.
No AIDL request is statically wired to the declared secondary channel. The Python
client implements zero live vendor requests; 85 request codecs (seven paired queries,
six raw commands, 26 settings mutations, and 46 additional main-command families), 26
non-runnable static behavior-evidence rows, one non-runnable raw control model, and all
86 opcode-originated callback declarations have offline decoder coverage only. This is
not a count of distinct wire families. Local album
saving, bitmap conversion, and worship-setting
operations are now included in the parity ledger even though they do not belong in a
Bluetooth client implementation.

`jring.vendor_coverage.static_vendor_operation_coverage()` is the checked source for
the request names and mutually exclusive routes. Tests require exactly 112 unique
entries, exact route totals, 85 offline request codecs, 26 static behavior-evidence
rows, one offline control model, zero unclassified request entries, zero live vendor methods,
and false hardware eligibility and verification for every entry. Request maturity uses
a closed state enum rather than labels inferred by substring. This corrects an earlier grouped count
that treated only three interface methods as stubs; static call-site tracing shows that
`getWifiState` is also a no-op in this build even though related response parsing exists.

`static_vendor_callback_coverage()` likewise accounts for all 105 callback declarations
exactly once. Eighty-six are reached by a structured main or raw Bluetooth opcode,
14 originate in Android transport, scan, network, OTA, authorization, or cache flows,
three end callbacks are APK-generated local timer/parser projections, and two
declarations have no invocation site in this SDK build. All 86 opcode-originated
callback declarations now have offline response decoder coverage: the seven query families plus bounded
non-health state, action, counter, dial, schedule, current-data, and unknown-motion
events, five raw notification families, operation-specific acknowledgements, and the
generic by-day history decoder. The three local end projections are modeled separately
rather than invented as wire frames. All 105 remain hardware-ineligible.

The coverage ledger is mechanically linked to code. Immutable registries account for
exactly 85 request-codec rows and 86 response-decoder rows. Every locator resolves to an
importable callable or closed typed/stateful factory. Four neutral sensor-setting
request rows still lack a proven row-to-mode binding, and five raw callback rows share a
broad parser without a closed expected-type parameter; those nine relationships are
reported as unresolved family bindings, not direct codecs. Locator resolution does not
run a codec or make a row live.

The request-routing evidence independently partitions all 112 rows: 79 deterministic
main layouts use the main queue/TX/RX roles, six deterministic raw layouts use the raw
queue/TX/RX roles, one stateful OTA preflight shares a main-query builder, one operation
is caller-directed dynamic GATT, one controls the raw notification descriptor, one is
internal DFU, and 23 produce no statically fixed vendor packet. The 85 standalone codec
count therefore remains distinct from 86 identifiable layouts and 80 source paths that
can reach the main queue. None establishes session readiness, owner authorization,
response correlation, safe retry, or hardware support.

The app-use evidence answers a different question: what this APK directly references,
not what the bundled SDK exposes. It partitions all 112 request rows into 51 direct
app interface targets (152 invoke sites), 43 uninvoked SDK wire entries, 14 uninvoked
local/composite entries, and four uninvoked no-op stubs. It also accounts for all 105
callbacks as 103 with a direct SDK dispatch and two declarations without one
(`onGetDeviceTime` and `onSendWeather`). The request and callback namespaces remain
descriptor-distinct; their single name collision, `setAutoHeartMode`, is not merged.
No positive owned dynamic request-interface invoke was observed, but reflection or
external/runtime activation is not thereby disproved.

## Control-flow domains and recovered ordering

Five domains must not be collapsed into one “authorized session”:

| Domain | Recovered role | What it does not prove |
|---|---|---|
| Developer-cloud validation | Asynchronous application/SDK policy with a time cache and one mutable callback slot | Ring ownership, GATT readiness, or a wire challenge |
| Device-cloud gear policy | Per-device cloud decision launched after the SDK reports BLE readiness | Descriptor acknowledgement, binding, or Android bond state |
| Application binding | Explicit `4b` request/notification exchange | Cloud approval or Android pairing |
| Android bonding | OS bond and optional classic-Bluetooth profile attachment | Vendor-GATT ownership or `4b` completion |
| Command transaction | Notification activation, one characteristic-write outcome, and an operation-matched response | Any of the four authorization/attachment decisions above |

Static control-flow review shows that developer validation is not awaited before the
app requests a connection. Device-cloud policy starts after notification configuration
has merely been submitted and after the SDK has already exposed connected state; normal
application initialization may therefore overlap its result. A later policy denial can
disconnect an otherwise ready-looking connection. The independent Python client does
not copy cloud credentials or endpoints, replay decisions, or relabel either cloud
flow as ring authentication.

Local bind/unbind remains disabled because physical confirmation behavior, timeout
state, and firmware coverage are unproven. The recovered request contains three fields;
the app uses explicit initialize, acknowledge, and unbind actions rather than treating
binding as connection setup. Android bonding remains a separate optional classic-
Bluetooth path and is not a prerequisite for vendor GATT.

The recovered SDK exposes connected state when its descriptor write is submitted, not
when the descriptor callback proves success. A submission failure schedules disconnect;
the callback handles one generic failure specially but otherwise schedules an automatic
`01` device-time mutation. Its timestamp uses the current total timezone offset while
its separate offset byte uses the raw non-DST whole-hour offset, so the two can disagree.
The Python client does not reproduce that premature readiness claim or startup write.
The exact frame remains available only through the explicit, hardware-ineligible offline
codec. Binding (`4b`) is likewise an explicit mutation, not an implicit part of
connection, subscription, or cloud policy.

Before any future live vendor command path can be ready, it must serialize notification
activation and characteristic writes, require successful primary subscription
readiness without relabeling it as direct CCCD evidence, match responses by an
operation-specific shape, clear pending work on disconnect, redact frames from logs,
and fail uncertain without automatically replaying a write. Every callback must carry
the active connection generation; a late callback from a closed GATT cannot advance a
replacement connection. Human and machine output must keep `connected`, endpoint
validation, subscription activation, write completion, application response, cloud
policy, binding, and Android bonding separately named. A timeout after write submission
must say that delivery is unknown and require a fresh connection, not invite a blind
retry.

## Non-health and general-use findings

The APK does not contain evidence that the ring exposes the standard HID service or
HID report UUID family. The client's standard HID inventory remains useful for any
model that advertises those assigned UUIDs, but it is a generic compatibility check,
not a claim about this APK or tested JRing firmware.

The strongest statically proven future input source is a main-channel device-action
event. `parse_vendor_device_action()` accepts the 20-byte `06` event and the `22`
weather/location variant. It classifies shutter, media navigation, and volume as
possible input candidates; find-phone, call control, location refresh, camera
lifecycle, time synchronization, and unknown codes remain non-candidates with visible
side-effect classes. These labels describe the Android app's interpretation, not the
physical ring gesture that produced the event. The decoder has no BLE subscription or
input-sink integration and every result remains hardware-unverified.

`parse_vendor_step_counter()` decodes the receive-only `51` cumulative 32-bit counter.
It is explicitly `experimental_counter_only`, not a button event and not input-eligible.
A future owner-verified adapter must baseline on each connection, ignore the initial
value, handle reset/wrap, avoid replaying batched increments as click bursts, debounce,
and rate-limit output.

`ExperimentalStepCounterAdapter` implements those transformations for synthetic input
only: a new connection or reset establishes a baseline, a multi-step jump is discarded
rather than replayed, and exact single increments are rate-limited. The adapter is
unconditionally hardware-ineligible and is not connected to the transport or uinput.

The motion path uses opcode family `78` and can yield nine signed 16-bit channels in
bytes 2–19; this APK branch consumes the entire fixed frame. Axis order, units, sampling
interval, subcommand scope, and gesture meanings are not proven.
`parse_vendor_motion_frame()` therefore requires the caller to name the exact expected
subcommand and rejects every known non-motion `78` subcommand. It retains neutral
channel names and remains hardware-unverified. Raw `33f5`/`33f6` traffic includes
AI/audio/image material and is privacy-sensitive; Wi-Fi, call control, files/dials,
arbitrary writes, and executable `fef5` OTA are outside the default input path. The
declared `57ff`, `ffe5`, and `ffe9` UUIDs have no executable call site in this build.

Additional strict offline event decoders cover three device-state bits, four neutral
custom-dial values, the `29` current-data event with two neutral counters, the host
volume-state request, screen-light time, touch mode, and two schedule-state variants.
They require exact 20-byte frames and exact subcommands, make no writes, and do not
claim that the fields are supported on owner hardware.

## Optional raw channel

`jring.vendor_raw_protocol` independently represents the six statically wired raw
commands as offline-only 20-byte frames for `33f5`. The raw type is a little-endian
16-bit value, followed by three constant little-endian words whose meanings remain
unknown, one typed argument byte, and zero padding. All six request objects hide bytes
from their representations, are marked `static_apk_only`, and are unconditionally
hardware-ineligible. They are not connected to `JRingClient`.

The `33f6` parser accepts the six statically handled inbound types: one-byte AI action,
AI state, bounded audio/image data, voice-command confirmation, and AI command type.
Audio/image bytes are hidden from object representations and available only through an
explicit local-use method. Unlike the APK, the clean parser requires the declared data
length to equal the available bytes and enforces a caller-configurable maximum; it
never silently zero-pads a truncated frame. Unknown types and undersized records fail
closed. Static evidence provides no transaction identifier, checksum, fragmentation,
reassembly, or dependable request/response pairing.

Raw command construction is closed over the six recovered operation types, and all
notification variants share a configurable overall frame bound. Raw notification
control has a non-runnable static behavior model only. It records that
the enable path requests MTU 247 and waits a fixed two seconds rather than for
negotiation; the disable path selects an enable action for `33f6` before disabling
separately configured endpoints. Those fields are explicitly observed APK actions,
including the unsafe enable action on a requested disable. The model exposes neither a CCCD value nor an execute
method. It also preserves the wider defects: descriptor submission is treated as
success and writes are not serialized. Python does not reproduce those behaviors. A
future live implementation needs a successful MTU result where required, serialized
descriptor writes, exact acknowledgement, a real disable value, payload consent,
bounded memory, and logs that never contain audio, image, or command bytes.

## Static acknowledgements

`StaticAckOperation` and `parse_vendor_ack()` cover 25 simple acknowledgement families.
Seventeen have statically paired success and failure opcodes; eight have only a proven
success branch, so the parser rejects a guessed high-bit failure opcode. The shared
sensor-mode acknowledgement remains deliberately generic because four different mode
requests use the same wire opcode and callback. The dispatcher also reports opcode
`25` as a successful generic sensor-mode acknowledgement before decoding the same frame
as multiple-sport data. Both relationships are preserved; the opcode is not counted as
two distinct wire families.

Notification-content acknowledgement is separate and requires the expected outbound
marker in addition to the response opcode. ECG-mode acknowledgement is also separate:
direct smali inspection disproved a decompiler-derived second `9a` branch, so `9a`
remains only the negative goal acknowledgement and is never accepted as ECG failure.
All acknowledgement results remain offline, static-only, and hardware-unverified.

## Static sensor and ECG events

Further offline parsers cover the `14`/`15` open/close measurement family and its
failures, eight neutral one-byte sensor fields, two neutral sensor-state families,
operation-specific one-byte temperature/oxygen state events, and two little-endian
temperature values. Labels remain callback-family descriptions rather than medical
interpretations or hardware claims.

Callback-faithful four-byte fields parsed through Java `Integer.parseInt` reject values
above `7fffffff`; accepting the unsigned wire value would incorrectly create a callback
the SDK suppresses on parse failure. ECG timestamp paths use the wider Java parser and
retain the full unsigned 32-bit range. Failed sensor open/close opcodes expose the
requested direction but report actual `active` state as unknown, because failure does
not establish device state.

ECG codecs cover the history descriptor, start/end event, and both live and history
sample frames. Six three-byte groups unpack into twelve unsigned 12-bit values. These
functions perform no subscription or measurement start, keep device timestamps raw,
and remain static-only. No physiological validation, diagnosis, owner measurement, or
raw capture is stored in the repository.

## Static device and configuration events

Strict offline parsers now also cover device-test and chat-action events, redacted
device-code responses, the complete 20-byte dial-information layout, device-file state,
signed EQ values, factory-test bytes, offline speech mode, binding fields, and three
`54` configuration-state subcommands. Identifier-like device-code bytes are discarded;
factory bytes are hidden from representations and exposed only through an explicit
local-use method. Binding fields remain neutral and cannot establish ownership.

EQ set/get is correlated with an expected response kind and preserves all 15 wire
values while reporting that this APK's callback drops the fifteenth. Dial fields cover
every byte of the frame. None of these decoders enables the corresponding write,
cloud, file, factory, binding, or OTA workflow.

Privacy-bearing Bluetooth names, app IDs, device identifiers, contact fingerprints,
SMS metadata, Wi-Fi addresses, and SSID fragments are decoded without exposing their
contents in representations or coverage output. Wi-Fi fragments use a bounded,
entry-keyed assembler; no parser starts host networking or copies private values into
logs. Explicit local SSID access is opt-in after a complete sequence.

## Static mutation encoders

Three settings modules encode 26 additional main-channel mutation families as hidden,
exactly 20-byte synthetic vectors: device behavior/schedules, profile and sensor-session
settings, and reminder/dial/personal settings. Every request fixes its endpoint,
reports `static_apk_only`, remains permanently hardware-ineligible, and has no client or
transport integration.

The Python contracts deliberately correct unsafe SDK behavior: integers cannot wrap to
low bytes, booleans and modes are closed types, strings use explicit UTF-8 and reject
ambiguous truncation, alarm batches are explicit and atomic, device-mode invalid
fallbacks are absent, host locale is never inferred, and private codes/text/schedules
are hidden from representations. The shared `23` sensor selector is modeled as one
neutral session with an identity-free stop rather than four independent toggles.

These encoders do not reproduce raw-frame logging, retained stale alarms, partial
sends, queue clearing, write retries, or ignored arguments. Health calibration,
reproductive schedules, sensor starts, device reset, identifiers, and personal text
remain high-risk offline evidence—not general-use or live-write features. A valid
synthetic vector does not grant consent, prove firmware behavior, or make timeout
replay safe.

Four further modules encode 46 main-channel families. They cover exact no-argument
and parameterized queries; phone volume and other host-state projections; device,
sensor, time, EQ, and factory controls; and private phone/contact/message/card/Wi-Fi
fragment streams plus a stateful notification planner. The coverage CLI therefore reports 85 offline request codecs in
total. Query/action roles and privacy/risk classes remain closed metadata: notably,
`scanWifi` is a network-scan action and ECG/by-day operations are health-history
queries. Timezone, locale, clock, weather, and phone state must be explicit inputs.

Private-transfer codecs are `wire_frames_only`. They reject silent truncation,
integer wrapping, ambiguous fingerprint widths, malformed/control text, empty Wi-Fi
passwords, and the recovered exact-17-byte Wi-Fi loss case. The extended Wi-Fi form
lists its omitted local timeout timer/callback state. Sync fingerprints are explicitly
not security checks, sensitive representations reveal neither data nor frame counts,
Notification planning preserves exact UID cycling, ephemeral-keyed digest-only
deduplication, and bounded frame sequencing without retaining raw IDs in planner state.
Its state output is only a proposal after atomic enqueue, never a delivery result; live
acknowledgement, planner/overlap serialization, caller throttling, and atomic delivery
remain explicit blockers.

The remaining 26 requests have non-runnable static behavior evidence rather than
behavioral parity or codecs: 14 Android-local/dynamic-GATT methods; cached/cloud metadata, callback
registration, phone FTP, filesystem/conversion, and four true no-op stubs; plus the
composite OTA-info and SUOTA workflows. The local inventory documents persisted raw
identifiers, active scanning, unsafe SDK logging, dynamic UUID state, and arbitrary
characteristic-write authority while granting none of it to Python.

OTA evidence separates the ordinary `33f3` mode/query frames from cache, plaintext
metadata fetch, local firmware files, and the hardware-specific `fef5` SUOTA state
machine. A fresh metadata response can download and overwrite the firmware cache even
when the caller requested information only; that flag gates callbacks/automatic
hardware start, not the download branch. The model records missing authenticity/model gates, unsafe ordering and file handling,
no-response firmware writes, callback gaps, and reboot/disconnect side effects. The
model exposes reconstructible field evidence but no runnable byte object, encoder,
parser, file/network access, or transport plan.

Warning-focused comparison preserves the historical structured/fallback GPIO-selector
divergence while a private, fingerprinted instruction review now confirms only its local
control flow: two recognized branches converge on one write-attempt sequence and other
values return locally. Selector meaning, safe values, device acceptance, dispatch, and
delivery remain unverified. The reviewed chunk path advances its cursor before delivery
confirmation, has no immediate local retry on a rejected dispatch boolean, and can set a
local end flag without accepted dispatch. A later local completion event is not a
peripheral acknowledgement.

The main dispatcher review also corrects its earlier surface terminology. The reviewed
method is an ordered case-insensitive comparison chain with no switch. Its 105 routing
comparisons cover 104 distinct top-level opcodes: 99 have a reachable direct callback
target and five do not. The method has 85 unique direct callback targets across 125
syntactic invokes, of which 124 are reachable; a later duplicate `9a` branch is
shadowed. The closed crosswalk records top-level opcode relationships without claiming
field meaning, runtime reachability, helper side effects, or hardware behavior.

The SDK's progress-named async handoff passes a GATT object, not a numeric OTA
percentage, and the reviewed handoff has no connection-generation guard. It remains
separate from broadcast percentage progress. A three-DEX direct-reference search found
no external construction edge for the separate custom-dial transfer implementation,
but reflection, JNI/native, resource-driven, and dynamic activation were not exhaustively
disproved. The result is therefore inconclusive for runtime dormancy;
`editDeviceDialCustom` remains only its existing offline main-channel setting request
and does not model or authorize dial-file transfer.

## Whole-artifact surface accounting

A private all-DEX audit independently reconciles the exact AIDL surfaces with the public
ledger: 112 request declarations and implementations match 112 request rows, and 105
callback declarations and implementations match 105 callback rows, with zero missing,
extra, or overloaded rows. An exclusive classification accounts for 903 owned
Bluetooth-facing methods across 125 classes. Those methods include interface
declarations, implementations, app call sites, SDK dispatch sites, Android Bluetooth
helpers, and 188 internal OTA methods. Only the declaration sets define interface rows.

The 16 callbacks outside the wire-opcode decoder are also explicitly accounted for.
Fourteen have closed, non-runnable behavior evidence for Android GATT, connection,
authorization, scan, network, OTA, raw-control, or local-file dispatch. Two are retained
as declarations with no observed direct dispatch. Their privacy classes identify raw
GATT values, Bluetooth addresses, advertisement data, network material, cloud content,
and file references without storing those values. None is a live callback adapter or a
hardware-support claim.

Manifest and receiver review finds a required BLE feature and one private connected-
device foreground service, but no app-owned static receiver or static Android Bluetooth
action. The central Bluetooth controller is one of two exported app activities, while
all three app services and all three OTA activities are non-exported. A bundled SDK
configuration asset contains credential material; the evidence model exposes only its
existence and never its values. Most Bluetooth-related dynamic filters use a
process-local broadcast mechanism
for system actions; three registered profile actions have no receiver case. The one
system receiver lacks an observed sender permission and its teardown uses a different
registration domain. These are app-side activation and lifecycle risks, not Python
capabilities or proof that the corresponding Android behavior works.

The reviewed XAPK contains one arm64 native library. Three JNI exports match app-side
native declarations; seven DEX native declarations remain unmatched. A bounded review
of all three packaged JNI roots and their transitive native call graph classifies them
as image/wallpaper processing and layout work. It finds no rooted Bluetooth transport,
dial-transfer, Java-reflection, JNI-registration, or module-loading edge. The six SDK
native declarations cannot bind to this packaged library through ordinary JNI names;
external or runtime binding remains inconclusive. This is not a whole-ELF instruction
review and does not establish native Bluetooth absence.

The 11 reflection calls in five owned Bluetooth-related files are
now instruction-resolved to nine constant Android bond, telephony, classic-profile, and
GATT-cache targets; none has a dial-transfer receiver, argument, class-loading, or
constructor flow. A bounded trace of manifest components, relevant resources, six
app-owned launch sites, nine relevant Binder requests, seven callbacks, and the direct
binding to the private app BLE service finds no static activation edge for the
standalone dial implementation. The
generic OTA implementation is constructed instead. Runtime-generated reflection,
encrypted activation, or externally supplied native binding are not disproved, so
runtime activation and complete artifact coverage remain inconclusive.

## Static history streams

`jring.vendor_history` provides a pure, transaction-scoped decoder for the `10`, `11`,
`16`, `39`, `40`, and `55` history notification families and their proven `90`, `96`,
and `b9` failure frames. It preserves raw device epoch integers, applies the recovered
little-endian layouts and Java half-up averages, and projects every sample into one
neutral shape without applying the host timezone or medical meaning.

The `16` stream retains only its current F0/AA/A0 metadata and closes as confirmed only
for the recovered metadata predicate or the explicit `ff` terminal. Other streams use
bounded local idle closure with unknown completeness; local quiet is never relabeled as
a wire terminal. First-frame, idle, and overall deadlines are monotonic and
generation-guarded. Disconnect and cancel close once, raw frames are not retained, and
representations redact timestamps and values. The APK's timer-derived oxygen and
advanced-sensor end callbacks remain local projections, preventing duplicate or
host-clock-derived completion claims.

## Offline vendor transaction model

`jring.vendor_transport` models the fail-closed ordering required before any live
vendor read can exist. It accepts only the closed typed static-query encoders, fixes
their request/response endpoint roles internally, and uses the corresponding strict
operation parser before a response can succeed. Arbitrary UUIDs, outbound bytes,
matchers, and parser callbacks are not public inputs.

The pure engine separates three distinct facts: generation-bound notification
subscription readiness, an operation-token-bound GATT characteristic-write outcome,
and a matched application response. Subscription readiness deliberately makes no
claim that a `2902` value was written or acknowledged by the peripheral. Write outcomes
are closed and explicit: acknowledged, definitely not dispatched, or unknown. An
unknown outcome taints the connection and requires disconnect before more work. The
engine allows one queued or in-flight operation, uses one finite monotonic deadline
from enqueue through response, rejects stale connection and operation tokens, and
never retries. Unrelated notifications do not refresh the deadline. A timeout,
cancellation, disconnect, malformed response, or unknown outcome after write issuance
is explicitly `uncertain`; work stopped before issuance is `aborted`.

This is simulator state only: every operation, intent, token, closure, and engine stays
hardware-ineligible and hides frame bytes from representations. It is not imported by
the BLE transport or client. A dedicated fake-only coordinator now proves race,
deadline, disconnect, bounded-queue, cleanup, and no-retry behavior without accepting
Bleak or arbitrary transport implementations. Its results always say synthetic and
hardware-unverified; an uncertain result explains that the command may have been
received, was not repeated, and requires a fresh simulator. A live adapter remains
blocked on surfaced ATT write outcomes, disconnect generations, endpoint/model
evidence, owner authorization state,
and read-only hardware canaries. It must also refuse duplicate UUID instances, select
characteristics by service/handle rather than UUID alone, require the response-write
property, serialize callbacks through a bounded generation-tagged queue, buffer any
response arriving before write completion, bound unsubscribe cleanup, and taint the
session after cancellation or an unknown write outcome. Bleak/BlueZ notification
activation is not promoted to direct CCCD evidence.

## Required hardware evidence to advance

Hardware evidence is owner-authorized and processed locally; autonomous work never
contacts a ring. Any original capture or application archive stays outside Git and is
deleted or retained privately according to the owner's decision. It is never accepted
in an issue, pull request, fixture directory, or CI artifact.

Contributors first create a schema-1 evidence manifest following
`tests/fixtures/evidence/synthetic-hid-manifest.json`. It declares provenance,
publication consent, coarse model/firmware context, redactions, coverage, and
confidence. Run both commands locally before sharing anything:

```sh
python3 scripts/evidence_tool.py validate path/to/manifest.json
python3 scripts/evidence_tool.py derive path/to/manifest.json
```

Validation fails closed on addresses, BlueZ paths, account identifiers, precise
timestamps, raw health fields, raw payload fields, long hex, missing consent, and
missing coverage. It reports a category and manifest field but never repeats the
value. `derive` writes a deterministic minimal fixture to stdout only after the whole
manifest passes. Review that output manually before publication; the tool deliberately
does not attempt to redact unsafe input automatically.

An `owner_authorized` schema-1 manifest is a private local ledger. Mode 0600 is
required for local validation and the repository scanner rejects it even with those
permissions; only a separately reviewed synthetic/public-derived fixture is eligible
for Git. The current schema cannot yet express packet layouts or authorize writes.
Issue #17 tracks a typed v2 public-claim schema with operation-specific fields,
synthetic vectors, maturity, and review gates.

Each fixture covers one operation and includes only declared facts needed by a test.
The repository scan checks every tracked, staged, and non-ignored new regular file,
regardless of extension. It rejects capture signatures, APK/XAPK/ZIP archives,
compressed archives, DEX, ELF/native binaries, and recognizable JADX/smali/vendor Java
output, including content disguised as Markdown, Python, or an extensionless file.
Ignored private working material is neither opened nor treated as publishable evidence.
Repeated owner-authorized observations may eventually establish opcodes, lengths,
endianness, checksum coverage, sequence/session state, acknowledgements, pagination,
and terminal markers. Until separately reviewed evidence proves those meanings,
vendor characteristics remain report-only and no guessed packet is sent.
