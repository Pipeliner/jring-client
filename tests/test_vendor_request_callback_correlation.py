from collections import Counter
from dataclasses import FrozenInstanceError, asdict
import json

import pytest

from jring.vendor_codec_registry import REQUEST_CODEC_LOCATORS
from jring.vendor_app_use_evidence import (
    CallbackDispatchState,
    RequestAppUseState,
    recovered_vendor_app_use_evidence,
)
from jring.vendor_phone_integration import encode_sms_reply_ack
from jring.vendor_protocol import parse_vendor_sms_send
from jring.vendor_request_callback_correlation import (
    recovered_request_callback_correlations,
)


def test_every_deterministic_request_has_one_closed_correlation_row():
    evidence = recovered_request_callback_correlations()
    rows = {row.request: row for row in evidence.rows}

    assert len(evidence.rows) == len(rows) == 85
    assert set(rows) == set(REQUEST_CODEC_LOCATORS)
    assert all(row.relationship_state != "unspecified" for row in rows.values())
    assert all(row.callbacks or row.unresolved_reasons for row in rows.values())
    assert evidence.unspecified_count == 0
    assert evidence.explicitly_unresolved_count == 13
    assert evidence.rows_with_unresolved_reasons_count == 58
    assert Counter(row.relationship_state for row in evidence.rows) == {
        "exact_single": 47,
        "exact_branching": 1,
        "shared_stream": 6,
        "shared_stateful": 5,
        "event_candidate_unproven": 7,
        "same_opcode_event_candidate_unproven": 1,
        "shared_stateful_event_candidate_unproven": 1,
        "reverse_direction_pipeline": 1,
        "reverse_direction_pipeline_candidate_unproven": 2,
        "reverse_direction_event_ack_candidate_unproven": 1,
        "explicitly_unresolved": 13,
    }
    assert evidence.terminal_rule_counts == (
        ("local_quiet_unknown", 2),
        ("metadata_or_explicit_marker_else_local_quiet_unknown", 1),
        ("none_proven", 29),
        ("per_frame_only", 17),
        ("single_matched_response", 36),
    )
    assert evidence.runnable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False


def test_endpoint_partition_and_raw_candidates_are_explicitly_non_acknowledging():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}

    assert Counter((row.tx_role, row.rx_role) for row in rows.values()) == {
        ("main_tx", "main_rx"): 79,
        ("raw_tx", "raw_rx"): 6,
    }
    assert rows["connectAiServerNotification"].callbacks == ("onGetAiAction",)
    assert rows["openAiAudioState"].callbacks == ("onGetRawData",)
    assert rows["openAiState"].callbacks == ("onGetAiState",)
    assert rows["queryAiState"].callbacks == ("onGetAiState",)
    assert rows["setAiCommandType"].callbacks == ("onGetAiCommandType",)
    assert rows["setAiExtraAction"].callbacks == ()
    assert all(
        rows[name].terminal_rule == "none_proven"
        and rows[name].relationship_state == "event_candidate_unproven"
        for name in (
            "connectAiServerNotification", "openAiAudioState", "openAiState",
            "queryAiState", "setAiCommandType", "setAiExtraAction",
        )
    )


def test_single_ack_silent_failure_and_success_only_families_stay_distinct():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}

    assert rows["setDeviceTime"].callbacks == ("onSetDeviceTime",)
    assert rows["setDeviceTime"].failure_delivery == "direct_callback"
    assert rows["getCurSportData"].callbacks == ("onGetCurSportData",)
    assert rows["getCurSportData"].failure_delivery == "callback_silent"
    assert rows["setDeviceName"].callbacks == ("onSetDeviceName",)
    assert rows["setDeviceName"].failure_delivery == "none_proven"
    assert rows["setAlarm"].terminal_rule == "per_frame_only"


def test_streaming_shared_and_local_idle_rules_never_claim_success_from_quiet():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}

    assert rows["getMultipleSportData"].callbacks == (
        "onSetBloodPressureMode", "onGetMultipleSportData",
    )
    assert rows["getMultipleSportData"].multiplicity == "one_then_six_per_frame"
    assert rows["getOxygenOfflineData"].callbacks == (
        "onGetDataByDay", "onGetOxygenOfflineData", "onGetOxygenOfflineDataEnd",
    )
    assert rows["getOxygenOfflineData"].terminal_rule == "local_quiet_unknown"
    assert rows["getAdvSensorOfflineData"].terminal_rule == "local_quiet_unknown"
    assert rows["getDataByDay"].relationship_state == "shared_stream"
    assert rows["getEcgHistory"].terminal_rule == "none_proven"
    assert rows["scanWifi"].terminal_rule == "none_proven"
    assert all(row.quiet_means_success is False for row in rows.values())


