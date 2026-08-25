import json
import os
from pathlib import Path

import pytest

from scripts import evidence_tool
from scripts.evidence_tool import (
    EvidenceError,
    derive_fixture,
    derive_public_claim,
    load_manifest,
    main,
    scan_repository,
    serialize_fixture,
    validate_manifest,
    validate_private_device_info_manifest,
    validate_public_claim,
)
from jring.vendor_gatt_preflight import VendorGattPreflightCode


FIXTURES = Path(__file__).parent / "fixtures" / "evidence"
SYNTHETIC_ADDRESS = ":".join(("DE", "AD", "BE", "EF", "00", "01"))
SYNTHETIC_BLUEZ_PATH = "/org/" + "bluez/hci0/dev_DE_AD_BE_EF_00_01"
SYNTHETIC_EMAIL = "person@" + "example.invalid"
SYNTHETIC_TIMESTAMP = "2026-08-" + "24T12:34:56Z"
SYNTHETIC_PAYLOAD = "00112233" + "445566778899"
OWNER_SOURCE = "owner_" + "authorized"
PRIVATE_DEVICE_INFO_KIND = "private_owner_" + "device_info_observation"


def safe_manifest():
    return json.loads((FIXTURES / "synthetic-hid-manifest.json").read_text())


def safe_public_claim():
    return json.loads(
        (FIXTURES / "synthetic-vendor-device-info-claim.json").read_text()
    )


def safe_private_device_info_manifest():
    return dict(
        schema_version=2,
        manifest_kind=PRIVATE_DEVICE_INFO_KIND,
        evidence_id="withheld",
        provenance=dict(
            source=OWNER_SOURCE,
            collection_method="self_declared_historical_record",
            original_retained=False,
        ),
        consent=dict(
            collection="granted_for_observed_single_attempt",
            operation_execution="granted_for_observed_single_attempt",
            repeat_execution="not_granted",
            publication="not_granted",
        ),
        evidence_scope=dict(
            observation_scope="single_attempt_single_generation",
            generation_ref="manifest_local_generation_1",
            model_family="withheld",
            firmware_major="withheld",
            model_scope="not_recorded",
            firmware_scope="not_recorded",
            protocol_evidence_contract="device_info_static_aggregate_v1",
            generalization="none",
        ),
        operation=dict(
            operation_id="vendor_main_device_info_canary_v1",
            route="main",
            write_kind="gatt_write_with_response",
            terminal_rule="single_matched_response",
            retry_policy="none",
        ),
        route_observation=dict(
            generation_ref="manifest_local_generation_1",
            connection_attempt_count=1,
            connection_outcome="connected",
            metadata_snapshot="complete",
            preflight_result="structurally_ready",
            request_target_ownership="confirmed_current_generation",
            response_target_ownership="confirmed_current_generation",
            values_read=False,
        ),
        dispatch_observation=dict(
            subscription_attempt_count=1,
            subscription_outcome="transport_call_completed",
            cccd_acknowledgement="not_independently_observed",
            write_attempt_count=1,
            write_outcome="att_write_response_completed",
            write_order="after_subscription_completion",
            retry_count=0,
        ),
        response_observation=dict(
            terminal_outcome="success_response",
            matched_terminal_count=1,
            callback_projection="accepted",
            parser_outcome="accepted",
            integrity_outcome="valid",
            identifier_projection="not_materialized",
            decoded_projection="not_retained",
            generation_match="confirmed_current_generation",
            terminal_acceptance="after_write_completion_current_generation",
            absence_reason="not_applicable",
        ),
        cleanup_observation=dict(
            callback_acceptance="disabled_before_cleanup",
            unsubscribe_attempt_count=1,
            unsubscribe_outcome="completed",
            disconnect_attempt_count=1,
            disconnect_outcome="completed",
            late_callback_disposition="none_observed",
            cleanup_sequence="unsubscribe_then_disconnect",
            cleanup_outcome="confirmed",
        ),
        attempt_outcome="succeeded",
        redactions=dict(
            bluetooth_addresses=True,
            bluez_paths=True,
            account_identifiers=True,
            precise_timestamps=True,
            unique_device_identifiers=True,
            exact_model=True,
            exact_firmware=True,
            raw_requests=True,
            raw_responses=True,
            decoded_device_information=True,
            health_measurements=True,
        ),
        authority=dict(
            purpose="evidence_only",
            runtime_authorized=False,
            repeat_execution_authorized=False,
            live_eligible=False,
            publication_authorized=False,
            generic_vendor_io_authorized=False,
            hardware_support_claimed=False,
            model_family_support_claimed=False,
            firmware_major_support_claimed=False,
        ),
    )


@pytest.mark.parametrize(
    "field,value,secret",
    [
        ("notes", "device " + SYNTHETIC_ADDRESS, "DE:AD"),
        ("notes", "object " + SYNTHETIC_BLUEZ_PATH, "/org/" + "bluez"),
        ("account_email", SYNTHETIC_EMAIL, "person@"),
        ("observed_at", SYNTHETIC_TIMESTAMP, "12:34"),
        ("heart_rate", 72, "72"),
        ("raw_payload", SYNTHETIC_PAYLOAD, "001122"),
    ],
)
def test_unsafe_evidence_is_rejected_without_echo(field, value, secret):
    manifest = safe_manifest()
    manifest[field] = value

    with pytest.raises(EvidenceError) as raised:
        validate_manifest(manifest)

    assert raised.value.code == "unsafe_content"
    assert secret not in str(raised.value)


