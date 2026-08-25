# Clean-room APK Binder interface specification

Status: declaration-exact appendix to `APK_FUNCTIONAL_SPEC.md`.

All 217 transactions are synchronous. Declared parameter order and recovered Parcel
read/write order agree for every row; no order mismatch is present. Request and
callback transaction numbers belong to separate Binder interfaces and therefore each
start at 1. `—` means no parameters. Type names are clean-room structural names, not
vendor class definitions.

This appendix specifies interface shape only. It does not establish runtime
reachability, payload meaning, Bluetooth routing, acknowledgement, or side effects.

Request declaration/Proxy/Stub/implementation counts each equal 112; callback counts
each equal 105. The request interface has 36 distinct semantic signatures and 28
distinct Parcel shapes; the callback interface has 33 and 31. Request results are 102
`int32`, six `void`, two `string`, and two `bool`; booleans marshal as `int32`, giving
104 integer Parcel results. Callback results are 103 `void` and two `int32`. No
explicit trailing-Parcel-data rejection is evidenced, and an exhaustive semantic-alias
partition is not established.

## Request interface — 112 transactions

| Tx | Method | Parameters | Result |
|---:|---|---|---|
| 1 | `registerCallback` | `callback_handle` | `void` |
| 2 | `registerCallback2` | `callback_handle, string, string, string` | `void` |
| 3 | `unregisterCallback` | `callback_handle` | `void` |
| 4 | `isAuthrize` | — | `int32` |
| 5 | `setOption` | `client_options_record` | `int32` |
| 6 | `setScanMode` | `int32` | `int32` |
| 7 | `scanDevice` | `bool` | `int32` |
| 8 | `connectBt` | `string, string` | `int32` |
| 9 | `isConnectBt` | — | `bool` |
| 10 | `getConnectedDevice` | — | `string` |
| 11 | `disconnectBt` | `bool` | `void` |
| 12 | `closeConnection` | — | `void` |
| 13 | `setDeviceTime` | — | `int32` |
| 14 | `setUserInfo` | — | `int32` |
| 15 | `getCurSportData` | — | `int32` |
| 16 | `sendVibrationSignal` | `int32` | `int32` |
| 17 | `setPhontMode` | `bool` | `int32` |
| 18 | `setIdleTime` | `int32, int32, int32, int32, int32` | `int32` |
| 19 | `setSleepTime` | `int32, int32, int32, int32, int32, int32, int32, int32` | `int32` |
| 20 | `getDeviceBatery` | — | `int32` |
| 21 | `getDeviceInfo` | — | `int32` |
| 22 | `setAlarm` | — | `int32` |
| 23 | `setDeviceMode` | `int32` | `int32` |
| 24 | `setNotify` | `string, int32, string, string` | `bool` |
| 25 | `setHeartRateMode` | `bool, int32, int32` | `int32` |
| 26 | `setAutoHeartMode` | `bool, int32, int32, int32, int32, int32, int32` | `int32` |
| 27 | `setDeviceInfo` | — | `int32` |
| 28 | `setHourFormat` | `int32` | `int32` |
| 29 | `getDataByDay` | `int32, int32` | `int32` |
| 30 | `setLanguage` | — | `int32` |
| 31 | `sendWeather` | — | `int32` |
| 32 | `setAntiLost` | `bool` | `int32` |
| 33 | `setBloodPressureMode` | `bool` | `int32` |
| 34 | `getMultipleSportData` | `int32` | `int32` |
| 35 | `setGoalStep` | `int32` | `int32` |
| 36 | `getBandFunction` | — | `int32` |
| 37 | `setDeviceHeartRateArea` | `bool, int32, int32` | `int32` |
| 38 | `openSDKLog` | `bool, string, string` | `int32` |
| 39 | `getOtaInfo` | `bool` | `int32` |
| 40 | `setDeviceCode` | `bytes` | `int32` |
| 41 | `getDeviceCode` | — | `int32` |
| 42 | `setUuid` | `string_array, string_array, bool` | `int32` |
| 43 | `writeCharacteristic` | `string, bytes` | `int32` |
| 44 | `setEcgMode` | `bool, int32` | `int32` |
| 45 | `getEcgHistory` | `int32` | `int32` |
| 46 | `setDeviceName` | `string` | `int32` |
| 47 | `getDeviceRssi` | — | `int32` |
| 48 | `setReminder` | `int32, int32, int32, int32, int32, int32, int32` | `int32` |
| 49 | `setReminderText` | `int32, string` | `int32` |
| 50 | `setBPAdjust` | `int32, int32` | `int32` |
| 51 | `setTemperatureMode` | `bool` | `int32` |
| 52 | `getDeviceDial` | — | `int32` |
| 53 | `setDeviceDialState` | `int32` | `int32` |
| 54 | `setDeviceWallpaperState` | `int32` | `int32` |
| 55 | `editDeviceDialCustom` | `int32, int32, int32, int32` | `int32` |
| 56 | `getDeviceDialCustom` | — | `int32` |
| 57 | `sendPhoneCallState` | `int32, int32, int32, int32` | `int32` |
| 58 | `setFemaleReminder` | `bool, int32, int32, int32, int32, int32` | `int32` |
| 59 | `setContactCrc` | `string` | `int32` |
| 60 | `setContactInfo` | `contact_record` | `int32` |
| 61 | `setAppId` | `string` | `int32` |
| 62 | `setPhoneMac` | `string` | `int32` |
| 63 | `sendPhoneVolume` | `int32, int32, int32, int32` | `int32` |
| 64 | `setBindedInfo` | `int32, int32, int32` | `int32` |
| 65 | `setECardInfoCrc` | `e_card_record` | `int32` |
| 66 | `setECardInfoContent` | `e_card_record` | `int32` |
| 67 | `setSmsRspInfoCrc` | `sms_response_record` | `int32` |
| 68 | `setSmsRspInfoContent` | `sms_response_record` | `int32` |
| 69 | `setSmsRspSendAck` | `int32` | `int32` |
| 70 | `startFileOta` | `int32, string` | `int32` |
| 71 | `translateBmpToBin` | `string, string, string, int32, int32, int32, int32, int32, int32, int32, int32, int32, int32, int32, int32, int32` | `string` |
| 72 | `setChatgptContent` | `int32, string` | `int32` |
| 73 | `startFactoryTestMode` | `bool` | `int32` |
| 74 | `getDialServerInfo` | `string` | `int32` |
| 75 | `setBloodOxygenMode` | `bool` | `int32` |
| 76 | `getEqInfo` | — | `int32` |
| 77 | `setEqInfo2` | `int32, int32, int32, int32_array` | `int32` |
| 78 | `setWifiHotSpotInfo` | `string, string` | `int32` |
| 79 | `setWifiHotSpotInfoEx` | `string, string, int32` | `int32` |
| 80 | `getWifiState` | — | `int32` |
| 81 | `scanWifi` | — | `int32` |
| 82 | `connectFtp` | `string, string, string, int32` | `int32` |
| 83 | `getDeviceFileState` | — | `int32` |
| 84 | `setDeviceFileState` | `int32` | `int32` |
| 85 | `getMediaFileState` | — | `int32` |
| 86 | `notifyDownloadFtpFileCompleted` | — | `int32` |
| 87 | `setAILang` | `string` | `int32` |
| 88 | `getDeviceSystemStateInfo` | — | `int32` |
| 89 | `setAiChatState` | `bool` | `int32` |
| 90 | `setGSensorIndState` | `bool` | `int32` |
| 91 | `setOfflineSpeechRecognitionState` | `bool` | `int32` |
| 92 | `openWifiApMode` | `bool` | `int32` |
| 93 | `setAppState` | `int32, int32` | `int32` |
| 94 | `setWorshipInfo` | `int32, int32` | `int32` |
| 95 | `setTouchMode` | `int32` | `int32` |
| 96 | `setAiConnectionMethod` | `int32` | `int32` |
| 97 | `getOxygenOfflineData` | `int32` | `int32` |
| 98 | `getAdvSensorOfflineData` | `int32` | `int32` |
| 99 | `openRawDataNotification` | `bool` | `int32` |
| 100 | `connectAiServerNotification` | `bool` | `int32` |
| 101 | `setAiExtraAction` | `int32` | `int32` |
| 102 | `openAiState` | `bool` | `int32` |
| 103 | `queryAiState` | — | `int32` |
| 104 | `saveFileToSystemAlbum` | `string` | `int32` |
| 105 | `openAiAudioState` | `bool` | `int32` |
| 106 | `startFtpDownloadTask` | `string, string, string, int32, string` | `void` |
| 107 | `SetScreenLightTime` | `int32` | `int32` |
| 108 | `setAiCommandType` | `int32` | `int32` |
| 109 | `queryOfflineSpeechRecognitionState` | — | `int32` |
| 110 | `setSpoMode` | `bool` | `int32` |
| 111 | `setSugarMode` | `bool` | `int32` |
| 112 | `setPressureMode` | `bool` | `int32` |

