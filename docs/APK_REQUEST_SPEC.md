# Clean-room APK request crosswalk

Status: complete static request crosswalk; packet-field and side-effect semantics remain
to be expanded where marked by unresolved evidence.

This appendix joins all 112 request declarations to their route, static app-use state,
packet shape/queue, request-callback relationship, terminal rule, callback set, and
count of explicitly recorded row-specific uncertainties. `—` means the operation does
not belong to the 85-row deterministic request/callback topology ledger; it does not
mean that its behavior is understood or absent.

App-use abbreviations are `direct:count` for a direct application invoke,
`wire:0` for an SDK wire entry without an app invoke, `local:0` for an SDK
local/composite entry without an app invoke, and `stub:0` for an uninvoked constant
no-op stub. Queue `0` is MAIN; queue `1` is raw.

`exact` in Relationship means exact static request/response topology eligibility, not
an acknowledged transaction. `Gaps` counts row-specific caveats only. Every row
inherits the shared queue/latch, absent wire transaction identity, ignored Android
write status, connection-generation, and runtime timing limitations below.

| Tx | Request | Route | App use | Packet/queue | Relationship | Terminal | Callback(s) | Gaps |
|---:|---|---|---|---|---|---|---|---:|
| 1 | `registerCallback` | cloud/cache | direct:1 | none/— | — | — | — | — |
| 2 | `registerCallback2` | cloud/cache | local:0 | none/— | — | — | — | — |
| 3 | `unregisterCallback` | local BLE/dynamic GATT | direct:1 | none/— | — | — | — | — |
| 4 | `isAuthrize` | local BLE/dynamic GATT | local:0 | none/— | — | — | — | — |
| 5 | `setOption` | local BLE/dynamic GATT | direct:11 | none/— | — | — | — | — |
| 6 | `setScanMode` | local BLE/dynamic GATT | local:0 | none/— | — | — | — | — |
| 7 | `scanDevice` | local BLE/dynamic GATT | direct:1 | none/— | — | — | — | — |
| 8 | `connectBt` | local BLE/dynamic GATT | direct:4 | none/— | — | — | — | — |
| 9 | `isConnectBt` | local BLE/dynamic GATT | direct:16 | none/— | — | — | — | — |
| 10 | `getConnectedDevice` | local BLE/dynamic GATT | local:0 | none/— | — | — | — | — |
| 11 | `disconnectBt` | local BLE/dynamic GATT | direct:3 | none/— | — | — | — | — |
| 12 | `closeConnection` | local BLE/dynamic GATT | local:0 | none/— | — | — | — | — |
| 13 | `setDeviceTime` | MAIN | direct:3 | deterministic/0 | exact | single response | `onSetDeviceTime` | 0 |
| 14 | `setUserInfo` | MAIN | direct:1 | deterministic/0 | exact | single response | `onSetUserInfo` | 0 |
| 15 | `getCurSportData` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetCurSportData` | 0 |
| 16 | `sendVibrationSignal` | MAIN | direct:2 | deterministic/0 | exact | single response | `onSendVibrationSignal` | 0 |
| 17 | `setPhontMode` | MAIN | direct:2 | deterministic/0 | exact | single response | `onSetPhontMode` | 0 |
| 18 | `setIdleTime` | MAIN | direct:4 | deterministic/0 | exact | single response | `onSetIdleTime` | 0 |
| 19 | `setSleepTime` | MAIN | direct:1 | deterministic/0 | exact | single response | `onSetSleepTime` | 0 |
| 20 | `getDeviceBatery` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetDeviceBatery` | 0 |
| 21 | `getDeviceInfo` | MAIN | direct:1 | deterministic/0 | exact | single response | `onGetDeviceInfo` | 0 |
| 22 | `setAlarm` | MAIN | direct:4 | deterministic/0 | exact | per frame | `onSetAlarm` | 1 |
| 23 | `setDeviceMode` | MAIN | direct:7 | deterministic/0 | exact | single response | `onSetDeviceMode` | 0 |
| 24 | `setNotify` | MAIN | direct:2 | deterministic/0 | shared stateful | per frame | `onSetNotify` | 1 |
| 25 | `setHeartRateMode` | MAIN | direct:3 | deterministic/0 | exact branching | single response | `onGetSenserData` | 0 |
| 26 | `setAutoHeartMode` | MAIN | direct:2 | deterministic/0 | exact | single response | callback `setAutoHeartMode` | 0 |
| 27 | `setDeviceInfo` | MAIN | direct:6 | deterministic/0 | exact | single response | `onSetDeviceInfo` | 0 |
| 28 | `setHourFormat` | MAIN | direct:8 | deterministic/0 | exact | single response | `onSetHourFormat` | 0 |
| 29 | `getDataByDay` | MAIN | direct:7 | deterministic/0 | shared stream | marker/metadata or quiet unknown | `onGetDataByDay`, `onGetDataByDayEnd`, `onGetOxygenOfflineData` | 1 |
| 30 | `setLanguage` | MAIN | wire:0 | deterministic/0 | exact | single response | `onSetLanguage` | 0 |
| 31 | `sendWeather` | MAIN | direct:1 | deterministic/0 | reverse candidate | none proven | `onGetDeviceAction` | 4 |
| 32 | `setAntiLost` | MAIN | direct:2 | deterministic/0 | exact | single response | `onSetAntiLost` | 0 |
| 33 | `setBloodPressureMode` | MAIN | direct:4 | deterministic/0 | shared stateful | per frame | `onSetBloodPressureMode` | 2 |
| 34 | `getMultipleSportData` | MAIN | direct:4 | deterministic/0 | shared stream | none proven | `onSetBloodPressureMode`, `onGetMultipleSportData` | 2 |
| 35 | `setGoalStep` | MAIN | direct:2 | deterministic/0 | exact | single response | `onSetGoalStep` | 0 |
| 36 | `getBandFunction` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetBandFunction` | 0 |
| 37 | `setDeviceHeartRateArea` | MAIN | wire:0 | deterministic/0 | exact | single response | `onSetDeviceHeartRateArea` | 0 |
| 38 | `openSDKLog` | local BLE/dynamic GATT | direct:1 | none/— | — | — | — | — |
| 39 | `getOtaInfo` | MAIN then cloud | direct:1 | shared preflight/0 | — | — | — | — |
| 40 | `setDeviceCode` | MAIN | direct:1 | deterministic/0 | exact | single response | `onSetDeviceCode` | 0 |
| 41 | `getDeviceCode` | MAIN | direct:2 | deterministic/0 | exact | single response | `onGetDeviceCode` | 0 |
| 42 | `setUuid` | local BLE/dynamic GATT | local:0 | none/— | — | — | — | — |
| 43 | `writeCharacteristic` | local BLE/dynamic GATT | local:0 | caller-directed/— | — | — | — | — |
| 44 | `setEcgMode` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onSetEcgMode` | 1 |
| 45 | `getEcgHistory` | MAIN | direct:1 | deterministic/0 | shared stream | none proven | `onGetEcgHistory`, `onGetEcgStartEnd`, `onGetEcgHistoryData` | 1 |
| 46 | `setDeviceName` | MAIN | wire:0 | deterministic/0 | exact | single response | `onSetDeviceName` | 1 |
| 47 | `getDeviceRssi` | local BLE/dynamic GATT | local:0 | none/— | — | — | — | — |
| 48 | `setReminder` | MAIN | direct:8 | deterministic/0 | exact | single response | `onSetReminder` | 1 |
| 49 | `setReminderText` | MAIN | wire:0 | deterministic/0 | exact | single response | `onSetReminderText` | 1 |
| 50 | `setBPAdjust` | MAIN | direct:1 | deterministic/0 | exact | single response | `onSetBPAdjust` | 1 |
| 51 | `setTemperatureMode` | MAIN | direct:2 | deterministic/0 | exact | per frame | `onSetTemperatureMode` | 1 |
| 52 | `getDeviceDial` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetDeviceDial` | 0 |
| 53 | `setDeviceDialState` | MAIN | wire:0 | deterministic/0 | exact | single response | `onSetDeviceDialState` | 1 |
| 54 | `setDeviceWallpaperState` | MAIN | wire:0 | deterministic/0 | exact | single response | `onSetDeviceWallpaperState` | 1 |
| 55 | `editDeviceDialCustom` | MAIN | wire:0 | deterministic/0 | exact | single response | `onEditDeviceDialCustom` | 1 |
| 56 | `getDeviceDialCustom` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetDeviceDialCustom` | 0 |
| 57 | `sendPhoneCallState` | MAIN | direct:1 | deterministic/0 | no eligible callback | none proven | — | 4 |
| 58 | `setFemaleReminder` | MAIN | direct:1 | deterministic/0 | exact | single response | `onSetFemaleReminder` | 1 |
| 59 | `setContactCrc` | MAIN | direct:3 | deterministic/0 | same-opcode candidate | none proven | `onNotifyContactCrc` | 1 |
| 60 | `setContactInfo` | MAIN | direct:3 | deterministic/0 | reverse candidate | none proven | `onNotifyContactCrc` | 6 |
| 61 | `setAppId` | MAIN | direct:5 | deterministic/0 | event candidate | none proven | `onNotifyAppId` | 5 |
| 62 | `setPhoneMac` | MAIN | wire:0 | deterministic/0 | opcode collision/no correlation | none proven | — | 3 |
| 63 | `sendPhoneVolume` | MAIN | direct:2 | deterministic/0 | reverse pipeline | none proven | `onGetPhoneVolume` | 1 |
| 64 | `setBindedInfo` | MAIN | direct:3 | deterministic/0 | exact | per frame | `onNotifyBindedInfo` | 1 |
| 65 | `setECardInfoCrc` | MAIN | direct:1 | deterministic/0 | reverse candidate | none proven | `onNotifyECardNeedUpdate` | 5 |
| 66 | `setECardInfoContent` | MAIN | direct:1 | deterministic/0 | reverse candidate | none proven | `onNotifyECardNeedUpdate` | 5 |
| 67 | `setSmsRspInfoCrc` | MAIN | direct:1 | deterministic/0 | reverse candidate | none proven | `onNotifySmsRspNeedUpdate` | 6 |
| 68 | `setSmsRspInfoContent` | MAIN | direct:1 | deterministic/0 | reverse candidate | none proven | `onNotifySmsRspNeedUpdate` | 6 |
| 69 | `setSmsRspSendAck` | MAIN | wire:0 | deterministic/0 | reverse ACK candidate | none proven | `onNotifySmsRspSend` | 4 |
| 70 | `startFileOta` | DFU | local:0 | internal DFU/— | — | — | — | — |
| 71 | `translateBmpToBin` | local filesystem/conversion | local:0 | none/— | — | — | — | — |
| 72 | `setChatgptContent` | MAIN | wire:0 | deterministic/0 | reverse candidate | none proven | `onGetChatgptAction` | 4 |
| 73 | `startFactoryTestMode` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onGetFactoryTestData` | 1 |
| 74 | `getDialServerInfo` | cloud/cache | local:0 | none/— | — | — | — | — |
| 75 | `setBloodOxygenMode` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onSetBloodOxygenMode` | 1 |
| 76 | `getEqInfo` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetEqInfo2` | 0 |
| 77 | `setEqInfo2` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onSetEqInfo2` | 1 |
| 78 | `setWifiHotSpotInfo` | MAIN | wire:0 | deterministic/0 | shared event candidate | none proven | `onGetWifiState` | 6 |
| 79 | `setWifiHotSpotInfoEx` | MAIN | wire:0 | deterministic/0 | shared event candidate | none proven | `onGetWifiState` | 7 |
| 80 | `getWifiState` | no-op stub | stub:0 | none/— | — | — | — | — |
| 81 | `scanWifi` | MAIN | wire:0 | deterministic/0 | shared stream | none proven | `onGetWifiSsidCount`, `onGetWifiSsid` | 1 |
| 82 | `connectFtp` | no-op stub | stub:0 | none/— | — | — | — | — |
| 83 | `getDeviceFileState` | no-op stub | stub:0 | none/— | — | — | — | — |
| 84 | `setDeviceFileState` | no-op stub | stub:0 | none/— | — | — | — | — |
| 85 | `getMediaFileState` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetDeviceFileState` | 0 |
| 86 | `notifyDownloadFtpFileCompleted` | MAIN | wire:0 | deterministic/0 | event candidate | none proven | `onNotifyFtpStateInfo` | 4 |
| 87 | `setAILang` | MAIN | wire:0 | deterministic/0 | no eligible callback | none proven | — | 5 |
| 88 | `getDeviceSystemStateInfo` | MAIN | wire:0 | deterministic/0 | exact | single response | `onNotifyDeviceSystemStateInfo` | 0 |
| 89 | `setAiChatState` | MAIN | wire:0 | deterministic/0 | event candidate | none proven | `onGetChatgptAction` | 4 |
| 90 | `setGSensorIndState` | MAIN | wire:0 | deterministic/0 | shared event candidate | none proven | `onGetGSensorData` | 4 |
| 91 | `setOfflineSpeechRecognitionState` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onGetOfflineSpeechRecognitionMode` | 1 |
| 92 | `openWifiApMode` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onNotifyDeviceWifiApState` | 1 |
| 93 | `setAppState` | MAIN | direct:4 | deterministic/0 | no eligible callback | none proven | — | 4 |
| 94 | `setWorshipInfo` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onGetWorshipInfo` | 1 |
| 95 | `setTouchMode` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onGetTouchMode` | 1 |
| 96 | `setAiConnectionMethod` | MAIN | wire:0 | deterministic/0 | exact | per frame | `onNotifyAiConnectionMethod` | 1 |
| 97 | `getOxygenOfflineData` | MAIN | wire:0 | deterministic/0 | shared stream | local quiet unknown | `onGetDataByDay`, `onGetOxygenOfflineData`, `onGetOxygenOfflineDataEnd` | 2 |
| 98 | `getAdvSensorOfflineData` | MAIN | direct:3 | deterministic/0 | shared stream | local quiet unknown | `onGetDataByDay`, `onGetAdvSensorOfflineData`, `onGetAdvSensorOfflineDataEnd` | 2 |
| 99 | `openRawDataNotification` | raw descriptor control | local:0 | descriptor/— | — | — | — | — |
| 100 | `connectAiServerNotification` | raw | wire:0 | deterministic/1 | event candidate | none proven | `onGetAiAction` | 1 |
| 101 | `setAiExtraAction` | raw | wire:0 | deterministic/1 | event candidate | none proven | — | 1 |
| 102 | `openAiState` | raw | wire:0 | deterministic/1 | event candidate | none proven | `onGetAiState` | 1 |
| 103 | `queryAiState` | raw | wire:0 | deterministic/1 | event candidate | none proven | `onGetAiState` | 1 |
| 104 | `saveFileToSystemAlbum` | local filesystem/conversion | local:0 | none/— | — | — | — | — |
| 105 | `openAiAudioState` | raw | wire:0 | deterministic/1 | event candidate | none proven | `onGetRawData` | 1 |
| 106 | `startFtpDownloadTask` | local phone network | local:0 | none/— | — | — | — | — |
| 107 | `SetScreenLightTime` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetScreenLightTime` | 0 |
| 108 | `setAiCommandType` | raw | wire:0 | deterministic/1 | event candidate | none proven | `onGetAiCommandType` | 1 |
| 109 | `queryOfflineSpeechRecognitionState` | MAIN | wire:0 | deterministic/0 | exact | single response | `onGetOfflineSpeechRecognitionMode` | 1 |
| 110 | `setSpoMode` | MAIN | direct:1 | deterministic/0 | shared stateful | per frame | `onSetBloodPressureMode` | 2 |
| 111 | `setSugarMode` | MAIN | direct:1 | deterministic/0 | shared stateful | per frame | `onSetBloodPressureMode` | 2 |
| 112 | `setPressureMode` | MAIN | direct:1 | deterministic/0 | shared stateful | per frame | `onSetBloodPressureMode` | 2 |

