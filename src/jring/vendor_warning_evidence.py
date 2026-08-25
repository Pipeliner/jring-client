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
    public_fact: bool = False,
) -> WarningComparisonEvidence:
    return _closed_instance(
        WarningComparisonEvidence,
        code=code,
        scope=scope,
        comparison_state=state,
        instruction_review=InstructionReviewState.NOT_PERFORMED,
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
        "both modes expose the same callback-label set already present in the ledger",
        ("branch_opcode_and_field_semantics_remain_unresolved",),
        count=85,
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.SDK_OTA_PROGRESS_FORWARDING,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.SAME_TOOL_SURFACE_CORROBORATION,
        "both modes retain the selected-connection progress forwarding edge",
        ("same_tool_agreement_does_not_prove_transfer_semantics",),
        requests=("startFileOta",),
        public_fact=True,
    ),
    _comparison(
        WarningComparisonCode.APP_OTA_SELECTOR_DIVERGENCE,
        WarningAuditScope.APPLICATION,
        ComparisonState.COMPARISON_DIVERGENCE,
        "the two modes disagree on selector packing and write control flow",
        ("requires_bounded_instruction_review_before_any_selector_claim",),
        requests=("startFileOta",),
    ),
    _comparison(
        WarningComparisonCode.APP_CLASSIC_ATTACHMENT_RECEIVER,
        WarningAuditScope.APPLICATION,
        ComparisonState.FALLBACK_BODY_UNAVAILABLE,
        "structured output routes classic discovery bonding and audio attachment events",
        ("exact_event_branch_mapping_remains_unresolved",),
    ),
    _comparison(
        WarningComparisonCode.APP_OTA_EVENT_RECEIVER,
        WarningAuditScope.APPLICATION,
        ComparisonState.FALLBACK_BODY_UNAVAILABLE,
        "structured output routes update progress terminal and reconnect events",
        ("exact_event_branch_mapping_remains_unresolved",),
        requests=("startFileOta",),
    ),
    _comparison(
        WarningComparisonCode.APP_SPORT_SENSOR_RECEIVER,
        WarningAuditScope.APPLICATION,
        ComparisonState.FALLBACK_BODY_UNAVAILABLE,
        "structured output separates connection-state and sensor-event handling",
        ("exact_branch_separation_and_fallthrough_remain_unresolved",),
    ),
    _comparison(
        WarningComparisonCode.SDK_OTA_PATCH_ADVANCE,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.INSTRUCTION_REVIEW_REQUIRED,
        "patch advance contains duplicated and removed control-flow regions",
        ("memory_branch_retry_and_terminal_ordering_remain_unresolved",),
        requests=("startFileOta",),
    ),
    _comparison(
        WarningComparisonCode.SDK_DORMANT_DIAL_TRANSFER_CALL_SITE,
        WarningAuditScope.EMBEDDED_SDK,
        ComparisonState.NO_OBSERVED_INTERFACE_CALL_SITE,
        "a separate dial-transfer implementation has no observed interface construction edge",
        ("does_not_authorize_or_model_dial_file_transfer",),
        requests=("editDeviceDialCustom",),
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
    "InstructionReviewState",
    "RecoveredWarningAudit",
    "WarningAuditScope",
    "WarningComparisonCode",
    "WarningComparisonEvidence",
    "WarningScopeEvidence",
    "recovered_warning_audit",
]
