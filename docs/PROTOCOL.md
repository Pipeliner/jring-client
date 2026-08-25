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
| Time | get/set device-time operations | High capability; unknown vendor frame | Standard CTS only, guarded |
| Live events | HR, oxygen, blood pressure, temperature, ECG, sensor/sport callbacks | High capability; unknown bytes | Standard HR only |
| History | by-day, oxygen offline, sensor offline, multiple sport, ECG history operations | High capability; unknown bytes | Simulator/export only |
| Pair/session | authorize, bind, session timeout/response strings | Medium | No automation or bypass |
| Integrity | CRC/XOR/check-CRC strings | Medium; coverage/algorithm unknown | No vendor frame implementation |
| Other | alarms, sedentary/sleep, user profile, goals, notifications, contacts, weather, dials/OTA, Wi-Fi/AI | High API surface | Parity tracked; intentionally not transmitted |
| Native | One arm64 native library in ABI split | High | Not redistributed or invoked |

Standard Bluetooth UUID semantics come from the Bluetooth SIG assignments; their
presence proves code support, not that every JRing model exposes each characteristic.
The Battery Service UUID was not observed in the extracted string set and is therefore
a standards-based compatibility attempt, not vendor verification.

## Static parity boundary

A second, owner-authorized clean-room pass used JADX 1.5.6 on the same digest-verified
archive in a mode-0700 temporary directory. It recovered 10,185 Java source renderings;
JADX reported errors for 89 of 6,705 processed classes. None of the APK, DEX, rendered
source, logs, assets, or native code is part of this repository.

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
| Session | authorization, binding, application/device identifiers, command queue and response timeout | Unknown owner-session protocol; no bypass or replay |
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
client implements zero live vendor requests; seven request codecs and seven response
families are offline-only. Local album saving, bitmap conversion, and worship-setting
operations are now included in the parity ledger even though they do not belong in a
Bluetooth client implementation.

`jring.vendor_coverage.static_vendor_operation_coverage()` is the checked source for
the request names and mutually exclusive routes. Tests require exactly 112 unique
entries, exact route totals, seven offline codec families, zero live vendor methods,
and false hardware eligibility for every entry. This corrects an earlier grouped count
that treated only three interface methods as stubs; static call-site tracing shows that
`getWifiState` is also a no-op in this build even though related response parsing exists.

`static_vendor_callback_coverage()` likewise accounts for all 105 callback declarations
exactly once. Eighty-nine are reached by a structured main or raw Bluetooth opcode,
14 originate in Android transport, scan, network, OTA, authorization, or cache flows,
and two declarations have no invocation site in this SDK build. Eighty-five callback
families now have offline response codecs: the seven query families plus bounded
non-health state, action, counter, dial, schedule, current-data, and unknown-motion
events, five raw notification families, and operation-specific acknowledgements. Every
other callback remains `not_reproduced`; all 105 remain hardware-ineligible.

Three authorization domains remain separate: vendor developer-cloud SDK validation,
device-cloud authorization, and a local BLE binding exchange. The independent Python
client does not copy cloud credentials or endpoints and does not forge or replay cloud
decisions. Local bind/unbind remains disabled because multiple fields, physical
confirmation behavior, timeout state, and firmware coverage are unproven. Android OS
bonding is not treated as vendor binding.

Before any future live vendor command path can be ready, it must serialize CCCD and
characteristic writes, require successful primary notification acknowledgement, match
responses by an operation-specific shape, clear pending work on disconnect, redact
frames from logs, and fail uncertain without automatically replaying a write.

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

The motion path uses opcode family `78` and can yield eight signed 16-bit channels in
bytes 2–17; bytes 18–19 are ignored by this APK branch. Axis order, units, sampling
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

Raw notification control is deliberately absent. The APK requests MTU 247, waits a
fixed two seconds rather than for negotiation, reports descriptor submission rather
than acknowledgement, does not serialize the CCCD write, and can write the enable
value while asked to disable. Python must not reproduce those defects. A future live
implementation needs a successful MTU result where required, serialized descriptor
writes, exact acknowledgement, a real disable value, payload consent, bounded memory,
and logs that never contain audio, image, or command bytes.

## Static acknowledgements

`StaticAckOperation` and `parse_vendor_ack()` cover 25 simple acknowledgement families.
Seventeen have statically paired success and failure opcodes; eight have only a proven
success branch, so the parser rejects a guessed high-bit failure opcode. The shared
sensor-mode acknowledgement remains deliberately generic because four different mode
requests use the same wire opcode and callback.

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
