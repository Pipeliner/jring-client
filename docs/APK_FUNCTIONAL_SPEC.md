# Clean-room APK functional specification

Status: complete clean-room static functionality specification for JRing 1.9.84/182.
Evidence-graded and runtime/peripheral unknowns remain explicit. This is not the Python
implementation plan and grants no runtime, hardware, network, filesystem, input, or
firmware authority.

## Purpose and completion rule

This document specifies the behavior exposed by the reviewed JRing Android package as
clean-room facts. It describes the APK, embedded BLE SDK, Android integration, and
observable interface contracts. It intentionally does not describe Python-client
features, test simulators, or desired safety adaptations.

The specification is complete only when all of these populations reconcile:

- 112 request Binder transactions, with one signature, implementation behavior class,
  app-use state, packet route, side-effect class, and unresolved-semantics set each;
- 105 callback Binder transactions, with one signature, dispatch origin, invoke count,
  app-consumption state, payload interpretation, and unresolved-semantics set each;
- all 217 Binder transactions with matching declared and Parcel order;
- all 86 statically identifiable request layouts, of which 85 are standalone
  deterministic codecs, and all 86 opcode-originated callback decoders;
- all 37 instruction-reviewed request-builder families;
- all 85 deterministic request/callback topology rows;
- all 33 recovered session transitions, six binding reactions, and 22 race cases;
- the selected 903-method/125-class exclusive surface population and, separately, the
  236-method direct executable Android Bluetooth reference population;
- manifest components and permissions, dynamic receivers, reflection, resources,
  packaged DEX units, native roots, and non-Bluetooth platform behavior; and
- every uncertainty left by source rendering, DEX coverage, resources, native code,
  reflection, runtime activation, firmware variation, or absent hardware evidence.

An explicit `unknown` is a valid specified state. An omitted function, argument,
branch, side effect, failure path, or activation edge is not.

## Evidence vocabulary

| State | Meaning |
|---|---|
| declaration-exact | Binder transaction number, argument order/types, and return type are recovered exactly |
| instruction-exact | The relevant DEX instruction path was reviewed and its bounded fact confirmed |
| source-static | Rendered source or static references establish a behavior, but complete instruction semantics are not established |
| topology-only | A request, callback, or local action is related structurally; causality, acknowledgement, or completion remains unproven |
| absent-in-owned-scope | No direct instruction reference exists in the reviewed application/SDK scope; this does not prove dependency or runtime absence |
| unknown | Current evidence does not establish the fact |

Runtime reachability and hardware behavior are separate dimensions. Neither follows
from a declaration, opcode, UUID, source branch, resource label, or callback name.

## Reviewed package composition

The reviewed JRing 1.9.84/182 distribution contains one base package plus 19 split packages: 17 locale
splits, one density split, and one arm64 split. The base contains three DEX units. The
owned application/embedded-SDK scope is classified in one DEX unit; two additional DEX
units contain no recognized owned application or SDK scope. Inventory classification
is complete for all three units, while complete DEX instruction review and complete
semantic source review remain unfinished.

The rendered corpus contains 12,817 files: 10,186 Java, 1,183 XML, and 1,448 other.
Owned structured source comprises 268 application and 47 embedded-SDK files. Its Java
declaration census is 5,898 methods/constructors: 4,220 application and 1,678 SDK,
with 5,335 bodies and 563 bodyless declarations. A direct-platform lexical pass covers
all 5,335 bodies; 3,673 contain none of its selected tokens and are syntactically
accounted rather than semantically reviewed. No owned hard “method not decompiled” stub
is present. Warning risk remains 161 markers in 23 app files and 62 in 21 SDK files.

The manifest declares 79 activities, six services, two receiver components, six
provider components, two provider-query nodes, 35 permissions, and nine features.
Three services are app-owned and non-exported; one is
the BLE foreground service. Two app-owned activities are exported, including one
Bluetooth-controller activity. Three OTA activities are non-exported. BLE hardware is
required. Legacy Bluetooth permissions and modern scan/connect plus connected-device
foreground-service permissions are declared; LE advertising is not declared.

These counts describe package structure. They do not imply that each component is
reachable, user-visible, or relevant to ring control.

