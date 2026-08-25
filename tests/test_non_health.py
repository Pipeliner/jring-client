from dataclasses import FrozenInstanceError

import pytest

from jring.non_health import NonHealthCapability, static_non_health_capabilities
from jring.vendor_callback_surfaces import recovered_callback_behavior_surfaces
from jring.vendor_codec_registry import (
    CALLBACK_CODEC_LOCATORS,
    REQUEST_CODEC_LOCATORS,
)
from jring.vendor_protocol import parse_vendor_device_action


def test_non_health_inventory_exposes_evidence_maturity_and_live_boundaries():
    items = static_non_health_capabilities()
    by_name = {item.name: item for item in items}

    assert len(items) == len(by_name) == 38
    assert set(by_name) == {
        "standard_hid_metadata",
        "find_phone_alarm",
        "camera_shutter",
        "call_hangup",
        "weather_location_refresh",
        "call_answer",
        "media_play_pause",
        "media_next",
        "media_previous",
        "camera_open",
        "camera_close",
        "time_sync_request",
        "volume_up",
        "volume_down",
        "cumulative_step_counter",
        "unknown_motion_channels",
        "raw_ai_actions",
        "raw_audio_or_image_payloads",
        "classic_profile_attachment",
        "classic_rfcomm_socket_lifecycle",
        "classic_bt_info_callback",
        "classic_bt_name_callback",
        "host_volume_state_request",
        "main_chatgpt_action",
        "offline_speech_mode",
        "raw_ai_state",
        "raw_ai_command_type",
        "raw_voice_command_confirmation",
        "wifi_state",
        "wifi_ssid_inventory",
        "wifi_ap_state",
        "device_system_state",
        "eq_profile",
        "media_file_state",
        "device_dial_metadata",
        "device_dial_custom",
        "touch_mode",
        "screen_light_time",
    }
    assert by_name["standard_hid_metadata"].evidence == "bluetooth_standard"
    assert by_name["standard_hid_metadata"].maturity == "selected_device_metadata"
    assert "this local list observes no device" in (
        by_name["standard_hid_metadata"].description
    )
    assert by_name["media_play_pause"].evidence == "static_apk"
    assert by_name["media_play_pause"].input_candidate is True
    for blocked in (
        "find_phone_alarm", "call_hangup", "weather_location_refresh", "call_answer",
        "camera_open", "camera_close", "time_sync_request",
    ):
        assert by_name[blocked].input_candidate is False
        assert by_name[blocked].live_available is False
        assert by_name[blocked].input_eligible is False
    assert by_name["cumulative_step_counter"].input_candidate is False
    assert by_name["unknown_motion_channels"].meaning == "unknown"
    assert by_name["unknown_motion_channels"].label == "Nine unknown motion channels"
    assert by_name["unknown_motion_channels"].privacy_classes == (
        "motion_sensor_data",
    )
    assert by_name["classic_profile_attachment"].group == "classic_bluetooth"
    rfcomm = by_name["classic_rfcomm_socket_lifecycle"]
    assert rfcomm.label == "Classic RFCOMM socket lifecycle reference"
    assert rfcomm.meaning == "socket_lifecycle_reference"
    assert "no connect, read, or write" in rfcomm.description
    assert "actual OTA transfer uses GATT" in rfcomm.description
    assert by_name["classic_bt_info_callback"].maturity == "offline_decoder"
    assert by_name["classic_bt_info_callback"].callback_operations == (
        "onNotifyClassicBtInfo",
    )
    assert by_name["classic_bt_info_callback"].scripted_fake_decoder_available is True
    assert by_name["classic_bt_name_callback"].meaning == "private_classic_metadata"
    assert by_name["classic_bt_name_callback"].privacy_classes == ("device_name",)
    assert by_name["classic_bt_name_callback"].callback_operations == (
        "onNotifyClassicBtName",
    )
    assert by_name["classic_bt_name_callback"].scripted_fake_decoder_available is True
    assert by_name["host_volume_state_request"].group == "host_integration"
    assert by_name["host_volume_state_request"].scripted_fake_decoder_available is True
    assert by_name["host_volume_state_request"].privacy_classes == (
        "host_audio_state_request",
    )
    assert by_name["host_volume_state_request"].request_operations == (
        "sendPhoneVolume",
    )
    assert by_name["host_volume_state_request"].callback_operations == (
        "onGetPhoneVolume",
    )
    assert by_name["cumulative_step_counter"].scripted_fake_decoder_available is True
    assert by_name["cumulative_step_counter"].privacy_classes == ("activity_count",)
    assert by_name["cumulative_step_counter"].callback_operations == (
        "onGetSportSteps",
    )
    assert by_name["touch_mode"].scripted_fake_decoder_available is True
    assert by_name["touch_mode"].privacy_classes == ("touch_setting",)
    assert by_name["touch_mode"].input_eligible is False
    unknown_motion = by_name["unknown_motion_channels"]
    assert unknown_motion.scripted_fake_decoder_available is True
    assert unknown_motion.request_operations == ("setGSensorIndState",)
    assert unknown_motion.callback_operations == ("onGetGSensorData",)
    assert unknown_motion.input_candidate is False
    assert unknown_motion.input_eligible is False
    assert "scripted fake only" in unknown_motion.description
    assert "zero writes" in unknown_motion.description
    assert "private" in unknown_motion.description
    assert "not a live motion event, gesture, activation, or input" in (
        unknown_motion.description
    )
    assert all(
        item.scripted_fake_decoder_available
        for item in items
        if item.group == "device_actions"
    )
    assert all(
        item.privacy_classes == ("user_intent",)
        for item in items
        if item.group == "device_actions"
    )
    assert all(
        item.callback_operations == ("onGetDeviceAction",)
        for item in items
        if item.group == "device_actions"
    )
    assert "discards" in by_name["raw_ai_actions"].description
    assert "discards" in by_name["unknown_motion_channels"].description
    assert all(item.hardware_verified is False for item in items)
    assert all(item.evidence and item.maturity for item in items)
    assert all(item.hardware_eligible is False for item in items)
    assert all(item.runnable is False for item in items)
    assert all(item.live_available is False for item in items)
    assert all(item.input_eligible is False for item in items)
    assert all(item.privacy_classes for item in items)


