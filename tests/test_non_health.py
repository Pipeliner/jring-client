from jring.non_health import static_non_health_capabilities


def test_non_health_inventory_exposes_evidence_maturity_and_live_boundaries():
    items = static_non_health_capabilities()
    by_name = {item.name: item for item in items}

    assert len(items) == len(by_name) == 11
    assert set(by_name) == {
        "standard_hid_metadata",
        "camera_shutter",
        "media_play_pause",
        "media_next",
        "media_previous",
        "volume_up",
        "volume_down",
        "cumulative_step_counter",
        "unknown_motion_channels",
        "raw_ai_actions",
        "raw_audio_or_image_payloads",
    }
    assert by_name["standard_hid_metadata"].evidence == "bluetooth_standard"
    assert by_name["standard_hid_metadata"].maturity == "selected_device_metadata"
    assert by_name["media_play_pause"].evidence == "static_apk"
    assert by_name["media_play_pause"].input_candidate is True
    assert by_name["cumulative_step_counter"].input_candidate is False
    assert by_name["unknown_motion_channels"].meaning == "unknown"
    assert by_name["unknown_motion_channels"].label == "Nine unknown motion channels"
    assert all(item.hardware_verified is False for item in items)
    assert all(item.live_available is False for item in items)
    assert all(item.input_eligible is False for item in items)


def test_non_health_inventory_is_immutable_and_contains_no_payloads():
    items = static_non_health_capabilities()

    assert isinstance(items, tuple)
    rendered = repr(items).lower()
    assert "payload=b" not in rendered
    assert "address" not in rendered