## Functional architecture

The APK has five distinct control planes:

1. Application code invokes an embedded SDK through a 112-transaction request Binder
   interface.
2. The SDK reports events through a 105-transaction callback Binder interface.
3. The SDK owns Android Bluetooth discovery, connection, GATT, notification,
   descriptor, queue, and teardown mechanics.
4. The application owns user flows, cache/network policy, Android platform work,
   binding reactions, media/files, and selected classic-Bluetooth actions.
5. OTA/DFU, phone-managed FTP, and image/dial preparation use distinct local or
   transfer subsystems rather than the ordinary main/raw command path.

The word “session” does not collapse these independent state domains:

- developer-cloud SDK validation;
- device-cloud gear policy after SDK connection exposure;
- application binding through the `4b` family;
- Android OS bonding and classic-profile state; and
- an individual command’s queue/write/callback lifecycle.

## Bluetooth transport surfaces

### Standard GATT references

The APK contains standard Device Information service/characteristic references,
standard Heart Rate service/measurement references, and the standard CCCD descriptor.
These establish code awareness, not that every ring model exposes them.

### Vendor GATT references

The embedded SDK assigns these static roles:

| UUID family | Static role |
|---|---|
| `56ff` | primary vendor service |
| `33f3` | primary request/write characteristic |
| `33f4` | primary response/notification characteristic |
| `33f5` | raw request/write characteristic |
| `33f6` | raw response/notification characteristic |
| `ffe5` / `ffe9` | secondary vendor path |
| `57ff` | declared vendor family with no executable call site established in this build |
| `fef5` | executable firmware-update service family |

The ordinary SDK command path uses a global application queue. Queue type `0` maps to
the primary main route; queue type `1` maps to the raw route. The reviewed builder
families are fixed 20-byte commands: 31 main-queue families and six raw-queue
families. Sensor-session start/stop are the only reviewed front-inserted families.
Source guards, logging, partial enqueue, queue clearing, and write-callback handling
are separate semantics and must not be inferred from the bytes alone.

### Android Bluetooth instruction surface

Within the complete owned direct-reference inventory:

| Scope | Owned class-file denominator | Direct-reference methods | Classes | Overlap methods/classes |
|---|---:|---:|---:|---:|
| application | 1,094 | 128 | 42 | 16 / 8 |
| embedded SDK | 138 | 108 | 21 | 10 / 5 |

The 236 methods are classified across GATT, LE scanning, adapter/device management,
and classic profile/socket families. Family counts overlap. Observed instruction
categories include connection lifecycle, service discovery, characteristic reads and
writes, notification and descriptor-write setup, MTU, connection priority, RSSI,
legacy and modern LE scan APIs, classic discovery, bonding, classic profiles, RFCOMM
socket construction/close, and adapter power.

No direct owned-scope instruction reference was found for descriptor reads, PHY
selection, LE advertising, L2CAP channels, GATT server operation, or Android HID-device
role. In the application scope, modern LE scan, connection-priority, and RSSI
references are also absent; their SDK-scope references remain present where noted.
Absence in this inventory is not an unsupported-device claim.

The RFCOMM evidence is construction and close only. No owned connect, read, or write
instruction reference was observed; the reviewed OTA transfer path uses GATT.

## Request interface: exhaustive route partition

Every request transaction belongs to exactly one route below. Names are preserved,
including spelling and capitalization defects in the package interface.

### Primary main command route — 79

