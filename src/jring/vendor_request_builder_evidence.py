"""Sanitized static evidence for the 37 reproduced request-builder families.

The ledger describes byte parity only inside each Python encoder's accepted input
domain.  It neither exposes captured frames nor reproduces the source queue, policy,
logging, or transport machinery.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, init=False, repr=False)
class RequestBuilderEvidenceRow:
    family: str
    public_operations: tuple[str, ...]
    module: str
    python_symbol: str
    frame_length: int
    checksum: str
    endpoint_role: str
    queue_item_type: int
    enqueue_position: str
    layout: str
    source_domain: str
    python_domain: str
    divergence_reasons: tuple[str, ...]
    batch_combinator_symbol: str | None
    source_pre_enqueue_effects: tuple[str, ...]
    source_pre_enqueue_effects_reproduced: bool | None
    byte_parity_scope: str

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request-builder evidence rows are closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredRequestBuilderEvidence:
    families: tuple[RequestBuilderEvidenceRow, ...]
    main_queue_facts: tuple[str, ...]
    raw_queue_facts: tuple[str, ...]
    omitted_runtime_behavior: tuple[str, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request-builder evidence is closed")

    @property
    def byte_exact_family_count(self) -> int:
        return len(self.families)

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


def _row(
    family: str,
    public_operations: tuple[str, ...],
    module: str,
    python_symbol: str,
    layout: str,
    source_domain: str,
    python_domain: str,
    divergences: tuple[str, ...] = (),
    *,
    raw: bool = False,
    front: bool = False,
    batch_combinator_symbol: str | None = None,
    effects: tuple[str, ...] = (),
    effects_reproduced: bool | None = None,
) -> RequestBuilderEvidenceRow:
    value = object.__new__(RequestBuilderEvidenceRow)
    values = {
        "family": family,
        "public_operations": public_operations,
        "module": module,
        "python_symbol": python_symbol,
        "frame_length": 20,
        "checksum": "none",
        "endpoint_role": "raw" if raw else "main",
        "queue_item_type": 1 if raw else 0,
        "enqueue_position": "front" if front else "tail",
        "layout": layout,
        "source_domain": source_domain,
        "python_domain": python_domain,
        "divergence_reasons": divergences,
        "batch_combinator_symbol": batch_combinator_symbol,
        "source_pre_enqueue_effects": effects,
        "source_pre_enqueue_effects_reproduced": effects_reproduced,
        "byte_parity_scope": "accepted_python_domain",
    }
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value


_VP = "jring.vendor_protocol"
_VS = "jring.vendor_settings"
_VB = "jring.vendor_behavior_settings"
_VPS = "jring.vendor_personal_settings"
_VR = "jring.vendor_raw_protocol"

_NO_ARG_SOURCE = "source_public_method_has_no_caller_payload"
_CLOSED_QUERY = "closed_enum_binding_with_no_caller_payload"
_LOW_BYTE = "source_integer_is_reduced_to_its_low_byte"
_STRICT_U8 = "non_boolean_integer_between_0_and_255"
_BOOL_SOURCE = "source_primitive_boolean"
_STRICT_BOOL = "python_boolean_only"


_ROWS = (
    _row("query_current_sport", ("getCurSportData",), _VP, "encode_static_query[StaticQuery.CURRENT_SPORT]", "opcode_then_zero_padding", _NO_ARG_SOURCE, _CLOSED_QUERY, ("python_binding_closes_operation_choice",)),
    _row("query_battery", ("getDeviceBatery",), _VP, "encode_static_query[StaticQuery.BATTERY]", "opcode_then_zero_padding", _NO_ARG_SOURCE, _CLOSED_QUERY, ("python_binding_closes_operation_choice",)),
    _row("query_device_info", ("getDeviceInfo",), _VP, "encode_static_query[StaticQuery.DEVICE_INFO]", "opcode_then_zero_padding", _NO_ARG_SOURCE, _CLOSED_QUERY, ("python_binding_closes_operation_choice",)),
    _row("query_band_functions", ("getBandFunction",), _VP, "encode_static_query[StaticQuery.BAND_FUNCTIONS]", "opcode_then_zero_padding", _NO_ARG_SOURCE, _CLOSED_QUERY, ("python_binding_closes_operation_choice",)),
    _row("query_multi_sport_day", ("getMultipleSportData",), _VP, "encode_day_query[StaticQuery.MULTI_SPORT_DAY]", "opcode_day_then_zero_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping_and_booleans",)),
    _row("query_oxygen_day", ("getOxygenOfflineData",), _VP, "encode_day_query[StaticQuery.OXYGEN_DAY]", "opcode_day_then_zero_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping_and_booleans",)),
    _row("query_advanced_sensor_day", ("getAdvSensorOfflineData",), _VP, "encode_day_query[StaticQuery.ADVANCED_SENSOR_DAY]", "opcode_day_then_zero_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping_and_booleans",)),
    _row("device_settings", ("setDeviceInfo",), _VS, "encode_device_settings", "opcode_flags_quiet_hours_inverted_calling_wear_brightness", "retained_options_with_primitive_booleans_and_raw_integers", "explicit_booleans_valid_clocks_and_closed_enums", ("python_requires_an_explicit_snapshot", "python_rejects_invalid_brightness_fallback", "calling_bit_remains_intentionally_inverted")),
    _row("hour_format", ("setHourFormat",), _VS, "encode_hour_format", "opcode_format_then_zero_padding", _LOW_BYTE, "closed_enum_zero_or_one", ("python_rejects_other_low_byte_values",)),
    _row("device_code", ("setDeviceCode",), _VS, "encode_device_code", "opcode_identifier_bytes_then_padding", "byte_array_may_be_empty_or_truncated_after_19", "immutable_bytes_length_1_through_19", ("python_rejects_empty_and_truncation",)),
    _row("language", ("setLanguage",), _VS, "encode_language", "opcode_language_tag_then_padding", "implicit_host_locale_with_source_specific_fallback_and_truncation", "explicit_canonical_language_region_utf8_tag", ("python_requires_explicit_locale", "python_rejects_split_or_truncated_utf8")),
    _row("sensor_session_start", ("setBloodPressureMode(true)", "setSpoMode(true)", "setSugarMode(true)", "setPressureMode(true)"), _VS, "encode_sensor_session_start", "opcode_closed_selector_then_zero_padding", "four_boolean_wrappers_select_fixed_integer_modes", "neutral_closed_selector_enum", ("python_does_not_claim_sensor_meaning", "source_queue_priority_is_evidence_only"), front=True),
    _row("sensor_session_stop", ("setBloodPressureMode(false)", "setSpoMode(false)", "setSugarMode(false)", "setPressureMode(false)"), _VS, "encode_sensor_session_stop", "opcode_zero_then_zero_padding", "four_wrappers_collapse_to_the_same_zero_selector", "single_identity_free_stop_encoder", ("per_wrapper_stop_identity_is_not_on_wire", "source_queue_priority_is_evidence_only"), front=True),
    _row("heart_rate_area", ("setDeviceHeartRateArea",), _VS, "encode_heart_rate_area", "opcode_enabled_two_neutral_bounds_then_padding", "primitive_boolean_and_two_low_byte_integers", "boolean_and_two_bounded_neutral_u8_values", ("python_rejects_wrapping_and_untyped_boolean",)),
    _row("device_name", ("setDeviceName",), _VS, "encode_device_name", "opcode_name_bytes_then_padding", "platform_charset_empty_allowed_and_byte_truncation_at_11", "nonempty_normalized_printable_utf8_up_to_11_bytes", ("python_uses_explicit_utf8", "python_rejects_empty_split_or_truncated_text")),
    _row("vibration", ("sendVibrationSignal",), _VB, "VibrationRequest", "opcode_count_then_zero_padding", "integer_outside_0_through_10_defaults_to_10", "non_boolean_integer_0_through_10", ("python_rejects_source_defaulting",)),
    _row("anti_lost", ("setAntiLost",), _VB, "AntiLostRequest", "opcode_boolean_then_zero_padding", _BOOL_SOURCE, _STRICT_BOOL, ("python_enforces_exact_boolean_type",)),
    _row("camera_mode", ("setPhontMode",), _VB, "CameraModeRequest", "opcode_boolean_then_zero_padding", _BOOL_SOURCE, _STRICT_BOOL, ("python_enforces_exact_boolean_type",)),
    _row("idle_reminder", ("setIdleTime",), _VB, "IdleReminderRequest", "opcode_interval_le32_start_end_then_padding", "signed_integer_interval_and_four_low_byte_clock_fields", "disabled_zero_or_1_through_240_minutes_with_valid_clocks", ("python_limits_inputs_to_observed_ui_domain",)),
    _row("sleep_schedule", ("setSleepTime",), _VB, "SleepScheduleRequest", "opcode_four_clock_pairs_then_padding", "eight_low_byte_clock_integers", "four_valid_clock_values", ("python_rejects_wrapping_and_invalid_clocks",)),
    _row("alarm", ("setAlarm",), _VB, "AlarmRequest", "one_base_frame_then_zero_to_three_text_chunk_frames_per_alarm", "retained_mutable_unbounded_alarm_list_with_raw_fields_and_utf8_truncation", "explicit_atomic_batch_of_1_through_16_unique_typed_alarms", ("python_rejects_text_truncation", "python_validates_before_returning_any_frame", "source_sequential_partial_enqueue_is_not_reproduced", "source_private_logging_is_not_reproduced"), batch_combinator_symbol="jring.vendor_behavior_settings:AlarmBatchRequest"),
    _row("device_mode", ("setDeviceMode",), _VB, "DeviceModeRequest", "opcode_eight_byte_mode_constant_then_padding", "integer_1_through_4_else_zero_body", "closed_four_value_enum", ("python_rejects_invalid_zero_body_fallback",)),
    _row("auto_heart_schedule", ("setAutoHeartMode",), _VB, "AutoHeartScheduleRequest", "opcode_clock_pairs_enabled_interval_modulo_255_constant_then_padding", "low_byte_clocks_boolean_modulo_255_interval_and_one_ignored_argument", "valid_clocks_boolean_interval_1_through_254_without_ignored_argument", ("python_omits_ignored_argument", "python_rejects_wrapping_and_modulo_aliases")),
    _row("goal_step", ("setGoalStep",), _VB, "GoalStepRequest", "opcode_steps_le32_then_zero_padding", "any_signed_java_integer", "non_boolean_1000_through_20000_in_1000_steps", ("python_limits_inputs_to_observed_ui_domain",)),
    _row("reminder", ("setReminder",), _VPS, "encode_reminder", "opcode_interval_le32_clock_pairs_two_neutral_bytes_then_padding", "signed_interval_and_low_byte_clock_and_neutral_fields", "zero_or_observed_minute_interval_valid_clocks_and_strict_u8", ("python_limits_inputs_to_observed_ui_domain", "python_rejects_wrapping")),
    _row("reminder_text", ("setReminderText",), _VPS, "encode_reminder_text", "opcode_index_utf8_text_then_padding", "platform_charset_low_byte_index_and_byte_truncation_at_18", "strict_u8_index_and_explicit_utf8_up_to_18_without_nul", ("python_rejects_split_or_truncated_text", "python_uses_explicit_utf8")),
    _row("bp_adjust", ("setBPAdjust",), _VPS, "encode_bp_adjust", "opcode_two_le16_values_then_padding", "two_integers_reduced_to_low_16_bits", "observed_picker_ranges_with_order_constraint", ("python_limits_inputs_to_observed_ui_domain", "python_rejects_wrapping")),
    _row("device_dial_state", ("setDeviceDialState",), _VPS, "encode_device_dial_state", "opcode_state_then_zero_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping", "source_queue_mutations_are_not_reproduced"), effects=("set_internal_mode_flag", "clear_ordinary_command_queue", "clear_current_retained_frame"), effects_reproduced=False),
    _row("device_wallpaper_state", ("setDeviceWallpaperState",), _VPS, "encode_device_wallpaper_state", "opcode_state_then_zero_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping_and_booleans",)),
    _row("edit_device_dial_custom", ("editDeviceDialCustom",), _VPS, "encode_edit_device_dial_custom", "opcode_four_neutral_bytes_then_padding", "four_low_byte_integers", "four_strict_neutral_u8_values", ("python_rejects_wrapping_and_booleans",)),
    _row("female_reminder", ("setFemaleReminder",), _VPS, "encode_female_reminder", "opcode_year_le16_date_length_period_enabled_then_padding", "primitive_boolean_low_16_bit_year_and_low_byte_fields_without_validation", "explicit_as_of_valid_date_observed_ranges_and_boolean", ("python_limits_inputs_to_observed_ui_domain", "python_rejects_invalid_dates_and_wrapping")),
    _row("ai_server_notification", ("connectAiServerNotification",), _VR, "encode_raw_ai_server_notification", "raw_envelope_type_0001_boolean_mapping_then_padding", _BOOL_SOURCE, _STRICT_BOOL, ("python_enforces_exact_boolean_type",), raw=True),
    _row("ai_extra_action", ("setAiExtraAction",), _VR, "encode_raw_ai_extra_action", "raw_envelope_type_0004_argument_then_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping_and_booleans",), raw=True),
    _row("ai_state", ("openAiState",), _VR, "encode_raw_ai_state", "raw_envelope_type_0005_boolean_then_padding", _BOOL_SOURCE, _STRICT_BOOL, ("python_enforces_exact_boolean_type",), raw=True),
    _row("ai_state_query", ("queryAiState",), _VR, "encode_raw_ai_state_query", "raw_envelope_type_0007_zero_then_padding", _NO_ARG_SOURCE, _NO_ARG_SOURCE, raw=True),
    _row("ai_audio_state", ("openAiAudioState",), _VR, "encode_raw_ai_audio_state", "raw_envelope_type_0008_boolean_then_padding", _BOOL_SOURCE, _STRICT_BOOL, ("python_enforces_exact_boolean_type",), raw=True),
    _row("ai_command_type", ("setAiCommandType",), _VR, "encode_raw_ai_command_type", "raw_envelope_type_000a_argument_then_padding", _LOW_BYTE, _STRICT_U8, ("python_rejects_wrapping_and_booleans",), raw=True),
)


_EVIDENCE = object.__new__(RecoveredRequestBuilderEvidence)
object.__setattr__(_EVIDENCE, "families", _ROWS)
object.__setattr__(_EVIDENCE, "main_queue_facts", (
    "source_policy_status_gate_precedes_construction",
    "connection_gate_precedes_type_zero_enqueue",
    "full_frame_logging_precedes_enqueue",
    "queue_drain_is_requested_after_enqueue",
    "these_families_do_not_use_the_special_history_or_sync_filters",
))
object.__setattr__(_EVIDENCE, "raw_queue_facts", (
    "source_policy_status_gate_precedes_construction",
    "connection_gate_precedes_type_one_enqueue",
    "full_frame_logging_precedes_tail_enqueue",
    "queue_drain_is_requested_after_enqueue",
))
object.__setattr__(_EVIDENCE, "omitted_runtime_behavior", (
    "policy_and_connection_gates",
    "queue_mutation_and_drain",
    "source_logging",
    "retry_and_delivery_outcomes",
))


def recovered_request_builder_evidence() -> RecoveredRequestBuilderEvidence:
    """Return the closed, sanitized, offline-only request-builder ledger."""

    return _EVIDENCE


__all__ = [
    "RecoveredRequestBuilderEvidence",
    "RequestBuilderEvidenceRow",
    "recovered_request_builder_evidence",
]