@pytest.mark.parametrize(
    "remove_path",
    [
        ("provenance",),
        ("consent",),
        ("coverage",),
        ("confidence",),
        ("device_context", "model_family"),
        ("redactions", "health_measurements"),
    ],
)
def test_manifest_requires_provenance_consent_coverage_and_redactions(remove_path):
    manifest = safe_manifest()
    target = manifest
    for component in remove_path[:-1]:
        target = target[component]
    del target[remove_path[-1]]

    with pytest.raises(EvidenceError) as raised:
        validate_manifest(manifest)

    assert raised.value.code == "invalid_manifest"


def test_safe_synthetic_manifest_derives_deterministically():
    manifest = safe_manifest()
    expected = json.loads((FIXTURES / "synthetic-hid-fixture.json").read_text())
    reordered = json.loads(json.dumps(manifest, sort_keys=True))

    first = derive_fixture(manifest)
    second = derive_fixture(reordered)

    assert first == expected
    assert serialize_fixture(first) == serialize_fixture(second)
    assert "consent" not in first
    assert "collection_method" not in first


def test_safe_v2_device_info_claim_derives_deterministically_without_authority():
    claim = safe_public_claim()
    expected = json.loads(
        (FIXTURES / "synthetic-vendor-device-info-fixture.json").read_text()
    )

    first = derive_public_claim(claim)
    second = derive_public_claim(json.loads(json.dumps(claim, sort_keys=True)))

    assert first == expected
    assert serialize_fixture(first) == serialize_fixture(second)
    assert "consent" not in first
    assert "private_evidence" not in json.dumps(first)
    assert first["runtime_authority"] == {
        "generic_vendor_io_authorized": False,
        "hardware_eligible": False,
        "hardware_verified": False,
        "live_eligible": False,
        "owner_authorized": False,
        "runnable": False,
    }


def test_private_device_info_observation_validates_success_but_grants_nothing():
    manifest = safe_private_device_info_manifest()

    validated = validate_private_device_info_manifest(manifest)

    assert validated["response_observation"]["terminal_outcome"] == "success_response"
    assert validated["authority"] == {
        "purpose": "evidence_only",
        "runtime_authorized": False,
        "repeat_execution_authorized": False,
        "live_eligible": False,
        "publication_authorized": False,
        "generic_vendor_io_authorized": False,
        "hardware_support_claimed": False,
        "model_family_support_claimed": False,
        "firmware_major_support_claimed": False,
    }


def test_private_device_info_preflight_codes_track_the_runtime_enum_exactly():
    assert evidence_tool._PREFLIGHT_CODES == {
        member.value for member in VendorGattPreflightCode
    }


def test_private_device_info_observation_accepts_negative_and_uncertain_evidence():
    route_failure = safe_private_device_info_manifest()
    route_failure["route_observation"].update(
        preflight_result="request_endpoint_missing",
        request_target_ownership="not_established",
        response_target_ownership="not_established",
    )
    route_failure["dispatch_observation"].update(
        subscription_attempt_count=0,
        subscription_outcome="not_attempted",
        write_attempt_count=0,
        write_outcome="not_attempted",
        write_order="not_applicable",
    )
    route_failure["response_observation"].update(
        terminal_outcome="not_observed",
        matched_terminal_count=0,
        callback_projection="not_observed",
        parser_outcome="not_attempted",
        integrity_outcome="not_evaluated",
        generation_match="not_observed",
        terminal_acceptance="not_applicable",
        absence_reason="write_not_dispatched",
    )
    route_failure["cleanup_observation"].update(
        unsubscribe_attempt_count=0,
        unsubscribe_outcome="not_required",
        cleanup_sequence="disconnect_only",
    )
    route_failure["attempt_outcome"] = "aborted"

    uncertain = safe_private_device_info_manifest()
    uncertain["dispatch_observation"]["write_outcome"] = "outcome_unknown"
    uncertain["response_observation"].update(
        integrity_outcome="invalid",
        terminal_acceptance=(
            "observed_current_generation_write_completion_unconfirmed"
        ),
    )
    uncertain["cleanup_observation"].update(
        callback_acceptance="not_confirmed",
        unsubscribe_outcome="outcome_unknown",
        disconnect_outcome="outcome_unknown",
        late_callback_disposition="not_observable",
        cleanup_outcome="outcome_unknown",
    )
    uncertain["attempt_outcome"] = "uncertain"

    assert validate_private_device_info_manifest(route_failure)["authority"][
        "runtime_authorized"
    ] is False
    assert validate_private_device_info_manifest(uncertain)["authority"][
        "hardware_support_claimed"
    ] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("provenance", "collection_method"), "sanitized_tool_export"),
        (("consent", "collection"), "granted"),
        (("consent", "operation_execution"), "granted"),
        (("consent", "publication"), "granted"),
        (("consent", "repeat_execution"), "granted"),
        (("operation", "route"), "raw"),
        (("operation", "write_kind"), "without_response"),
        (("dispatch_observation", "retry_count"), 1),
        (("dispatch_observation", "write_attempt_count"), True),
        (("dispatch_observation", "cccd_acknowledgement"), "confirmed"),
        (("dispatch_observation", "write_order"), "before_subscription_completion"),
        (("response_observation", "generation_match"), "stale_generation"),
        (("response_observation", "terminal_acceptance"), "before_write_completion"),
        (("response_observation", "identifier_projection"), "redacted"),
        (("response_observation", "decoded_projection"), "retained"),
        (("authority", "runtime_authorized"), True),
        (("authority", "hardware_support_claimed"), True),
    ],
)
def test_private_device_info_manifest_cannot_expand_operation_or_authority(path, value):
    manifest = safe_private_device_info_manifest()
    target = manifest
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value

    with pytest.raises(EvidenceError) as raised:
        validate_private_device_info_manifest(manifest)
    assert raised.value.code == "invalid_manifest"


