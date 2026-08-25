# Clean-room APK callback and dispatcher specification

Status: static dispatcher appendix to `APK_FUNCTIONAL_SPEC.md`.

This appendix specifies callback origin and routing. Callback delivery is not by
itself request ownership, acknowledgement, state application, or terminal completion.

## Denominator reconciliation

The callback interface has 105 declarations: 86 Bluetooth-opcode callbacks, 14
Android/network/OTA/transport callbacks, three APK-local timer/parser projections,
and two declarations without a direct invoke. Static call accounting finds 103 invoked
targets, 181 invokes, and 126 unique caller-to-callback edges from 34 methods in 17
classes.

The primary MAIN dispatcher has 85 targets and 125 invokes: 81 opcode callbacks, three
local end projections, and `onDeviceConnectedWifi`. The raw dispatcher has five targets
and six invokes. Outside-dispatcher behavior has 17 targets and 50 invokes. Four targets
have both MAIN and outside origins, so origin target counts overlap.

## MAIN top-level opcode routes

There are 104 distinct compared opcodes: 99 callback-bearing and five callback-silent.
Shared opcodes require lower-level selector/body discrimination.
The implementation is an ordered case-insensitive comparison chain with 105 routing
comparisons, 125 syntactic callback invokes, 124 reachable invokes, and 85 unique
targets. The first `9A` branch emits `onSetGoalStep(0)`; a later case-insensitive
`9a` ECG-failure branch is unreachable.

| Opcode(s) | Reachable callback target(s) |
|---|---|
| `01` | `onSetDeviceTime` |
| `02` | `onSetUserInfo` |
| `03`, `13` | `onGetCurSportData` |
| `04`, `84` | `onSendVibrationSignal` |
| `05`, `85` | `onSetAntiLost` |
| `06`, `22` | `onGetDeviceAction` |
| `07`, `87` | `onSetPhontMode` |
| `08`, `88` | `onSetIdleTime` |
| `09`, `89` | `onSetSleepTime` |
| `0B` | `onGetDeviceBatery` |
| `0C` | `onGetDeviceInfo` |
| `0D`, `8D` | `onSetAlarm` |
| `0E`, `8E` | `onSetDeviceMode` |
| `10`, `11`, `39` | `onGetDataByDay` |
| `12`, `92` | `onSetNotify` |
| `14`, `15`, `94`, `95` | `onGetSenserData` |
| `16` | `onGetDataByDay`, local `onGetDataByDayEnd` |
| `19`, `99` | callback-interface `setAutoHeartMode` |
| `1A`, `9A` | `onSetGoalStep` |
| `1B`, `9B` | `onSetDeviceInfo` |
| `1D`, `9D` | `onSetHourFormat` |
| `1E`, `9E` | `onSetDeviceCode` |
| `1F`, `9F` | `onGetDeviceCode` |
| `20`, `A0` | `onGetBandFunction` |
| `21`, `A1` | `onSetLanguage` |
| `23`, `A3` | `onSetBloodPressureMode` |
| `24` | `onReceiveSensorData` |
| `25` | `onGetMultipleSportData`, `onSetBloodPressureMode` |
| `26`, `A6` | `onSetDeviceHeartRateArea` |
| `27`, `28` | `onSensorStateChange` |
| `29` | `onReadCurrentSportData` |
| `2A` | `onSetEcgMode` |
| `2B` | `onGetEcgValue` |
| `2C` | `onGetEcgHistory` |
| `2D` | `onGetEcgStartEnd` |
| `2E` | `onGetEcgHistoryData` |
| `30` | `onSetDeviceName` |
| `31` | `onSetReminder` |
| `32` | `onSetReminderText` |
| `33` | `onSetBPAdjust` |
| `34` | `onGetDeviceDial` |
| `35` | `onSetDeviceDialState` |
| `36` | `onSetDeviceWallpaperState` |
| `37` | `onSetTemperatureMode` |
| `38` | `onGetTemperatureData` |
| `3A` | `onDeviceTestCmd` |
| `3B` | `onTemperatureModeChange` |
| `3D` | `onGetDeviceState` |
| `3E` | `onSetBloodOxygenMode` |
| `3F` | `onReceiveSensorOxygenData` |
| `40` | `onGetDataByDay`, `onGetOxygenOfflineData`, local `onGetOxygenOfflineDataEnd` |
| `41` | `onEditDeviceDialCustom` |
| `42` | `onGetDeviceDialCustom` |
| `44` | `onSetFemaleReminder` |
| `45` | `onNotifyAppId`, `onNotifyClassicBtInfo`, `onNotifyClassicBtName` |
| `46` | `onNotifyContactCrc` |
| `49` | `onGetPhoneVolume` |
| `4B` | `onNotifyBindedInfo` |
| `4C` | `onNotifyECardNeedUpdate` |
| `4D` | `onNotifySmsRspNeedUpdate`, `onNotifySmsRspSend` |
| `4E` | `onGetChatgptAction` |
| `50` | `onGetFactoryTestData` |
| `51` | `onGetSportSteps` |
| `53` | `onGetEqInfo2`, `onSetEqInfo2` |
| `54` | `onDeviceConnectedWifi`, `onGetDeviceFileState`, `onGetWifiSsid`, `onGetWifiSsidCount`, `onGetWifiState`, `onNotifyAiConnectionMethod`, `onNotifyDeviceSystemStateInfo`, `onNotifyDeviceWifiApState` |
| `55` | `onGetAdvSensorOfflineData`, local `onGetAdvSensorOfflineDataEnd`, `onGetDataByDay` |
| `78` | `onGetGSensorData`, `onGetOfflineSpeechRecognitionMode`, `onGetScreenLightTime`, `onGetTouchMode`, `onGetWorshipInfo`, `onGetWorshipTimesData` |
| `90`, `96`, `B9` | `onGetDataByDayEnd` |
| `A5` | `onGetMultipleSportData` |

