"""Aggregate-only evidence for the authorized decompilation coverage audit.

The records deliberately keep run telemetry, emitted marker observations, and package
scope counts separate.  They contain no artifact content or locator and cannot inspect
or execute anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DecompilationMode(str, Enum):
    STRUCTURED = "structured"
    FALLBACK = "fallback"


class DecompilationScope(str, Enum):
    JRING_APPLICATION = "jring_application"
    EMBEDDED_BLE_SDK = "embedded_ble_sdk"
    OTHER_DEPENDENCY = "other_dependency"


class RecoveryCompleteness(str, Enum):
    NOT_ESTABLISHED = "not_established"


class CountReconciliation(str, Enum):
    DIFFERENT_OBSERVABLES = "different_observables"


def _closed_instance(model: type, **values: object) -> object:
    instance = object.__new__(model)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


@dataclass(frozen=True, init=False, repr=False)
class DecompilationPassEvidence:
    mode: DecompilationMode
    processed_class_count: int
    rendered_source_count: int
    run_reported_failure_count: int | None
    run_failure_count_available: bool
    jadx_error_marker_count: int
    failed_method_stub_count: int
    incorrect_code_marker_count: int
    hard_failure_file_count: int
    warning_marker_count: int | None
    warning_file_count: int | None
    completed_without_reported_failures: bool
    semantic_review_completed: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("decompilation pass evidence is closed")

    @property
    def error_or_incorrect_marker_count(self) -> int:
        return self.jadx_error_marker_count + self.incorrect_code_marker_count


@dataclass(frozen=True, init=False, repr=False)
class DecompilationScopeEvidence:
    scope: DecompilationScope
    structured_files_scanned: int
    structured_hard_failure_files: int
    structured_warning_marker_count: int
    structured_warning_files: int
    bluetooth_related_warning_files: int
    hard_failure_direct_bluetooth_reference_files: int
    fallback_files_scanned: int
    fallback_hard_failure_files: int

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("decompilation scope evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredDecompilationCoverage:
    artifact_ref: str
    tool_family: str
    tool_version: str
    structured_configuration_ref: str
    fallback_configuration_ref: str
    namespace_classifier_version: int
    marker_rule_version: int
    primary_pass: DecompilationPassEvidence
    fallback_pass: DecompilationPassEvidence
    scopes: tuple[DecompilationScopeEvidence, ...]
    count_reconciliation: CountReconciliation
    source_recovery_completeness: RecoveryCompleteness
    run_to_marker_mapping_established: bool
    complete_semantic_source_review_completed: bool
    complete_smali_review_completed: bool
    complete_dex_instruction_review_completed: bool
    complete_dex_coverage: bool
    semantic_correctness_established: bool
    limitations: tuple[str, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use recovered_decompilation_coverage()")

    @property
    def no_recognized_owned_scope_markers(self) -> bool:
        owned = {
            DecompilationScope.JRING_APPLICATION,
            DecompilationScope.EMBEDDED_BLE_SDK,
        }
        return all(
            item.structured_files_scanned > 0
            and item.fallback_files_scanned > 0
            and item.structured_hard_failure_files == 0
            and item.fallback_hard_failure_files == 0
            for item in self.scopes
            if item.scope in owned
        )

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def evidence_scope(self) -> str:
        return "decompiler_run_and_marker_triage"

    @property
    def interface_entries(self) -> bool:
        return False

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
    def static_review_authorized(self) -> bool:
        return True

    @property
    def hardware_authority(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "RecoveredDecompilationCoverage("
            f"processed_class_count={self.primary_pass.processed_class_count}, "
            f"structured_rendering_count={self.primary_pass.rendered_source_count}, "
            f"fallback_rendering_count={self.fallback_pass.rendered_source_count}, "
            "source_recovery_completeness=not_established, "
            "hardware_verified=False)"
        )


_PRIMARY = _closed_instance(
    DecompilationPassEvidence,
    mode=DecompilationMode.STRUCTURED,
    processed_class_count=6_705,
    rendered_source_count=10_185,
    run_reported_failure_count=89,
    run_failure_count_available=True,
    jadx_error_marker_count=69,
    failed_method_stub_count=88,
    incorrect_code_marker_count=18,
    hard_failure_file_count=52,
    warning_marker_count=6_191,
    warning_file_count=1_215,
    completed_without_reported_failures=False,
    semantic_review_completed=False,
)

_FALLBACK = _closed_instance(
    DecompilationPassEvidence,
    mode=DecompilationMode.FALLBACK,
    processed_class_count=6_705,
    rendered_source_count=10_267,
    run_reported_failure_count=None,
    run_failure_count_available=False,
    jadx_error_marker_count=0,
    failed_method_stub_count=0,
    incorrect_code_marker_count=0,
    hard_failure_file_count=0,
    warning_marker_count=None,
    warning_file_count=None,
    completed_without_reported_failures=True,
    semantic_review_completed=False,
)

_SCOPES = (
    _closed_instance(
        DecompilationScopeEvidence,
        scope=DecompilationScope.JRING_APPLICATION,
        structured_files_scanned=268,
        structured_hard_failure_files=0,
        structured_warning_marker_count=161,
        structured_warning_files=23,
        bluetooth_related_warning_files=11,
        hard_failure_direct_bluetooth_reference_files=0,
        fallback_files_scanned=268,
        fallback_hard_failure_files=0,
    ),
    _closed_instance(
        DecompilationScopeEvidence,
        scope=DecompilationScope.EMBEDDED_BLE_SDK,
        structured_files_scanned=47,
        structured_hard_failure_files=0,
        structured_warning_marker_count=62,
        structured_warning_files=21,
        bluetooth_related_warning_files=21,
        hard_failure_direct_bluetooth_reference_files=0,
        fallback_files_scanned=47,
        fallback_hard_failure_files=0,
    ),
    _closed_instance(
        DecompilationScopeEvidence,
        scope=DecompilationScope.OTHER_DEPENDENCY,
        structured_files_scanned=9_870,
        structured_hard_failure_files=52,
        structured_warning_marker_count=5_968,
        structured_warning_files=1_171,
        bluetooth_related_warning_files=5,
        hard_failure_direct_bluetooth_reference_files=0,
        fallback_files_scanned=9_952,
        fallback_hard_failure_files=0,
    ),
)

_COVERAGE = _closed_instance(
    RecoveredDecompilationCoverage,
    artifact_ref="authorized_xapk_1_9_84_182",
    tool_family="jadx",
    tool_version="1.5.6",
    structured_configuration_ref="structured_clean_room_v1",
    fallback_configuration_ref="fallback_clean_room_v1",
    namespace_classifier_version=1,
    marker_rule_version=1,
    primary_pass=_PRIMARY,
    fallback_pass=_FALLBACK,
    scopes=_SCOPES,
    count_reconciliation=CountReconciliation.DIFFERENT_OBSERVABLES,
    source_recovery_completeness=RecoveryCompleteness.NOT_ESTABLISHED,
    run_to_marker_mapping_established=False,
    complete_semantic_source_review_completed=False,
    complete_smali_review_completed=False,
    complete_dex_instruction_review_completed=False,
    complete_dex_coverage=False,
    semantic_correctness_established=False,
    limitations=(
        "marker_absence_does_not_establish_correct_control_flow",
        "fallback_output_is_not_semantic_or_instruction_review",
        "native_resources_reflection_and_other_firmware_are_outside_this_measurement",
        "counts_are_bound_to_the_recorded_artifact_and_tool_configurations",
    ),
)


def recovered_decompilation_coverage() -> RecoveredDecompilationCoverage:
    """Return the immutable aggregate from the authorized offline audit."""

    return _COVERAGE


__all__ = [
    "CountReconciliation",
    "DecompilationMode",
    "DecompilationPassEvidence",
    "DecompilationScope",
    "DecompilationScopeEvidence",
    "RecoveredDecompilationCoverage",
    "RecoveryCompleteness",
    "recovered_decompilation_coverage",
]
