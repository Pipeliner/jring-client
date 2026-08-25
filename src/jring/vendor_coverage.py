"""Machine-readable static coverage of the authorized APK's request surface."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StaticVendorOperation:
    name: str
    route: str
    python_state: str = "not_reproduced"
    maturity: str = "static_apk_only"
    hardware_eligible: bool = False


@dataclass(frozen=True)
class StaticVendorCallback:
    name: str
    source: str
    python_state: str = "not_reproduced"
    maturity: str = "static_apk_only"
    hardware_eligible: bool = False


_MAIN_COMMANDS = (
    "SetScreenLightTime",
    "editDeviceDialCustom",
    "getAdvSensorOfflineData",
    "getBandFunction",
    "getCurSportData",
    "getDataByDay",
    "getDeviceBatery",
    "getDeviceCode",
    "getDeviceDial",
    "getDeviceDialCustom",
    "getDeviceInfo",
    "getDeviceSystemStateInfo",
    "getEcgHistory",
    "getEqInfo",
    "getMediaFileState",
    "getMultipleSportData",
    "getOxygenOfflineData",
    "notifyDownloadFtpFileCompleted",
    "openWifiApMode",
    "queryOfflineSpeechRecognitionState",
    "scanWifi",
    "sendPhoneCallState",
    "sendPhoneVolume",
    "sendVibrationSignal",
    "sendWeather",
    "setAILang",
    "setAiChatState",
    "setAiConnectionMethod",
    "setAlarm",
    "setAntiLost",
    "setAppId",
    "setAppState",
    "setAutoHeartMode",
    "setBPAdjust",
    "setBindedInfo",
    "setBloodOxygenMode",
    "setBloodPressureMode",
    "setChatgptContent",
    "setContactCrc",
    "setContactInfo",
    "setDeviceCode",
    "setDeviceDialState",
    "setDeviceHeartRateArea",
    "setDeviceInfo",
    "setDeviceMode",
    "setDeviceName",
    "setDeviceTime",
    "setDeviceWallpaperState",
    "setECardInfoContent",
    "setECardInfoCrc",
    "setEcgMode",
    "setEqInfo2",
    "setFemaleReminder",
    "setGSensorIndState",
    "setGoalStep",
    "setHeartRateMode",
    "setHourFormat",
    "setIdleTime",
    "setLanguage",
    "setNotify",
    "setOfflineSpeechRecognitionState",
    "setPhoneMac",
    "setPhontMode",
    "setPressureMode",
    "setReminder",
    "setReminderText",
    "setSleepTime",
    "setSmsRspInfoContent",
    "setSmsRspInfoCrc",
    "setSmsRspSendAck",
    "setSpoMode",
    "setSugarMode",
    "setTemperatureMode",
    "setTouchMode",
    "setUserInfo",
    "setWifiHotSpotInfo",
    "setWifiHotSpotInfoEx",
    "setWorshipInfo",
    "startFactoryTestMode",
)

_MAIN_THEN_CLOUD = ("getOtaInfo",)
_RAW_COMMANDS = (
    "connectAiServerNotification",
    "openAiAudioState",
    "openAiState",
    "queryAiState",
    "setAiCommandType",
    "setAiExtraAction",
)
_RAW_NOTIFICATION_CONTROL = ("openRawDataNotification",)
_LOCAL_BLE = (
    "closeConnection",
    "connectBt",
    "disconnectBt",
    "getConnectedDevice",
    "getDeviceRssi",
    "isAuthrize",
    "isConnectBt",
    "openSDKLog",
    "scanDevice",
    "setOption",
    "setScanMode",
    "setUuid",
    "unregisterCallback",
    "writeCharacteristic",
)
_CLOUD_CACHE = ("getDialServerInfo", "registerCallback", "registerCallback2")
_LOCAL_PHONE_NETWORK = ("startFtpDownloadTask",)
_LOCAL_FILESYSTEM = ("saveFileToSystemAlbum", "translateBmpToBin")
_DFU = ("startFileOta",)
_NO_OP_STUBS = (
    "connectFtp",
    "getDeviceFileState",
    "getWifiState",
    "setDeviceFileState",
)

_OFFLINE_REQUEST_CODECS = frozenset(
    {
        "getAdvSensorOfflineData",
        "getBandFunction",
        "getCurSportData",
        "getDeviceBatery",
        "getDeviceInfo",
        "getMultipleSportData",
        "getOxygenOfflineData",
    }
)
_OFFLINE_RAW_REQUEST_CODECS = frozenset(_RAW_COMMANDS)

_ROUTES = (
    ("main_command", _MAIN_COMMANDS),
    ("main_then_cloud", _MAIN_THEN_CLOUD),
    ("raw_command", _RAW_COMMANDS),
    ("raw_notification_control", _RAW_NOTIFICATION_CONTROL),
    ("local_ble_or_dynamic_gatt", _LOCAL_BLE),
    ("cloud_or_cache", _CLOUD_CACHE),
    ("local_phone_network", _LOCAL_PHONE_NETWORK),
    ("local_filesystem_or_conversion", _LOCAL_FILESYSTEM),
    ("dfu", _DFU),
    ("no_op_stub", _NO_OP_STUBS),
)


def static_vendor_operation_coverage() -> tuple[StaticVendorOperation, ...]:
    return tuple(
        StaticVendorOperation(
            name=name,
            route=route,
            python_state=(
                "offline_request_and_response_codec"
                if name in _OFFLINE_REQUEST_CODECS
                else "offline_raw_request_codec"
                if name in _OFFLINE_RAW_REQUEST_CODECS
                else "not_reproduced"
            ),
        )
        for route, names in _ROUTES
        for name in names
    )


_CALLBACKS = (
    "onAuthDeviceResult",
    "onAuthSdkResult",
    "onCharacteristicChanged",
    "onCharacteristicWrite",
    "onConnectStateChanged",
    "onDeviceConnectedWifi",
    "onDeviceTestCmd",
    "onEditDeviceDialCustom",
    "onGetAdvSensorOfflineData",
    "onGetAdvSensorOfflineDataEnd",
    "onGetAiAction",
    "onGetAiCommandType",
    "onGetAiState",
    "onGetBandFunction",
    "onGetChatgptAction",
    "onGetCurSportData",
    "onGetDataByDay",
    "onGetDataByDayEnd",
    "onGetDeviceAction",
    "onGetDeviceBatery",
    "onGetDeviceCode",
    "onGetDeviceDial",
    "onGetDeviceDialCustom",
    "onGetDeviceFileState",
    "onGetDeviceInfo",
    "onGetDeviceRssi",
    "onGetDeviceState",
    "onGetDeviceTime",
    "onGetEcgHistory",
    "onGetEcgHistoryData",
    "onGetEcgStartEnd",
    "onGetEcgValue",
    "onGetEqInfo2",
    "onGetFactoryTestData",
    "onGetGSensorData",
    "onGetMultipleSportData",
    "onGetOfflineSpeechRecognitionMode",
    "onGetOtaInfo",
    "onGetOtaUpdate",
    "onGetOxygenOfflineData",
    "onGetOxygenOfflineDataEnd",
    "onGetPhoneVolume",
    "onGetRawData",
    "onGetScreenLightTime",
    "onGetSenserData",
    "onGetSportSteps",
    "onGetTemperatureData",
    "onGetTouchMode",
    "onGetWifiSsid",
    "onGetWifiSsidCount",
    "onGetWifiState",
    "onGetWorshipInfo",
    "onGetWorshipTimesData",
    "onNotifyAiConnectionMethod",
    "onNotifyAppId",
    "onNotifyBindedInfo",
    "onNotifyClassicBtInfo",
    "onNotifyClassicBtName",
    "onNotifyContactCrc",
    "onNotifyDeviceSystemStateInfo",
    "onNotifyDeviceWifiApState",
    "onNotifyDialJsonContent",
    "onNotifyECardNeedUpdate",
    "onNotifyFtpStateInfo",
    "onNotifyNewMediaInfo",
    "onNotifySmsRspNeedUpdate",
    "onNotifySmsRspSend",
    "onOpenRawDataNotificationState",
    "onReadCurrentSportData",
    "onReceiveSensorData",
    "onReceiveSensorOxygenData",
    "onRecvDeviceVoiceCommandConfirm",
    "onScanCallback",
    "onSendVibrationSignal",
    "onSendWeather",
    "onSensorStateChange",
    "onSetAlarm",
    "onSetAntiLost",
    "onSetBPAdjust",
    "onSetBloodOxygenMode",
    "onSetBloodPressureMode",
    "onSetDeviceCode",
    "onSetDeviceDialState",
    "onSetDeviceHeartRateArea",
    "onSetDeviceInfo",
    "onSetDeviceMode",
    "onSetDeviceName",
    "onSetDeviceTime",
    "onSetDeviceWallpaperState",
    "onSetEcgMode",
    "onSetEqInfo2",
    "onSetFemaleReminder",
    "onSetGoalStep",
    "onSetHourFormat",
    "onSetIdleTime",
    "onSetLanguage",
    "onSetNotify",
    "onSetPhontMode",
    "onSetReminder",
    "onSetReminderText",
    "onSetSleepTime",
    "onSetTemperatureMode",
    "onSetUserInfo",
    "onTemperatureModeChange",
    "setAutoHeartMode",
)

_NON_BLE_CALLBACKS = frozenset(
    {
        "onAuthDeviceResult",
        "onAuthSdkResult",
        "onCharacteristicChanged",
        "onCharacteristicWrite",
        "onConnectStateChanged",
        "onDeviceConnectedWifi",
        "onGetDeviceRssi",
        "onGetOtaInfo",
        "onGetOtaUpdate",
        "onNotifyDialJsonContent",
        "onNotifyFtpStateInfo",
        "onNotifyNewMediaInfo",
        "onOpenRawDataNotificationState",
        "onScanCallback",
    }
)
_UNUSED_CALLBACKS = frozenset({"onGetDeviceTime", "onSendWeather"})
_OFFLINE_RESPONSE_CODECS = frozenset(
    {
        "onGetAdvSensorOfflineData",
        "onGetAiAction",
        "onGetAiCommandType",
        "onGetAiState",
        "onGetBandFunction",
        "onGetCurSportData",
        "onGetDeviceAction",
        "onGetDeviceBatery",
        "onGetDeviceDialCustom",
        "onGetDeviceInfo",
        "onGetDeviceState",
        "onGetGSensorData",
        "onGetMultipleSportData",
        "onGetOxygenOfflineData",
        "onGetPhoneVolume",
        "onGetRawData",
        "onGetScreenLightTime",
        "onGetSportSteps",
        "onGetTouchMode",
        "onGetWorshipInfo",
        "onGetWorshipTimesData",
        "onReadCurrentSportData",
        "onRecvDeviceVoiceCommandConfirm",
        "onEditDeviceDialCustom",
        "onSendVibrationSignal",
        "onSetAlarm",
        "onSetAntiLost",
        "onSetBPAdjust",
        "onSetBloodPressureMode",
        "onSetDeviceCode",
        "onSetDeviceDialState",
        "onSetDeviceHeartRateArea",
        "onSetDeviceInfo",
        "onSetDeviceMode",
        "onSetDeviceName",
        "onSetDeviceTime",
        "onSetDeviceWallpaperState",
        "onSetEcgMode",
        "onSetFemaleReminder",
        "onSetGoalStep",
        "onSetHourFormat",
        "onSetIdleTime",
        "onSetLanguage",
        "onSetNotify",
        "onSetPhontMode",
        "onSetReminder",
        "onSetReminderText",
        "onSetSleepTime",
        "onSetUserInfo",
        "setAutoHeartMode",
    }
)


def static_vendor_callback_coverage() -> tuple[StaticVendorCallback, ...]:
    def source(name: str) -> str:
        if name in _NON_BLE_CALLBACKS:
            return "android_network_ota_or_transport"
        if name in _UNUSED_CALLBACKS:
            return "declared_without_invocation"
        return "bluetooth_opcode"

    return tuple(
        StaticVendorCallback(
            name=name,
            source=source(name),
            python_state=(
                "offline_response_codec"
                if name in _OFFLINE_RESPONSE_CODECS
                else "not_reproduced"
            ),
        )
        for name in _CALLBACKS
    )