`editDeviceDialCustom`, `getAdvSensorOfflineData`, `getBandFunction`,
`getCurSportData`, `getDataByDay`, `getDeviceBatery`, `getDeviceCode`,
`getDeviceDial`, `getDeviceDialCustom`, `getDeviceInfo`,
`getDeviceSystemStateInfo`, `getEcgHistory`, `getEqInfo`, `getMediaFileState`,
`getMultipleSportData`, `getOxygenOfflineData`,
`notifyDownloadFtpFileCompleted`, `openWifiApMode`,
`queryOfflineSpeechRecognitionState`, `scanWifi`, `sendPhoneCallState`,
`sendPhoneVolume`, `sendVibrationSignal`, `sendWeather`, `setAiChatState`,
`setAiConnectionMethod`, `setAILang`, `setAlarm`, `setAntiLost`, `setAppId`,
`setAppState`, `setAutoHeartMode`, `setBindedInfo`, `setBloodOxygenMode`,
`setBloodPressureMode`, `setBPAdjust`, `setChatgptContent`, `setContactCrc`,
`setContactInfo`, `setDeviceCode`, `setDeviceDialState`,
`setDeviceHeartRateArea`, `setDeviceInfo`, `setDeviceMode`, `setDeviceName`,
`setDeviceTime`, `setDeviceWallpaperState`, `setECardInfoContent`,
`setECardInfoCrc`, `setEcgMode`, `setEqInfo2`, `setFemaleReminder`,
`setGoalStep`, `setGSensorIndState`, `setHeartRateMode`, `setHourFormat`,
`setIdleTime`, `setLanguage`, `setNotify`,
`setOfflineSpeechRecognitionState`, `setPhoneMac`, `setPhontMode`,
`setPressureMode`, `setReminder`, `setReminderText`, `SetScreenLightTime`,
`setSleepTime`, `setSmsRspInfoContent`, `setSmsRspInfoCrc`,
`setSmsRspSendAck`, `setSpoMode`, `setSugarMode`, `setTemperatureMode`,
`setTouchMode`, `setUserInfo`, `setWifiHotSpotInfo`, `setWifiHotSpotInfoEx`,
`setWorshipInfo`, `startFactoryTestMode`.

### Raw command route — 6

`connectAiServerNotification`, `openAiAudioState`, `openAiState`, `queryAiState`,
`setAiCommandType`, `setAiExtraAction`.

### Local BLE or dynamic GATT behavior — 14

`closeConnection`, `connectBt`, `disconnectBt`, `getConnectedDevice`,
`getDeviceRssi`, `isAuthrize`, `isConnectBt`, `openSDKLog`, `scanDevice`,
`setOption`, `setScanMode`, `setUuid`, `unregisterCallback`,
`writeCharacteristic`.

`writeCharacteristic` is caller-directed dynamic GATT rather than a fixed packet.
The other rows have no standalone deterministic command layout.

### Cloud/cache, phone, local, and exceptional behavior — 13

| Route | Operations | Recovered behavior |
|---|---|---|
| cloud/cache | `getDialServerInfo` | cache then vendor network |
| cloud/cache | `registerCallback`, `registerCallback2` | install one shared callback slot; use cached SDK validation or initiate vendor validation |
| main then cloud | `getOtaInfo` | shared main preflight followed by application/network behavior |
| raw descriptor control | `openRawDataNotification` | raw notification/descriptor state control, not a fixed request packet |
| internal DFU | `startFileOta` | internal firmware subsystem |
| phone network/filesystem | `startFtpDownloadTask` | phone-managed FTP download |
| local filesystem/conversion | `saveFileToSystemAlbum`, `translateBmpToBin` | Android media-store/broadcast or bitmap conversion |
| constant no-op stubs | `connectFtp`, `getDeviceFileState`, `getWifiState`, `setDeviceFileState` | return without the named operation in this SDK build |

The route total is 79 + 6 + 14 + 3 + 1 + 1 + 1 + 2 + 4 + 1 = 112.

## Callback interface: exhaustive source partition

### Bluetooth opcode dispatcher — 86