def test_non_health_inventory_is_immutable_and_contains_no_payloads():
    items = static_non_health_capabilities()

    assert isinstance(items, tuple)
    rendered = repr(items).lower()
    assert "payload=b" not in rendered
    assert "address" not in rendered


def test_general_use_rows_are_closed_privacy_aware_ledger_projections():
    rows = {
        item.name: item
        for item in static_non_health_capabilities()
        if item.group == "general_use"
    }

    assert set(rows) == {
        "main_chatgpt_action",
        "offline_speech_mode",
        "raw_ai_state",
        "raw_ai_command_type",
        "raw_voice_command_confirmation",
        "wifi_state",
        "wifi_ssid_inventory",
        "wifi_ap_state",
        "device_system_state",
        "eq_profile",
        "media_file_state",
        "device_dial_metadata",
        "device_dial_custom",
        "touch_mode",
        "screen_light_time",
    }
    assert rows["main_chatgpt_action"].callback_operations == (
        "onGetChatgptAction",
    )
    assert rows["main_chatgpt_action"].scripted_fake_decoder_available is True
    assert rows["main_chatgpt_action"].input_eligible is False
    assert "exact 4E" in rows["main_chatgpt_action"].description
    assert "zero writes" in rows["main_chatgpt_action"].description
    assert "no fake-run request ownership" in rows["main_chatgpt_action"].description
    assert "protocol request relationship is unknown" in (
        rows["main_chatgpt_action"].description
    )
    assert "does not parse or retain prompt" in rows["main_chatgpt_action"].description
    assert rows["offline_speech_mode"].request_operations == (
        "queryOfflineSpeechRecognitionState",
        "setOfflineSpeechRecognitionState",
    )
    assert rows["raw_ai_state"].callback_operations == ("onGetAiState",)
    assert rows["raw_ai_state"].request_operations == (
        "openAiState",
        "queryAiState",
    )
    assert rows["raw_ai_command_type"].callback_operations == (
        "onGetAiCommandType",
    )
    assert rows["raw_voice_command_confirmation"].request_operations == ()
    assert rows["wifi_ssid_inventory"].privacy_classes == (
        "network_identifier",
    )
    assert rows["wifi_ssid_inventory"].scripted_fake_decoder_available is True
    assert rows["wifi_ssid_inventory"].runnable is False
    assert rows["wifi_ssid_inventory"].live_available is False
    assert rows["wifi_ssid_inventory"].hardware_eligible is False
    assert rows["wifi_ssid_inventory"].input_eligible is False
    assert "network_credential" in rows["wifi_ap_state"].privacy_classes
    assert "file_reference" in rows["media_file_state"].privacy_classes

    with pytest.raises(TypeError, match="closed"):
        NonHealthCapability(  # type: ignore[call-arg]
            "invented", "Invented", "general_use", "", "", "", "", False
        )
    with pytest.raises(FrozenInstanceError):
        rows["wifi_state"].label = "mutable"  # type: ignore[misc]
    assert "NonHealthCapability" not in repr(rows["wifi_state"])