def test_private_device_info_manifest_rejects_impossible_state_combinations():
    cases = []

    route = safe_private_device_info_manifest()
    route["route_observation"]["request_target_ownership"] = "not_established"
    cases.append(route)

    dispatch = safe_private_device_info_manifest()
    dispatch["dispatch_observation"].update(
        subscription_outcome="failed_before_completion",
        write_attempt_count=1,
    )
    cases.append(dispatch)

    response = safe_private_device_info_manifest()
    response["response_observation"]["matched_terminal_count"] = 0
    cases.append(response)

    cleanup = safe_private_device_info_manifest()
    cleanup["cleanup_observation"]["cleanup_outcome"] = "confirmed"
    cleanup["cleanup_observation"]["disconnect_outcome"] = "outcome_unknown"
    cases.append(cleanup)

    disconnect_semantics = safe_private_device_info_manifest()
    disconnect_semantics["cleanup_observation"].update(
        disconnect_outcome="retired_by_disconnect",
        cleanup_outcome="confirmed",
    )
    cases.append(disconnect_semantics)

    for manifest in cases:
        with pytest.raises(EvidenceError) as raised:
            validate_private_device_info_manifest(manifest)
        assert raised.value.code == "invalid_manifest"


def _set_no_terminal(manifest, absence_reason):
    manifest["response_observation"].update(
        terminal_outcome="not_observed",
        matched_terminal_count=0,
        callback_projection="not_observed",
        parser_outcome="not_attempted",
        integrity_outcome="not_evaluated",
        generation_match="not_observed",
        terminal_acceptance="not_applicable",
        absence_reason=absence_reason,
    )


def _set_no_dispatch(manifest):
    manifest["dispatch_observation"].update(
        subscription_attempt_count=0,
        subscription_outcome="not_attempted",
        write_attempt_count=0,
        write_outcome="not_attempted",
        write_order="not_applicable",
    )
    _set_no_terminal(manifest, "write_not_dispatched")
    manifest["cleanup_observation"].update(
        unsubscribe_attempt_count=0,
        unsubscribe_outcome="not_required",
    )


def test_private_device_info_attempt_outcomes_preserve_terminal_semantics():
    no_terminal = safe_private_device_info_manifest()
    _set_no_terminal(no_terminal, "deadline_elapsed_after_possible_dispatch")
    no_terminal["attempt_outcome"] = "uncertain"

    uncertain_write = safe_private_device_info_manifest()
    uncertain_write["dispatch_observation"]["write_outcome"] = "outcome_unknown"
    uncertain_write["response_observation"]["terminal_acceptance"] = (
        "observed_current_generation_write_completion_unconfirmed"
    )
    uncertain_write["attempt_outcome"] = "uncertain"

    device_failure = safe_private_device_info_manifest()
    device_failure["response_observation"].update(
        terminal_outcome="device_failure",
        callback_projection="suppressed_failure",
        parser_outcome="not_attempted",
        integrity_outcome="not_evaluated",
    )
    device_failure["attempt_outcome"] = "device_rejected"

    bad_integrity = safe_private_device_info_manifest()
    bad_integrity["response_observation"]["integrity_outcome"] = "invalid"
    bad_integrity["attempt_outcome"] = "rejected_bad_integrity"

    malformed = safe_private_device_info_manifest()
    malformed["response_observation"].update(
        terminal_outcome="malformed_response",
        callback_projection="suppressed_malformed",
        parser_outcome="rejected",
        integrity_outcome="not_evaluated",
    )
    malformed["attempt_outcome"] = "rejected_malformed_response"

    for manifest in (
        no_terminal,
        uncertain_write,
        device_failure,
        bad_integrity,
        malformed,
    ):
        assert validate_private_device_info_manifest(manifest)["authority"][
            "hardware_support_claimed"
        ] is False

    for terminal_manifest in (device_failure, bad_integrity, malformed):
        write_unknown = json.loads(json.dumps(terminal_manifest))
        write_unknown["dispatch_observation"]["write_outcome"] = "outcome_unknown"
        write_unknown["response_observation"]["terminal_acceptance"] = (
            "observed_current_generation_write_completion_unconfirmed"
        )
        write_unknown["attempt_outcome"] = "uncertain"
        assert validate_private_device_info_manifest(write_unknown)[
            "attempt_outcome"
        ] == "uncertain"


def test_private_response_absence_reason_must_match_dispatch_possibility():
    possible = safe_private_device_info_manifest()
    _set_no_terminal(possible, "write_not_dispatched")

    impossible = safe_private_device_info_manifest()
    _set_no_dispatch(impossible)
    impossible["response_observation"]["absence_reason"] = (
        "deadline_elapsed_after_possible_dispatch"
    )
    impossible["cleanup_observation"]["cleanup_sequence"] = "disconnect_only"

    for manifest in (possible, impossible):
        with pytest.raises(EvidenceError) as raised:
            validate_private_device_info_manifest(manifest)
        assert raised.value.code == "invalid_manifest"


def test_private_device_info_definite_non_dispatch_is_attempt_local_abort():
    subscription_failure = safe_private_device_info_manifest()
    subscription_failure["dispatch_observation"].update(
        subscription_outcome="failed_before_completion",
        write_attempt_count=0,
        write_outcome="not_attempted",
        write_order="not_applicable",
    )
    _set_no_terminal(subscription_failure, "write_not_dispatched")
    subscription_failure["attempt_outcome"] = "aborted"

    definite_write_failure = safe_private_device_info_manifest()
    definite_write_failure["dispatch_observation"]["write_outcome"] = (
        "definitely_not_dispatched"
    )
    _set_no_terminal(definite_write_failure, "write_not_dispatched")
    definite_write_failure["attempt_outcome"] = "aborted"

    for manifest in (subscription_failure, definite_write_failure):
        assert validate_private_device_info_manifest(manifest)["attempt_outcome"] == (
            "aborted"
        )


