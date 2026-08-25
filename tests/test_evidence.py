import json
from pathlib import Path

import pytest

from scripts.evidence_tool import (
    EvidenceError,
    derive_fixture,
    derive_public_claim,
    main,
    scan_repository,
    serialize_fixture,
    validate_manifest,
    validate_public_claim,
)


FIXTURES = Path(__file__).parent / "fixtures" / "evidence"
SYNTHETIC_ADDRESS = ":".join(("DE", "AD", "BE", "EF", "00", "01"))
SYNTHETIC_BLUEZ_PATH = "/org/" + "bluez/hci0/dev_DE_AD_BE_EF_00_01"
SYNTHETIC_EMAIL = "person@" + "example.invalid"
SYNTHETIC_TIMESTAMP = "2026-08-" + "24T12:34:56Z"
SYNTHETIC_PAYLOAD = "00112233" + "445566778899"
OWNER_SOURCE = "owner_" + "authorized"


def safe_manifest():
    return json.loads((FIXTURES / "synthetic-hid-manifest.json").read_text())


def safe_public_claim():
    return json.loads(
        (FIXTURES / "synthetic-vendor-device-info-claim.json").read_text()
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
