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
                else "not_reproduced"
            ),
        )
        for route, names in _ROUTES
        for name in names
    )