@pytest.mark.parametrize(
    "cleanup_update",
    [
        {
            "unsubscribe_outcome": "failed",
            "cleanup_outcome": "failed",
        },
        {
            "callback_acceptance": "not_confirmed",
            "unsubscribe_outcome": "outcome_unknown",
            "late_callback_disposition": "not_observable",
            "cleanup_outcome": "outcome_unknown",
        },
    ],
)
def test_private_device_info_cleanup_uncertainty_prevents_success(cleanup_update):
    manifest = safe_private_device_info_manifest()
    manifest["cleanup_observation"].update(cleanup_update)
    manifest["attempt_outcome"] = "uncertain"

    assert validate_private_device_info_manifest(manifest)["attempt_outcome"] == (
        "uncertain"
    )


@pytest.mark.parametrize("metadata", ["unavailable", "timed_out"])
def test_connected_metadata_failure_is_observed_without_hardware_claim(metadata):
    manifest = safe_private_device_info_manifest()
    manifest["route_observation"].update(
        metadata_snapshot=metadata,
        preflight_result="not_evaluated",
        request_target_ownership="not_established",
        response_target_ownership="not_established",
    )
    _set_no_dispatch(manifest)
    manifest["cleanup_observation"]["cleanup_sequence"] = "disconnect_only"
    manifest["attempt_outcome"] = "aborted"

    assert validate_private_device_info_manifest(manifest)["attempt_outcome"] == (
        "aborted"
    )


@pytest.mark.parametrize(
    "connection_count,connection_outcome,disconnect_count,disconnect_outcome,cleanup_sequence,cleanup_outcome,attempt_outcome",
    [
        (0, "not_attempted", 0, "not_required", "no_cleanup_actions", "not_required", "aborted"),
        (1, "failed", 0, "not_required", "no_cleanup_actions", "not_required", "aborted"),
        (1, "outcome_unknown", 1, "outcome_unknown", "disconnect_only", "outcome_unknown", "uncertain"),
    ],
)
def test_connection_outcomes_preserve_not_attempted_failed_and_uncertain(
    connection_count,
    connection_outcome,
    disconnect_count,
    disconnect_outcome,
    cleanup_sequence,
    cleanup_outcome,
    attempt_outcome,
):
    manifest = safe_private_device_info_manifest()
    manifest["route_observation"].update(
        connection_attempt_count=connection_count,
        connection_outcome=connection_outcome,
        metadata_snapshot="not_evaluated",
        preflight_result="not_evaluated",
        request_target_ownership="not_established",
        response_target_ownership="not_established",
    )
    _set_no_dispatch(manifest)
    manifest["cleanup_observation"].update(
        disconnect_attempt_count=disconnect_count,
        disconnect_outcome=disconnect_outcome,
        cleanup_sequence=cleanup_sequence,
        cleanup_outcome=cleanup_outcome,
    )
    manifest["attempt_outcome"] = attempt_outcome

    assert validate_private_device_info_manifest(manifest)["attempt_outcome"] == (
        attempt_outcome
    )


@pytest.mark.parametrize(
    "cleanup_update",
    [
        {"unsubscribe_outcome": "already_disconnected"},
        {"unsubscribe_outcome": "retired_by_disconnect"},
        {"late_callback_disposition": "not_observable"},
        {
            "callback_acceptance": "not_confirmed",
            "late_callback_disposition": "discarded",
        },
    ],
)
def test_private_cleanup_rejects_ambiguous_or_contradictory_states(cleanup_update):
    manifest = safe_private_device_info_manifest()
    manifest["cleanup_observation"].update(cleanup_update)

    with pytest.raises(EvidenceError) as raised:
        validate_private_device_info_manifest(manifest)
    assert raised.value.code == "invalid_manifest"


def test_private_observation_cannot_carry_linkable_context_or_identifier():
    for path, value in (
        (("evidence_id",), "alice-ring-12345"),
        (("evidence_scope", "model_family"), "alice-personal-ring"),
        (("evidence_scope", "firmware_major"), "serial-12345"),
    ):
        manifest = safe_private_device_info_manifest()
        target = manifest
        for component in path[:-1]:
            target = target[component]
        target[path[-1]] = value
        with pytest.raises(EvidenceError) as raised:
            validate_private_device_info_manifest(manifest)
        assert raised.value.code == "invalid_manifest"
        assert "alice" not in str(raised.value)


def test_private_observation_validation_cannot_promote_runtime_eligibility():
    from jring.vendor_runtime_eligibility import require_fake_singleton_terminal

    validate_private_device_info_manifest(safe_private_device_info_manifest())
    eligibility = require_fake_singleton_terminal("getDeviceInfo")

    assert eligibility.runnable is False
    assert eligibility.live_eligible is False
    assert eligibility.owner_authorized is False
    assert eligibility.hardware_eligible is False
    assert eligibility.hardware_verified is False


def test_private_and_public_schema_two_inputs_cannot_cross_validators():
    with pytest.raises(EvidenceError):
        validate_public_claim(safe_private_device_info_manifest())
    with pytest.raises(EvidenceError):
        validate_private_device_info_manifest(safe_public_claim())


