from collections import Counter
from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_request_builder_evidence as evidence_module
from jring.vendor_request_builder_evidence import recovered_request_builder_evidence


EXPECTED_FAMILIES = {
    "query_current_sport",
    "query_battery",
    "query_device_info",
    "query_band_functions",
    "query_multi_sport_day",
    "query_oxygen_day",
    "query_advanced_sensor_day",
    "device_settings",
    "hour_format",
    "device_code",
    "language",
    "sensor_session_start",
    "sensor_session_stop",
    "heart_rate_area",
    "device_name",
    "vibration",
    "anti_lost",
    "camera_mode",
    "idle_reminder",
    "sleep_schedule",
    "alarm",
    "device_mode",
    "auto_heart_schedule",
    "goal_step",
    "reminder",
    "reminder_text",
    "bp_adjust",
    "device_dial_state",
    "device_wallpaper_state",
    "edit_device_dial_custom",
    "female_reminder",
    "ai_server_notification",
    "ai_extra_action",
    "ai_state",
    "ai_state_query",
    "ai_audio_state",
    "ai_command_type",
}


def test_all_thirty_seven_reviewed_request_builder_families_are_accounted_for():
    evidence = recovered_request_builder_evidence()

    assert len(evidence.families) == 37
    assert {row.family for row in evidence.families} == EXPECTED_FAMILIES
    assert Counter(row.module for row in evidence.families) == {
        "jring.vendor_protocol": 7,
        "jring.vendor_settings": 8,
        "jring.vendor_behavior_settings": 9,
        "jring.vendor_personal_settings": 7,
        "jring.vendor_raw_protocol": 6,
    }


def test_every_builder_row_separates_wire_queue_and_domain_evidence():
    evidence = recovered_request_builder_evidence()

    assert all(row.frame_length == 20 for row in evidence.families)
    assert all(row.checksum == "none" for row in evidence.families)
    assert all(row.endpoint_role in {"main", "raw"} for row in evidence.families)
    assert all(row.queue_item_type in {0, 1} for row in evidence.families)
    assert all(row.enqueue_position in {"front", "tail"} for row in evidence.families)
    assert all(
        row.byte_parity_scope == "accepted_python_domain"
        for row in evidence.families
    )
    assert all(row.public_operations for row in evidence.families)
    assert all(row.python_symbol for row in evidence.families)
    assert all(row.source_domain for row in evidence.families)
    assert all(row.python_domain for row in evidence.families)
    assert all(
        row.source_domain == row.python_domain or row.divergence_reasons
        for row in evidence.families
    )
    assert evidence.byte_exact_family_count == 37
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False


def test_queue_topology_matches_the_reviewed_builder_partition():
    rows = {row.family: row for row in recovered_request_builder_evidence().families}

    assert Counter(
        (row.endpoint_role, row.queue_item_type, row.enqueue_position)
        for row in rows.values()
    ) == {
        ("main", 0, "tail"): 29,
        ("main", 0, "front"): 2,
        ("raw", 1, "tail"): 6,
    }
    assert {
        row.family for row in rows.values() if row.enqueue_position == "front"
    } == {"sensor_session_start", "sensor_session_stop"}
    assert rows["alarm"].batch_combinator_symbol == (
        "jring.vendor_behavior_settings:AlarmBatchRequest"
    )
    assert all(
        row.batch_combinator_symbol is None
        for family, row in rows.items()
        if family != "alarm"
    )


def test_dial_pre_enqueue_mutation_is_exact_and_not_reproduced():
    rows = {row.family: row for row in recovered_request_builder_evidence().families}
    dial = rows["device_dial_state"]

    assert dial.source_pre_enqueue_effects == (
        "set_internal_mode_flag",
        "clear_ordinary_command_queue",
        "clear_current_retained_frame",
    )
    assert dial.source_pre_enqueue_effects_reproduced is False
    assert all(
        row.source_pre_enqueue_effects == ()
        and row.source_pre_enqueue_effects_reproduced is None
        for family, row in rows.items()
        if family != "device_dial_state"
    )


def test_builder_evidence_is_closed_sanitized_static_and_non_runnable():
    evidence = recovered_request_builder_evidence()
    row = evidence.families[0]

    with pytest.raises(TypeError):
        type(evidence)()
    with pytest.raises(TypeError):
        type(row)()
    with pytest.raises(FrozenInstanceError):
        row.family = "changed"
    assert evidence.runnable is False
    assert evidence.python_callable is False
    forbidden = {
        "path",
        "hash",
        "instruction_offset",
        "dex_digest",
        "payload",
        "frame_bytes",
    }
    for model in (type(evidence), type(row)):
        assert forbidden.isdisjoint(field.name for field in fields(model))
    serialized = json.dumps(asdict(evidence), sort_keys=True).lower()
    assert "sha256" not in serialized
    assert ".smali" not in serialized
    source = inspect.getsource(evidence_module).lower()
    assert "bleak" not in source
    assert "open(" not in source
    assert "subprocess" not in source
