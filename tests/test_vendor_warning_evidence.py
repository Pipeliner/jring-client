from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_warning_evidence as warning_module
from jring.vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)
from jring.vendor_warning_evidence import (
    ComparisonState,
    InstructionFactScope,
    InstructionReviewState,
    WarningAuditScope,
    WarningComparisonCode,
    WarningComparisonEvidence,
    WarningScopeEvidence,
    recovered_warning_audit,
)


def _comparisons():
    return {item.code: item for item in recovered_warning_audit().comparisons}


def test_warning_audit_accounts_for_owned_scope_without_inflating_interfaces():
    audit = recovered_warning_audit()
    scopes = {item.scope: item for item in audit.scopes}

    assert scopes[WarningAuditScope.APPLICATION].selected_file_count == 11
    assert scopes[WarningAuditScope.APPLICATION].warning_occurrence_count == 29
    assert scopes[WarningAuditScope.EMBEDDED_SDK].selected_file_count == 21
    assert scopes[WarningAuditScope.EMBEDDED_SDK].warning_occurrence_count == 62
    assert scopes[WarningAuditScope.EXCLUDED_DEPENDENCY].selected_file_count == 5
    assert scopes[WarningAuditScope.EXCLUDED_DEPENDENCY].warning_occurrence_count is None
    assert audit.interface_entries is False
    assert len(static_vendor_operation_coverage()) == 112
    assert len(static_vendor_callback_coverage()) == 105


def test_application_warning_partition_keeps_risk_exclusion_and_sites_distinct():
    app = next(
        item for item in recovered_warning_audit().scopes
        if item.scope is WarningAuditScope.APPLICATION
    )

    assert app.high_risk_warning_occurrences == 14
    assert app.low_risk_warning_occurrences == 3
    assert app.excluded_warning_occurrences == 12
    assert (
        app.high_risk_warning_occurrences
        + app.low_risk_warning_occurrences
        + app.excluded_warning_occurrences
        == app.warning_occurrence_count
    )
    assert app.retained_method_site_count == 7
    assert app.retained_file_count == 6
    assert app.warning_occurrence_count != app.retained_method_site_count


def test_sdk_warning_partition_preserves_kind_and_consequence_axes():
    sdk = next(
        item for item in recovered_warning_audit().scopes
        if item.scope is WarningAuditScope.EMBEDDED_SDK
    )

    assert sdk.warning_kind_counts == (
        ("rename_collision", 27),
        ("duplicated_control_flow", 12),
        ("type_inference", 21),
        ("unsupported_multi_entry_loop", 1),
        ("instruction_removed_from_duplicate", 1),
    )
    assert sum(count for _kind, count in sdk.warning_kind_counts) == 62
    assert sdk.low_risk_file_count == 12
    assert sdk.medium_risk_file_count == 4
    assert sdk.high_risk_file_count == 5
    assert sdk.low_risk_file_count + sdk.medium_risk_file_count + sdk.high_risk_file_count == 21


def test_same_tool_dispatch_surface_corroboration_does_not_validate_branches():
    dispatch = _comparisons()[WarningComparisonCode.SDK_MAIN_DISPATCH_LABEL_SURFACE]

    assert dispatch.comparison_state is ComparisonState.SAME_TOOL_SURFACE_CORROBORATION
    assert dispatch.surface_item_count == 85
    assert dispatch.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
    assert dispatch.instruction_fact_scope is InstructionFactScope.INTRAPROCEDURAL
    assert dispatch.reviewed_span_count == 1
    assert dispatch.reviewed_occurrence_count == 125
    assert "not switch labels or cases" in dispatch.observation
    assert dispatch.semantic_correctness_established is False
    assert "branch_opcode_and_field_semantics_remain_unresolved" in dispatch.limitations


def test_instruction_review_resolves_selector_and_receiver_control_flow_only():
    comparisons = _comparisons()

    selector = comparisons[WarningComparisonCode.APP_OTA_SELECTOR_DIVERGENCE]
    assert selector.comparison_state is ComparisonState.COMPARISON_DIVERGENCE
    assert selector.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
    assert selector.instruction_fact_scope is InstructionFactScope.INTRAPROCEDURAL
    assert selector.reviewed_span_count == 1
    assert selector.public_fact_eligible is True
    assert "hardware_meaning_and_acceptance_remain_unverified" in selector.limitations

    for code in (
        WarningComparisonCode.APP_CLASSIC_ATTACHMENT_RECEIVER,
        WarningComparisonCode.APP_OTA_EVENT_RECEIVER,
        WarningComparisonCode.APP_SPORT_SENSOR_RECEIVER,
    ):
        item = comparisons[code]
        assert item.comparison_state is ComparisonState.FALLBACK_BODY_UNAVAILABLE
        assert item.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
        assert item.reviewed_span_count >= 1
        assert item.public_fact_eligible is True


