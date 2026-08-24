import json
from pathlib import Path

import pytest

from scripts.evidence_tool import (
    EvidenceError,
    derive_fixture,
    main,
    scan_repository,
    serialize_fixture,
    validate_manifest,
)


FIXTURES = Path(__file__).parent / "fixtures" / "evidence"


def safe_manifest():
    return json.loads((FIXTURES / "synthetic-hid-manifest.json").read_text())


@pytest.mark.parametrize(
    "field,value,secret",
    [
        ("notes", "device DE:AD:BE:EF:00:01", "DE:AD"),
        ("notes", "object /org/bluez/hci0/dev_DE_AD_BE_EF_00_01", "/org/bluez"),
        ("account_email", "person@example.invalid", "person@"),
        ("observed_at", "2026-08-24T12:34:56Z", "12:34"),
        ("heart_rate", 72, "72"),
        ("raw_payload", "00112233445566778899", "001122"),
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


def test_cli_failure_does_not_echo_sensitive_values(tmp_path, capsys):
    unsafe = safe_manifest()
    unsafe["notes"] = "device DE:AD:BE:EF:00:01"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(unsafe))

    assert main(["validate", str(path)]) == 2
    captured = capsys.readouterr()
    assert "unsafe_content" in captured.err
    assert "DE:AD" not in captured.out + captured.err


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
    unsafe["account_email"] = "person@example.invalid"
    (evidence / "unsafe-manifest.json").write_text(json.dumps(unsafe))

    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path)
    assert raised.value.code == "unsafe_content"
    assert "person@" not in str(raised.value)


def test_repository_scan_rejects_disguised_sensitive_data(tmp_path):
    secret = "DE:AD:BE:EF:00:01"
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


def test_owner_evidence_file_requires_private_permissions(tmp_path):
    manifest = safe_manifest()
    manifest["provenance"] = {
        "source": "owner_authorized",
        "collection_method": "manual_gatt_inventory",
        "original_retained": False,
    }
    manifest["confidence"] = "low"
    manifest["device_context"] = {"model_family": "jring-family", "firmware_major": "v1"}
    path = tmp_path / "owner-manifest.json"
    path.write_text(json.dumps(manifest))
    path.chmod(0o644)

    assert main(["validate", str(path)]) == 2


def test_repository_scan_fails_closed_for_missing_root(tmp_path):
    with pytest.raises(EvidenceError) as raised:
        scan_repository(tmp_path / "missing")
    assert raised.value.code == "invalid_repository"