def test_general_use_operation_links_exist_in_recovered_ledgers():
    rows = tuple(
        item
        for item in static_non_health_capabilities()
        if item.group == "general_use"
    )
    callback_names = set(CALLBACK_CODEC_LOCATORS) | {
        row.name for row in recovered_callback_behavior_surfaces()
    }

    assert {name for row in rows for name in row.request_operations} <= set(
        REQUEST_CODEC_LOCATORS
    )
    assert {name for row in rows for name in row.callback_operations} <= callback_names
    assert {name for row in rows for name in row.request_operations} == {
        "getDeviceDial",
        "getDeviceDialCustom",
        "getDeviceSystemStateInfo",
        "getEqInfo",
        "getMediaFileState",
        "openAiState",
        "openWifiApMode",
        "queryAiState",
        "queryOfflineSpeechRecognitionState",
        "scanWifi",
        "setAiCommandType",
        "setAiChatState",
        "setChatgptContent",
        "setDeviceDialState",
        "setDeviceWallpaperState",
        "setEqInfo2",
        "setOfflineSpeechRecognitionState",
        "setTouchMode",
        "setWifiHotSpotInfo",
        "setWifiHotSpotInfoEx",
        "SetScreenLightTime",
        "editDeviceDialCustom",
    }
    assert {name for row in rows for name in row.callback_operations} == {
        "onDeviceConnectedWifi",
        "onGetAiCommandType",
        "onGetAiState",
        "onGetChatgptAction",
        "onGetDeviceDial",
        "onGetDeviceDialCustom",
        "onGetDeviceFileState",
        "onGetEqInfo2",
        "onGetOfflineSpeechRecognitionMode",
        "onGetScreenLightTime",
        "onGetTouchMode",
        "onGetWifiSsid",
        "onGetWifiSsidCount",
        "onGetWifiState",
        "onNotifyDeviceSystemStateInfo",
        "onNotifyDeviceWifiApState",
        "onNotifyDialJsonContent",
        "onNotifyNewMediaInfo",
        "onRecvDeviceVoiceCommandConfirm",
        "onEditDeviceDialCustom",
        "onSetDeviceDialState",
        "onSetDeviceWallpaperState",
        "onSetEqInfo2",
    }


def test_all_thirteen_statically_mapped_device_actions_are_discoverable_once():
    inventory = {
        item.name: item
        for item in static_non_health_capabilities()
        if item.group == "device_actions"
    }
    decoded = {
        parse_vendor_device_action(bytes((0x06, code)) + bytes(18)).label
        for code in (1, 2, 4, 5, 8, 16, 32, 64, 65, 66, 67, 68, 69)
    }

    assert len(inventory) == 13
    assert set(inventory) == decoded
    assert {item.meaning for item in inventory.values()} == {
        "unverified_static_action_code"
    }
