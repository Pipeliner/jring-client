from collections import Counter
from dataclasses import FrozenInstanceError, asdict
import json

import pytest

from jring.vendor_codec_registry import REQUEST_CODEC_LOCATORS
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
    assert evidence.explicitly_unresolved_count == 20
    assert evidence.rows_with_unresolved_reasons_count == 58
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
