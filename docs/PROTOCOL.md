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