def _write_private_manifest(path, manifest=None, mode=0o600):
    path.write_text(json.dumps(manifest or safe_private_device_info_manifest()))
    path.chmod(mode)
    return path


@pytest.mark.parametrize("mode", [0o400, 0o600])
def test_private_device_info_loader_accepts_only_owner_readable_modes(tmp_path, mode):
    path = _write_private_manifest(tmp_path / "observation.json", mode=mode)

    loaded = load_manifest(path)

    assert loaded["manifest_kind"] == PRIVATE_DEVICE_INFO_KIND


@pytest.mark.parametrize("mode", [0o000, 0o200, 0o440, 0o600 | 0o060, 0o644])
def test_private_device_info_loader_rejects_other_modes(tmp_path, mode):
    path = _write_private_manifest(tmp_path / "observation.json", mode=mode)

    with pytest.raises(EvidenceError) as raised:
        load_manifest(path)
    assert raised.value.code in {"invalid_manifest", "unsafe_permissions"}


def test_private_device_info_loader_rejects_wrong_owner_without_path_echo(
    tmp_path, monkeypatch
):
    path = _write_private_manifest(tmp_path / "owner-secret.json")
    real_fstat = evidence_tool.os.fstat

    def wrong_owner(descriptor):
        values = list(real_fstat(descriptor))
        values[4] = os.geteuid() + 1
        return os.stat_result(values)

    monkeypatch.setattr(evidence_tool.os, "fstat", wrong_owner)
    with pytest.raises(EvidenceError) as raised:
        load_manifest(path)
    assert raised.value.code == "unsafe_permissions"
    assert path.name not in str(raised.value)


def test_artifact_loader_rejects_links_non_files_and_oversize_growth(
    tmp_path, monkeypatch
):
    target = _write_private_manifest(tmp_path / "target.json")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    fifo = tmp_path / "artifact.fifo"
    os.mkfifo(fifo)

    for path in (link, tmp_path, fifo):
        with pytest.raises(EvidenceError) as raised:
            load_manifest(path)
        assert raised.value.code == "invalid_manifest"

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"{" + b" " * (64 * 1024) + b"}")
    oversized.chmod(0o600)
    real_fstat = evidence_tool.os.fstat

    def stale_size(descriptor):
        values = list(real_fstat(descriptor))
        values[6] = 0
        return os.stat_result(values)

    monkeypatch.setattr(evidence_tool.os, "fstat", stale_size)
    with pytest.raises(EvidenceError) as raised:
        load_manifest(oversized)
    assert raised.value.code == "invalid_manifest"


def test_schema_two_dispatch_requires_one_explicit_artifact_kind(tmp_path):
    hybrid = safe_private_device_info_manifest()
    hybrid["claim_id"] = "synthetic-vendor-device-info"
    missing = safe_private_device_info_manifest()
    del missing["manifest_kind"]

    for index, payload in enumerate((hybrid, missing)):
        path = _write_private_manifest(tmp_path / f"invalid-{index}.json", payload)
        with pytest.raises(EvidenceError) as raised:
            load_manifest(path)
        assert raised.value.code == "invalid_manifest"


def test_public_claim_loader_remains_valid_with_public_permissions(tmp_path):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(safe_public_claim()))
    path.chmod(0o644)

    assert load_manifest(path)["claim_id"] == "synthetic-vendor-device-info"


def test_private_device_info_cli_validates_locally_but_never_derives(
    tmp_path, capsys
):
    path = _write_private_manifest(tmp_path / "observation.json")

    assert main(["validate", str(path)]) == 0
    validated = capsys.readouterr()
    assert validated.out == (
        "Private owner device-info observation manifest passed local validation; "
        "validation performed no Bluetooth operation; not publishable.\n"
    )
    assert validated.err == ""

    assert main(["derive", str(path)]) == 2
    refused = capsys.readouterr()
    assert refused.out == ""
    assert "private_evidence" in refused.err
    assert path.name not in refused.err


@pytest.mark.parametrize(
    "name",
    ["owner-manifest.json", "owner-MANIFEST.JSON", "renamed.json"],
)
def test_repository_scan_quarantines_private_device_info_at_any_json_name(
    tmp_path, name
):
    path = _write_private_manifest(tmp_path / name)
    if name.endswith("-manifest.json"):
        (tmp_path / "owner-fixture.json").write_text("{}")

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


@pytest.mark.parametrize("syntax", ["python", "yaml"])
def test_repository_scan_quarantines_embedded_private_device_info(tmp_path, syntax):
    if syntax == "python":
        content = "manifest_kind = " + repr(PRIVATE_DEVICE_INFO_KIND) + "\n"
        name = "observation.py"
    else:
        content = "manifest_kind: " + PRIVATE_DEVICE_INFO_KIND + "\n"
        name = "observation.md"
    (tmp_path / name).write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


@pytest.mark.parametrize("container", ["wrapper", "array", "jsonl"])
def test_repository_scan_quarantines_nested_private_device_info(tmp_path, container):
    private = safe_private_device_info_manifest()
    if container == "wrapper":
        content = json.dumps({"records": [{"observation": private}]})
        name = "nested.json"
    elif container == "array":
        content = json.dumps([{"public": True}, private])
        name = "records.json"
    else:
        content = json.dumps({"public": True}) + "\n" + json.dumps(private) + "\n"
        name = "records.jsonl"
    (tmp_path / name).write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


