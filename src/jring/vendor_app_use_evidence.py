"""Closed, sanitized evidence for APK-owned SDK interface use."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)


class RequestAppUseState(str, Enum):
    DIRECT_APP_INTERFACE_INVOKE = "direct_app_interface_invoke"
    SDK_WIRE_ENTRY_WITHOUT_APP_INVOKE = "sdk_wire_entry_without_app_invoke"
    SDK_LOCAL_COMPOSITE_WITHOUT_APP_INVOKE = (
        "sdk_local_composite_without_app_invoke"
    )
    NO_OP_STUB_WITHOUT_APP_INVOKE = "no_op_stub_without_app_invoke"


class CallbackDispatchState(str, Enum):
    DIRECT_INVOKE_OBSERVED = "direct_invoke_observed"
    DECLARED_WITHOUT_DIRECT_INVOKE = "declared_without_direct_invoke"


@dataclass(frozen=True, init=False, repr=False)
class RequestAppUseRow:
    name: str
    interface_role: str
    state: RequestAppUseState
    direct_invoke_count: int

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request app-use evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class CallbackDispatchRow:
    name: str
    interface_role: str
    state: CallbackDispatchState
    main_response_invoke_count: int
    raw_response_invoke_count: int
    outside_dispatcher_invoke_count: int

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("callback dispatch evidence is closed")

    @property
    def invoke_counts(self) -> tuple[int, int, int]:
        return (
            self.main_response_invoke_count,
            self.raw_response_invoke_count,
            self.outside_dispatcher_invoke_count,
        )

    @property
    def direct_invoke_count(self) -> int:
        return sum(self.invoke_counts)


@dataclass(frozen=True, init=False, repr=False)
class RecoveredVendorAppUseEvidence:
    requests: tuple[RequestAppUseRow, ...]
    callbacks: tuple[CallbackDispatchRow, ...]
    cross_namespace_name_collisions: tuple[str, ...]
    dynamic_request_interface_invokes_observed: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor app-use evidence is closed")

    @property
    def direct_request_target_count(self) -> int:
        return sum(
            row.state is RequestAppUseState.DIRECT_APP_INTERFACE_INVOKE
            for row in self.requests
        )

    @property
    def direct_request_invoke_count(self) -> int:
        return sum(row.direct_invoke_count for row in self.requests)

    @property
    def directly_invoked_callback_count(self) -> int:
        return sum(
            row.state is CallbackDispatchState.DIRECT_INVOKE_OBSERVED
            for row in self.callbacks
        )

    @property
    def direct_callback_invoke_count(self) -> int:
        return sum(row.direct_invoke_count for row in self.callbacks)

    def _callback_target_count(self, field: str) -> int:
        return sum(getattr(row, field) > 0 for row in self.callbacks)

    def _callback_invoke_count(self, field: str) -> int:
        return sum(getattr(row, field) for row in self.callbacks)

    @property
    def main_response_callback_target_count(self) -> int:
        return self._callback_target_count("main_response_invoke_count")

    @property
    def main_response_callback_invoke_count(self) -> int:
        return self._callback_invoke_count("main_response_invoke_count")

    @property
    def raw_response_callback_target_count(self) -> int:
        return self._callback_target_count("raw_response_invoke_count")

    @property
    def raw_response_callback_invoke_count(self) -> int:
        return self._callback_invoke_count("raw_response_invoke_count")

    @property
    def outside_dispatcher_callback_target_count(self) -> int:
        return self._callback_target_count("outside_dispatcher_invoke_count")

    @property
    def outside_dispatcher_callback_invoke_count(self) -> int:
        return self._callback_invoke_count("outside_dispatcher_invoke_count")

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def evidence_scope(self) -> str:
        return "owned_direct_interface_references"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False


_DIRECT_REQUEST_INVOKE_COUNTS = {
    "connectBt": 4,
    "disconnectBt": 3,
    "getAdvSensorOfflineData": 3,
    "getDataByDay": 7,
    "getDeviceCode": 2,
    "getDeviceInfo": 1,
    "getEcgHistory": 1,
    "getMultipleSportData": 4,
    "getOtaInfo": 1,
    "isConnectBt": 16,
    "openSDKLog": 1,
    "registerCallback": 1,
    "scanDevice": 1,
    "sendPhoneCallState": 1,
    "sendPhoneVolume": 2,
    "sendVibrationSignal": 2,
    "sendWeather": 1,
    "setAlarm": 4,
    "setAntiLost": 2,
    "setAppId": 5,
    "setAppState": 4,
    "setAutoHeartMode": 2,
    "setBPAdjust": 1,
    "setBindedInfo": 3,
    "setBloodPressureMode": 4,
    "setContactCrc": 3,
    "setContactInfo": 3,
    "setDeviceCode": 1,
    "setDeviceInfo": 6,
    "setDeviceMode": 7,
    "setDeviceTime": 3,
    "setECardInfoContent": 1,
    "setECardInfoCrc": 1,
    "setFemaleReminder": 1,
    "setGoalStep": 2,
    "setHeartRateMode": 3,
    "setHourFormat": 8,
    "setIdleTime": 4,
    "setNotify": 2,
    "setOption": 11,
    "setPhontMode": 2,
    "setPressureMode": 1,
    "setReminder": 8,
    "setSleepTime": 1,
    "setSmsRspInfoContent": 1,
    "setSmsRspInfoCrc": 1,
    "setSpoMode": 1,
    "setSugarMode": 1,
    "setTemperatureMode": 2,
    "setUserInfo": 1,
    "unregisterCallback": 1,
}

_SDK_WIRE_WITHOUT_APP_INVOKE = frozenset(
    {
        "SetScreenLightTime", "editDeviceDialCustom", "getBandFunction",
        "getCurSportData", "getDeviceBatery", "getDeviceDial",
        "getDeviceDialCustom", "getDeviceSystemStateInfo", "getEqInfo",
        "getMediaFileState", "getOxygenOfflineData",
        "notifyDownloadFtpFileCompleted", "openWifiApMode",
        "queryOfflineSpeechRecognitionState", "scanWifi", "setAILang",
        "setAiChatState", "setAiConnectionMethod", "setBloodOxygenMode",
        "setChatgptContent", "setDeviceDialState", "setDeviceHeartRateArea",
        "setDeviceName", "setDeviceWallpaperState", "setEcgMode", "setEqInfo2",
        "setGSensorIndState", "setLanguage", "setOfflineSpeechRecognitionState",
        "setPhoneMac", "setReminderText", "setSmsRspSendAck", "setTouchMode",
        "setWifiHotSpotInfo", "setWifiHotSpotInfoEx", "setWorshipInfo",
        "startFactoryTestMode", "connectAiServerNotification", "openAiAudioState",
        "openAiState", "queryAiState", "setAiCommandType", "setAiExtraAction",
    }
)

_SDK_LOCAL_COMPOSITE_WITHOUT_APP_INVOKE = frozenset(
    {
        "closeConnection", "getConnectedDevice", "getDeviceRssi", "isAuthrize",
        "setScanMode", "setUuid", "writeCharacteristic", "getDialServerInfo",
        "registerCallback2", "saveFileToSystemAlbum", "translateBmpToBin",
        "startFtpDownloadTask", "startFileOta", "openRawDataNotification",
    }
)

_NO_OP_STUBS_WITHOUT_APP_INVOKE = frozenset(
    {"connectFtp", "getDeviceFileState", "getWifiState", "setDeviceFileState"}
)

# Exact direct interface-invoke occurrences in three mutually exclusive source
# regions: the main response dispatcher, the raw response dispatcher, and all other
# owned SDK/app code. A callback may appear in both main and outside regions.
_CALLBACK_INVOKE_COUNTS = {
    "onAuthDeviceResult": (0, 0, 3),
    "onAuthSdkResult": (0, 0, 6),
    "onCharacteristicChanged": (0, 0, 1),
    "onCharacteristicWrite": (0, 0, 1),
    "onConnectStateChanged": (0, 0, 4),
    "onDeviceConnectedWifi": (1, 0, 0),
    "onDeviceTestCmd": (1, 0, 0),
    "onEditDeviceDialCustom": (1, 0, 0),
    "onGetAdvSensorOfflineData": (1, 0, 0),
    "onGetAdvSensorOfflineDataEnd": (1, 0, 1),
    "onGetAiAction": (0, 1, 0),
    "onGetAiCommandType": (0, 1, 0),
    "onGetAiState": (0, 1, 0),
    "onGetBandFunction": (2, 0, 0),
    "onGetChatgptAction": (1, 0, 0),
    "onGetCurSportData": (2, 0, 0),
    "onGetDataByDay": (7, 0, 0),
    "onGetDataByDayEnd": (5, 0, 4),
    "onGetDeviceAction": (2, 0, 0),
    "onGetDeviceBatery": (1, 0, 0),
    "onGetDeviceCode": (2, 0, 0),
    "onGetDeviceDial": (1, 0, 0),
    "onGetDeviceDialCustom": (1, 0, 0),
    "onGetDeviceFileState": (1, 0, 0),
    "onGetDeviceInfo": (1, 0, 0),
    "onGetDeviceRssi": (0, 0, 1),
    "onGetDeviceState": (1, 0, 0),
    "onGetDeviceTime": (0, 0, 0),
    "onGetEcgHistory": (1, 0, 0),
    "onGetEcgHistoryData": (1, 0, 0),
    "onGetEcgStartEnd": (1, 0, 0),
    "onGetEcgValue": (1, 0, 0),
    "onGetEqInfo2": (1, 0, 0),
    "onGetFactoryTestData": (1, 0, 0),
    "onGetGSensorData": (1, 0, 0),
    "onGetMultipleSportData": (2, 0, 1),
    "onGetOfflineSpeechRecognitionMode": (2, 0, 0),
    "onGetOtaInfo": (0, 0, 4),
    "onGetOtaUpdate": (0, 0, 15),
    "onGetOxygenOfflineData": (1, 0, 0),
    "onGetOxygenOfflineDataEnd": (1, 0, 1),
    "onGetPhoneVolume": (1, 0, 0),
    "onGetRawData": (0, 2, 0),
    "onGetScreenLightTime": (1, 0, 0),
    "onGetSenserData": (4, 0, 0),
    "onGetSportSteps": (1, 0, 0),
    "onGetTemperatureData": (1, 0, 0),
    "onGetTouchMode": (1, 0, 0),
    "onGetWifiSsid": (1, 0, 0),
    "onGetWifiSsidCount": (1, 0, 0),
    "onGetWifiState": (1, 0, 0),
    "onGetWorshipInfo": (1, 0, 0),
    "onGetWorshipTimesData": (1, 0, 0),
    "onNotifyAiConnectionMethod": (1, 0, 0),
    "onNotifyAppId": (1, 0, 0),
    "onNotifyBindedInfo": (1, 0, 0),
    "onNotifyClassicBtInfo": (1, 0, 0),
    "onNotifyClassicBtName": (1, 0, 0),
    "onNotifyContactCrc": (1, 0, 0),
    "onNotifyDeviceSystemStateInfo": (1, 0, 0),
    "onNotifyDeviceWifiApState": (1, 0, 0),
    "onNotifyDialJsonContent": (0, 0, 2),
    "onNotifyECardNeedUpdate": (1, 0, 0),
    "onNotifyFtpStateInfo": (0, 0, 3),
    "onNotifyNewMediaInfo": (0, 0, 1),
    "onNotifySmsRspNeedUpdate": (1, 0, 0),
    "onNotifySmsRspSend": (1, 0, 0),
    "onOpenRawDataNotificationState": (0, 0, 1),
    "onReadCurrentSportData": (1, 0, 0),
    "onReceiveSensorData": (1, 0, 0),
    "onReceiveSensorOxygenData": (1, 0, 0),
    "onRecvDeviceVoiceCommandConfirm": (0, 1, 0),
    "onScanCallback": (0, 0, 1),
    "onSendVibrationSignal": (2, 0, 0),
    "onSendWeather": (0, 0, 0),
    "onSensorStateChange": (2, 0, 0),
    "onSetAlarm": (2, 0, 0),
    "onSetAntiLost": (2, 0, 0),
    "onSetBPAdjust": (1, 0, 0),
    "onSetBloodOxygenMode": (1, 0, 0),
    "onSetBloodPressureMode": (3, 0, 0),
    "onSetDeviceCode": (2, 0, 0),
    "onSetDeviceDialState": (1, 0, 0),
    "onSetDeviceHeartRateArea": (2, 0, 0),
    "onSetDeviceInfo": (2, 0, 0),
    "onSetDeviceMode": (2, 0, 0),
    "onSetDeviceName": (1, 0, 0),
    "onSetDeviceTime": (2, 0, 0),
    "onSetDeviceWallpaperState": (1, 0, 0),
    "onSetEcgMode": (2, 0, 0),
    "onSetEqInfo2": (1, 0, 0),
    "onSetFemaleReminder": (1, 0, 0),
    "onSetGoalStep": (2, 0, 0),
    "onSetHourFormat": (2, 0, 0),
    "onSetIdleTime": (2, 0, 0),
    "onSetLanguage": (2, 0, 0),
    "onSetNotify": (2, 0, 0),
    "onSetPhontMode": (2, 0, 0),
    "onSetReminder": (1, 0, 0),
    "onSetReminderText": (1, 0, 0),
    "onSetSleepTime": (2, 0, 0),
    "onSetTemperatureMode": (1, 0, 0),
    "onSetUserInfo": (2, 0, 0),
    "onTemperatureModeChange": (1, 0, 0),
    "setAutoHeartMode": (2, 0, 0),
}


def _request_row(name: str) -> RequestAppUseRow:
    if name in _DIRECT_REQUEST_INVOKE_COUNTS:
        state = RequestAppUseState.DIRECT_APP_INTERFACE_INVOKE
        count = _DIRECT_REQUEST_INVOKE_COUNTS[name]
    elif name in _SDK_WIRE_WITHOUT_APP_INVOKE:
        state = RequestAppUseState.SDK_WIRE_ENTRY_WITHOUT_APP_INVOKE
        count = 0
    elif name in _SDK_LOCAL_COMPOSITE_WITHOUT_APP_INVOKE:
        state = RequestAppUseState.SDK_LOCAL_COMPOSITE_WITHOUT_APP_INVOKE
        count = 0
    elif name in _NO_OP_STUBS_WITHOUT_APP_INVOKE:
        state = RequestAppUseState.NO_OP_STUB_WITHOUT_APP_INVOKE
        count = 0
    else:
        raise RuntimeError(f"unclassified request app-use row: {name}")
    row = object.__new__(RequestAppUseRow)
    object.__setattr__(row, "name", name)
    object.__setattr__(row, "interface_role", "request")
    object.__setattr__(row, "state", state)
    object.__setattr__(row, "direct_invoke_count", count)
    return row


def _callback_row(name: str) -> CallbackDispatchRow:
    try:
        main_count, raw_count, outside_count = _CALLBACK_INVOKE_COUNTS[name]
    except KeyError as error:
        raise RuntimeError(f"unclassified callback invoke row: {name}") from error
    state = (
        CallbackDispatchState.DECLARED_WITHOUT_DIRECT_INVOKE
        if main_count + raw_count + outside_count == 0
        else CallbackDispatchState.DIRECT_INVOKE_OBSERVED
    )
    row = object.__new__(CallbackDispatchRow)
    object.__setattr__(row, "name", name)
    object.__setattr__(row, "interface_role", "callback")
    object.__setattr__(row, "state", state)
    object.__setattr__(row, "main_response_invoke_count", main_count)
    object.__setattr__(row, "raw_response_invoke_count", raw_count)
    object.__setattr__(row, "outside_dispatcher_invoke_count", outside_count)
    return row


_REQUEST_ROWS = tuple(
    _request_row(row.name) for row in static_vendor_operation_coverage()
)
_CALLBACK_ROWS = tuple(
    _callback_row(row.name) for row in static_vendor_callback_coverage()
)

_EVIDENCE = object.__new__(RecoveredVendorAppUseEvidence)
object.__setattr__(_EVIDENCE, "requests", _REQUEST_ROWS)
object.__setattr__(_EVIDENCE, "callbacks", _CALLBACK_ROWS)
object.__setattr__(
    _EVIDENCE, "cross_namespace_name_collisions", ("setAutoHeartMode",)
)
object.__setattr__(
    _EVIDENCE, "dynamic_request_interface_invokes_observed", False
)


def recovered_vendor_app_use_evidence() -> RecoveredVendorAppUseEvidence:
    """Return the immutable owned-interface use reconciliation."""

    return _EVIDENCE


__all__ = [
    "CallbackDispatchRow",
    "CallbackDispatchState",
    "RecoveredVendorAppUseEvidence",
    "RequestAppUseRow",
    "RequestAppUseState",
    "recovered_vendor_app_use_evidence",
]