def test_phone_volume_is_an_inbound_request_then_outbound_projection_not_an_ack():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}
    volume = rows["sendPhoneVolume"]

    assert volume.request_discriminator == (
        "inbound_opcode_49_onGetPhoneVolume_triggers_outbound_host_volume_projection"
    )
    assert volume.accepted_response_predicates == ()
    assert volume.callbacks == ("onGetPhoneVolume",)
    assert volume.multiplicity == "one_outbound_projection_per_inbound_callback"
    assert volume.terminal_rule == "none_proven"
    assert volume.failure_delivery == "none_proven"
    assert volume.relationship_state == "reverse_direction_pipeline"
    assert volume.shared_or_unsolicited is True
    assert volume.unresolved_reasons == (
        "outbound_projection_ack_and_terminal_not_proven",
    )
    assert volume.quiet_means_success is False

    phone_mac = rows["setPhoneMac"]
    assert phone_mac.request_discriminator == "statically_recovered_request_codec"
    assert phone_mac.accepted_response_predicates == ()
    assert phone_mac.callbacks == ()
    assert phone_mac.terminal_rule == "none_proven"
    assert phone_mac.relationship_state == "explicitly_unresolved"
    assert phone_mac.unresolved_reasons == (
        "exact_response_relationship_not_statically_closed",
    )


def test_contact_crc_is_same_opcode_event_candidate_not_an_ack():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}
    contact = rows["setContactCrc"]

    assert contact.request_discriminator == "outbound_opcode_46_four_byte_fingerprint"
    assert contact.accepted_response_predicates == (
        "inbound_opcode_46_four_byte_fingerprint",
    )
    assert contact.callbacks == ("onNotifyContactCrc",)
    assert contact.multiplicity == "zero_or_more_same_opcode_notifications"
    assert contact.terminal_rule == "none_proven"
    assert contact.failure_delivery == "none_proven"
    assert contact.relationship_state == "same_opcode_event_candidate_unproven"
    assert contact.shared_or_unsolicited is True
    assert contact.unresolved_reasons == (
        "notification_is_not_proven_to_acknowledge_request",
    )
    assert contact.quiet_means_success is False


def test_sms_send_is_reverse_direction_event_ack_candidate_not_a_response():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}
    sms = rows["setSmsRspSendAck"]

    assert sms.request_discriminator == (
        "inbound_opcode_4d_subcommand_06_event_and_outbound_subcommand_07_candidate"
    )
    assert sms.accepted_response_predicates == ()
    assert sms.callbacks == ("onNotifySmsRspSend",)
    assert sms.multiplicity == "inbound_event_and_outbound_ack_multiplicity_not_proven"
    assert sms.terminal_rule == "none_proven"
    assert sms.failure_delivery == "none_proven"
    assert sms.relationship_state == "reverse_direction_event_ack_candidate_unproven"
    assert sms.shared_or_unsolicited is True
    assert sms.unresolved_reasons == (
        "callback_value_to_ack_value_propagation_not_proven",
        "app_ack_invoke_not_observed",
        "local_sms_side_effect_and_ack_order_not_proven",
        "outbound_ack_response_and_terminal_not_proven",
    )
    assert sms.quiet_means_success is False
    assert "onNotifySmsRspNeedUpdate" not in sms.callbacks

    evidence = recovered_request_callback_correlations()
    assert evidence.runnable is False
    assert evidence.python_callable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False


def test_sms_event_ack_candidate_is_anchored_to_direction_and_app_use_evidence():
    app_use = recovered_vendor_app_use_evidence()
    requests = {row.name: row for row in app_use.requests}
    callbacks = {row.name: row for row in app_use.callbacks}

    request_use = requests["setSmsRspSendAck"]
    assert request_use.state is RequestAppUseState.SDK_WIRE_ENTRY_WITHOUT_APP_INVOKE
    assert request_use.direct_invoke_count == 0
    callback_use = callbacks["onNotifySmsRspSend"]
    assert callback_use.state is CallbackDispatchState.DIRECT_INVOKE_OBSERVED
    assert callback_use.invoke_counts == (1, 0, 0)

    outbound = encode_sms_reply_ack(reply_id=200).synthetic_frames_for_test()[0]
    assert outbound[:3] == bytes((0x4D, 0x07, 0xC8))
    inbound = parse_vendor_sms_send(
        bytes((0x4D, 0x06, 0x07, 0x02)) + b"ABC" + bytes(13)
    )
    assert inbound.value == 7
    assert inbound.declared_text_length == 2
    assert inbound.text_redacted is True


