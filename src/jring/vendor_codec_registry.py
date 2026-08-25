"""Immutable ledger-to-codec linkage for offline vendor coverage.

The registry resolves Python symbols only. It never constructs a transport, encodes
caller data, parses device data, or grants hardware authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import importlib
from types import MappingProxyType
from typing import Mapping


class CodecBindingKind(str, Enum):
    DIRECT_CALLABLE = "direct_callable"
    ENUM_BOUND_CALLABLE = "enum_bound_callable"
    TYPED_FACTORY = "typed_factory"
    BRANCHING_FACTORY = "branching_factory"
    PIPELINE = "pipeline"
    STATEFUL_FACTORY = "stateful_factory"
    FAMILY_BINDING_UNRESOLVED = "family_binding_unresolved"


@dataclass(frozen=True)
class CodecSymbol:
    module: str
    qualname: str
    binding: tuple[str, ...] = ()


@dataclass(frozen=True)
class CodecLocator:
    kind: CodecBindingKind
    targets: tuple[CodecSymbol, ...]
    limitations: tuple[str, ...] = ()
    source_pre_enqueue_effects: tuple[str, ...] = ()
    source_effects_reproduced: bool | None = None

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False


def _symbol(module: str, qualname: str, *binding: str) -> CodecSymbol:
    return CodecSymbol(module, qualname, tuple(binding))


def _locator(
    kind: CodecBindingKind,
    *targets: CodecSymbol,
    limitations: tuple[str, ...] = (),
    source_pre_enqueue_effects: tuple[str, ...] = (),
    source_effects_reproduced: bool | None = None,
) -> CodecLocator:
    return CodecLocator(
        kind,
        tuple(targets),
        limitations,
        source_pre_enqueue_effects,
        source_effects_reproduced,
    )


def _direct(module: str, qualname: str) -> CodecLocator:
    return _locator(
        CodecBindingKind.DIRECT_CALLABLE,
        _symbol(module, qualname),
    )


def _bound(module: str, qualname: str, *binding: str) -> CodecLocator:
    return _locator(
        CodecBindingKind.ENUM_BOUND_CALLABLE,
        _symbol(module, qualname, *binding),
    )


def _factory(module: str, qualname: str, *binding: str) -> CodecLocator:
    return _locator(
        CodecBindingKind.TYPED_FACTORY,
        _symbol(module, qualname, *binding),
    )


def resolve_codec_symbols(locator: CodecLocator) -> tuple[object, ...]:
    """Resolve registry symbols without invoking them."""

    if type(locator) is not CodecLocator:
        raise TypeError("locator must be a CodecLocator")
    resolved = []
    for target in locator.targets:
        value: object = importlib.import_module(target.module)
        for component in target.qualname.split("."):
            value = getattr(value, component)
        resolved.append(value)
    return tuple(resolved)


_VP = "jring.vendor_protocol"
_VR = "jring.vendor_raw_protocol"
_VM = "jring.vendor_main_commands"
_VC = "jring.vendor_commands"
_VF = "jring.vendor_phone_integration"
_VN = "jring.vendor_notify"
_VPS = "jring.vendor_personal_settings"
_VBS = "jring.vendor_behavior_settings"
_VS = "jring.vendor_settings"
_VH = "jring.vendor_history"


_REQUESTS: dict[str, CodecLocator] = {
    "getCurSportData": _bound(_VP, "encode_static_query", "StaticQuery.CURRENT_SPORT"),
    "getDeviceBatery": _bound(_VP, "encode_static_query", "StaticQuery.BATTERY"),
    "getDeviceInfo": _bound(_VP, "encode_static_query", "StaticQuery.DEVICE_INFO"),
    "getBandFunction": _bound(_VP, "encode_static_query", "StaticQuery.BAND_FUNCTIONS"),
    "getMultipleSportData": _bound(_VP, "encode_day_query", "StaticQuery.MULTI_SPORT_DAY"),
    "getOxygenOfflineData": _bound(_VP, "encode_day_query", "StaticQuery.OXYGEN_DAY"),
    "getAdvSensorOfflineData": _bound(_VP, "encode_day_query", "StaticQuery.ADVANCED_SENSOR_DAY"),
    "connectAiServerNotification": _direct(_VR, "encode_raw_ai_server_notification"),
    "openAiAudioState": _direct(_VR, "encode_raw_ai_audio_state"),
    "openAiState": _direct(_VR, "encode_raw_ai_state"),
    "queryAiState": _direct(_VR, "encode_raw_ai_state_query"),
    "setAiCommandType": _direct(_VR, "encode_raw_ai_command_type"),
    "setAiExtraAction": _direct(_VR, "encode_raw_ai_extra_action"),
    "SetScreenLightTime": _factory(_VM, "ScreenLightTimeRequest"),
    "getDataByDay": _factory(_VM, "DayDataRequest"),
    "getEcgHistory": _factory(_VM, "EcgHistoryRequest"),
    "sendPhoneVolume": _factory(_VM, "PhoneVolumeRequest"),
}

for _name, _binding in {
    "getDeviceCode": "NoArgumentMainCommand.DEVICE_CODE",
    "getDeviceDial": "NoArgumentMainCommand.DEVICE_DIAL",
    "getDeviceDialCustom": "NoArgumentMainCommand.DEVICE_DIAL_CUSTOM",
    "getDeviceSystemStateInfo": "NoArgumentMainCommand.DEVICE_SYSTEM_STATE",
    "getEqInfo": "NoArgumentMainCommand.EQ_INFO",
    "getMediaFileState": "NoArgumentMainCommand.MEDIA_FILE_STATE",
    "queryOfflineSpeechRecognitionState": "NoArgumentMainCommand.OFFLINE_SPEECH_STATE",
    "scanWifi": "NoArgumentMainCommand.SCAN_WIFI",
}.items():
    _REQUESTS[_name] = _factory(_VM, "NoArgumentMainCommandRequest", _binding)

for _name, _qualname in {
    "sendPhoneCallState": "encode_phone_call_state",
    "sendWeather": "encode_weather",
    "setAILang": "encode_ai_language",
    "setAiChatState": "encode_ai_chat_state",
    "setAiConnectionMethod": "encode_ai_connection_method",
    "setAppState": "encode_app_state",
    "setBindedInfo": "encode_binding_info",
    "setBloodOxygenMode": "encode_blood_oxygen_mode",
    "setDeviceTime": "encode_device_time",
    "setEcgMode": "encode_ecg_mode",
    "setEqInfo2": "encode_eq_info",
    "setGSensorIndState": "encode_g_sensor_indicator",
    "setOfflineSpeechRecognitionState": "encode_offline_speech_recognition",
    "setTemperatureMode": "encode_temperature_mode",
    "setTouchMode": "encode_touch_mode",
    "startFactoryTestMode": "encode_factory_test_mode",
}.items():
    _REQUESTS[_name] = _direct(_VC, _qualname)

_REQUESTS["setHeartRateMode"] = _locator(
    CodecBindingKind.BRANCHING_FACTORY,
    _symbol(_VC, "encode_heart_rate_session_start"),
    _symbol(_VC, "encode_heart_rate_session_stop"),
    limitations=("interface_row_selects_one_of_two_closed_factories",),
)

for _name, _qualname in {
    "notifyDownloadFtpFileCompleted": "encode_download_completed",
    "openWifiApMode": "encode_open_wifi_ap_mode",
    "setAppId": "encode_app_id",
    "setChatgptContent": "encode_chat_content",
    "setContactCrc": "encode_contact_crc",
    "setContactInfo": "encode_contact_info",
    "setECardInfoContent": "encode_e_card_content",
    "setECardInfoCrc": "encode_e_card_crc",
    "setPhoneMac": "encode_phone_mac",
    "setSmsRspInfoContent": "encode_sms_reply_content",
    "setSmsRspInfoCrc": "encode_sms_reply_crc",
    "setSmsRspSendAck": "encode_sms_reply_ack",
    "setUserInfo": "encode_user_info",
    "setWifiHotSpotInfo": "encode_wifi_hotspot_info",
    "setWifiHotSpotInfoEx": "encode_wifi_hotspot_info_ex",
    "setWorshipInfo": "encode_worship_info",
}.items():
    _REQUESTS[_name] = _direct(_VF, _qualname)

_REQUESTS["setNotify"] = _locator(
    CodecBindingKind.PIPELINE,
    _symbol(_VN, "NotifyRequest.create"),
    _symbol(_VN, "plan_notify", "NotifyPlannerState"),
    limitations=("stateful_two_stage_planner",),
)

for _name, _qualname in {
    "editDeviceDialCustom": "encode_edit_device_dial_custom",
    "setBPAdjust": "encode_bp_adjust",
    "setDeviceDialState": "encode_device_dial_state",
    "setDeviceWallpaperState": "encode_device_wallpaper_state",
    "setFemaleReminder": "encode_female_reminder",
    "setReminder": "encode_reminder",
    "setReminderText": "encode_reminder_text",
}.items():
    _REQUESTS[_name] = _direct(_VPS, _qualname)

_REQUESTS["setDeviceDialState"] = _locator(
    CodecBindingKind.DIRECT_CALLABLE,
    _symbol(_VPS, "encode_device_dial_state"),
    limitations=("source_queue_and_retained_state_mutation_not_reproduced",),
    source_pre_enqueue_effects=(
        "set_internal_mode_flag",
        "clear_ordinary_command_queue",
        "clear_current_retained_frame",
    ),
    source_effects_reproduced=False,
)

for _name, _qualname in {
    "sendVibrationSignal": "VibrationRequest",
    "setAlarm": "AlarmBatchRequest",
    "setAntiLost": "AntiLostRequest",
    "setAutoHeartMode": "AutoHeartScheduleRequest",
    "setDeviceMode": "DeviceModeRequest",
    "setGoalStep": "GoalStepRequest",
    "setIdleTime": "IdleReminderRequest",
    "setPhontMode": "CameraModeRequest",
    "setSleepTime": "SleepScheduleRequest",
}.items():
    _REQUESTS[_name] = _factory(_VBS, _qualname)

_REQUESTS["setAlarm"] = _locator(
    CodecBindingKind.STATEFUL_FACTORY,
    _symbol(_VBS, "AlarmBatchRequest"),
    limitations=(
        "source_retained_list_not_reproduced",
        "source_sequential_enqueue_not_atomic",
        "byte_exact_for_observed_boolean_app_subset",
    ),
)

for _name, _qualname in {
    "setDeviceInfo": "encode_device_settings",
    "setHourFormat": "encode_hour_format",
    "setDeviceCode": "encode_device_code",
    "setLanguage": "encode_language",
    "setDeviceHeartRateArea": "encode_heart_rate_area",
    "setDeviceName": "encode_device_name",
}.items():
    _REQUESTS[_name] = _direct(_VS, _qualname)

_REQUESTS["setLanguage"] = _locator(
    CodecBindingKind.DIRECT_CALLABLE,
    _symbol(_VS, "encode_language"),
    limitations=(
        "source_no_argument_host_locale_derived",
        "python_requires_explicit_canonical_tag",
    ),
)

for _name, _mode in {
    "setBloodPressureMode": "SensorSessionMode.MODE_1",
    "setSpoMode": "SensorSessionMode.MODE_2",
    "setSugarMode": "SensorSessionMode.MODE_3",
    "setPressureMode": "SensorSessionMode.MODE_4",
}.items():
    _REQUESTS[_name] = _locator(
        CodecBindingKind.BRANCHING_FACTORY,
        _symbol(_VS, "encode_sensor_session_start", f"enabled=true:{_mode}"),
        _symbol(_VS, "encode_sensor_session_stop", "enabled=false:mode_zero"),
    )


_CALLBACKS: dict[str, CodecLocator] = {
    "onGetAdvSensorOfflineData": _direct(_VP, "parse_vendor_advanced_sensor_day"),
    "onGetBandFunction": _direct(_VP, "parse_vendor_band_functions"),
    "onGetCurSportData": _direct(_VP, "parse_vendor_current_sport"),
    "onGetDeviceBatery": _direct(_VP, "parse_vendor_battery"),
    "onGetDeviceInfo": _direct(_VP, "parse_vendor_device_info"),
    "onGetMultipleSportData": _direct(_VP, "parse_vendor_multi_sport_day"),
    "onGetOxygenOfflineData": _direct(_VP, "parse_vendor_oxygen_day"),
    "onGetDataByDay": _direct(_VH, "decode_vendor_history_frame"),
}

for _name, _qualname in {
    "onGetDeviceAction": "parse_vendor_device_action",
    "onGetDeviceState": "parse_vendor_device_state",
    "onGetDeviceDialCustom": "parse_vendor_device_dial_custom",
    "onReadCurrentSportData": "parse_vendor_read_current_sport",
    "onGetPhoneVolume": "parse_vendor_phone_volume_request",
    "onGetScreenLightTime": "parse_vendor_screen_light_time",
    "onGetTouchMode": "parse_vendor_touch_mode",
    "onGetWorshipInfo": "parse_vendor_worship_info",
    "onGetWorshipTimesData": "parse_vendor_worship_times",
    "onGetSportSteps": "parse_vendor_step_counter",
    "onGetChatgptAction": "parse_vendor_chat_action",
    "onDeviceTestCmd": "parse_vendor_device_test_event",
    "onGetSenserData": "parse_vendor_sensor_values",
    "onReceiveSensorData": "parse_vendor_sensor_measurement",
    "onSensorStateChange": "parse_vendor_sensor_state_change",
    "onGetTemperatureData": "parse_vendor_temperature_data",
    "onGetEcgHistory": "parse_vendor_ecg_history_info",
    "onGetEcgStartEnd": "parse_vendor_ecg_start_end",
    "onGetDeviceCode": "parse_vendor_device_code",
    "onGetDeviceDial": "parse_vendor_device_dial",
    "onGetDeviceFileState": "parse_vendor_device_file_state",
    "onGetFactoryTestData": "parse_vendor_factory_test_data",
    "onGetOfflineSpeechRecognitionMode": "parse_vendor_offline_speech_mode",
    "onNotifyBindedInfo": "parse_vendor_binding_info",
    "onNotifyContactCrc": "parse_vendor_contact_crc",
    "onNotifyECardNeedUpdate": "parse_vendor_e_card_need_update",
    "onNotifySmsRspNeedUpdate": "parse_vendor_sms_need_update",
    "onNotifySmsRspSend": "parse_vendor_sms_send",
    "onGetWifiState": "parse_vendor_wifi_state",
    "onGetWifiSsidCount": "parse_vendor_wifi_ssid_count",
}.items():
    _CALLBACKS[_name] = _direct(_VP, _qualname)

for _name, _binding in {
    "onGetEcgValue": "kind=live",
    "onGetEcgHistoryData": "kind=history",
}.items():
    _CALLBACKS[_name] = _bound(_VP, "parse_vendor_ecg_values", _binding)

for _name, _binding in {
    "onGetEqInfo2": "expected_kind=get",
    "onSetEqInfo2": "expected_kind=set",
}.items():
    _CALLBACKS[_name] = _bound(_VP, "parse_vendor_eq_info", _binding)

_CALLBACKS["onSetEcgMode"] = _direct(_VP, "parse_vendor_ecg_mode_ack")
_CALLBACKS["onGetGSensorData"] = _bound(
    _VP, "parse_vendor_motion_frame", "expected_subcommand=runtime"
)
_CALLBACKS["onGetWifiSsid"] = _locator(
    CodecBindingKind.STATEFUL_FACTORY,
    _symbol(_VP, "VendorWifiSsidAssembler"),
    limitations=("ordered_fragment_state_required",),
)

for _name, _binding in {
    "onSetTemperatureMode": "StaticValueEvent.TEMPERATURE_MODE",
    "onTemperatureModeChange": "StaticValueEvent.TEMPERATURE_MODE_CHANGE",
    "onSetBloodOxygenMode": "StaticValueEvent.BLOOD_OXYGEN_MODE",
    "onReceiveSensorOxygenData": "StaticValueEvent.SENSOR_OXYGEN_DATA",
}.items():
    _CALLBACKS[_name] = _bound(_VP, "parse_vendor_value_event", _binding)

for _name, _binding in {
    "onNotifyDeviceSystemStateInfo": "Static54ValueEvent.DEVICE_SYSTEM_STATE",
    "onNotifyDeviceWifiApState": "Static54ValueEvent.WIFI_AP_STATE",
    "onNotifyAiConnectionMethod": "Static54ValueEvent.AI_CONNECTION_METHOD",
}.items():
    _CALLBACKS[_name] = _bound(_VP, "parse_vendor_54_value_event", _binding)

for _name, _binding in {
    "onNotifyClassicBtInfo": "Static45Notification.CLASSIC_INFO",
    "onNotifyClassicBtName": "Static45Notification.CLASSIC_NAME",
    "onNotifyAppId": "Static45Notification.APP_ID",
}.items():
    _CALLBACKS[_name] = _bound(_VP, "parse_vendor_45_notification", _binding)

for _name, _binding in {
    "onGetAiAction": "type=0001",
    "onGetRawData": "type=0002_or_0003",
    "onGetAiState": "type=0006",
    "onRecvDeviceVoiceCommandConfirm": "type=0009",
    "onGetAiCommandType": "type=000a",
}.items():
    _CALLBACKS[_name] = _locator(
        CodecBindingKind.FAMILY_BINDING_UNRESOLVED,
        _symbol(_VR, "parse_raw_vendor_notification", _binding),
        limitations=("broad_parser_has_no_closed_expected_type_parameter",),
    )

for _name, _binding in {
    "onSetDeviceTime": "StaticAckOperation.DEVICE_TIME",
    "onSetUserInfo": "StaticAckOperation.USER_INFO",
    "onSendVibrationSignal": "StaticAckOperation.VIBRATION",
    "onSetAntiLost": "StaticAckOperation.ANTI_LOST",
    "onSetPhontMode": "StaticAckOperation.PHONE_MODE",
    "onSetIdleTime": "StaticAckOperation.IDLE_TIME",
    "onSetSleepTime": "StaticAckOperation.SLEEP_TIME",
    "onSetAlarm": "StaticAckOperation.ALARM",
    "onSetDeviceMode": "StaticAckOperation.DEVICE_MODE",
    "setAutoHeartMode": "StaticAckOperation.AUTO_HEART",
    "onSetGoalStep": "StaticAckOperation.GOAL",
    "onSetDeviceInfo": "StaticAckOperation.DEVICE_INFO_SET",
    "onSetHourFormat": "StaticAckOperation.HOUR_FORMAT",
    "onSetDeviceCode": "StaticAckOperation.DEVICE_CODE_SET",
    "onSetLanguage": "StaticAckOperation.LANGUAGE",
    "onSetBloodPressureMode": "StaticAckOperation.GENERIC_SENSOR_MODE",
    "onSetDeviceHeartRateArea": "StaticAckOperation.HEART_RATE_AREA",
    "onSetDeviceName": "StaticAckOperation.DEVICE_NAME",
    "onSetReminder": "StaticAckOperation.REMINDER",
    "onSetReminderText": "StaticAckOperation.REMINDER_TEXT",
    "onSetBPAdjust": "StaticAckOperation.BP_ADJUST",
    "onSetDeviceDialState": "StaticAckOperation.DEVICE_DIAL_STATE",
    "onSetDeviceWallpaperState": "StaticAckOperation.WALLPAPER_STATE",
    "onEditDeviceDialCustom": "StaticAckOperation.EDIT_DIAL_CUSTOM",
    "onSetFemaleReminder": "StaticAckOperation.FEMALE_REMINDER",
}.items():
    _CALLBACKS[_name] = _bound(_VP, "parse_vendor_ack", _binding)

_CALLBACKS["onSetNotify"] = _bound(
    _VP, "parse_vendor_notify_ack", "expected_marker=request_context"
)


REQUEST_CODEC_LOCATORS: Mapping[str, CodecLocator] = MappingProxyType(_REQUESTS)
CALLBACK_CODEC_LOCATORS: Mapping[str, CodecLocator] = MappingProxyType(_CALLBACKS)


__all__ = [
    "CALLBACK_CODEC_LOCATORS",
    "REQUEST_CODEC_LOCATORS",
    "CodecBindingKind",
    "CodecLocator",
    "CodecSymbol",
    "resolve_codec_symbols",
]