## Cross-cutting request semantics

These rules are normative for each applicable row above; a row's status-shaped return
must not be reinterpreted as transport or device success.

- The common packet policy gate permits construction when internal mode is zero or
  shared SDK status is 200. Type-0 and type-1 enqueue silently drops while disconnected,
  while the public call still normally returns shared status.
- Integer inputs are normally reduced to Java's low byte or low word. Text builders
  often use the platform-default charset and byte-truncate, including through a
  multibyte character. No general domain/range validation layer exists.
- MAIN frames append at queue tail except sensor-session commands, which insert at the
  front. Enqueuing a state opcode removes older queued frames with that opcode. Silence
  mode blocks one opcode and history mode blocks a fixed opcode family.
- A synchronous Android write rejection is retried up to 31 calls with blocking 300 ms
  gaps. An accepted write waits on one global latch for five seconds, or ten in sync
  mode. Neither the latch nor retries are request/connection-generation-bound; Android
  callback status is ignored.
- Builder/batch methods enqueue sequentially and can partially mutate the queue before
  a later construction exception. Full command content can be logged before enqueue.
- `setDeviceDialState` clears the ordinary queue and retained current frame first.
  `getOtaInfo` changes pending/automatic flags before querying Device Information.
  `startFileOta` clears the queue and requests device mode before validating/opening
  the caller path.