Recognized callback-silent opcodes are `1C`, `83`, `8B`, `8C`, and `9C`. A later
duplicate `9A → onSetEcgMode` comparison is shadowed; reachable `9A` dispatches
`onSetGoalStep`.

## Shared-opcode discriminator requirements

- `45`: Classic info, Classic name, and App-ID are separate selector branches.
- `4C`: E-card CRC/content output and inbound need-update event are distinct.
- `4D`: message CRC/content, inbound update, send event, and acknowledgement candidate
  are distinct.
- `49`: outbound phone identifier and inbound phone-volume request are unrelated
  directions despite sharing the opcode.
- `53`: EQ GET and EQ SET kinds must remain separate.
- `54`: Wi-Fi credentials `01/02`, Wi-Fi state `04`, file state `06`, FTP signal `07`,
  scan count/data `09/0A`, AI language `10`, device-system query/response `11/12`,
  Wi-Fi AP `13`, and AI connection `14` are different branches. The local/network
  `onDeviceConnectedWifi` projection is also distinct from raw MAIN receipt.
- `78`: selectors `03`, `07`, `08`, `09`, `0B`, and `0C` have dedicated
  offline-speech, worship, touch, screen, or worship-time decoders. Every other
  selector, including but not limited to `00` and `01`, falls through to
  `onGetGSensorData(selector, nine signed little-endian 16-bit values)`.

## Raw typed callback routes

| Raw type | Typed callback |
|---|---|
| `0001` | `onGetAiAction` |
| `0002`, `0003` | `onGetRawData` |
| `0006` | `onGetAiState` |
| `0009` | `onRecvDeviceVoiceCommandConfirm` |
| `000A` | `onGetAiCommandType` |

Unknown and short raw frames can still take generic characteristic-forwarding behavior
without a typed callback. No cross-frame raw assembly is established.

## Non-opcode and declaration-only callback behavior

| Callback(s) | Recovered behavior | Unresolved semantics |
|---|---|---|
| `onAuthDeviceResult`, `onAuthSdkResult` | authorization-result pipelines with cache/network/log effects | mixed transport/vendor status; exception/null silence; no owner proof |
| `onCharacteristicChanged` | Android GATT identifier plus current value copy; parse/log/route behavior | raw value meaning, null/parse suppression, request ownership |
| `onCharacteristicWrite` | Android GATT status plus current value; unconditional local completion latch | status is not a safe success terminal |
| `onConnectStateChanged` | Android GATT duplicate states are suppressed; a new manual-connect attempt rejected because shared SDK state is already nonzero re-emits that SDK state | link, service, notification, policy, and operation readiness remain distinct |
| `onDeviceConnectedWifi` | connected-only projection of dotted device address, fixed device-network name/credential/port, and derived app-files path | automatic-download can replace callback with FTP start; missing path broadcasts an error; FTP terminal remains separate |
| `onGetDeviceRssi` | RSSI projection | Android callback status is discarded |
| `onGetOtaInfo` | OTA eligibility metadata/file projection | request/parse silence, cache/network/download/transfer meaning; non-200 maps false/empty |
| `onGetOtaUpdate` | OTA phase/detail projection | not percentage; OTA and dormant dial origins differ; gate/duplicate suppression |
| `onNotifyDialJsonContent` | parsed dial JSON/cloud metadata forwarding | transport status can be ignored; activation and consumption incomplete |
| `onNotifyFtpStateInfo` | FTP state plus retry-remaining projection | retry/restart suppression, duplicate progress, empty file on success/error |
| `onNotifyNewMediaInfo` | two file-reference projection | silent unless media action is enabled |
| `onOpenRawDataNotificationState` | local raw-enable submission acceptance | not descriptor completion; disable/missing/rejected branches can be silent |
| `onScanCallback` | local-name/device-name fallback, address, RSSI, four little-endian two-byte vendor identifiers, one one-byte identifier, and one direct two-byte advertisement identifier | not raw advertisement; predicate/malformed/null/dead callback silence; duplicate results; auto-connect/OTA side effects |
| `onGetDeviceTime`, `onSendWeather` | declarations only | no direct invocation observed in this build |