@pytest.mark.parametrize("shape", ["malformed", "duplicate", "serialized"])
def test_repository_scan_prioritizes_private_markers_before_json_shape(tmp_path, shape):
    marker = json.dumps(PRIVATE_DEVICE_INFO_KIND)
    if shape == "malformed":
        content = '{"manifest_kind": ' + marker
    elif shape == "duplicate":
        content = (
            '{"manifest_kind": "public", "manifest_kind": ' + marker + "}"
        )
    else:
        content = json.dumps('{"manifest_kind": ' + marker + "}")
    (tmp_path / "disguised.json").write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


@pytest.mark.parametrize(
    "path,value",
    [
        (("operation",), "vendor_battery_query"),
        (("protocol", "endpoint_profile"), "vendor_raw"),
        (("protocol", "request_builder"), "arbitrary_frame"),
        (("protocol", "integrity_rule"), "unchecked"),
        (("effects", "maximum_attempts"), 2),
        (("effects", "maximum_writes_per_attempt"), True),
        (("effects", "vendor_write"), False),
        (("effects", "vendor_write_kind"), "without_response"),
        (("effects", "cleanup_must_complete_before_result"), False),
        (("effects", "binding"), True),
        (("effects", "raw_retention"), True),
        (("maturity",), "hardware_supported"),
        (("runtime_authority", "live_eligible"), True),
        (("review", "status"), "approved"),
    ],
)
def test_v2_claim_is_operation_specific_and_cannot_manufacture_runtime_authority(
    path, value
):
    claim = safe_public_claim()
    target = claim
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value

    with pytest.raises(EvidenceError) as raised:
        validate_public_claim(claim)
    assert raised.value.code == "invalid_claim"


def test_v2_claim_rejects_unknown_fields_and_raw_vectors_without_echo():
    claim = safe_public_claim()
    secret = SYNTHETIC_PAYLOAD
    claim["synthetic_vectors"][0]["raw_payload"] = secret

    with pytest.raises(EvidenceError) as raised:
        validate_public_claim(claim)
    assert raised.value.code == "unsafe_content"
    assert secret not in str(raised.value)


def test_v2_public_derived_claim_requires_private_reference_and_coarse_context():
    claim = safe_public_claim()
    claim["provenance"] = {
        "source": "public_derived",
        "private_evidence_reference": "withheld",
    }
    claim["device_context"] = {
        "model_family": "withheld",
        "firmware_major": "withheld",
    }
    claim["claim_id"] = "vendor-device-info-public-candidate"
    claim["maturity"] = "public_derived_candidate"

    validated = validate_public_claim(claim)
    assert validated["provenance"]["source"] == "public_derived"

    claim["provenance"]["private_evidence_reference"] = "owner-observation-id"
    with pytest.raises(EvidenceError) as raised:
        validate_public_claim(claim)
    assert raised.value.code == "invalid_claim"

    unsafe = safe_public_claim()
    unsafe["provenance"] = {
        "source": "public_derived",
        "private_evidence_reference": "withheld",
    }
    unsafe["claim_id"] = "owner-alice-observation"
    unsafe["device_context"] = {
        "model_family": "owner-alice-personal-ring",
        "firmware_major": "serial-12345",
    }
    unsafe["maturity"] = "public_derived_candidate"
    with pytest.raises(EvidenceError) as raised:
        validate_public_claim(unsafe)
    assert raised.value.code == "invalid_claim"


def test_v2_candidate_is_linked_to_existing_static_device_info_contract():
    from jring.protocol import ProtocolError
    from jring.vendor_protocol import (
        StaticQuery,
        encode_static_query,
        parse_vendor_device_info,
        static_protocol_coverage,
    )
    from jring.vendor_runtime_eligibility import require_fake_singleton_terminal

    claim = validate_public_claim(safe_public_claim())
    request = encode_static_query(StaticQuery.DEVICE_INFO)
    coverage = next(
        item
        for item in static_protocol_coverage()
        if item.operation is StaticQuery.DEVICE_INFO
    )
    eligibility = require_fake_singleton_terminal("getDeviceInfo")

    assert request.operation is StaticQuery.DEVICE_INFO
    assert claim["protocol"]["request_builder"] == "encode_static_query:device_info"
    assert parse_vendor_device_info.__name__ == claim["protocol"]["response_parser"]
    assert coverage.success_opcodes == (0x0C,)
    assert coverage.failure_opcodes == (0x8C,)
    assert eligibility.correlation_terminal_rule == "single_matched_response"
    assert eligibility.runnable is False
    assert eligibility.live_eligible is False
    assert eligibility.hardware_eligible is False

    body = bytes(range(1, 16))
    valid = parse_vendor_device_info(
        bytes((0x0C,)) + body + bytes.fromhex("47b17004")
    )
    invalid = parse_vendor_device_info(bytes((0x0C,)) + body + bytes(4))
    with pytest.raises(ProtocolError):
        parse_vendor_device_info(bytes((0x8C,)) + bytes(19))
    outcomes = {
        item["case"]: item["expected_canary_outcome"]
        for item in claim["synthetic_vectors"]
    }
    assert valid.integrity_valid is True
    assert invalid.integrity_valid is False
    assert outcomes == {
        "bad_integrity": "rejected_bad_integrity",
        "rejection": "device_rejected",
        "success": "succeeded",
    }


@pytest.mark.parametrize("version", [True, 1.0, "1"])
def test_evidence_schema_version_requires_an_exact_integer(version):
    manifest = safe_manifest()
    manifest["schema_version"] = version

    with pytest.raises(EvidenceError) as raised:
        validate_manifest(manifest)
    assert raised.value.code == "invalid_manifest"


