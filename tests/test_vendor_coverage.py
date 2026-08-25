from collections import Counter

from jring.vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)


def test_static_vendor_operation_coverage_accounts_for_all_112_requests_once():
    coverage = static_vendor_operation_coverage()
    names = [entry.name for entry in coverage]

    assert len(names) == 112
    assert len(set(names)) == 112
    assert Counter(entry.route for entry in coverage) == {
        "main_command": 79,
        "main_then_cloud": 1,
        "raw_command": 6,
        "raw_notification_control": 1,
        "local_ble_or_dynamic_gatt": 14,
        "cloud_or_cache": 3,
        "local_phone_network": 1,
        "local_filesystem_or_conversion": 2,
        "dfu": 1,
        "no_op_stub": 4,
    }


def test_only_seven_operations_have_offline_request_and_response_codecs():
    coverage = static_vendor_operation_coverage()
    implemented = {
        entry.name
        for entry in coverage
        if entry.python_state == "offline_request_and_response_codec"
    }
    assert implemented == {
        "getAdvSensorOfflineData",
        "getBandFunction",
        "getCurSportData",
        "getDeviceBatery",
        "getDeviceInfo",
        "getMultipleSportData",
        "getOxygenOfflineData",
    }


def test_all_six_raw_commands_have_offline_request_codecs_only():
    implemented = {
        entry.name
        for entry in static_vendor_operation_coverage()
        if entry.python_state == "offline_raw_request_codec"
    }

    assert implemented == {
        "connectAiServerNotification",
        "openAiAudioState",
        "openAiState",
        "queryAiState",
        "setAiCommandType",
        "setAiExtraAction",
    }


def test_twenty_six_mutations_have_offline_codecs_without_live_eligibility():
    implemented = {
        entry.name
        for entry in static_vendor_operation_coverage()
        if entry.python_state == "offline_mutation_codec"
    }

    assert implemented == {
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
    assert all(
        entry.hardware_eligible is False
        for entry in static_vendor_operation_coverage()
        if entry.name in implemented
    )


def test_static_coverage_never_promotes_an_operation_to_hardware():
    coverage = static_vendor_operation_coverage()

    assert all(entry.maturity == "static_apk_only" for entry in coverage)
    assert all(entry.hardware_eligible is False for entry in coverage)
    assert all(entry.python_state != "live_vendor" for entry in coverage)


def test_sensitive_and_destructive_surfaces_remain_visibly_unimplemented():
    by_name = {entry.name: entry for entry in static_vendor_operation_coverage()}

    for name in (
        "setContactInfo",
        "setWifiHotSpotInfo",
        "setChatgptContent",
        "startFactoryTestMode",
        "startFileOta",
        "writeCharacteristic",
    ):
        assert by_name[name].python_state == "not_reproduced"
        assert by_name[name].hardware_eligible is False

    assert by_name["setDeviceMode"].python_state == "offline_mutation_codec"
    assert by_name["setDeviceMode"].hardware_eligible is False


def test_static_vendor_callback_coverage_accounts_for_all_105_callbacks_once():
    coverage = static_vendor_callback_coverage()
    names = [entry.name for entry in coverage]

    assert len(names) == 105
    assert len(set(names)) == 105
    assert Counter(entry.source for entry in coverage) == {
        "bluetooth_opcode": 86,
        "android_network_ota_or_transport": 14,
        "declared_without_invocation": 2,
        "local_timer_or_parser_projection": 3,
    }


def test_callback_coverage_distinguishes_unused_and_non_ble_sources():
    by_name = {entry.name: entry for entry in static_vendor_callback_coverage()}

    assert by_name["onGetDeviceTime"].source == "declared_without_invocation"
    assert by_name["onSendWeather"].source == "declared_without_invocation"
    assert by_name["onCharacteristicChanged"].source == "android_network_ota_or_transport"
    assert by_name["onAuthSdkResult"].source == "android_network_ota_or_transport"
    assert by_name["onGetDeviceAction"].source == "bluetooth_opcode"
    assert by_name["onGetDataByDayEnd"].source == "local_timer_or_parser_projection"


def test_all_eighty_six_wire_callback_families_have_offline_response_codecs():
    implemented = {
        entry.name
        for entry in static_vendor_callback_coverage()
        if entry.python_state == "offline_response_codec"
    }

    assert implemented == {
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
    assert all(
        entry.hardware_eligible is False
        for entry in static_vendor_callback_coverage()
    )


def test_three_apk_generated_end_callbacks_are_local_projections_not_wire_codecs():
    projections = {
        entry.name
        for entry in static_vendor_callback_coverage()
        if entry.python_state == "offline_local_projection"
    }

    assert projections == {
        "onGetAdvSensorOfflineDataEnd",
        "onGetDataByDayEnd",
        "onGetOxygenOfflineDataEnd",
    }
