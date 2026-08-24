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
| Standard HID | HID service `1812` is a standards-based compatibility check, not observed vendor evidence | Low for JRing presence | Detect/report only; no raw reports |
| Vendor GATT | `33f3`–`33f6`, `56ff`, `57ff`, `fef5`, `ffe5`, `ffe9` strings | High existence; medium roles | Detect/report only |
| Battery | SDK methods/callbacks and Android UI actions mention battery | High capability; unknown UUID | Standard `2a19` safe read |
| Device info | SDK get-device-info operations and standard DIS UUIDs | High | Safe reads |
| Time | get/set device-time operations | High capability; unknown vendor frame | Standard CTS only, guarded |
| Live events | HR, oxygen, blood pressure, temperature, ECG, sensor/sport callbacks | High capability; unknown bytes | Standard HR only |
| History | by-day, oxygen offline, sensor offline, multiple sport, ECG history operations | High capability; unknown bytes | Simulator/export only |
| Pair/session | authorize, bind, session timeout/response strings | Medium | No automation or bypass |
| Integrity | CRC/XOR/check-CRC strings | Medium; coverage/algorithm unknown | No vendor frame implementation |
| Other | alarms, sedentary/sleep, user profile, goals, notifications, contacts, weather, dials/OTA, Wi-Fi/AI | High API surface | Intentionally not implemented |
| Native | One arm64 native library in ABI split | High | Not redistributed or invoked |

Standard Bluetooth UUID semantics come from the Bluetooth SIG assignments; their
presence proves code support, not that every JRing model exposes each characteristic.
The Battery Service UUID was not observed in the extracted string set and is therefore
a standards-based compatibility attempt, not vendor verification.

## Required hardware evidence to advance

With the owner's ring explicitly selected, record a redacted GATT service listing and
captures of one operation at a time from the official app: battery read, device info,
time read/write, start/stop heart rate, and a bounded history request. Remove addresses,
account material, and health values before retaining fixtures. Repeated captures with
controlled single-byte changes are needed to establish opcodes, lengths, endianness,
checksum coverage, sequence/session state, acknowledgements, pagination, and terminal
markers. Until then, vendor characteristics remain read/report-only and no guessed
packet should be sent.