def test_v2_claim_does_not_accept_private_owner_ledger_as_public_provenance():
    claim = safe_public_claim()
    claim["provenance"] = dict(
        source=OWNER_SOURCE,
        private_evidence_reference="withheld",
    )

    with pytest.raises(EvidenceError) as raised:
        validate_public_claim(claim)
    assert raised.value.code == "invalid_claim"


def test_repository_scan_accepts_standalone_v2_claim_and_requires_exact_fixture(
    tmp_path,
):
    evidence = tmp_path / "tests" / "fixtures" / "evidence"
    evidence.mkdir(parents=True)
    claim = safe_public_claim()
    fixture = derive_public_claim(claim)
    (evidence / "synthetic-vendor-device-info-claim.json").write_text(
        json.dumps(claim)
    )
    fixture_path = evidence / "synthetic-vendor-device-info-fixture.json"
    fixture_path.write_text(json.dumps(fixture))

    scan_repository(tmp_path)

    fixture["runtime_authority"]["live_eligible"] = True
    fixture_path.write_text(json.dumps(fixture))
    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "invalid_fixture"


@pytest.mark.parametrize(
    "path,value",
    [
        (("effects", "maximum_attempts"), True),
        (("runtime_authority", "live_eligible"), 0),
    ],
)
def test_repository_scan_uses_strict_types_for_derived_fixture(tmp_path, path, value):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    claim = safe_public_claim()
    fixture = derive_public_claim(claim)
    target = fixture
    for component in path[:-1]:
        target = target[component]
    target[path[-1]] = value
    (evidence / "candidate-claim.json").write_text(json.dumps(claim))
    (evidence / "candidate-fixture.json").write_text(json.dumps(fixture))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "invalid_fixture"


def test_repository_scan_uses_strict_types_for_v1_fixture(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    manifest = safe_manifest()
    fixture = derive_fixture(manifest)
    fixture["synthetic"] = 1
    (evidence / "synthetic-manifest.json").write_text(json.dumps(manifest))
    (evidence / "synthetic-fixture.json").write_text(json.dumps(fixture))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "invalid_fixture"


def test_repository_scan_reserves_claim_suffix_outside_evidence_directory(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "unpaired-claim.json").write_text(json.dumps(safe_public_claim()))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "invalid_fixture"


@pytest.mark.parametrize("name", ["candidate.JSON", "candidate-Claim.json"])
def test_repository_scan_rejects_case_variant_evidence_names(tmp_path, name):
    (tmp_path / name).write_text(json.dumps(safe_public_claim()))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code in {"invalid_fixture", "unsafe_content"}


def test_repository_scan_rejects_renamed_private_owner_ledger(tmp_path):
    manifest = safe_manifest()
    manifest["provenance"] = dict(
        source=OWNER_SOURCE,
        collection_method="manual_gatt_inventory",
        original_retained=False,
    )
    manifest["confidence"] = "low"
    manifest["device_context"] = {
        "model_family": "jring-family",
        "firmware_major": "v1",
    }
    (tmp_path / "renamed-owner-ledger.json").write_text(json.dumps(manifest))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


@pytest.mark.parametrize("container", ["markdown", "python", "python_kwargs", "yaml"])
def test_repository_scan_rejects_private_ledger_embedded_in_text(tmp_path, container):
    manifest = safe_manifest()
    manifest["provenance"] = dict(
        source=OWNER_SOURCE,
        collection_method="manual_gatt_inventory",
        original_retained=False,
    )
    manifest["confidence"] = "low"
    manifest["device_context"] = {
        "model_family": "jring-family",
        "firmware_major": "v1",
    }
    serialized = json.dumps(manifest)
    if container == "markdown":
        name, content = "notes.md", "```json\n" + serialized + "\n```\n"
    elif container == "python":
        name, content = "helper.py", "ledger = " + repr(manifest) + "\n"
    elif container == "python_kwargs":
        name = "helper.py"
        content = (
            "ledger = dict(schema_" + "version=1, provenance=dict(source="
            + repr(OWNER_SOURCE)
            + "), redactions={})\n"
        )
    else:
        name = "notes.md"
        content = "source: " + OWNER_SOURCE + "\n"
    (tmp_path / name).write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


def test_repository_scan_rejects_public_claim_embedded_in_markdown(tmp_path):
    content = "```json\n" + json.dumps(safe_public_claim()) + "\n```\n"
    (tmp_path / "candidate.md").write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "invalid_fixture"


@pytest.mark.parametrize("container", ["python", "yaml"])
def test_repository_scan_rejects_public_claim_in_other_mapping_syntax(
    tmp_path, container
):
    operation = "vendor_main_" + "device_info_canary_v1"
    if container == "python":
        content = (
            "claim = dict(schema_" + "version=2, provenance={}, operation="
            + repr(operation)
            + ", runtime_"
            + "authority={})\n"
        )
        name = "claim.py"
    else:
        content = (
            "schema_" + "version: 2\nprovenance: {}\noperation: " + operation
            + "\nruntime_" + "authority: {}\n"
        )
        name = "claim.md"
    (tmp_path / name).write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "invalid_fixture"


@pytest.mark.parametrize(
    "name,content",
    [
        ("notes.md", "device=" + ":".join(("AA", "BB", "CC", "DD", "EE", "FF"))),
        ("helper.py", "device = " + repr(":".join(("AA", "BB", "CC", "DD", "EE", "FF")))),
        ("payload.md", "raw_payload: " + "00112233" + "44556677"),
        ("time.py", "observed_at = " + repr("2026-08-" + "24T12:34:56Z")),
        ("health.rst", "heart_" + "rate: 72\n"),
        ("inline.md", "record = {\"heart_" + "rate\": 72}\n"),
        (
            "raw.py",
            "raw_" + "payload = bytes.fromhex(" + repr("0011223344556677") + ")\n",
        ),
        ("SOURCE", "heart_rate=72\n"),
    ],
)
def test_repository_scan_rejects_sensitive_text_regardless_of_filename(
    tmp_path, name, content
):
    (tmp_path / name).write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "unsafe_content"


def test_cli_failure_does_not_echo_sensitive_values(tmp_path, capsys):
    unsafe = safe_manifest()
    unsafe["notes"] = "device " + SYNTHETIC_ADDRESS
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(unsafe))

    assert main(["validate", str(path)]) == 2
    captured = capsys.readouterr()
    assert "unsafe_content" in captured.err
    assert "DE:AD" not in captured.out + captured.err


