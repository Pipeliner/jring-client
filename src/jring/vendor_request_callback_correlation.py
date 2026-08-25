"""Closed static request-to-callback correlation evidence.

This ledger does not turn callback eligibility into transaction ownership.  It records
exactly what the reviewed dispatcher can project, including ambiguity, silence, and
unknown completion, without storing packets or constructing a transport.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .vendor_codec_registry import REQUEST_CODEC_LOCATORS


@dataclass(frozen=True, init=False, repr=False)
class RequestCallbackCorrelationRow:
    request: str
    tx_role: str
    rx_role: str
    request_discriminator: str
    accepted_response_predicates: tuple[str, ...]
    callbacks: tuple[str, ...]
    multiplicity: str
    terminal_rule: str
    failure_delivery: str
    relationship_state: str
    shared_or_unsolicited: bool
    unresolved_reasons: tuple[str, ...]
    quiet_means_success: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request/callback correlation rows are closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredRequestCallbackCorrelations:
    rows: tuple[RequestCallbackCorrelationRow, ...]
    matching_rules: tuple[str, ...]
    global_limitations: tuple[str, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request/callback correlation evidence is closed")

    @property
    def unspecified_count(self) -> int:
        return sum(row.relationship_state == "unspecified" for row in self.rows)

    @property
    def explicitly_unresolved_count(self) -> int:
        return sum(
            row.relationship_state == "explicitly_unresolved" for row in self.rows
        )

    @property
    def rows_with_unresolved_reasons_count(self) -> int:
        """Count every caveated row, not only statically unclosed relationships."""

        return sum(bool(row.unresolved_reasons) for row in self.rows)

    @property
    def terminal_rule_counts(self) -> tuple[tuple[str, int], ...]:
        """Return the complete terminal-rule denominator in stable order."""

        counts = Counter(row.terminal_rule for row in self.rows)
        return tuple(sorted(counts.items()))

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

    @property
    def owner_authorized(self) -> bool:
        return False


_RAW_REQUESTS = frozenset({
    "connectAiServerNotification", "openAiAudioState", "openAiState",
    "queryAiState", "setAiCommandType", "setAiExtraAction",
})


def _make_row(
    request: str,
    *,
    rx_role: str | None = None,
    request_discriminator: str = "statically_recovered_request_codec",
    predicates: tuple[str, ...] = (),
    callbacks: tuple[str, ...] = (),
    multiplicity: str = "none_proven",
    terminal_rule: str = "none_proven",
    failure_delivery: str = "none_proven",
    state: str = "explicitly_unresolved",
    shared: bool = False,
    unresolved: tuple[str, ...] = (),
) -> RequestCallbackCorrelationRow:
    raw = request in _RAW_REQUESTS
    if not callbacks and not unresolved:
        unresolved = ("exact_response_relationship_not_statically_closed",)
    row = object.__new__(RequestCallbackCorrelationRow)
    values = {
        "request": request,
        "tx_role": "raw_tx" if raw else "main_tx",
        "rx_role": rx_role or ("raw_rx" if raw else "main_rx"),
        "request_discriminator": request_discriminator,
        "accepted_response_predicates": predicates,
        "callbacks": callbacks,
        "multiplicity": multiplicity,
        "terminal_rule": terminal_rule,
        "failure_delivery": failure_delivery,
        "relationship_state": state,
        "shared_or_unsolicited": shared,
        "unresolved_reasons": unresolved,
        "quiet_means_success": False,
    }
    for name, value in values.items():
        object.__setattr__(row, name, value)
    return row


def _single(
    callback: str,
    *predicates: str,
    failure: str = "none_proven",
    terminal: str = "single_matched_response",
    unresolved: tuple[str, ...] = (),
) -> dict[str, object]:
    return {
        "predicates": tuple(predicates),
        "callbacks": (callback,),
        "multiplicity": "one_per_matching_frame",
        "terminal_rule": terminal,
        "failure_delivery": failure,
        "state": "exact_single",
        "unresolved": unresolved,
    }


def _private_sync_candidate(
    discriminator: str,
    callback: str,
    multiplicity: str,
    batch_kind: str,
    *,
    opcode_shared: bool = False,
) -> dict[str, object]:
    unresolved = (
        "need_update_to_outbound_request_causation_and_order_not_proven",
        "need_update_does_not_select_crc_versus_content",
        "callback_blob_to_outbound_record_or_fingerprint_propagation_not_proven",
        "local_private_store_access_not_reproduced",
        f"{batch_kind}_batch_failure_and_terminal_not_proven",
    )
    if opcode_shared:
        unresolved += ("opcode_4d_is_shared_with_sms_send_and_ack_candidates",)
    return {
        "request_discriminator": discriminator,
        "predicates": (),
        "callbacks": (callback,),
        "multiplicity": multiplicity,
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "reverse_direction_pipeline_candidate_unproven",
        "shared": True,
        "unresolved": unresolved,
    }


def _wifi_private_state_candidate(*, extended: bool) -> dict[str, object]:
    discriminator = (
        "outbound_opcode_54_subcommands_01_02_private_credential_fragments_"
        "and_inbound_subcommand_04_wifi_state_candidate"
    )
    unresolved = (
        "request_to_state_event_causation_and_order_not_proven",
        "credential_and_state_selectors_are_disjoint",
        "basic_and_extended_requests_have_identical_wire_identity",
        "network_join_credential_use_failure_and_terminal_not_proven",
        "host_network_and_ftp_side_effects_not_reproduced",
        "setter_app_invoke_not_observed",
    )
    if extended:
        discriminator += "_with_unreproduced_local_timeout"
        unresolved += ("timeout_timer_and_callback_state_not_reproduced",)
    return {
        "request_discriminator": discriminator,
        "predicates": (),
        "callbacks": ("onGetWifiState",),
        "multiplicity": (
            "credential_fragment_batch_and_wifi_state_events_not_operation_bound"
        ),
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "shared_stateful_event_candidate_unproven",
        "shared": True,
        "unresolved": unresolved,
    }


_OVERRIDES: dict[str, dict[str, object]] = {
    "getCurSportData": _single("onGetCurSportData", "success_opcode_03_or_13", "failure_opcode_83", failure="callback_silent"),
    "getDeviceBatery": _single("onGetDeviceBatery", "success_opcode_0b", "failure_opcode_8b", failure="callback_silent"),
    "getDeviceInfo": _single("onGetDeviceInfo", "success_opcode_0c", "failure_opcode_8c", failure="callback_silent"),
    "getBandFunction": _single("onGetBandFunction", "success_opcode_20", "failure_opcode_a0", failure="direct_callback"),
    "getDeviceCode": _single("onGetDeviceCode", "success_opcode_1f", "failure_opcode_9f", failure="direct_callback"),
    "getDeviceDial": _single("onGetDeviceDial", "opcode_34"),
    "getDeviceDialCustom": _single("onGetDeviceDialCustom", "opcode_42"),
    "getDeviceSystemStateInfo": _single("onNotifyDeviceSystemStateInfo", "opcode_54_subcommand_12"),
    "getEqInfo": _single("onGetEqInfo2", "opcode_53_get_kind"),
    "getMediaFileState": _single("onGetDeviceFileState", "opcode_54_subcommand_06"),
    "queryOfflineSpeechRecognitionState": _single("onGetOfflineSpeechRecognitionMode", "opcode_78_subcommand_0c", unresolved=("decoder_family_is_shared_with_setter_subcommand_03",)),
    "SetScreenLightTime": _single("onGetScreenLightTime", "opcode_78_subcommand_0b"),
    "getMultipleSportData": {
        "predicates": ("opcode_25", "failure_opcode_a5_requires_marker_ff"),
        "callbacks": ("onSetBloodPressureMode", "onGetMultipleSportData"),
        "multiplicity": "one_then_six_per_frame",
        "terminal_rule": "none_proven", "failure_delivery": "conditional_callback",
        "state": "shared_stream", "shared": True,
        "unresolved": ("opcode_25_is_shared_with_sensor_mode_success", "history_terminal_not_proven"),
    },
    "getOxygenOfflineData": {
        "predicates": ("opcode_40",),
        "callbacks": ("onGetDataByDay", "onGetOxygenOfflineData", "onGetOxygenOfflineDataEnd"),
        "multiplicity": "fifteen_generic_and_fifteen_specialized_per_frame_then_local_end",
        "terminal_rule": "local_quiet_unknown", "failure_delivery": "none_proven",
        "state": "shared_stream", "shared": True,
        "unresolved": ("wire_terminal_not_proven", "end_projection_is_local_not_wire"),
    },
    "getAdvSensorOfflineData": {
        "predicates": ("opcode_55",),
        "callbacks": ("onGetDataByDay", "onGetAdvSensorOfflineData", "onGetAdvSensorOfflineDataEnd"),
        "multiplicity": "three_generic_and_three_specialized_per_frame_then_local_end",
        "terminal_rule": "local_quiet_unknown", "failure_delivery": "none_proven",
        "state": "shared_stream", "shared": True,
        "unresolved": ("wire_terminal_not_proven", "end_projection_is_local_not_wire"),
    },
    "getDataByDay": {
        "request_discriminator": "kind_selects_opcodes_10_16_39_40",
        "predicates": ("opcode_10_or_11", "opcode_16_marker", "opcode_39", "opcode_40", "failures_90_96_b9"),
        "callbacks": ("onGetDataByDay", "onGetDataByDayEnd", "onGetOxygenOfflineData"),
        "multiplicity": "kind_and_marker_dependent_stream",
        "terminal_rule": "metadata_or_explicit_marker_else_local_quiet_unknown",
        "failure_delivery": "direct_callback_for_90_96_b9",
        "state": "shared_stream", "shared": True,
        "unresolved": ("kinds_1_12_13_have_no_proven_normal_wire_terminal",),
    },
    "getEcgHistory": {
        "predicates": ("metadata_opcode_2c", "event_opcode_2d", "history_data_opcode_2e"),
        "callbacks": ("onGetEcgHistory", "onGetEcgStartEnd", "onGetEcgHistoryData"),
        "multiplicity": "one_metadata_then_zero_or_more_events_and_samples",
        "terminal_rule": "none_proven", "failure_delivery": "none_proven",
        "state": "shared_stream", "shared": True,
        "unresolved": ("start_end_event_terminal_semantics_not_proven",),
    },
    "scanWifi": {
        "predicates": ("opcode_54_subcommand_09_count", "opcode_54_subcommand_0a_fragments"),
        "callbacks": ("onGetWifiSsidCount", "onGetWifiSsid"),
        "multiplicity": "one_count_then_zero_or_more_fragment_assembled_entries",
        "terminal_rule": "none_proven", "failure_delivery": "none_proven",
        "state": "shared_stream", "shared": True,
        "unresolved": ("whole_scan_terminal_not_proven",),
    },
    "sendPhoneVolume": {
        "request_discriminator": (
            "inbound_opcode_49_onGetPhoneVolume_triggers_outbound_host_volume_projection"
        ),
        "predicates": (),
        "callbacks": ("onGetPhoneVolume",),
        "multiplicity": "one_outbound_projection_per_inbound_callback",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "reverse_direction_pipeline",
        "shared": True,
        "unresolved": ("outbound_projection_ack_and_terminal_not_proven",),
    },
    "setPhoneMac": {
        "request_discriminator": (
            "outbound_opcode_49_private_phone_identifier_is_distinct_from_"
            "inbound_opcode_49_host_volume_request"
        ),
        "predicates": (),
        "callbacks": (),
        "multiplicity": "none_proven",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "same_opcode_semantic_collision_no_correlation",
        "shared": True,
        "unresolved": (
            "exact_response_relationship_not_statically_closed",
            "inbound_opcode_49_belongs_to_reverse_phone_volume_pipeline",
            "private_identifier_payload_not_response_data",
        ),
    },
    "setAppId": {
        "request_discriminator": (
            "outbound_opcode_48_private_app_identifier_and_inbound_opcode_45_"
            "selector_02_app_id_event_candidate"
        ),
        "predicates": ("inbound_opcode_45_selector_02_app_id_event",),
        "callbacks": ("onNotifyAppId",),
        "multiplicity": "zero_or_more_notifications",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "event_candidate_unproven",
        "shared": True,
        "unresolved": (
            "setter_to_notification_causation_and_order_not_proven",
            "outbound_to_inbound_identifier_propagation_not_proven",
            "outbound_and_inbound_text_layouts_differ",
            "opcode_45_is_shared_with_classic_info_and_name",
            "notification_failure_and_terminal_not_proven",
        ),
    },
    "notifyDownloadFtpFileCompleted": {
        "rx_role": "local_service_projection",
        "request_discriminator": (
            "source_media_ftp_terminal_path_emits_outbound_opcode_54_subcommand_07"
        ),
        "predicates": (),
        "callbacks": ("onNotifyFtpStateInfo",),
        "multiplicity": (
            "source_terminal_signal_and_local_callback_projection_not_operation_bound"
        ),
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "event_candidate_unproven",
        "shared": True,
        "unresolved": (
            "success_and_exhausted_failure_share_terminal_signal",
            "callback_payload_to_terminal_signal_mapping_not_closed",
            "wire_ack_and_terminal_not_proven",
            "ftp_network_file_retry_and_local_side_effects_not_reproduced",
        ),
    },
    "setWifiHotSpotInfo": _wifi_private_state_candidate(extended=False),
    "setWifiHotSpotInfoEx": _wifi_private_state_candidate(extended=True),
    "setContactCrc": {
        "request_discriminator": "outbound_opcode_46_four_byte_fingerprint",
        "predicates": ("inbound_opcode_46_four_byte_fingerprint",),
        "callbacks": ("onNotifyContactCrc",),
        "multiplicity": "zero_or_more_same_opcode_notifications",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "same_opcode_event_candidate_unproven",
        "shared": True,
        "unresolved": ("notification_is_not_proven_to_acknowledge_request",),
    },
    "setSmsRspSendAck": {
        "request_discriminator": (
            "inbound_opcode_4d_subcommand_06_event_and_outbound_"
            "subcommand_07_candidate"
        ),
        "predicates": (),
        "callbacks": ("onNotifySmsRspSend",),
        "multiplicity": "inbound_event_and_outbound_ack_multiplicity_not_proven",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "reverse_direction_event_ack_candidate_unproven",
        "shared": True,
        "unresolved": (
            "callback_value_to_ack_value_propagation_not_proven",
            "app_ack_invoke_not_observed",
            "local_sms_side_effect_and_ack_order_not_proven",
            "outbound_ack_response_and_terminal_not_proven",
        ),
    },
    "sendWeather": {
        "request_discriminator": (
            "inbound_opcode_22_weather_refresh_and_outbound_cached_weather_"
            "projection_candidate"
        ),
        "predicates": (),
        "callbacks": ("onGetDeviceAction",),
        "multiplicity": "refresh_event_and_weather_record_multiplicity_not_proven",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "reverse_direction_pipeline_candidate_unproven",
        "shared": True,
        "unresolved": (
            "opcode_06_also_projects_device_actions",
            "refresh_to_weather_call_order_and_batch_count_not_proven",
            "local_location_acquisition_not_reproduced",
            "outbound_weather_response_and_terminal_not_proven",
        ),
    },
    "setGSensorIndState": {
        "request_discriminator": "outbound_opcode_78_boolean_subcommand_00_or_01",
        "predicates": ("inbound_opcode_78_runtime_subcommand_00_or_01",),
        "callbacks": ("onGetGSensorData",),
        "multiplicity": "zero_or_more_motion_candidate_frames",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "shared_stateful_event_candidate_unproven",
        "shared": True,
        "unresolved": (
            "setter_app_invoke_not_observed",
            "opcode_78_is_shared_with_known_non_motion_subcommands",
            "selector_meaning_axes_and_enable_delivery_causation_not_proven",
            "disable_behavior_and_terminal_not_proven",
        ),
    },
    "setAiChatState": {
        "predicates": ("opcode_4e_action_event",),
        "callbacks": ("onGetChatgptAction",),
        "multiplicity": "zero_or_more_notifications",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "event_candidate_unproven",
        "shared": True,
        "unresolved": (
            "setter_app_invoke_not_observed",
            "opcode_or_field_correlation_and_temporal_order_not_proven",
            "shared_opcode_54_enable_disable_ownership_not_proven",
            "action_event_terminal_not_proven",
        ),
    },
    "setChatgptContent": {
        "request_discriminator": (
            "inbound_opcode_4e_action_and_outbound_opcode_4f_content_candidate"
        ),
        "predicates": (),
        "callbacks": ("onGetChatgptAction",),
        "multiplicity": "action_event_and_content_frame_multiplicity_not_proven",
        "terminal_rule": "none_proven",
        "failure_delivery": "none_proven",
        "state": "reverse_direction_pipeline_candidate_unproven",
        "shared": True,
        "unresolved": (
            "content_request_app_invoke_not_observed",
            "action_to_content_type_value_mapping_and_call_order_not_proven",
            "fragment_batch_failure_and_terminal_not_proven",
            "local_ai_execution_not_reproduced",
        ),
    },
    "setECardInfoCrc": _private_sync_candidate(
        "outbound_opcode_4c_subcommands_01_02_and_inbound_subcommand_03_"
        "private_sync_candidate",
        "onNotifyECardNeedUpdate",
        "update_event_and_crc_frame_multiplicity_not_proven",
        "crc",
    ),
    "setECardInfoContent": _private_sync_candidate(
        "outbound_opcode_4c_subcommands_04_05_and_inbound_subcommand_03_"
        "private_sync_candidate",
        "onNotifyECardNeedUpdate",
        "update_event_and_content_frame_multiplicity_not_proven",
        "content",
    ),
    "setSmsRspInfoCrc": _private_sync_candidate(
        "outbound_opcode_4d_subcommands_01_02_and_inbound_subcommand_03_"
        "private_sync_candidate",
        "onNotifySmsRspNeedUpdate",
        "update_event_and_crc_frame_multiplicity_not_proven",
        "crc",
        opcode_shared=True,
    ),
    "setSmsRspInfoContent": _private_sync_candidate(
        "outbound_opcode_4d_subcommand_04_and_inbound_subcommand_03_"
        "private_sync_candidate",
        "onNotifySmsRspNeedUpdate",
        "update_event_and_content_frame_multiplicity_not_proven",
        "content",
        opcode_shared=True,
    ),
}


for _request, _callback, _success, _failure in (
    ("setDeviceTime", "onSetDeviceTime", "01", "81"),
    ("setUserInfo", "onSetUserInfo", "02", "82"),
    ("sendVibrationSignal", "onSendVibrationSignal", "04", "84"),
    ("setAntiLost", "onSetAntiLost", "05", "85"),
    ("setPhontMode", "onSetPhontMode", "07", "87"),
    ("setIdleTime", "onSetIdleTime", "08", "88"),
    ("setSleepTime", "onSetSleepTime", "09", "89"),
    ("setAlarm", "onSetAlarm", "0d", "8d"),
    ("setDeviceMode", "onSetDeviceMode", "0e", "8e"),
    ("setAutoHeartMode", "setAutoHeartMode", "19", "99"),
    ("setGoalStep", "onSetGoalStep", "1a", "9a"),
    ("setDeviceInfo", "onSetDeviceInfo", "1b", "9b"),
    ("setHourFormat", "onSetHourFormat", "1d", "9d"),
    ("setDeviceCode", "onSetDeviceCode", "1e", "9e"),
    ("setLanguage", "onSetLanguage", "21", "a1"),
    ("setDeviceHeartRateArea", "onSetDeviceHeartRateArea", "26", "a6"),
):
    _OVERRIDES[_request] = _single(
        _callback, f"success_opcode_{_success}", f"failure_opcode_{_failure}",
        failure="direct_callback",
        terminal="per_frame_only" if _request == "setAlarm" else "single_matched_response",
        unresolved=("high_level_batch_terminal_not_proven",) if _request == "setAlarm" else (),
    )


for _request, _callback, _opcode in (
    ("setDeviceName", "onSetDeviceName", "30"),
    ("setReminder", "onSetReminder", "31"),
    ("setReminderText", "onSetReminderText", "32"),
    ("setBPAdjust", "onSetBPAdjust", "33"),
    ("setDeviceDialState", "onSetDeviceDialState", "35"),
    ("setDeviceWallpaperState", "onSetDeviceWallpaperState", "36"),
    ("editDeviceDialCustom", "onEditDeviceDialCustom", "41"),
    ("setFemaleReminder", "onSetFemaleReminder", "44"),
):
    _OVERRIDES[_request] = _single(
        _callback, f"success_opcode_{_opcode}", failure="none_proven",
        unresolved=("failure_branch_not_proven",),
    )


for _request, _callback, _predicate in (
    ("setEcgMode", "onSetEcgMode", "opcode_2a"),
    ("setEqInfo2", "onSetEqInfo2", "opcode_53_set_kind"),
    ("setTemperatureMode", "onSetTemperatureMode", "opcode_37"),
    ("setBloodOxygenMode", "onSetBloodOxygenMode", "opcode_3e"),
    ("setTouchMode", "onGetTouchMode", "opcode_78_subcommand_09"),
    ("setOfflineSpeechRecognitionState", "onGetOfflineSpeechRecognitionMode", "opcode_78_subcommand_03"),
    ("setAiConnectionMethod", "onNotifyAiConnectionMethod", "opcode_54_subcommand_14"),
    ("setBindedInfo", "onNotifyBindedInfo", "opcode_4b"),
    ("openWifiApMode", "onNotifyDeviceWifiApState", "opcode_54_subcommand_13"),
    ("setWorshipInfo", "onGetWorshipInfo", "opcode_78_subcommand_07"),
    ("startFactoryTestMode", "onGetFactoryTestData", "opcode_50"),
):
    _OVERRIDES[_request] = _single(
        _callback, _predicate, terminal="per_frame_only",
        unresolved=("callback_is_value_or_event_projection_not_explicit_ack",),
    )


_OVERRIDES["setNotify"] = {
    "predicates": ("opcode_12_marker_matches_request", "failure_opcode_92"),
    "callbacks": ("onSetNotify",), "multiplicity": "planner_state_dependent",
    "terminal_rule": "per_frame_only", "failure_delivery": "direct_callback",
    "state": "shared_stateful", "shared": True,
    "unresolved": ("high_level_multi_frame_terminal_not_proven",),
}

for _request in ("setBloodPressureMode", "setSpoMode", "setSugarMode", "setPressureMode"):
    _OVERRIDES[_request] = {
        "request_discriminator": "wrapper_and_start_selector_or_shared_stop_zero",
        "predicates": ("success_opcode_23", "shared_success_opcode_25", "failure_opcode_a3"),
        "callbacks": ("onSetBloodPressureMode",), "multiplicity": "one_per_matching_frame",
        "terminal_rule": "per_frame_only", "failure_delivery": "direct_callback",
        "state": "shared_stateful", "shared": True,
        "unresolved": ("opcode_25_also_projects_multiple_sport_samples", "stop_frame_loses_wrapper_identity"),
    }

_OVERRIDES["setHeartRateMode"] = {
    "request_discriminator": "start_opcode_14_or_stop_opcode_15",
    "predicates": ("success_14_or_15", "failure_94_or_95"),
    "callbacks": ("onGetSenserData",), "multiplicity": "one_per_matching_frame",
    "terminal_rule": "single_matched_response", "failure_delivery": "direct_callback",
    "state": "exact_branching", "unresolved": (),
}

for _request, _callbacks, _predicate in (
    ("connectAiServerNotification", ("onGetAiAction",), "raw_type_0001"),
    ("openAiAudioState", ("onGetRawData",), "raw_type_0002_or_0003"),
    ("openAiState", ("onGetAiState",), "raw_type_0006"),
    ("queryAiState", ("onGetAiState",), "raw_type_0006"),
    ("setAiCommandType", ("onGetAiCommandType",), "raw_type_000a"),
    ("setAiExtraAction", (), "no_response_type_handler"),
):
    _OVERRIDES[_request] = {
        "predicates": (_predicate,), "callbacks": _callbacks,
        "multiplicity": "zero_or_more_notifications", "terminal_rule": "none_proven",
        "failure_delivery": "none_proven", "state": "event_candidate_unproven",
        "shared": True,
        "unresolved": ("typed_notification_is_not_proven_to_acknowledge_request",),
    }


_ROWS = tuple(
    _make_row(request, **_OVERRIDES.get(request, {}))
    for request in REQUEST_CODEC_LOCATORS
)

_EVIDENCE = object.__new__(RecoveredRequestCallbackCorrelations)
object.__setattr__(_EVIDENCE, "rows", _ROWS)
object.__setattr__(_EVIDENCE, "matching_rules", (
    "bind_operation_token_and_connection_generation",
    "require_endpoint_opcode_and_subcommand_or_marker",
    "do_not_refresh_deadline_for_unrelated_or_unsolicited_events",
    "never_promote_silence_or_local_quiet_to_success",
    "never_retry_after_an_uncertain_write",
))
object.__setattr__(_EVIDENCE, "global_limitations", (
    "no_wire_transaction_identifier",
    "source_response_wait_state_is_not_operation_bound",
    "write_callback_status_is_ignored",
    "callback_arrival_is_not_peripheral_acknowledgement",
    "hardware_timing_and_support_are_unverified",
))


def recovered_request_callback_correlations() -> RecoveredRequestCallbackCorrelations:
    """Return immutable sanitized request/callback correlation evidence."""

    return _EVIDENCE


__all__ = [
    "RecoveredRequestCallbackCorrelations",
    "RequestCallbackCorrelationRow",
    "recovered_request_callback_correlations",
]
