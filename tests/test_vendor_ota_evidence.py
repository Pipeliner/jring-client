import inspect

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3, VENDOR_SERVICE_FEF5
from jring.vendor_ota_evidence import (
    FirmwareAndTransferEvidenceOperation,
    OfflineFirmwareAndTransferEvidence,
    evidence_for,
)


def _blocker_codes(evidence):
    return {blocker.code for blocker in evidence.blockers}


def _phase_codes(evidence):
    return tuple(phase.code for phase in evidence.phases)


def test_get_ota_info_models_exact_main_request_without_exposing_a_frame():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.GET_OTA_INFO)
    frame = evidence.main_channel_frame

    assert frame.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert frame.frame_length == 20
    assert frame.fixed_fields == ((0, 1, 0x0C),)
    assert frame.zero_ranges == ((1, 20),)
    assert frame.source_enqueue_position == "tail"
    assert frame.source_clears_queue_first is False
    assert not hasattr(frame, "bytes")
    assert not hasattr(evidence, "synthetic_bytes_for_test")


def test_get_ota_info_separates_device_response_cache_network_and_auto_start():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.GET_OTA_INFO)

    assert _phase_codes(evidence) == (
        "main_device_info_query",
        "device_info_response",
        "metadata_cache_lookup",
        "metadata_http_fetch",
        "eligibility_and_version_compare",
        "firmware_download_branch",
        "download_digest_compare",
        "optional_start_file_ota",
    )
    assert {callback.name for callback in evidence.callbacks} == {
        "onGetDeviceInfo",
        "onGetOtaInfo",
        "onGetOtaUpdate",
    }


def test_get_ota_info_records_the_actual_integrity_and_availability_blockers():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.GET_OTA_INFO)

    assert {
        "device_info_crc_not_an_ota_gate",
        "plaintext_metadata_transport",
        "unauthenticated_metadata",
        "weak_firmware_digest",
        "unbounded_download_materialization",
        "info_query_can_download_firmware",
        "download_written_before_digest_acceptance",
        "network_auto_start_precedes_eligibility_compare",
        "network_exception_callback_gap",
    } <= _blocker_codes(evidence)


def test_start_file_ota_models_mode_transition_and_separate_suota_service():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.START_FILE_OTA)
    frame = evidence.main_channel_frame

    assert frame.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert frame.frame_length == 20
    assert frame.fixed_fields == ((0, 1, 0x35),)
    assert frame.derived_fields == (
        (1, 1, "0x02 when requested OTA type is 3; otherwise 0x01"),
    )
    assert frame.zero_ranges == ((2, 20),)
    assert frame.source_clears_queue_first is True
    assert evidence.secondary_gatt_service_uuid == VENDOR_SERVICE_FEF5


def test_start_file_ota_is_descriptive_only_and_lists_dangerous_side_effects():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.START_FILE_OTA)

    assert evidence.runnable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert evidence.safety.binary_parsing is False
    assert evidence.safety.network_access is False
    assert evidence.safety.file_access is False
    assert evidence.safety.file_mutation is False
    assert evidence.safety.transport_integration is False
    assert evidence.evidence_scope == (
        "reconstructible_main_frame_and_non_runnable_workflow_evidence"
    )
    assert "eligible_device_models" in evidence.known_unknowns
    assert {
        "clears the ordinary command queue",
        "changes device firmware-update mode",
        "opens a second GATT connection",
        "writes firmware chunks to SUOTA characteristics",
        "may reboot and disconnect the device",
        "may refresh the platform GATT cache",
    } <= set(evidence.dangerous_side_effects)


def test_start_file_ota_preserves_precise_non_runnable_blockers():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.START_FILE_OTA)

    assert {
        "caller_controlled_file_path",
        "unvalidated_ota_type",
        "no_preflight_file_validation",
        "success_callback_precedes_file_open",
        "firmware_fully_materialized_in_memory",
        "unchecked_single_file_read",
        "xor_byte_is_not_authenticity",
        "hardware_specific_suota_state_machine",
        "write_without_response_chunk_stream",
        "coarse_progress_integer_division",
        "ota_error_callback_gap",
        "no_terminal_success_service_callback",
        "no_static_hardware_eligibility",
    } <= _blocker_codes(evidence)


def test_start_file_ota_traces_connection_chunk_status_and_cleanup_phases():
    evidence = evidence_for(FirmwareAndTransferEvidenceOperation.START_FILE_OTA)

    assert _phase_codes(evidence) == (
        "resolve_current_device",
        "clear_queue_and_request_mode",
        "delayed_secondary_gatt_connect",
        "discover_suota_and_enable_status",
        "open_and_materialize_firmware",
        "append_xor_check_byte",
        "configure_suota_transfer",
        "stream_no_response_chunks",
        "consume_status_notifications",
        "end_reboot_disconnect_cleanup",
    )
    assert {callback.source for callback in evidence.callbacks} >= {
        "service callback",
        "GATT callback",
        "broadcast receiver",
    }


def test_ftp_completion_is_explicitly_not_an_ota_completion_signal():
    evidence = evidence_for(
        FirmwareAndTransferEvidenceOperation.NOTIFY_FTP_DOWNLOAD_COMPLETED
    )
    frame = evidence.main_channel_frame

    assert frame.fixed_fields == ((0, 1, 0x54), (1, 1, 0x07))
    assert frame.zero_ranges == ((2, 20),)
    assert evidence.relationship_code == "ftp_media_boundary_not_firmware_ota"
    assert _phase_codes(evidence) == ("ftp_terminal_signal",)


def test_evidence_operations_and_models_are_closed():
    with pytest.raises(TypeError):
        evidence_for("get_ota_info")
    with pytest.raises(TypeError):
        OfflineFirmwareAndTransferEvidence()


def test_module_has_no_runnable_io_or_transport_dependencies():
    module = inspect.getmodule(evidence_for)
    source = inspect.getsource(module)

    assert "import pathlib" not in source
    assert "import socket" not in source
    assert "import urllib" not in source
    assert "import requests" not in source
    assert "import bleak" not in source
    assert "open(" not in source
    assert "subprocess" not in source
