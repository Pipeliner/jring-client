"""Closed aggregate evidence for warning-bearing Bluetooth recovery regions.

The two decompiler modes share one tool and can corroborate only a visible surface.
Comparison never substitutes for bounded instruction review or hardware evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WarningAuditScope(str, Enum):
    APPLICATION = "application"
    EMBEDDED_SDK = "embedded_sdk"
    EXCLUDED_DEPENDENCY = "excluded_dependency"


class ComparisonState(str, Enum):
    SAME_TOOL_SURFACE_CORROBORATION = "same_tool_surface_corroboration"
    COMPARISON_DIVERGENCE = "comparison_divergence"
    FALLBACK_BODY_UNAVAILABLE = "fallback_body_unavailable"
    INSTRUCTION_REVIEW_REQUIRED = "instruction_review_required"
    NO_OBSERVED_INTERFACE_CALL_SITE = "no_observed_interface_call_site"


class InstructionReviewState(str, Enum):
    NOT_PERFORMED = "not_performed"
    BOUNDED_FACT_CONFIRMED = "bounded_fact_confirmed"
    BOUNDED_FACT_CONTRADICTED = "bounded_fact_contradicted"
    INCONCLUSIVE = "inconclusive"


class InstructionFactScope(str, Enum):
    NOT_REVIEWED = "not_reviewed"
    INTRAPROCEDURAL = "intraprocedural"
    INTERPROCEDURAL = "interprocedural"
    WHOLE_CORPUS_SEARCH = "whole_corpus_search"


class WarningComparisonCode(str, Enum):
    SDK_MAIN_DISPATCH_LABEL_SURFACE = "sdk_main_dispatch_label_surface"
    SDK_OTA_PROGRESS_FORWARDING = "sdk_ota_progress_forwarding"
    APP_OTA_SELECTOR_DIVERGENCE = "app_ota_selector_divergence"
    APP_CLASSIC_ATTACHMENT_RECEIVER = "app_classic_attachment_receiver"
    APP_OTA_EVENT_RECEIVER = "app_ota_event_receiver"
    APP_SPORT_SENSOR_RECEIVER = "app_sport_sensor_receiver"
    SDK_OTA_PATCH_ADVANCE = "sdk_ota_patch_advance"
    SDK_DORMANT_DIAL_TRANSFER_CALL_SITE = "sdk_dormant_dial_transfer_call_site"


def _closed_instance(model: type, **values: object) -> object:
    instance = object.__new__(model)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


@dataclass(frozen=True, init=False, repr=False)
class WarningScopeEvidence:
    scope: WarningAuditScope
    selected_file_count: int
    warning_occurrence_count: int | None
    retained_file_count: int | None
    retained_method_site_count: int | None
    high_risk_warning_occurrences: int
    low_risk_warning_occurrences: int
    excluded_warning_occurrences: int
    low_risk_file_count: int
    medium_risk_file_count: int
    high_risk_file_count: int
    warning_kind_counts: tuple[tuple[str, int], ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("warning scope evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class WarningComparisonEvidence:
    code: WarningComparisonCode
    scope: WarningAuditScope
    comparison_state: ComparisonState
    instruction_review: InstructionReviewState
    instruction_fact_scope: InstructionFactScope
    reviewed_span_count: int
    reviewed_occurrence_count: int | None
    surface_item_count: int | None
    related_requests: tuple[str, ...]
    related_callbacks: tuple[str, ...]
    observation: str
    limitations: tuple[str, ...]
    public_fact_eligible: bool
    semantic_correctness_established: bool
    hardware_verified: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("warning comparison evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredWarningAudit:
    scopes: tuple[WarningScopeEvidence, ...]
    comparisons: tuple[WarningComparisonEvidence, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use recovered_warning_audit()")

    @property
    def source_recovery_completeness(self) -> str:
        return "not_established"

    @property
    def semantic_correctness_established(self) -> bool:
        return False

    @property
    def instruction_review_complete(self) -> bool:
        return False

    @property
    def target_review_count(self) -> int:
        return len(self.comparisons)

    @property
    def bounded_fact_confirmed_count(self) -> int:
        return sum(
            item.instruction_review is InstructionReviewState.BOUNDED_FACT_CONFIRMED
            for item in self.comparisons
        )

    @property
    def bounded_fact_contradicted_count(self) -> int:
        return sum(
            item.instruction_review is InstructionReviewState.BOUNDED_FACT_CONTRADICTED
            for item in self.comparisons
        )

    @property
    def inconclusive_review_count(self) -> int:
        return sum(
            item.instruction_review is InstructionReviewState.INCONCLUSIVE
            for item in self.comparisons
        )

    @property
    def instruction_review_not_performed_count(self) -> int:
        return sum(
            item.instruction_review is InstructionReviewState.NOT_PERFORMED
            for item in self.comparisons
        )

    @property
    def all_target_reviews_attempted(self) -> bool:
        return self.instruction_review_not_performed_count == 0

    @property
    def all_bounded_facts_resolved(self) -> bool:
        return self.all_target_reviews_attempted and self.inconclusive_review_count == 0

    @property
    def exhaustive_bluetooth_dependency_audit(self) -> bool:
        return False

    @property
    def interface_entries(self) -> bool:
        return False

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def evidence_scope(self) -> str:
        return "owned_scope_warning_triage"

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

    def __repr__(self) -> str:
        return (
            "RecoveredWarningAudit("
            f"scope_count={len(self.scopes)}, comparison_count={len(self.comparisons)}, "
            "semantic_correctness_established=False, hardware_verified=False)"
        )


def _scope(
    scope: WarningAuditScope,
    *,
    selected_files: int,
    warnings: int | None,
    retained_files: int | None = None,
    retained_sites: int | None = None,
    high_warnings: int = 0,
    low_warnings: int = 0,
    excluded_warnings: int = 0,
    low_files: int = 0,
    medium_files: int = 0,
    high_files: int = 0,
    kinds: tuple[tuple[str, int], ...] = (),
) -> WarningScopeEvidence:
    return _closed_instance(
        WarningScopeEvidence,
        scope=scope,
        selected_file_count=selected_files,
        warning_occurrence_count=warnings,
        retained_file_count=retained_files,
        retained_method_site_count=retained_sites,
        high_risk_warning_occurrences=high_warnings,
        low_risk_warning_occurrences=low_warnings,
        excluded_warning_occurrences=excluded_warnings,
        low_risk_file_count=low_files,
        medium_risk_file_count=medium_files,
        high_risk_file_count=high_files,
        warning_kind_counts=kinds,
    )


_SCOPES = (
    _scope(
        WarningAuditScope.APPLICATION,
        selected_files=11,
        warnings=29,
        retained_files=6,
        retained_sites=7,
        high_warnings=14,
        low_warnings=3,
        excluded_warnings=12,
        kinds=(
            ("duplicated_control_flow", 13),
            ("type_inference", 5),
            ("string_switch_reconstruction", 6),
            ("instruction_removed_from_duplicate", 2),
            ("rename_collision", 3),
        ),
    ),
    _scope(
        WarningAuditScope.EMBEDDED_SDK,
        selected_files=21,
        warnings=62,
        low_files=12,
        medium_files=4,
        high_files=5,
        kinds=(
            ("rename_collision", 27),
            ("duplicated_control_flow", 12),
            ("type_inference", 21),
            ("unsupported_multi_entry_loop", 1),
            ("instruction_removed_from_duplicate", 1),
        ),
    ),
    _scope(
        WarningAuditScope.EXCLUDED_DEPENDENCY,
        selected_files=5,
        warnings=None,
    ),
)


def _comparison(
    code: WarningComparisonCode,
    scope: WarningAuditScope,
    state: ComparisonState,
    observation: str,
    limitations: tuple[str, ...],
    *,
    count: int | None = None,
    requests: tuple[str, ...] = (),
    callbacks: tuple[str, ...] = (),
    instruction_review: InstructionReviewState = InstructionReviewState.NOT_PERFORMED,
    fact_scope: InstructionFactScope = InstructionFactScope.NOT_REVIEWED,
    reviewed_spans: int = 0,
    reviewed_occurrences: int | None = None,
    public_fact: bool = False,
) -> WarningComparisonEvidence:
    return _closed_instance(
        WarningComparisonEvidence,
        code=code,
        scope=scope,
        comparison_state=state,
        instruction_review=instruction_review,
        instruction_fact_scope=fact_scope,
        reviewed_span_count=reviewed_spans,
        reviewed_occurrence_count=reviewed_occurrences,
        surface_item_count=count,
        related_requests=requests,
        related_callbacks=callbacks,
        observation=observation,
        limitations=limitations,
        public_fact_eligible=public_fact,
        semantic_correctness_established=False,
        hardware_verified=False,
    )


_COMPARISONS = (
    _comparison(
        WarningComparisonCode.SDK_MAIN_DISPATCH_LABEL_SURFACE,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.SAME_TOOL_SURFACE_CORROBORATION,
        "instruction review confirms 85 unique direct callback targets across 125 "
        "syntactic invokes, of which 124 are reachable; an ordered comparison chain "
        "covers 104 distinct opcode literals and contains no switch",
        (
            "semantic_meanings_and_hardware_behavior_remain_unresolved",
            "unreviewed_helper_effects_remain_unresolved",
            "static_route_presence_does_not_establish_runtime_reachability",
        ),
        count=85,
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTRAPROCEDURAL,
        reviewed_spans=1,
        reviewed_occurrences=125,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.SDK_OTA_PROGRESS_FORWARDING,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.SAME_TOOL_SURFACE_CORROBORATION,
        "instruction review identifies the progress-named edge as a GATT object "
        "handoff rather than a numeric percentage callback",
        (
            "generation_guard_not_present_in_reviewed_handoff",
            "handoff_does_not_prove_transfer_or_session_correctness",
        ),
        requests=("startFileOta",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTERPROCEDURAL,
        reviewed_spans=7,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.APP_OTA_SELECTOR_DIVERGENCE,
        WarningAuditScope.APPLICATION,
        ComparisonState.COMPARISON_DIVERGENCE,
        "the decompiler modes disagree, while instruction review confirms two "
        "recognized selector branches converge on one local write-attempt sequence",
        (
            "packing_helper_internals_not_part_of_this_bounded_fact",
            "hardware_meaning_and_acceptance_remain_unverified",
            "dispatch_result_does_not_prove_delivery",
        ),
        requests=("startFileOta",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTRAPROCEDURAL,
        reviewed_spans=1,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.APP_CLASSIC_ATTACHMENT_RECEIVER,
        WarningAuditScope.APPLICATION,
        ComparisonState.FALLBACK_BODY_UNAVAILABLE,
        "instruction review confirms the recovered action cases and common-return "
        "control flow without unintended case fallthrough",
        ("platform_side_effects_and_complete_attachment_workflow_remain_unverified",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTERPROCEDURAL,
        reviewed_spans=6,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.APP_OTA_EVENT_RECEIVER,
        WarningAuditScope.APPLICATION,
        ComparisonState.FALLBACK_BODY_UNAVAILABLE,
        "instruction review confirms the recovered update-event cases and their "
        "common-return control flow",
        ("event_reachability_and_peripheral_completion_remain_unverified",),
        requests=("startFileOta",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTRAPROCEDURAL,
        reviewed_spans=1,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.APP_SPORT_SENSOR_RECEIVER,
        WarningAuditScope.APPLICATION,
        ComparisonState.FALLBACK_BODY_UNAVAILABLE,
        "instruction review confirms a deliberate shared nonzero-state processing "
        "tail, with an additional local mode call on the connected branch",
        ("sensor_meaning_correctness_and_event_completeness_remain_unverified",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTERPROCEDURAL,
        reviewed_spans=2,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.SDK_OTA_PATCH_ADVANCE,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.INSTRUCTION_REVIEW_REQUIRED,
        "instruction review confirms local cursor-before-dispatch and terminal-flag "
        "control flow without a local false-dispatch retry",
        (
            "local_completion_is_not_peripheral_acknowledgement",
            "end_to_end_retry_delivery_and_terminal_semantics_remain_unverified",
        ),
        requests=("startFileOta",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.INTERPROCEDURAL,
        reviewed_spans=5,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.SDK_DORMANT_DIAL_TRANSFER_CALL_SITE,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.NO_OBSERVED_INTERFACE_CALL_SITE,
        "a bounded whole-artifact trace found no static activation edge for the "
        "separate dial-transfer implementation through reviewed reflection, Binder, "
        "service, manifest, resource, navigation, or packaged JNI-root paths",
        (
            "does_not_authorize_or_model_dial_file_transfer",
            "runtime_generated_or_external_activation_not_exhaustively_disproved",
            "static_no_edge_does_not_establish_runtime_dormancy",
        ),
        requests=("editDeviceDialCustom",),
        instruction_review=InstructionReviewState.BOUNDED_FACT_CONFIRMED,
        fact_scope=InstructionFactScope.WHOLE_CORPUS_SEARCH,
        reviewed_spans=23,
        public_fact=True,
    ),
)


_AUDIT = _closed_instance(
    RecoveredWarningAudit,
    scopes=_SCOPES,
    comparisons=_COMPARISONS,
)


def recovered_warning_audit() -> RecoveredWarningAudit:
    """Return immutable aggregate warning-triage evidence."""

    return _AUDIT


__all__ = [
    "ComparisonState",
    "InstructionFactScope",
    "InstructionReviewState",
    "RecoveredWarningAudit",
    "WarningAuditScope",
    "WarningComparisonCode",
    "WarningComparisonEvidence",
    "WarningScopeEvidence",
    "recovered_warning_audit",
]