`onDeviceTestCmd`, `onEditDeviceDialCustom`, `onGetAdvSensorOfflineData`,
`onGetAiAction`, `onGetAiCommandType`, `onGetAiState`, `onGetBandFunction`,
`onGetChatgptAction`, `onGetCurSportData`, `onGetDataByDay`,
`onGetDeviceAction`, `onGetDeviceBatery`, `onGetDeviceCode`, `onGetDeviceDial`,
`onGetDeviceDialCustom`, `onGetDeviceFileState`, `onGetDeviceInfo`,
`onGetDeviceState`, `onGetEcgHistory`, `onGetEcgHistoryData`,
`onGetEcgStartEnd`, `onGetEcgValue`, `onGetEqInfo2`, `onGetFactoryTestData`,
`onGetGSensorData`, `onGetMultipleSportData`,
`onGetOfflineSpeechRecognitionMode`, `onGetOxygenOfflineData`,
`onGetPhoneVolume`, `onGetRawData`, `onGetScreenLightTime`,
`onGetSenserData`, `onGetSportSteps`, `onGetTemperatureData`, `onGetTouchMode`,
`onGetWifiSsid`, `onGetWifiSsidCount`, `onGetWifiState`, `onGetWorshipInfo`,
`onGetWorshipTimesData`, `onNotifyAiConnectionMethod`, `onNotifyAppId`,
`onNotifyBindedInfo`, `onNotifyClassicBtInfo`, `onNotifyClassicBtName`,
`onNotifyContactCrc`, `onNotifyDeviceSystemStateInfo`,
`onNotifyDeviceWifiApState`, `onNotifyECardNeedUpdate`,
`onNotifySmsRspNeedUpdate`, `onNotifySmsRspSend`, `onReadCurrentSportData`,
`onReceiveSensorData`, `onReceiveSensorOxygenData`,
`onRecvDeviceVoiceCommandConfirm`, `onSendVibrationSignal`,
`onSensorStateChange`, `onSetAlarm`, `onSetAntiLost`,
`onSetBloodOxygenMode`, `onSetBloodPressureMode`, `onSetBPAdjust`,
`onSetDeviceCode`, `onSetDeviceDialState`, `onSetDeviceHeartRateArea`,
`onSetDeviceInfo`, `onSetDeviceMode`, `onSetDeviceName`, `onSetDeviceTime`,
`onSetDeviceWallpaperState`, `onSetEcgMode`, `onSetEqInfo2`,
`onSetFemaleReminder`, `onSetGoalStep`, `onSetHourFormat`, `onSetIdleTime`,
`onSetLanguage`, `onSetNotify`, `onSetPhontMode`, `onSetReminder`,
`onSetReminderText`, `onSetSleepTime`, `onSetTemperatureMode`, `onSetUserInfo`,
`onTemperatureModeChange`, `setAutoHeartMode`.

### Android, network, OTA, or transport origin — 14

`onAuthDeviceResult`, `onAuthSdkResult`, `onCharacteristicChanged`,
`onCharacteristicWrite`, `onConnectStateChanged`, `onDeviceConnectedWifi`,
`onGetDeviceRssi`, `onGetOtaInfo`, `onGetOtaUpdate`,
`onNotifyDialJsonContent`, `onNotifyFtpStateInfo`, `onNotifyNewMediaInfo`,
`onOpenRawDataNotificationState`, `onScanCallback`.

### APK-local projections — 3

`onGetAdvSensorOfflineDataEnd`, `onGetDataByDayEnd`, and
`onGetOxygenOfflineDataEnd` are timer/parser-local end projections. They are not wire
frames and do not prove peripheral acknowledgement or whole-operation completion.

### Declared without direct invocation — 2

`onGetDeviceTime` and `onSendWeather` have no direct invocation site in the reviewed
SDK build. This is a static-build fact, not proof that all variants or dynamic paths
are silent.

The callback total is 86 + 14 + 3 + 2 = 105.

## Static app-use and dispatch reachability

The 112 request declarations partition into 51 directly invoked targets with 152
observed invoke instructions, 43 SDK wire entries without a direct app invoke, 14
local/composite entries without a direct app invoke, and four constant no-op stubs.
The inclusive link inventory contains 130 unique request edges from 86 caller methods
in 48 classes to those 51 targets. These caller/link counts use a different counting
basis from the 80 exclusively classified request-call-site methods in 47 classes and
must not be substituted for one another.

The 105 callbacks partition into 103 with a direct invoke and two without one. Static
accounting finds 181 invokes and 126 unique edges from 34 caller methods in 17 classes.
Primary, raw, and outside-dispatcher target counts overlap: 85 targets/125 invokes,
five targets/six invokes, and 17 targets/50 invokes respectively. A direct invoke is
activation evidence, not runtime reachability or proof that an app screen consumes or
renders the callback.

## Dispatcher behavior

