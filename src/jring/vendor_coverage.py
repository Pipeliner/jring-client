"""Machine-readable static coverage of the authorized APK's request surface."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from .vendor_session_evidence import recovered_session_evidence


class VendorPythonState(str, Enum):
    NOT_REPRODUCED = "not_reproduced"
    OFFLINE_REQUEST_AND_RESPONSE_CODEC = "offline_request_and_response_codec"
    OFFLINE_RAW_REQUEST_CODEC = "offline_raw_request_codec"
    OFFLINE_MAIN_REQUEST_CODEC = "offline_main_request_codec"
    OFFLINE_MUTATION_CODEC = "offline_mutation_codec"
    OFFLINE_CONTROL_MODEL = "offline_control_model"
    OFFLINE_BEHAVIOR_EVIDENCE = "offline_behavior_evidence"
    OFFLINE_RESPONSE_CODEC = "offline_response_codec"
    OFFLINE_LOCAL_PROJECTION = "offline_local_projection"
    LIVE_VENDOR = "live_vendor"


OFFLINE_REQUEST_CODEC_STATES = frozenset(
    {
        VendorPythonState.OFFLINE_REQUEST_AND_RESPONSE_CODEC,
        VendorPythonState.OFFLINE_RAW_REQUEST_CODEC,
        VendorPythonState.OFFLINE_MAIN_REQUEST_CODEC,
        VendorPythonState.OFFLINE_MUTATION_CODEC,
    }
)


@dataclass(frozen=True)
class StaticVendorOperation:
    name: str
    route: str
    python_state: VendorPythonState = VendorPythonState.NOT_REPRODUCED
    maturity: str = "static_apk_only"
    hardware_eligible: bool = False
    hardware_verified: bool = False
    evidence_locator: str | None = None
    evidence_scope: str | None = None
    known_limitations: tuple[str, ...] = ()
    session_sequence_locators: tuple[str, ...] = ()


@dataclass(frozen=True)
class StaticVendorCallback:
    name: str
    source: str
    python_state: VendorPythonState = VendorPythonState.NOT_REPRODUCED
    maturity: str = "static_apk_only"
    hardware_eligible: bool = False
    hardware_verified: bool = False
    session_sequence_locators: tuple[str, ...] = ()


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
_OFFLINE_CONTROL_MODELS = frozenset(_RAW_NOTIFICATION_CONTROL)
_OFFLINE_MAIN_REQUEST_CODECS = frozenset(
    {
        "SetScreenLightTime",
        "getDataByDay",
        "getDeviceCode",
        "getDeviceDial",
        "getDeviceDialCustom",
        "getDeviceSystemStateInfo",
        "getEcgHistory",
        "getEqInfo",
        "getMediaFileState",
        "notifyDownloadFtpFileCompleted",
        "openWifiApMode",
        "queryOfflineSpeechRecognitionState",
        "scanWifi",
        "sendPhoneCallState",
        "sendPhoneVolume",
        "sendWeather",
        "setAILang",
        "setAiChatState",
        "setAiConnectionMethod",
        "setAppId",
        "setAppState",
        "setBindedInfo",
        "setBloodOxygenMode",
        "setChatgptContent",
        "setContactCrc",
        "setContactInfo",
        "setDeviceTime",
        "setECardInfoContent",
        "setECardInfoCrc",
        "setEcgMode",
        "setEqInfo2",
        "setGSensorIndState",
        "setHeartRateMode",
        "setOfflineSpeechRecognitionState",
        "setNotify",
        "setPhoneMac",
        "setSmsRspInfoContent",
        "setSmsRspInfoCrc",
        "setSmsRspSendAck",
        "setTemperatureMode",
        "setTouchMode",
        "setUserInfo",
        "setWifiHotSpotInfo",
        "setWifiHotSpotInfoEx",
        "setWorshipInfo",
        "startFactoryTestMode",
    }
)
_OFFLINE_BEHAVIOR_EVIDENCE = frozenset(
    (
        *_LOCAL_BLE,
        *_CLOUD_CACHE,
        *_LOCAL_PHONE_NETWORK,
        *_LOCAL_FILESYSTEM,
        *_NO_OP_STUBS,
        "getOtaInfo",
        "startFileOta",
    )
)

BEHAVIOR_EVIDENCE_LOCATORS = {
    **{
        name: f"jring.vendor_local_operations:LocalBleOperation:{name}"
        for name in _LOCAL_BLE
    },
    **{
        name: f"jring.vendor_platform_surface:PlatformSurfaceOperation:{name}"
        for name in (
            *_CLOUD_CACHE,
            *_LOCAL_PHONE_NETWORK,
            *_LOCAL_FILESYSTEM,
            *_NO_OP_STUBS,
        )
    },
    "getOtaInfo": (
        "jring.vendor_ota_evidence:FirmwareAndTransferEvidenceOperation:get_ota_info"
    ),
    "startFileOta": (
        "jring.vendor_ota_evidence:FirmwareAndTransferEvidenceOperation:start_file_ota"
    ),
}
SUPPLEMENTAL_EVIDENCE_LOCATORS = {
    "notifyDownloadFtpFileCompleted": (
        "jring.vendor_ota_evidence:FirmwareAndTransferEvidenceOperation:"
        "notify_ftp_download_completed"
    )
}


def _session_sequence_locator(code: str) -> str:
    return f"jring.vendor_session_evidence:SessionTransitionCode:{code}"


def _session_sequence_locator_index(
    relationship: str,
) -> Mapping[str, tuple[str, ...]]:
    indexed: dict[str, list[str]] = {}
    for transition in recovered_session_evidence().transitions:
        locator = _session_sequence_locator(transition.code.value)
        for name in getattr(transition, relationship):
            indexed.setdefault(name, []).append(locator)
    return MappingProxyType(
        {name: tuple(locators) for name, locators in indexed.items()}
    )


# These supplemental indexes point from existing interface declarations to recovered
# internal sequencing evidence.  They are deliberately not routes, operations, or
# callbacks and therefore cannot change the 112/105 interface ledgers.
REQUEST_SEQUENCE_EVIDENCE_LOCATORS: Mapping[str, tuple[str, ...]] = (
    _session_sequence_locator_index("related_requests")
)
CALLBACK_SEQUENCE_EVIDENCE_LOCATORS: Mapping[str, tuple[str, ...]] = (
    _session_sequence_locator_index("related_callbacks")
)
_OFFLINE_MUTATION_CODECS = frozenset(
    {
        "editDeviceDialCustom",
        "sendVibrationSignal",
        "setAlarm",
        "setAntiLost",
        "setAutoHeartMode",
        "setBPAdjust",
        "setBloodPressureMode",
        "setDeviceCode",
        "setDeviceDialState",
        "setDeviceHeartRateArea",
        "setDeviceInfo",
        "setDeviceMode",
        "setDeviceName",
        "setDeviceWallpaperState",
        "setFemaleReminder",
        "setGoalStep",
        "setHourFormat",
        "setIdleTime",
        "setLanguage",
        "setPhontMode",
        "setPressureMode",
        "setReminder",
        "setReminderText",
        "setSleepTime",
        "setSpoMode",
        "setSugarMode",
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
                VendorPythonState.OFFLINE_REQUEST_AND_RESPONSE_CODEC
                if name in _OFFLINE_REQUEST_CODECS
                else VendorPythonState.OFFLINE_RAW_REQUEST_CODEC
                if name in _OFFLINE_RAW_REQUEST_CODECS
                else VendorPythonState.OFFLINE_CONTROL_MODEL
                if name in _OFFLINE_CONTROL_MODELS
                else VendorPythonState.OFFLINE_MAIN_REQUEST_CODEC
                if name in _OFFLINE_MAIN_REQUEST_CODECS
                else VendorPythonState.OFFLINE_BEHAVIOR_EVIDENCE
                if name in _OFFLINE_BEHAVIOR_EVIDENCE
                else VendorPythonState.OFFLINE_MUTATION_CODEC
                if name in _OFFLINE_MUTATION_CODECS
                else VendorPythonState.NOT_REPRODUCED
            ),
            evidence_locator=BEHAVIOR_EVIDENCE_LOCATORS.get(name),
            evidence_scope=(
                "statically_classified_non_runnable_surface"
                if name in BEHAVIOR_EVIDENCE_LOCATORS
                else None
            ),
            known_limitations=(
                ("not_behavioral_parity", "no_runtime_or_hardware_verification")
                if name in BEHAVIOR_EVIDENCE_LOCATORS
                else ()
            ),
            session_sequence_locators=REQUEST_SEQUENCE_EVIDENCE_LOCATORS.get(
                name, ()
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

_NON_OPCODE_CALLBACKS = frozenset(
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
_LOCAL_PROJECTION_CALLBACKS = frozenset(
    {
        "onGetAdvSensorOfflineDataEnd",
        "onGetDataByDayEnd",
        "onGetOxygenOfflineDataEnd",
    }
)
_OFFLINE_RESPONSE_CODECS = frozenset(
    {
        "onGetAdvSensorOfflineData",
        "onGetAiAction",
        "onGetAiCommandType",
        "onGetAiState",
        "onGetBandFunction",
        "onGetChatgptAction",
        "onGetCurSportData",
        "onGetDataByDay",
        "onGetDeviceAction",
        "onGetDeviceBatery",
        "onGetDeviceCode",
        "onGetDeviceDial",
        "onGetDeviceDialCustom",
        "onGetDeviceFileState",
        "onGetDeviceInfo",
        "onGetDeviceState",
        "onGetEcgHistory",
        "onGetEcgHistoryData",
        "onGetEcgStartEnd",
        "onGetEcgValue",
        "onGetEqInfo2",
        "onGetFactoryTestData",
        "onGetGSensorData",
        "onGetMultipleSportData",
        "onGetOfflineSpeechRecognitionMode",
        "onGetOxygenOfflineData",
        "onGetPhoneVolume",
        "onGetRawData",
        "onGetScreenLightTime",
        "onGetSenserData",
        "onGetSportSteps",
        "onGetTouchMode",
        "onGetWifiSsid",
        "onGetWifiSsidCount",
        "onGetWifiState",
        "onGetWorshipInfo",
        "onGetWorshipTimesData",
        "onReadCurrentSportData",
        "onReceiveSensorData",
        "onReceiveSensorOxygenData",
        "onRecvDeviceVoiceCommandConfirm",
        "onDeviceTestCmd",
        "onEditDeviceDialCustom",
        "onSendVibrationSignal",
        "onNotifyAiConnectionMethod",
        "onNotifyAppId",
        "onNotifyBindedInfo",
        "onNotifyClassicBtInfo",
        "onNotifyClassicBtName",
        "onNotifyContactCrc",
        "onNotifyDeviceSystemStateInfo",
        "onNotifyDeviceWifiApState",
        "onNotifyECardNeedUpdate",
        "onNotifySmsRspNeedUpdate",
        "onNotifySmsRspSend",
        "onSetAlarm",
        "onSetAntiLost",
        "onSetBPAdjust",
        "onSetBloodPressureMode",
        "onSetBloodOxygenMode",
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
        "onSensorStateChange",
        "onTemperatureModeChange",
        "onGetTemperatureData",
        "setAutoHeartMode",
    }
)


def static_vendor_callback_coverage() -> tuple[StaticVendorCallback, ...]:
    def source(name: str) -> str:
        if name in _NON_OPCODE_CALLBACKS:
            return "android_network_ota_or_transport"
        if name in _UNUSED_CALLBACKS:
            return "declared_without_invocation"
        if name in _LOCAL_PROJECTION_CALLBACKS:
            return "local_timer_or_parser_projection"
        return "bluetooth_opcode"

    return tuple(
        StaticVendorCallback(
            name=name,
            source=source(name),
            python_state=(
                VendorPythonState.OFFLINE_RESPONSE_CODEC
                if name in _OFFLINE_RESPONSE_CODECS
                else VendorPythonState.OFFLINE_LOCAL_PROJECTION
                if name in _LOCAL_PROJECTION_CALLBACKS
                else VendorPythonState.NOT_REPRODUCED
            ),
            session_sequence_locators=CALLBACK_SEQUENCE_EVIDENCE_LOCATORS.get(
                name, ()
            ),
        )
        for name in _CALLBACKS
    )