def test_weather_motion_and_chat_topologies_are_non_terminal_event_candidates():
    rows = {row.request: row for row in recovered_request_callback_correlations().rows}

    weather = rows["sendWeather"]
    assert weather.request_discriminator == (
        "inbound_opcode_22_weather_refresh_and_outbound_cached_weather_"
        "projection_candidate"
    )
    assert weather.accepted_response_predicates == ()
    assert weather.callbacks == ("onGetDeviceAction",)
    assert weather.multiplicity == (
        "refresh_event_and_weather_record_multiplicity_not_proven"
    )
    assert weather.relationship_state == "reverse_direction_pipeline_candidate_unproven"
    assert weather.unresolved_reasons == (
        "opcode_06_also_projects_device_actions",
        "refresh_to_weather_call_order_and_batch_count_not_proven",
        "local_location_acquisition_not_reproduced",
        "outbound_weather_response_and_terminal_not_proven",
    )

    motion = rows["setGSensorIndState"]
    assert motion.request_discriminator == (
        "outbound_opcode_78_boolean_subcommand_00_or_01"
    )
    assert motion.accepted_response_predicates == (
        "inbound_opcode_78_runtime_subcommand_00_or_01",
    )
    assert motion.callbacks == ("onGetGSensorData",)
    assert motion.multiplicity == "zero_or_more_motion_candidate_frames"
    assert motion.relationship_state == "shared_stateful_event_candidate_unproven"
    assert motion.unresolved_reasons == (
        "setter_app_invoke_not_observed",
        "opcode_78_is_shared_with_known_non_motion_subcommands",
        "selector_meaning_axes_and_enable_delivery_causation_not_proven",
        "disable_behavior_and_terminal_not_proven",
    )

    chat_state = rows["setAiChatState"]
    assert chat_state.accepted_response_predicates == ("opcode_4e_action_event",)
    assert chat_state.callbacks == ("onGetChatgptAction",)
    assert chat_state.multiplicity == "zero_or_more_notifications"
    assert chat_state.relationship_state == "event_candidate_unproven"
    assert chat_state.unresolved_reasons == (
        "setter_app_invoke_not_observed",
        "opcode_or_field_correlation_and_temporal_order_not_proven",
        "shared_opcode_54_enable_disable_ownership_not_proven",
        "action_event_terminal_not_proven",
    )

    chat_content = rows["setChatgptContent"]
    assert chat_content.request_discriminator == (
        "inbound_opcode_4e_action_and_outbound_opcode_4f_content_candidate"
    )
    assert chat_content.accepted_response_predicates == ()
    assert chat_content.callbacks == ("onGetChatgptAction",)
    assert chat_content.multiplicity == (
        "action_event_and_content_frame_multiplicity_not_proven"
    )
    assert chat_content.relationship_state == (
        "reverse_direction_pipeline_candidate_unproven"
    )
    assert chat_content.unresolved_reasons == (
        "content_request_app_invoke_not_observed",
        "action_to_content_type_value_mapping_and_call_order_not_proven",
        "fragment_batch_failure_and_terminal_not_proven",
        "local_ai_execution_not_reproduced",
    )

    for row in (weather, motion, chat_state, chat_content):
        assert row.terminal_rule == "none_proven"
        assert row.failure_delivery == "none_proven"
        assert row.shared_or_unsolicited is True
        assert row.quiet_means_success is False
        assert not row.relationship_state.startswith("exact_")


def test_correlation_evidence_is_closed_sanitized_and_non_authorizing():
    evidence = recovered_request_callback_correlations()
    row = evidence.rows[0]

    with pytest.raises(TypeError):
        type(evidence)()
    with pytest.raises(TypeError):
        type(row)()
    with pytest.raises(FrozenInstanceError):
        row.request = "changed"
    rendered = json.dumps(asdict(evidence), sort_keys=True).lower()
    for forbidden in (".smali", "sha256", "bluetooth address", "captured payload"):
        assert forbidden not in rendered
    assert evidence.matching_rules == (
        "bind_operation_token_and_connection_generation",
        "require_endpoint_opcode_and_subcommand_or_marker",
        "do_not_refresh_deadline_for_unrelated_or_unsolicited_events",
        "never_promote_silence_or_local_quiet_to_success",
        "never_retry_after_an_uncertain_write",
    )
