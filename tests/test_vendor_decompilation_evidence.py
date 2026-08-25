from dataclasses import FrozenInstanceError, fields
import inspect

import pytest

import jring.vendor_decompilation_evidence as decompilation_module
from jring.vendor_decompilation_evidence import (
    CountReconciliation,
    DecompilationMode,
    DecompilationPassEvidence,
    DecompilationScope,
    DecompilationScopeEvidence,
    RecoveredDecompilationCoverage,
    RecoveryCompleteness,
    recovered_decompilation_coverage,
)


def test_decompilation_evidence_is_closed_immutable_and_aggregate_only():
    evidence = recovered_decompilation_coverage()

    assert evidence is recovered_decompilation_coverage()
    for model in (
        DecompilationPassEvidence,
        DecompilationScopeEvidence,
        RecoveredDecompilationCoverage,
    ):
        with pytest.raises(TypeError):
            model()
    with pytest.raises(TypeError):
        recovered_decompilation_coverage("archive")
    with pytest.raises(FrozenInstanceError):
        evidence.scopes = ()

    forbidden_fields = {
        "class_name", "digest", "file_name", "log", "method_name", "package_name",
        "path", "source", "stack_trace",
    }
    for model in (
        DecompilationPassEvidence,
        DecompilationScopeEvidence,
        RecoveredDecompilationCoverage,
    ):
        assert forbidden_fields.isdisjoint(field.name for field in fields(model))
    assert "com." not in repr(evidence)
    assert "/tmp" not in repr(evidence)


def test_primary_run_and_emitted_markers_remain_different_observables():
    evidence = recovered_decompilation_coverage()
    primary = evidence.primary_pass

    assert primary.mode is DecompilationMode.STRUCTURED
    assert primary.processed_class_count == 6_705
    assert primary.rendered_source_count == 10_185
    assert primary.run_reported_failure_count == 89
    assert primary.jadx_error_marker_count == 69
    assert primary.failed_method_stub_count == 88
    assert primary.incorrect_code_marker_count == 18
    assert primary.hard_failure_file_count == 52
    assert primary.warning_marker_count == 6_191
    assert primary.warning_file_count == 1_215
    assert primary.error_or_incorrect_marker_count == 87
    assert evidence.count_reconciliation is CountReconciliation.DIFFERENT_OBSERVABLES
    assert evidence.run_to_marker_mapping_established is False
    assert not hasattr(evidence, "missing_error_count")
    assert not hasattr(evidence, "success_rate")


def test_zero_scoped_markers_have_nonzero_scanned_denominators():
    scopes = {
        item.scope: item for item in recovered_decompilation_coverage().scopes
    }

    assert scopes[DecompilationScope.JRING_APPLICATION].structured_files_scanned == 268
    assert scopes[DecompilationScope.EMBEDDED_BLE_SDK].structured_files_scanned == 47
    assert scopes[DecompilationScope.OTHER_DEPENDENCY].structured_files_scanned == 9_870
    assert scopes[DecompilationScope.JRING_APPLICATION].structured_hard_failure_files == 0
    assert scopes[DecompilationScope.EMBEDDED_BLE_SDK].structured_hard_failure_files == 0
    assert scopes[DecompilationScope.OTHER_DEPENDENCY].structured_hard_failure_files == 52
    assert sum(item.structured_files_scanned for item in scopes.values()) == 10_185
    assert sum(item.structured_hard_failure_files for item in scopes.values()) == 52
    assert evidence_scope_names(scopes) == set(DecompilationScope)


