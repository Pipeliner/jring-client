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
    DIRECT_SDK_DISPATCH = "direct_sdk_dispatch"
    DECLARED_WITHOUT_DIRECT_DISPATCH = "declared_without_direct_dispatch"


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

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("callback dispatch evidence is closed")


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
    def directly_dispatched_callback_count(self) -> int:
        return sum(
            row.state is CallbackDispatchState.DIRECT_SDK_DISPATCH
            for row in self.callbacks
        )

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
    state = (
        CallbackDispatchState.DECLARED_WITHOUT_DIRECT_DISPATCH
        if name in {"onGetDeviceTime", "onSendWeather"}
        else CallbackDispatchState.DIRECT_SDK_DISPATCH
    )
    row = object.__new__(CallbackDispatchRow)
    object.__setattr__(row, "name", name)
    object.__setattr__(row, "interface_role", "callback")
    object.__setattr__(row, "state", state)
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
