"""Closed structural evidence for the recovered main callback dispatcher."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, init=False, repr=False)
class CallbackOpcodeRoute:
    callback: str
    reachable_opcodes: tuple[int, ...]
    shadowed_opcodes: tuple[int, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("dispatcher route evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredDispatcherEvidence:
    token_comparison_count: int
    routing_branch_comparison_count: int
    distinct_casefolded_opcode_count: int
    recognized_opcodes: tuple[int, ...]
    recognized_no_direct_callback_opcodes: tuple[int, ...]
    callback_bearing_distinct_opcode_count: int
    syntactic_callback_invoke_count: int
    reachable_callback_invoke_count: int
    shadowed_callback_invoke_count: int
    unique_callback_target_count: int
    unique_target_without_reachable_invoke_count: int
    switch_instruction_count: int
    switch_payload_count: int
    minimum_token_count: int
    null_input_returns: bool
    short_input_returns: bool
    callback_routes: tuple[CallbackOpcodeRoute, ...]
    semantic_meanings_established: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("dispatcher evidence is closed")

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def python_callable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False


def _route(
    callback: str,
    *reachable: int,
    shadowed: tuple[int, ...] = (),
) -> CallbackOpcodeRoute:
    row = object.__new__(CallbackOpcodeRoute)
    object.__setattr__(row, "callback", callback)
    object.__setattr__(row, "reachable_opcodes", tuple(reachable))
    object.__setattr__(row, "shadowed_opcodes", tuple(shadowed))
    return row


_ROUTES = (
    _route("onDeviceConnectedWifi", 0x54),
    _route("onDeviceTestCmd", 0x3A),
    _route("onEditDeviceDialCustom", 0x41),
    _route("onGetAdvSensorOfflineData", 0x55),
    _route("onGetAdvSensorOfflineDataEnd", 0x55),
    _route("onGetBandFunction", 0x20, 0xA0),
    _route("onGetChatgptAction", 0x4E),
    _route("onGetCurSportData", 0x03, 0x13),
    _route("onGetDataByDay", 0x10, 0x11, 0x16, 0x39, 0x40, 0x55),
    _route("onGetDataByDayEnd", 0x16, 0x90, 0x96, 0xB9),
    _route("onGetDeviceAction", 0x06, 0x22),
    _route("onGetDeviceBatery", 0x0B),
    _route("onGetDeviceCode", 0x1F, 0x9F),
    _route("onGetDeviceDial", 0x34),
    _route("onGetDeviceDialCustom", 0x42),
    _route("onGetDeviceFileState", 0x54),
    _route("onGetDeviceInfo", 0x0C),
    _route("onGetDeviceState", 0x3D),
    _route("onGetEcgHistory", 0x2C),
    _route("onGetEcgHistoryData", 0x2E),
    _route("onGetEcgStartEnd", 0x2D),
    _route("onGetEcgValue", 0x2B),
    _route("onGetEqInfo2", 0x53),
    _route("onGetFactoryTestData", 0x50),
    _route("onGetGSensorData", 0x78),
    _route("onGetMultipleSportData", 0x25, 0xA5),
    _route("onGetOfflineSpeechRecognitionMode", 0x78),
    _route("onGetOxygenOfflineData", 0x40),
    _route("onGetOxygenOfflineDataEnd", 0x40),
    _route("onGetPhoneVolume", 0x49),
    _route("onGetScreenLightTime", 0x78),
    _route("onGetSenserData", 0x14, 0x15, 0x94, 0x95),
    _route("onGetSportSteps", 0x51),
    _route("onGetTemperatureData", 0x38),
    _route("onGetTouchMode", 0x78),
    _route("onGetWifiSsid", 0x54),
    _route("onGetWifiSsidCount", 0x54),
    _route("onGetWifiState", 0x54),
    _route("onGetWorshipInfo", 0x78),
    _route("onGetWorshipTimesData", 0x78),
    _route("onNotifyAiConnectionMethod", 0x54),
    _route("onNotifyAppId", 0x45),
    _route("onNotifyBindedInfo", 0x4B),
    _route("onNotifyClassicBtInfo", 0x45),
    _route("onNotifyClassicBtName", 0x45),
    _route("onNotifyContactCrc", 0x46),
    _route("onNotifyDeviceSystemStateInfo", 0x54),
    _route("onNotifyDeviceWifiApState", 0x54),
    _route("onNotifyECardNeedUpdate", 0x4C),
    _route("onNotifySmsRspNeedUpdate", 0x4D),
    _route("onNotifySmsRspSend", 0x4D),
    _route("onReadCurrentSportData", 0x29),
    _route("onReceiveSensorData", 0x24),
    _route("onReceiveSensorOxygenData", 0x3F),
    _route("onSendVibrationSignal", 0x04, 0x84),
    _route("onSensorStateChange", 0x27, 0x28),
    _route("onSetAlarm", 0x0D, 0x8D),
    _route("onSetAntiLost", 0x05, 0x85),
    _route("onSetBPAdjust", 0x33),
    _route("onSetBloodOxygenMode", 0x3E),
    _route("onSetBloodPressureMode", 0x23, 0x25, 0xA3),
    _route("onSetDeviceCode", 0x1E, 0x9E),
    _route("onSetDeviceDialState", 0x35),
    _route("onSetDeviceHeartRateArea", 0x26, 0xA6),
    _route("onSetDeviceInfo", 0x1B, 0x9B),
    _route("onSetDeviceMode", 0x0E, 0x8E),
    _route("onSetDeviceName", 0x30),
    _route("onSetDeviceTime", 0x01, 0x81),
    _route("onSetDeviceWallpaperState", 0x36),
    _route("onSetEcgMode", 0x2A, shadowed=(0x9A,)),
    _route("onSetEqInfo2", 0x53),
    _route("onSetFemaleReminder", 0x44),
    _route("onSetGoalStep", 0x1A, 0x9A),
    _route("onSetHourFormat", 0x1D, 0x9D),
    _route("onSetIdleTime", 0x08, 0x88),
    _route("onSetLanguage", 0x21, 0xA1),
    _route("onSetNotify", 0x12, 0x92),
    _route("onSetPhontMode", 0x07, 0x87),
    _route("onSetReminder", 0x31),
    _route("onSetReminderText", 0x32),
    _route("onSetSleepTime", 0x09, 0x89),
    _route("onSetTemperatureMode", 0x37),
    _route("onSetUserInfo", 0x02, 0x82),
    _route("onTemperatureModeChange", 0x3B),
    _route("setAutoHeartMode", 0x19, 0x99),
)

_NO_DIRECT_CALLBACK = (0x1C, 0x83, 0x8B, 0x8C, 0x9C)
_REACHABLE_OPCODES = frozenset(
    opcode for row in _ROUTES for opcode in row.reachable_opcodes
)
_RECOGNIZED_OPCODES = tuple(sorted(_REACHABLE_OPCODES | set(_NO_DIRECT_CALLBACK)))

_EVIDENCE = object.__new__(RecoveredDispatcherEvidence)
for _name, _value in {
    "token_comparison_count": 106,
    "routing_branch_comparison_count": 105,
    "distinct_casefolded_opcode_count": 104,
    "recognized_opcodes": _RECOGNIZED_OPCODES,
    "recognized_no_direct_callback_opcodes": _NO_DIRECT_CALLBACK,
    "callback_bearing_distinct_opcode_count": 99,
    "syntactic_callback_invoke_count": 125,
    "reachable_callback_invoke_count": 124,
    "shadowed_callback_invoke_count": 1,
    "unique_callback_target_count": 85,
    "unique_target_without_reachable_invoke_count": 0,
    "switch_instruction_count": 0,
    "switch_payload_count": 0,
    "minimum_token_count": 20,
    "null_input_returns": True,
    "short_input_returns": True,
    "callback_routes": _ROUTES,
    "semantic_meanings_established": False,
}.items():
    object.__setattr__(_EVIDENCE, _name, _value)


def recovered_dispatcher_evidence() -> RecoveredDispatcherEvidence:
    """Return immutable sanitized dispatcher structure and route evidence."""

    return _EVIDENCE


__all__ = [
    "CallbackOpcodeRoute",
    "RecoveredDispatcherEvidence",
    "recovered_dispatcher_evidence",
]