The primary response dispatcher has 104 distinct case-folded opcode targets. Static
instruction accounting finds 125 syntactic callback invokes, 124 reachable invokes,
85 unique callback targets, and five recognized opcodes with no direct callback.
Opcode identity is not a one-to-one capability identifier: opcodes are shared by
selectors, success/failure branches, settings, event streams, and reverse-direction
phone actions.

The raw response path supplies six direct invokes across five callback targets. The
remaining 50 callback invokes across 17 targets occur outside the primary/raw
dispatchers.

## Functional domains

| Domain | APK behavior represented by the interfaces |
|---|---|
| discovery and connection | scan configuration, LE discovery, selected-device connect/disconnect, connection state, dynamic UUID setup, GATT lifecycle |
| authorization and policy | SDK validation, device authorization result, cloud gear policy, explicit application binding, cached status |
| device information | battery, device identity/code/revisions, function flags, time, name, mode, state, screen light, touch, system state |
| activity and history | current sport, cumulative steps, generic day history, multiple sport, advanced sensor offline, oxygen offline |
| live sensing | heart rate, blood pressure, blood oxygen, temperature, ECG, generic sensor, G-sensor, raw sensor channels |
| personal settings | user profile, goal, idle/sleep windows, alarms, reminders, language, hour format, female reminder, anti-lost, vibration |
| phone integration | phone calls, host volume, notifications, weather, contacts, application ID, phone identifier, message responses, cards |
| device presentation | dials, custom dial editing, wallpaper state, bitmap conversion, device name, EQ |
| network and media | Wi-Fi credentials/AP mode/scan/state/SSID events, phone FTP, device file/media state, new-media callbacks |
| AI and speech | ChatGPT content/action, AI connection/language/state/action/command/audio, offline speech recognition, voice confirmation |
| religious schedule | worship settings and time callbacks |
| diagnostics and factory | SDK logging, factory test mode/data, generic device test command, arbitrary characteristic access |
| firmware and transfer | OTA info, file OTA, SUOTA phases, dial/media/file transfer, progress/error callbacks |

Each domain remains a grouping convenience. Its individual interface entries and
branches retain their own request, callback, failure, and terminal semantics.

## Request/callback relationship rules

All 85 deterministic request rows have a topology classification. The terminal-rule
partition is:

| Rule | Count |
|---|---:|
| one matched response | 36 |
| no proven terminal | 29 |
| per-frame only | 17 |
| local quiet, completion unknown | 2 |
| metadata or explicit marker, otherwise local quiet unknown | 1 |

Fifty-eight rows retain at least one explicit caveat. A shared opcode, nearby callback,
equal-looking value, local timeout, callback silence, callback method name, queue drain,
or returned Android write call does not by itself establish causality,
acknowledgement, successful application, or terminal completion.

Special topology classes that remain non-causal include:

- contact fingerprint and contact-content reverse synchronization;
- E-card and message-response CRC/content update streams;
- inbound SMS-send plus outbound acknowledgement candidate;
- App-ID setter plus cross-opcode App-ID event;
- outbound phone identifier versus inbound host-volume request on shared opcode `49`;
- Wi-Fi credential fragments versus the disjoint Wi-Fi state event;
- device weather refresh versus cached/application weather behavior;
- motion setting versus shared motion callback stream;
- ChatGPT action/content shared families; and
- media/FTP local completion-shaped projections shared by success and failure paths.

## Connection, queue, and failure semantics

Recovered startup ordering exposes SDK connected state after notification setup is
submitted but before descriptor acknowledgement. Device-cloud policy starts after that
exposure. A descriptor callback schedules an implicit device-time write. Therefore the
following facts are distinct:

- Android link connected;
- services discovered;
- characteristic targets resolved;
- notification activation requested;
- descriptor callback received;
- command accepted into the SDK queue;
- characteristic write invoked;
- Android write callback observed;
- application callback matched; and
- device or operation terminal established.

The SDK’s mutable status gates, global queue, pending payload, timeout state, and write
callback behavior are shared rather than operation-token-bound. A callback can arrive
without proving ownership by the most recent request. A write callback status is
ignored in reviewed source, and an accepted dispatch can end with an unknown outcome.
Automatic retry safety is therefore unknown.

## Android platform and non-Bluetooth behavior