- `setOption` snapshots nested device/user values but retains caller timer/weather
  collections. `setScanMode`, `setUuid`, and callback registration retain/mutate global
  state without defensive copies. `unregisterCallback` ignores the passed identity and
  clears the sole global callback.
- `openSDKLog` mutates global logging/path fields and always returns 1. The four no-op
  stubs return zero without transport. RSSI, dynamic write, notification, scan, and
  connect returns do not prove that the corresponding Android operation was accepted.

Applicable structured/batch builders have additional exact constraints:

- Wi-Fi credentials use 17-byte fragments with an end bit and no transaction identity.
- Alarm text uses at most three continuation frames per alarm; alarm batching is
  non-atomic.
- Contact, E-card, and message lists use distinct count caps, CRC aggregation, item
  framing, and truncation; CRC/content calls may partially enqueue. Empty strings can
  produce no content frames after a total/count frame was already sent.
- Call, volume, app state, sensor state, worship, screen, touch, and AI values are raw
  low-byte casts with little or no validation.
- All six raw-AI builders use queue 1 but retain the same connection, policy, return,
  retry, and shared-latch caveats as MAIN.

## Reconciliation

The request-route partition is 79 MAIN + 6 raw + 14 local BLE/dynamic GATT + 3
cloud/cache + 2 local filesystem/conversion + 1 MAIN-then-cloud + 1 descriptor control
+ 1 phone network + 1 DFU + 4 no-op stubs = 112.

The app-use partition is 51 direct targets/152 invokes + 43 uninvoked SDK wire entries
+ 14 uninvoked local/composite entries + 4 no-op stubs = 112.

The deterministic topology partition is 85 rows. Terminal rules reconcile as 36
single-response + 17 per-frame + 29 no-proven-terminal + 2 local-quiet-unknown + 1
metadata/marker-or-quiet-unknown. Fifty-eight rows have one or more explicit caveats.

## Precision boundary

The table plus cross-cutting rules account for all 112 public requests and distinguish
deterministic packet construction from local, cloud, filesystem, phone-network, DFU,
descriptor, dynamic-GATT, and no-op behavior. Exact byte layouts already represented
by the sanitized 85-codec ledger remain authoritative. Names or integers whose domain,
unit, enum, peripheral effect, or firmware range is not established are `unknown`;
they are not inferred from method names. Runtime acceptance and hardware behavior are
also unknown until owner-authorized observation.