## Callback interface — 105 transactions

| Tx | Method | Parameters | Result |
|---:|---|---|---|
| 1 | `onAuthSdkResult` | `int32` | `void` |
| 2 | `onScanCallback` | `string, string, int32, string, string, string, string, string, string` | `void` |
| 3 | `onConnectStateChanged` | `int32` | `void` |
| 4 | `onAuthDeviceResult` | `int32` | `void` |
| 5 | `onGetDeviceTime` | `int32, string` | `void` |
| 6 | `onSetDeviceTime` | `int32` | `void` |
| 7 | `onSetUserInfo` | `int32` | `void` |
| 8 | `onGetCurSportData` | `int32, int64, int32, int32, int32, int32, int32, int32` | `void` |
| 9 | `onSendVibrationSignal` | `int32` | `void` |
| 10 | `onSetPhontMode` | `int32` | `void` |
| 11 | `onSetIdleTime` | `int32` | `void` |
| 12 | `onSetSleepTime` | `int32` | `void` |
| 13 | `onGetDeviceBatery` | `int32, int32` | `void` |
| 14 | `onGetDeviceInfo` | `int32, string, string, string, int32` | `void` |
| 15 | `onSetAlarm` | `int32` | `void` |
| 16 | `onSetDeviceMode` | `int32` | `void` |
| 17 | `onSetNotify` | `int32` | `void` |
| 18 | `onGetSenserData` | `int32, int64, int32, int32` | `void` |
| 19 | `setAutoHeartMode` | `int32` | `void` |
| 20 | `onSetDeviceInfo` | `int32` | `void` |
| 21 | `onSetHourFormat` | `int32` | `void` |
| 22 | `onGetDataByDay` | `int32, int64, int32, int32` | `void` |
| 23 | `onGetDataByDayEnd` | `int32, int64` | `void` |
| 24 | `onGetDeviceAction` | `int32` | `void` |
| 25 | `onGetBandFunction` | `int32, bool_array` | `void` |
| 26 | `onSetLanguage` | `int32` | `void` |
| 27 | `onSendWeather` | `int32` | `void` |
| 28 | `onSetAntiLost` | `int32` | `void` |
| 29 | `onSetBloodPressureMode` | `int32` | `void` |
| 30 | `onReceiveSensorData` | `int32, int32, int32, int32, int32, int32, int32, int32` | `void` |
| 31 | `onSetBloodOxygenMode` | `int32` | `void` |
| 32 | `onReceiveSensorOxygenData` | `int32` | `void` |
| 33 | `onGetMultipleSportData` | `int32, string, int32, int32` | `void` |
| 34 | `onSetGoalStep` | `int32` | `void` |
| 35 | `onSetDeviceHeartRateArea` | `int32` | `void` |
| 36 | `onSensorStateChange` | `int32, int32` | `void` |
| 37 | `onReadCurrentSportData` | `int32, string, int32, int32` | `void` |
| 38 | `onGetOtaInfo` | `bool, string, string` | `void` |
| 39 | `onGetOtaUpdate` | `int32, int32` | `void` |
| 40 | `onSetDeviceCode` | `int32` | `void` |
| 41 | `onGetDeviceCode` | `bytes` | `void` |
| 42 | `onCharacteristicChanged` | `string, bytes` | `void` |
| 43 | `onCharacteristicWrite` | `string, bytes, int32` | `void` |
| 44 | `onSetEcgMode` | `int32, int32` | `void` |
| 45 | `onGetEcgValue` | `int32, int32_array` | `void` |
| 46 | `onGetEcgHistory` | `int64, int32` | `void` |
| 47 | `onGetEcgStartEnd` | `int32, int32, int64` | `void` |
| 48 | `onGetEcgHistoryData` | `int32, int32_array` | `void` |
| 49 | `onSetDeviceName` | `int32` | `void` |
| 50 | `onGetDeviceRssi` | `int32` | `void` |
| 51 | `onSetReminder` | `int32` | `void` |
| 52 | `onSetReminderText` | `int32` | `void` |
| 53 | `onSetBPAdjust` | `int32` | `void` |
| 54 | `onSetTemperatureMode` | `int32` | `void` |
| 55 | `onGetTemperatureData` | `int32, int32` | `void` |
| 56 | `onTemperatureModeChange` | `int32` | `void` |
| 57 | `onGetDeviceDial` | `string, string, int32, int32, int32, int32, int32, int32, int32, int32, int32` | `void` |
| 58 | `onSetDeviceDialState` | — | `void` |
| 59 | `onSetDeviceWallpaperState` | — | `void` |
| 60 | `onEditDeviceDialCustom` | — | `void` |
| 61 | `onGetDeviceDialCustom` | `int32, int32, int32, int32` | `void` |
| 62 | `onSetFemaleReminder` | — | `void` |
| 63 | `onNotifyClassicBtName` | `string` | `void` |
| 64 | `onNotifyClassicBtInfo` | `int32, int32, string, string` | `void` |
| 65 | `onNotifyContactCrc` | `string` | `void` |
| 66 | `onNotifyAppId` | `string` | `void` |
| 67 | `onGetPhoneVolume` | — | `void` |
| 68 | `onNotifyBindedInfo` | `int32, int32` | `void` |
| 69 | `onGetDeviceState` | `bool, bool, bool` | `void` |
| 70 | `onNotifyECardNeedUpdate` | `bytes` | `void` |
| 71 | `onNotifySmsRspNeedUpdate` | `bytes` | `void` |
| 72 | `onNotifySmsRspSend` | `int32, string` | `void` |
| 73 | `onGetChatgptAction` | `int32` | `void` |
| 74 | `onGetFactoryTestData` | `bytes` | `void` |
| 75 | `onNotifyDialJsonContent` | `string` | `void` |
| 76 | `onGetSportSteps` | `int32` | `void` |
| 77 | `onDeviceTestCmd` | — | `void` |
| 78 | `onGetEqInfo2` | `int32, int32, int32, int32_array` | `int32` |
| 79 | `onSetEqInfo2` | `int32, int32, int32, int32_array` | `int32` |
| 80 | `onGetWifiState` | `int32, string, string, string, int32` | `void` |
| 81 | `onGetWifiSsidCount` | `int32` | `void` |
| 82 | `onGetWifiSsid` | `int32, int32, int32, int32, string` | `void` |
| 83 | `onGetDeviceFileState` | `int32` | `void` |
| 84 | `onNotifyDeviceSystemStateInfo` | `int32` | `void` |
| 85 | `onGetGSensorData` | `int32, int32_array` | `void` |
| 86 | `onNotifyFtpStateInfo` | `int32, string, int64, int32` | `void` |
| 87 | `onNotifyNewMediaInfo` | `int32, string, string` | `void` |
| 88 | `onNotifyDeviceWifiApState` | `int32` | `void` |
| 89 | `onGetOfflineSpeechRecognitionMode` | `int32` | `void` |
| 90 | `onGetWorshipInfo` | `int32, int32` | `void` |
| 91 | `onGetWorshipTimesData` | `int32` | `void` |
| 92 | `onGetTouchMode` | `int32` | `void` |
| 93 | `onNotifyAiConnectionMethod` | `int32` | `void` |
| 94 | `onGetOxygenOfflineData` | `int64, int32` | `void` |
| 95 | `onGetOxygenOfflineDataEnd` | `int64` | `void` |
| 96 | `onGetAdvSensorOfflineData` | `int64, int32, int32, int32, int32, int32` | `void` |
| 97 | `onGetAdvSensorOfflineDataEnd` | `int64` | `void` |
| 98 | `onGetAiAction` | `int32` | `void` |
| 99 | `onGetRawData` | `int32, int32, int32, int32, bytes` | `void` |
| 100 | `onGetAiState` | `int32, int32` | `void` |
| 101 | `onDeviceConnectedWifi` | `string, string, string, int32, string` | `void` |
| 102 | `onGetScreenLightTime` | `int32` | `void` |
| 103 | `onRecvDeviceVoiceCommandConfirm` | `int32` | `void` |
| 104 | `onOpenRawDataNotificationState` | `bool` | `void` |
| 105 | `onGetAiCommandType` | `int32` | `void` |

## Remaining semantic work

Each row still needs its corresponding functional-spec crosswalk: implementation
behavior class, direct app use, packet/non-packet route, callback origin, argument
derivation and consumption, local/platform side effects, failure behavior, terminal
rule, activation evidence, and explicit unknowns. Those facts belong in row-level
functional appendices rather than being inferred from these signatures.
