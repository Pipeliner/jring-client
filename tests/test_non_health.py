from jring.non_health import static_non_health_capabilities
from jring.vendor_protocol import parse_vendor_device_action


def test_non_health_inventory_exposes_evidence_maturity_and_live_boundaries():
    items = static_non_health_capabilities()
    by_name = {item.name: item for item in items}

    assert len(items) == len(by_name) == 23
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
        "classic_rfcomm_ota_transport",
        "classic_bt_info_callback",
        "classic_bt_name_callback",
        "host_volume_state_request",
    }
    assert by_name["standard_hid_metadata"].evidence == "bluetooth_standard"
    assert by_name["standard_hid_metadata"].maturity == "selected_device_metadata"
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
    assert by_name["classic_profile_attachment"].group == "classic_bluetooth"
    assert by_name["classic_rfcomm_ota_transport"].meaning == "file_transfer_transport"
    assert by_name["classic_bt_info_callback"].maturity == "offline_decoder"
    assert by_name["classic_bt_name_callback"].meaning == "private_classic_metadata"
    assert by_name["host_volume_state_request"].group == "host_integration"
    assert "discards" in by_name["raw_ai_actions"].description
    assert "discards" in by_name["unknown_motion_channels"].description
    assert all(item.hardware_verified is False for item in items)
    assert all(item.live_available is False for item in items)
    assert all(item.input_eligible is False for item in items)


def test_non_health_inventory_is_immutable_and_contains_no_payloads():
    items = static_non_health_capabilities()

    assert isinstance(items, tuple)
    rendered = repr(items).lower()
    assert "payload=b" not in rendered
    assert "address" not in rendered


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