def test_cli_names_v2_as_a_non_authoritative_public_candidate(tmp_path, capsys):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(safe_public_claim()))

    assert main(["validate", str(path)]) == 0
    captured = capsys.readouterr()
    assert "Public evidence candidate" in captured.out
    assert "runtime and hardware authority remain false" in captured.out
    assert captured.err == ""


def test_repository_evidence_scan_rejects_raw_artifacts(tmp_path):
    clean_repository = Path(__file__).parents[1]
    scan_repository(clean_repository)

    (tmp_path / "private.pcapng").write_bytes(b"synthetic")
    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "forbidden_artifact"
    assert "private.pcapng" not in str(raised.value)


def test_repository_scan_revalidates_evidence_json(tmp_path):
    evidence = tmp_path / "tests" / "fixtures" / "evidence"
    evidence.mkdir(parents=True)
    unsafe = safe_manifest()
    unsafe["account_email"] = SYNTHETIC_EMAIL
    (evidence / "unsafe-manifest.json").write_text(json.dumps(unsafe))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "unsafe_content"
    assert "person@" not in str(raised.value)


def test_repository_scan_rejects_disguised_sensitive_data(tmp_path):
    secret = SYNTHETIC_ADDRESS
    (tmp_path / "innocent-looking.txt").write_text(f"device={secret}\n")

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "unsafe_content"
    assert secret not in str(raised.value)


def test_repository_scan_rejects_disguised_capture_signature(tmp_path):
    (tmp_path / "ordinary.bin").write_bytes(b"\x0a\x0d\x0d\x0a" + b"synthetic")

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "forbidden_artifact"


def test_repository_scan_rejects_health_data_in_text(tmp_path):
    (tmp_path / "measurements.csv").write_text("heart_rate,72\n")

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "unsafe_content"


@pytest.mark.parametrize(
    "name,content",
    [
        (
            "notes.md",
            "/* " + "JADX INFO: loaded from: classes2.dex */\npublic class Copy {}\n",
        ),
        (
            "helper.py",
            "package com.sxr.sdk.ble." + "keepfit;\npublic class Copy {}\n",
        ),
        (
            "app-helper.py",
            "package com.jaga.ibraceletplus." + "jyring;\npublic class Copy {}\n",
        ),
        (
            "warning.txt",
            "/* " + "JADX WARN: reconstructed output */\n",
        ),
        (
            "failed.txt",
            "Method not " + "decompiled: dependency method\n",
        ),
        (
            "incorrect.txt",
            "Code decompiled " + "incorrectly, please refer to instructions dump.\n",
        ),
        (
            "SOURCE",
            "." + "class public Lcom/vendor/Copy;\n." + "super Ljava/lang/Object;\n",
        ),
    ],
)
def test_repository_scan_rejects_decompiler_output_in_every_text_type(
    tmp_path, name, content
):
    (tmp_path / name).write_text(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "forbidden_artifact"
    assert name not in str(raised.value)


@pytest.mark.parametrize(
    "name,content",
    [
        ("classes.bin", b"dex\n035\x00" + b"x" * 16),
        ("native.bin", b"\x7fELF" + b"x" * 16),
        ("bundle.bin", b"\x1f\x8b\x08" + b"x" * 16),
        ("archive.bin", b"Rar!\x1a\x07\x00" + b"x" * 16),
    ],
)
def test_repository_scan_rejects_disguised_vendor_binary_classes(
    tmp_path, name, content
):
    (tmp_path / name).write_bytes(content)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "forbidden_artifact"
    assert name not in str(raised.value)


def test_owner_evidence_file_requires_private_permissions(tmp_path):
    manifest = safe_manifest()
    manifest["provenance"] = dict(
        source=OWNER_SOURCE,
        collection_method="manual_gatt_inventory",
        original_retained=False,
    )
    manifest["confidence"] = "low"
    manifest["device_context"] = {"model_family": "jring-family", "firmware_major": "v1"}
    path = tmp_path / "owner-manifest.json"
    path.write_text(json.dumps(manifest))
    path.chmod(0o644)

    assert main(["validate", str(path)]) == 2


def test_owner_evidence_is_never_commit_eligible_even_with_private_permissions(tmp_path):
    evidence = tmp_path / "tests" / "fixtures" / "evidence"
    evidence.mkdir(parents=True)
    manifest = safe_manifest()
    manifest["provenance"] = dict(
        source=OWNER_SOURCE,
        collection_method="manual_gatt_inventory",
        original_retained=False,
    )
    manifest["confidence"] = "low"
    manifest["device_context"] = {
        "model_family": "jring-family",
        "firmware_major": "v1",
    }
    path = evidence / "owner-manifest.json"
    path.write_text(json.dumps(manifest))
    path.chmod(0o600)

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "private_evidence"


def test_repository_scan_fails_closed_for_missing_root(tmp_path):
    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path / "missing")
    assert raised.value.code == "invalid_repository"