def test_warning_scope_is_visible_without_becoming_a_hard_failure_or_success_claim():
    scopes = {
        item.scope: item for item in recovered_decompilation_coverage().scopes
    }

    assert (
        scopes[DecompilationScope.JRING_APPLICATION].structured_warning_marker_count,
        scopes[DecompilationScope.JRING_APPLICATION].structured_warning_files,
        scopes[DecompilationScope.JRING_APPLICATION].bluetooth_related_warning_files,
    ) == (161, 23, 11)
    assert (
        scopes[DecompilationScope.EMBEDDED_BLE_SDK].structured_warning_marker_count,
        scopes[DecompilationScope.EMBEDDED_BLE_SDK].structured_warning_files,
        scopes[DecompilationScope.EMBEDDED_BLE_SDK].bluetooth_related_warning_files,
    ) == (62, 21, 21)
    assert (
        scopes[DecompilationScope.OTHER_DEPENDENCY].structured_warning_marker_count,
        scopes[DecompilationScope.OTHER_DEPENDENCY].structured_warning_files,
        scopes[DecompilationScope.OTHER_DEPENDENCY].bluetooth_related_warning_files,
    ) == (5_968, 1_171, 5)
    assert sum(item.structured_warning_marker_count for item in scopes.values()) == 6_191
    assert sum(item.structured_warning_files for item in scopes.values()) == 1_215
    assert all(item.hard_failure_direct_bluetooth_reference_files == 0 for item in scopes.values())


def evidence_scope_names(scopes):
    return set(scopes)


def test_fallback_pass_is_complete_output_generation_not_semantic_or_smali_review():
    evidence = recovered_decompilation_coverage()
    fallback = evidence.fallback_pass

    assert fallback.mode is DecompilationMode.FALLBACK
    assert fallback.processed_class_count == 6_705
    assert fallback.rendered_source_count == 10_267
    assert fallback.run_reported_failure_count is None
    assert fallback.run_failure_count_available is False
    assert fallback.jadx_error_marker_count == 0
    assert fallback.failed_method_stub_count == 0
    assert fallback.incorrect_code_marker_count == 0
    assert fallback.hard_failure_file_count == 0
    assert fallback.warning_marker_count is None
    assert fallback.warning_file_count is None
    assert fallback.completed_without_reported_failures is True
    assert fallback.semantic_review_completed is False
    assert evidence.complete_semantic_source_review_completed is False
    assert evidence.complete_smali_review_completed is False
    assert evidence.complete_dex_instruction_review_completed is False
    assert evidence.complete_dex_coverage is False
    assert evidence.source_recovery_completeness is RecoveryCompleteness.NOT_ESTABLISHED


def test_fallback_scope_counts_match_owned_scopes_without_proving_correctness():
    scopes = {
        item.scope: item for item in recovered_decompilation_coverage().scopes
    }

    assert scopes[DecompilationScope.JRING_APPLICATION].fallback_files_scanned == 268
    assert scopes[DecompilationScope.EMBEDDED_BLE_SDK].fallback_files_scanned == 47
    assert scopes[DecompilationScope.OTHER_DEPENDENCY].fallback_files_scanned == 9_952
    assert all(item.fallback_hard_failure_files == 0 for item in scopes.values())
    assert sum(item.fallback_files_scanned for item in scopes.values()) == 10_267
    assert recovered_decompilation_coverage().no_recognized_owned_scope_markers is True
    assert recovered_decompilation_coverage().semantic_correctness_established is False


def test_decompilation_evidence_never_promotes_runtime_or_hardware_maturity():
    evidence = recovered_decompilation_coverage()

    from jring.vendor_coverage import (
        static_vendor_callback_coverage,
        static_vendor_operation_coverage,
    )

    assert evidence.maturity == "static_apk_only"
    assert evidence.evidence_scope == "decompiler_run_and_marker_triage"
    assert evidence.runnable is False
    assert evidence.python_callable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert evidence.static_review_authorized is True
    assert evidence.hardware_authority is False
    assert evidence.interface_entries is False
    assert len(static_vendor_operation_coverage()) == 112
    assert len(static_vendor_callback_coverage()) == 105


def test_public_model_has_no_io_or_private_artifact_dependency():
    source = inspect.getsource(decompilation_module).lower()

    for dependency in (
        "import pathlib", "import subprocess", "import zipfile", "open(",
        "bluetooth_address", "raw_payload", "stack trace",
    ):
        assert dependency not in source
    for method in ("scan", "run", "decompile", "execute", "open", "read"):
        assert not hasattr(recovered_decompilation_coverage(), method)