Callback registration stores one shared service callback. The no-credential form uses
bundled SDK configuration; the credential-taking form uses caller values. Fresh cached
SDK validation reports cached status, while stale validation can initiate a vendor
network request. Registration does not establish device policy, binding, ownership, or
Bluetooth readiness.

`getDialServerInfo` uses application cache/vendor network behavior.
`startFtpDownloadTask` is a phone-network and filesystem operation.
`saveFileToSystemAlbum` uses Android media/filesystem behavior and a broadcast.
`translateBmpToBin` performs local image/file conversion. These are part of the APK
surface but are not ring GATT commands.

The package contains resource labels related to Bluetooth and device functions, but
733 matching named entries in 24 of 1,107 decoded base XML files are not treated as
capabilities. Component and app-visible resource roles are bounded in
[APK_UI_SPEC.md](APK_UI_SPEC.md); locale resources are not counted as capabilities at
this stage, while semantic activation/configuration in unreviewed resource content
remains unknown. One SDK configuration asset contains credential-bearing
configuration; no credential material belongs in this specification.

The ten platform-operation rows, 14 local/dynamic-GATT request rows, and 16 non-opcode
callback rows are exact interface-surface denominators. The three OTA/transfer rows are
exactly the `vendor_ota_evidence` population, not every transfer path. The separate
whole-app component and data/platform appendices account for
the app database, preference, account, background-work, cloud, camera, contact,
notification, file, media, and UI domains without conflating them with Binder rows.

## UI and app integration

The manifest’s 79 activities partition into 65 app-owned functions and 14 dependency
surfaces. Eleven concrete fragment classes partition into four main-pager tabs, six
initial profile pages, and one aggregate-data fragment with no established activation.
All three app-owned services, the application class, dependency
activities/services/providers/receivers, navigation domains, local data domains,
network purposes, phone integrations, and background roles are accounted in
[APK_UI_SPEC.md](APK_UI_SPEC.md) and
[APK_DATA_PLATFORM_SPEC.md](APK_DATA_PLATFORM_SPEC.md).

This is a functionality partition, not a claim that every page is reachable or renders
correctly for every account, locale, permission state, API level, ring, firmware, or
server state. Runtime presentation, accessibility behavior, and external service
success remain explicit variability dimensions.

## Dynamic receivers and reflection

The primary Bluetooth action registration names seven unique Android actions, handles
four, and leaves three registered profile actions without an observed receiver case.
The system-context receiver names 12 actions, including two BLE-related app actions;
it has no observed sender permission, is exported on the current API, and has no
matching unregister path in the same registration domain. Sixteen other filter files
are process-local and do not receive Android system broadcasts without an explicit
bridge; no such bridge was observed.

Eleven reflective invokes in ten methods resolve to constant Android helper targets:
bond hidden APIs, telephony hidden APIs, classic-profile hidden APIs, and GATT cache
refresh. No reviewed reflection edge activates standalone dial transfer. Reflection
review is bounded to the five observed files; runtime-generated or encrypted targets
are not excluded.

## Native behavior

The arm64 split contains one packaged native library. All three packaged JNI exports
match application native declarations and their rooted transitive call graph is
classified as image/wallpaper processing. No rooted Bluetooth transport or dial
transfer edge was observed. Seven of ten native declarations remain unresolved,
including six SDK declarations. Whole-library instruction review and external/runtime
SDK binding are incomplete, so native Bluetooth absence is not established.

## Firmware, OTA, file, and dial transfer

Ordinary device queries, application/network OTA metadata, file OTA, and executable
SUOTA are distinct paths. The SUOTA service has six required transfer/status roles and
four optional metadata roles. The reviewed flow includes preparation, service/role
resolution, memory/device selection, block transfer, status observation, finalize, and
disconnect/reboot-shaped phases. Failure surfaces include GATT errors, missing roles,
notification/descriptor failure, block/chunk failure, timeout, disconnect, network
metadata errors, file errors, and callback gaps.

Firmware writes, address/memory selection, finalize/reboot behavior, retry safety,
firmware/model coverage, and error-code meanings are not completely established.
Dial-transfer activation is also inconclusive: static construction edges are absent,
but reflection, resources, Binder, native, dependency, and runtime-generated activation
are not exhaustively disproved.

