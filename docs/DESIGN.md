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

**Hypothesis (low):** vendor frames use an application checksum and session command
queue. Static strings mention CRC/XOR, command responses, authorization and session
timeouts, but do not establish an unambiguous frame format. Consequently no guessed
frame is sent to hardware. The simulator uses a documented, client-owned envelope
solely to test reassembly, event parsing, and history export.

**Unknown:** exact pairing/authentication exchange, vendor opcodes, byte ordering,
checksum coverage, live vendor payloads, history pagination/acknowledgement, and
which UUID family applies to a particular ring firmware.

## Architecture and safety

`jring.protocol` contains strict typed parsers and the simulator-only envelope.
`jring.vendor_protocol` contains pure offline encoders for statically proven query
layouts plus strict offline response decoders. Its request objects cannot claim
hardware eligibility and are not accepted by any client transmission API. Decoder
objects omit device identifiers and raw bytes; ambiguous fields retain neutral names.
`jring.vendor_history` adds a pure per-request state machine for recovered history
frames. It uses finite monotonic deadlines, distinguishes wire/device/local closure,
and never turns an idle timeout into confirmed completeness or retains a raw frame.
`jring.non_health` is an immutable, local-only evidence inventory; it exposes no frame,
transport, parser, input sink, or authority to promote a static candidate.
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

`status --select --active-scan` retains the scan's private address association only in
an in-process selection candidate whose representation and public summary omit it.
Aliases use a new cryptographic salt for each discovery call. A numbered choice is
followed by a distinct default-no connection confirmation before `BleakTransport` is
constructed. This interactive path has no JSON mode; non-interactive callers use the
private address-file contract.
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