For MAIN selector `54/04`, `onGetWifiState` receives connection state, a four-byte
device address encoded as a contiguous hexadecimal string, a fixed device-network name,
a fixed credential, and a fixed port. On connected state, the local projection converts
the address to dotted decimal for `onDeviceConnectedWifi`. The literal credential and
endpoint values are intentionally not reproduced in this public clean-room spec.

## Argument-derivation groups

The following groups cover the nontrivial MAIN decoders without assigning unstated
domain meaning to their integers:

| Group | Exact APK projection |
|---|---|
| fixed acknowledgements | 18 setter families use distinct success/failure opcodes and emit integer `1`/`0`: device time, user info, vibration, anti-lost, camera mode, idle, sleep, alarm frame, device mode, notification frame, automatic heart, device info, hour format, language, device code, blood-pressure family, goal, and heart-rate area; batched operations acknowledge per frame |
| device-time success | queues a host-locale language update before the callback |
| current sport `03` | kind 0; LE32 timestamp minus stored total offset; three LE32 values; one LE24; trailing zeros |
| current sport `13` | kind 1; offset timestamp; one LE32; zeros; then two later LE32 values |
| battery | two unsigned bytes |
| Device Information | LE16, six-byte identifier text, two two-byte text values, CRC-valid `1`/`0`; CRC compares bytes 1–15 with wire bytes 16–19; CRC failure still calls back and pending OTA continues without CRC gating |
| day data `10/11` | fifteen one-minute samples, kinds 1/2, unsigned value plus zero |
| sensor `14/15/94/95` | start success carries offset timestamp plus two unsigned bytes; stop success and both failure opcodes carry zeros |
| opcode `16` history | metadata markers and calculated values; explicit marker can emit the local end projection; exact branch exclusivity remains warning-sensitive |
| band functions | success plus 96 booleans from 12 bytes, or failure plus an empty array |
| live sensor `24` | eight unsigned bytes |
| multiple sport `25` | first emits `onSetBloodPressureMode(1)`, then six kind-1 sport samples, then invokes the history helper; `A5` emits failure/end only when byte 1 is `FF` and is otherwise callback-silent |
| sensor state `27/28` | `(1,0)` and `(2,0)` |
| current sport `29` | unsigned kind, formatted local datetime from offset LE32 timestamp, two LE32 values |
| ECG samples | first byte plus twelve unsigned 12-bit samples unpacked from six three-byte groups |
| ECG history metadata | LE32 timestamp minus raw timezone offset, then unsigned count |
| ECG start/end | two unsigned bytes and LE32 timestamp minus raw timezone offset |
| temperature `38` | two LE16 values |
| temperature history `39` | three five-minute kind-12 samples, each with two LE16 values |
| oxygen `40` | fifteen one-minute specialized and generic kind-13 callbacks; a 23:45 sample emits end at base+14 minutes and a delayed end can duplicate it |
| advanced sensor `55` | three 15-minute five-value callbacks plus generic kind 14; generic output incorrectly reuses fixed early bytes; 23:45 emits base+44-minute end and delayed end can duplicate it |
| dial `34` | two two-byte hex strings; five LE16 values from pairs 5–10 and 13–18; unsigned bytes 11–12; final unsigned byte 19 |
| classic `45/00` | two unsigned bytes plus two six-byte hex-text segments |
| classic name/App-ID | body-character decoding with final token excluded; App-ID starts at byte 2 |
| contact CRC | characters from bytes 1–4 |
| bind/device state | bind uses two unsigned bytes; device state uses three booleans, each true only when its corresponding byte equals 1 |
| E-card/message | newly allocated body arrays omit the final token; send event is selector plus decoded body text |
| factory `50` | 20-byte result with only tokens 0–18 copied, leaving the last byte zero |
| steps `51` | unsigned/int LE32 parse |
| EQ `53` | byte 1 selects SET only at zero and GET otherwise; three unsigned headers and signed values copied to the declared-length array |
| Wi-Fi scan `54/09` | unsigned count |
| Wi-Fi SSID `54/0A` | end bit, part bit, six-bit current ID, signed signal, up to 16 fragment bytes; one unkeyed global builder; only end emits; failed UTF-8 percent decode yields empty text |
| system/AP/AI `54/12,13,14` | one unsigned state; AP state 1 constructs a phone SSID from persisted device name/address suffix and uses an embedded credential |
| motion/default `78` | explicit selectors as above; all other selectors emit selector plus nine signed LE16 values |
| raw | minimum eight bytes; `0001/0006/0009/000A` use fixed bodies; `0002/0003` copy declared length subject to available bytes; no cross-frame assembly |