## Completion accounting and bounded unknowns

The clean-room static specification is closed at its declared population and domain
boundaries:

- all 217 Binder signatures, 112 request rows, and 105 callback rows reconcile;
- all 85 deterministic request codecs, 86 opcode-originated decoders, 85 topology
  rows, request routes, callback origins, and terminal-rule classes are represented;
- ordinary/raw/SUOTA UUID roles, scan/connect/discovery/notification/queue behavior,
  33 session transitions, six binding reactions, and 22 races are published;
- all 62 warnings in 21 SDK files are classified, and warning-sensitive dispatcher,
  SUOTA, FTP, MediaStore, and digest control flow is instruction-resolved;
- all 23 warning-bearing app files/161 markers are dispositioned, with seven material
  and two lower-impact branch contracts explicitly marked unknown;
- all manifest components, permissions, features, app activities/services, concrete
  fragments, dependency components, explicit Intent constructions, closed action
  subsets, SQLite tables, network-purpose groups, phone integrations, and transfer
  domains are accounted; and
- resources, reflection, native declarations, dynamic receivers, activation-unknown
  classes, runtime-permission/API branches, and hardware/firmware variability are
  bounded rather than silently omitted.

“Complete” here means every known static function surface is represented or explicitly
bounded. It does not mean every one of 5,335 owned method bodies was instruction-reviewed,
that every UI path is reachable, that dependency/native/runtime-generated behavior is
absent, or that a ring accepts any operation. The seven unresolved native declarations,
unreviewed resource/locale activation, nine warning-sensitive app edge contracts,
otherwise-unknown `78` selector meanings, firmware/model matrix, peripheral delivery,
and external server outcomes remain `unknown` by specification. Those unknowns do not
authorize guessing in the client.

## Authoritative clean-room ledgers

The row-level evidence currently resides in these public, sanitized ledgers:

- `jring._vendor_binder_rows`: exact request and callback Binder declarations;
- `jring.vendor_coverage`: complete request/callback interface partition;
- `jring.vendor_app_use_evidence`: app invoke and callback-dispatch counts;
- `jring.vendor_request_routing`: packet shapes, queue roles, and exceptional routes;
- `jring.vendor_request_builder_evidence`: 37 instruction-reviewed builders;
- `jring.vendor_dispatcher_evidence`: opcode branch and callback dispatch accounting;
- `jring.vendor_request_callback_correlation`: all 85 deterministic topologies;
- `jring.vendor_session_evidence`: transitions, binding reactions, and races;
- `jring.vendor_platform_surface`: non-Bluetooth/platform behaviors;
- `jring.vendor_ota_evidence`: firmware and transfer behavior;
- `jring.vendor_artifact_evidence`: manifest, method, Android API, receiver, resource,
  reflection, native, and DEX-scope accounting; and
- `jring.vendor_warning_evidence` / `jring.vendor_decompilation_evidence`: source
  recovery limits and bounded instruction findings.

The exact Binder signatures, request crosswalk, and dispatcher/callback topology are
published in [APK_BINDER_SPEC.md](APK_BINDER_SPEC.md),
[APK_REQUEST_SPEC.md](APK_REQUEST_SPEC.md), and
[APK_CALLBACK_SPEC.md](APK_CALLBACK_SPEC.md). Bluetooth routes and Android transport
references are in [APK_TRANSPORT_SPEC.md](APK_TRANSPORT_SPEC.md); recovered session,
binding, queue, and race behavior is in [APK_SESSION_SPEC.md](APK_SESSION_SPEC.md).
Android-local, platform, manifest, receiver, reflection, resource, and native accounting
is in [APK_PLATFORM_SPEC.md](APK_PLATFORM_SPEC.md). The closed component/named-class
partition and bounded UI/data/cloud/phone domains are in [APK_UI_SPEC.md](APK_UI_SPEC.md) and
[APK_DATA_PLATFORM_SPEC.md](APK_DATA_PLATFORM_SPEC.md); firmware workflows are in
[APK_OTA_SPEC.md](APK_OTA_SPEC.md).

These ledgers are evidence inputs to the specification. Python codec or simulator
availability is not APK behavior and is intentionally non-normative here.