def test_progress_named_handoff_is_not_relabelled_as_numeric_ota_progress():
    progress = _comparisons()[WarningComparisonCode.SDK_OTA_PROGRESS_FORWARDING]

    assert progress.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
    assert progress.instruction_fact_scope is InstructionFactScope.INTERPROCEDURAL
    assert progress.reviewed_span_count == 7
    assert "GATT object" in progress.observation
    assert "numeric percentage" in progress.observation
    assert "generation_guard_not_present_in_reviewed_handoff" in progress.limitations


def test_ota_patch_and_dormant_dial_transfer_stay_separate_and_non_runnable():
    comparisons = _comparisons()
    patch = comparisons[WarningComparisonCode.SDK_OTA_PATCH_ADVANCE]
    dial = comparisons[WarningComparisonCode.SDK_DORMANT_DIAL_TRANSFER_CALL_SITE]

    assert patch.related_requests == ("startFileOta",)
    assert patch.comparison_state is ComparisonState.INSTRUCTION_REVIEW_REQUIRED
    assert patch.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
    assert patch.instruction_fact_scope is InstructionFactScope.INTERPROCEDURAL
    assert patch.reviewed_span_count == 5
    assert "local_completion_is_not_peripheral_acknowledgement" in patch.limitations
    assert dial.related_requests == ("editDeviceDialCustom",)
    assert dial.comparison_state is ComparisonState.NO_OBSERVED_INTERFACE_CALL_SITE
    assert dial.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
    assert dial.instruction_fact_scope is InstructionFactScope.WHOLE_CORPUS_SEARCH
    assert dial.reviewed_span_count == 23
    assert dial.public_fact_eligible is True
    assert "runtime_generated_or_external_activation_not_exhaustively_disproved" in (
        dial.limitations
    )
    assert "does_not_authorize_or_model_dial_file_transfer" in dial.limitations
    assert len(static_vendor_operation_coverage()) == 112


def test_warning_evidence_is_closed_aggregate_only_and_without_authority():
    audit = recovered_warning_audit()

    for model in (WarningScopeEvidence, WarningComparisonEvidence, type(audit)):
        with pytest.raises(TypeError):
            model()
    with pytest.raises(FrozenInstanceError):
        audit.comparisons = ()

    assert audit.source_recovery_completeness == "not_established"
    assert audit.semantic_correctness_established is False
    assert audit.instruction_review_complete is False
    assert audit.target_review_count == 8
    assert audit.bounded_fact_confirmed_count == 8
    assert audit.bounded_fact_contradicted_count == 0
    assert audit.inconclusive_review_count == 0
    assert audit.instruction_review_not_performed_count == 0
    assert audit.all_target_reviews_attempted is True
    assert audit.all_bounded_facts_resolved is True

    for item in audit.comparisons:
        assert item.public_fact_eligible is (
            item.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
        )
    assert audit.exhaustive_bluetooth_dependency_audit is False
    assert audit.runnable is False
    assert audit.python_callable is False
    assert audit.hardware_eligible is False
    assert audit.hardware_verified is False

    forbidden = {
        "class_name", "file_name", "method_name", "path", "source", "warning_text",
        "dex_digest", "descriptor", "prototype", "fingerprint", "instruction_offset",
    }
    for model in (WarningScopeEvidence, WarningComparisonEvidence, type(audit)):
        assert forbidden.isdisjoint(field.name for field in fields(model))
    source = inspect.getsource(warning_module).lower()
    assert "import pathlib" not in source
    assert "import subprocess" not in source
    assert "open(" not in source

    serialized = json.dumps(
        [asdict(item) for item in audit.comparisons], sort_keys=True
    ).lower()
    for private_token in (
        "sha-256", "sha256", "classes.dex", "classes2.dex", "classes3.dex",
        "descriptor", "prototype", "fingerprint", "instruction_offset", ".smali",
    ):
        assert private_token not in serialized