The MAIN dispatcher tokenizes text and every branch requires at least 20 tokens, even
when fewer fields are consumed. Short input logs and returns. Text/blob loops commonly
exclude the final token. Parse failure suppresses the intended callback while still
changing shared command/history state; callback absence/exception normally only logs.
A recognized frame generally releases shared queue/session state rather than a
transaction-specific waiter.
Specifically, recognized ordinary branches call the shared cleanup/reset; unknown
top-level opcodes return before it. Parse or callback exceptions also call cleanup,
log the stack trace, and toggle the history worker off then on when history sync is
active. Explicit failure routes include `81 → onSetDeviceTime(0)` and
`82 → onSetUserInfo(0)`.

## Callback completion rules

Method names containing “success,” “state,” “progress,” “end,” “ACK,” or “completed”
do not establish wire or operation completion. In particular:

- the three history `End` callbacks are APK-local projections;
- `onOpenRawDataNotificationState(true)` is local submission acceptance;
- `onCharacteristicWrite` sets a local latch regardless of Android status;
- `onGetOtaUpdate` carries phase/detail rather than a generic percentage;
- `onNotifyFtpStateInfo` can arise across retry, progress, success, and error branches;
- per-frame alarm/notification/settings callbacks do not close a whole batch; and
- shared events and reverse-direction phone actions are not acknowledgements of nearby
setters merely because their values or opcodes look related.

## Application consumption — 105/105 overrides

The exported main activity installs one callback stub implementing all 105 methods.
Thirty-seven implementations are empty in this build:

`onCharacteristicChanged`, `onCharacteristicWrite`, `onDeviceConnectedWifi`,
`onDeviceTestCmd`, `onGetAdvSensorOfflineDataEnd`, `onGetAiAction`,
`onGetAiCommandType`, `onGetAiState`, `onGetChatgptAction`,
`onGetDeviceFileState`, `onGetDeviceRssi`, `onGetEcgHistoryData`,
`onGetFactoryTestData`, `onGetGSensorData`,
`onGetOfflineSpeechRecognitionMode`, `onGetOtaUpdate`, `onGetRawData`,
`onGetScreenLightTime`, `onGetTouchMode`, `onGetWifiSsid`,
`onGetWifiSsidCount`, `onGetWifiState`, `onGetWorshipInfo`,
`onGetWorshipTimesData`, `onNotifyAiConnectionMethod`,
`onNotifyDeviceSystemStateInfo`, `onNotifyDeviceWifiApState`,
`onNotifyDialJsonContent`, `onNotifyFtpStateInfo`, `onNotifyNewMediaInfo`,
`onOpenRawDataNotificationState`, `onReadCurrentSportData`,
`onReceiveSensorOxygenData`, `onRecvDeviceVoiceCommandConfirm`,
`onSetBloodOxygenMode`, `onSetDeviceHeartRateArea`, and `onSetDeviceName`.

The remaining 68 overrides have executable app-side behavior. They partition into
connection/scan/cloud status; device capability and configuration persistence; current
and historical activity/health/ECG persistence and local broadcasts; battery/device
identity and OTA-info state; alarms/reminders/temperature; camera/media/call actions;
classic-profile and vendor-binding reactions; contacts/App-ID/cards/message-response
synchronization; and dial/customization state. A non-empty override may still only log,
return a constant, or emit a local projection; it is not automatically user-visible or
terminal.

This 37-empty + 68-nonempty partition is app consumption, not SDK invocation. It is
therefore separate from the 103 callback declarations with a direct SDK invoke and two
declaration-only callbacks.

## Semantic precision boundary

All 105 declaration signatures, SDK invoke state, dispatcher origins, and app override
consumption states are accounted. Decoder expressions are statically represented and
reconciled by the 86 decoder ledgers; only separately instruction-reviewed expressions
are called instruction-exact. An argument whose domain label, unit, enum meaning, firmware
range, or hardware provenance is not established by those ledgers is explicitly
`unknown`; the Binder type and byte conversion must not be promoted into a guessed
meaning. This applies especially to device-dial geometry/style integers, factory bytes,
G-sensor arrays, raw AI/audio frames, firmware-specific feature-array positions, and
multi-frame terminal state.
