#!/usr/bin/env python3
"""Fail-closed validation and minimal derivation for JRing evidence manifests."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_REPOSITORY_FILE_BYTES = 16 * 1024 * 1024
_MAC = re.compile(r"(?i)(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}")
_BLUEZ_PATH = re.compile(r"/org/bluez(?:/[A-Za-z0-9_]+)+")
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PRECISE_TIME = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?")
_PERSONAL_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?"
)
_LONG_HEX = re.compile(r"(?i)\b[0-9a-f]{16,}\b")
_UNSAFE_TEXT_FIELD = re.compile(
    r"(?im)^\s*(?:account|account_email|account_id|bluetooth_address|blood_pressure|"
    r"device_id|ecg|email|heart_rate|health|health_measurement|mac|mac_address|"
    r"oxygen|payload|raw_bytes|raw_payload|raw_report|report_map|serial|serial_number|"
    r"spo2|temperature|timestamp|token|user|user_id|username)\s*[:=,]"
)
_UNSAFE_TEXT_ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:account|account_email|account_id|bluetooth_address|blood_pressure|"
    r"device_id|ecg|email|heart_rate|health_measurement|mac_address|raw_bytes|"
    r"raw_payload|raw_report|report_map|serial_number|spo2|temperature|timestamp|"
    r"user_id|username)\s*[:=]"
)
_PYTHON_PRIVATE_VALUE = re.compile(
    r"(?im)^\s*(?:(?:blood_pressure|heart_rate|spo2|temperature)\s*=\s*[-+]?\d|"
    r"(?:raw_bytes|raw_payload|raw_report|report_map)\s*=\s*"
    r"(?:[rubf]*['\"][0-9a-f]|[-+]?\d))"
)
_EMBEDDED_OWNER_LEDGER = re.compile(
    r"(?im)['\"]?source['\"]?\s*"
    r"(?::|(?<![=!])=(?!=))\s*['\"]?owner_authorized['\"]?"
)
_EMBEDDED_MEASUREMENT = re.compile(
    r"(?im)(?:['\"](?:blood_pressure|heart_rate|spo2|temperature)['\"]|"
    r"(?<![A-Za-z0-9_.])(?:blood_pressure|heart_rate|spo2|temperature))"
    r"\s*:\s*[-+]?\d"
)
_EMBEDDED_RAW_CONSTRUCTOR = re.compile(
    r"(?im)\b(?:raw_bytes|raw_payload|raw_report|report_map)\s*=\s*"
    r"bytes\.fromhex\s*\("
)
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

_UNSAFE_FIELDS = {
    "account",
    "account_email",
    "account_id",
    "bluetooth_address",
    "blood_pressure",
    "captured_at",
    "capture",
    "device_id",
    "ecg",
    "email",
    "heart_rate",
    "health",
    "health_measurement",
    "mac",
    "mac_address",
    "observed_at",
    "oxygen",
    "packet",
    "payload",
    "raw_bytes",
    "raw_payload",
    "raw_report",
    "report_map",
    "serial",
    "serial_number",
    "sleep",
    "spo2",
    "temperature",
    "timestamp",
    "token",
    "user",
    "user_id",
    "username",
}
_REQUIRED_REDACTIONS = {
    "bluetooth_addresses",
    "account_identifiers",
    "precise_timestamps",
    "health_measurements",
    "raw_payloads",
}
_PUBLIC_CLAIM_REDACTIONS = _REQUIRED_REDACTIONS | {
    "bluez_paths",
    "unique_device_identifiers",
}
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "evidence_id",
    "provenance",
    "consent",
    "operation",
    "device_context",
    "redactions",
    "coverage",
    "confidence",
    "facts",
}
_OPERATIONS = {"service_inventory", "device_information", "neutral_event"}
_CONFIDENCE = {"synthetic", "low", "medium", "high"}
_SOURCES = {"synthetic", "owner_authorized"}
_METHODS = {"synthetic_construction", "manual_gatt_inventory", "sanitized_tool_export"}
_PUBLIC_CLAIM_FIELDS = {
    "schema_version",
    "claim_id",
    "provenance",
    "consent",
    "operation",
    "device_context",
    "redactions",
    "protocol",
    "effects",
    "synthetic_vectors",
    "maturity",
    "review",
    "runtime_authority",
}
_DEVICE_INFO_OPERATION = "vendor_main_device_info_canary_v1"
_DEVICE_INFO_PROTOCOL = {
    "endpoint_profile": "vendor_main",
    "request_builder": "encode_static_query:device_info",
    "response_parser": "parse_vendor_device_info",
    "terminal_set": [
        "device_information_rejected",
        "device_information_succeeded",
    ],
    "integrity_rule": "canary_success_requires_valid_seeded_crc",
    "identifier_policy": "not_materialized",
}
_DEVICE_INFO_EFFECTS = {
    "connection": True,
    "notification_activation": True,
    "notification_deactivation_required": True,
    "vendor_write": True,
    "vendor_write_kind": "with_response",
    "maximum_attempts": 1,
    "maximum_writes_per_attempt": 1,
    "automatic_retry": False,
    "disconnect_required": True,
    "cleanup_must_complete_before_result": True,
    "binding": False,
    "bonding": False,
    "cloud_network": False,
    "startup_time_write": False,
    "input_injection": False,
    "ota": False,
    "raw_retention": False,
}
_DEVICE_INFO_VECTORS = [
    {
        "case": "bad_integrity",
        "fixture_kind": "device_information_bad_integrity",
        "expected_canary_outcome": "rejected_bad_integrity",
    },
    {
        "case": "rejection",
        "fixture_kind": "device_information_rejection",
        "expected_canary_outcome": "device_rejected",
    },
    {
        "case": "success",
        "fixture_kind": "device_information_success",
        "expected_canary_outcome": "succeeded",
    },
]
_CANDIDATE_REVIEW = {
    "status": "candidate",
    "required_gates": [
        "hardware_evidence",
        "operation_authorization",
        "privacy_review",
        "protocol_review",
    ],
}
_NO_RUNTIME_AUTHORITY = {
    "runnable": False,
    "live_eligible": False,
    "owner_authorized": False,
    "hardware_eligible": False,
    "hardware_verified": False,
    "generic_vendor_io_authorized": False,
}
_FORBIDDEN_NAMES = (".pcap", ".pcapng", ".btsnoop", ".hcidump")
_FORBIDDEN_SUFFIXES = {".har", ".apk", ".xapk"}
_RESERVED_EVIDENCE_SUFFIXES = (
    "-manifest.json",
    "-claim.json",
    "-fixture.json",
)
_IGNORED_DIRECTORIES = {".git", ".venv", ".pytest_cache", "build", "dist", "__pycache__"}
_FORBIDDEN_MAGIC_PREFIXES = (
    b"dex\n",
    b"\x7fELF",
    b"\x1f\x8b",
    b"BZh",
    b"Rar!\x1a\x07",
    b"7z\xbc\xaf\x27\x1c",
    b"\x28\xb5\x2f\xfd",
)
_DECOMPILER_MARKERS = (
    b"/* " + b"JADX INFO:",
    b"/*  " + b"JADX ERROR:",
    b"/* " + b"JADX WARN:",
    b"Method not " + b"decompiled:",
    b"Code decompiled " + b"incorrectly, please refer to instructions dump.",
    b"." + b"class public L",
    b"." + b"super Ljava/",
)
_VENDOR_JAVA_PACKAGES = (
    b"package com.sxr.sdk.ble." + b"keepfit;",
    b"package com.jaga.ibraceletplus." + b"jyring;",
)


class EvidenceError(ValueError):
    def __init__(self, code: str, field: str):
        self.code = code
        self.field = field
        super().__init__(f"{code}: evidence rejected at {field}")


def _reject(code: str, field: str) -> None:
    raise EvidenceError(code, field)


def _normalized_field(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def _scan_sensitive(
    value: object, *, in_redactions: bool = False, allow_long_hex: bool = False
) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_field(key)
            if not in_redactions and normalized in _UNSAFE_FIELDS:
                _reject("unsafe_content", "sensitive field")
            _scan_sensitive(
                child,
                in_redactions=in_redactions or key == "redactions",
                allow_long_hex=allow_long_hex,
            )
        return
    if isinstance(value, list):
        for child in value:
            _scan_sensitive(
                child, in_redactions=in_redactions, allow_long_hex=allow_long_hex
            )
        return
    if isinstance(value, str):
        patterns = (_MAC, _BLUEZ_PATH, _EMAIL, _PRECISE_TIME)
        if any(pattern.search(value) for pattern in patterns) or (
            not allow_long_hex and _LONG_HEX.search(value)
        ):
            _reject("unsafe_content", "sensitive value")


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _reject("invalid_manifest", field)
    return value


def _exact_fields(value: dict[str, Any], fields: set[str], field: str) -> None:
    if set(value) != fields:
        _reject("invalid_manifest", field)


def _strict_equal(value: object, expected: object) -> bool:
    if type(value) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(value) == set(expected) and all(
            _strict_equal(value[key], child) for key, child in expected.items()
        )
    if isinstance(expected, list):
        return len(value) == len(expected) and all(
            _strict_equal(item, child) for item, child in zip(value, expected)
        )
    return value == expected


def _claim_mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _reject("invalid_claim", field)
    return value


def _claim_exact_fields(value: dict[str, Any], fields: set[str], field: str) -> None:
    if set(value) != fields:
        _reject("invalid_claim", field)


def _claim_slug(value: object, field: str, *, limit: int = 64) -> str:
    if not isinstance(value, str) or len(value) > limit or not _SLUG.fullmatch(value):
        _reject("invalid_claim", field)
    return value


def _slug(value: object, field: str, *, limit: int = 64) -> str:
    if not isinstance(value, str) or len(value) > limit or not _SLUG.fullmatch(value):
        _reject("invalid_manifest", field)
    return value


def validate_manifest(manifest: object) -> dict[str, Any]:
    _scan_sensitive(manifest)
    root = _mapping(manifest, "manifest")
    _exact_fields(root, _TOP_LEVEL_FIELDS, "manifest fields")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        _reject("invalid_manifest", "schema_version")
    _slug(root.get("evidence_id"), "evidence_id")

    provenance = _mapping(root.get("provenance"), "provenance")
    _exact_fields(
        provenance,
        {"source", "collection_method", "original_retained"},
        "provenance fields",
    )
    if provenance.get("source") not in _SOURCES:
        _reject("invalid_manifest", "provenance.source")
    if provenance.get("collection_method") not in _METHODS:
        _reject("invalid_manifest", "provenance.collection_method")
    if provenance.get("original_retained") is not False:
        _reject("invalid_manifest", "provenance.original_retained")
    if (
        provenance["source"] == "synthetic"
        and provenance["collection_method"] != "synthetic_construction"
    ):
        _reject("invalid_manifest", "synthetic provenance")
    if (
        provenance["source"] == "owner_authorized"
        and provenance["collection_method"] == "synthetic_construction"
    ):
        _reject("invalid_manifest", "owner provenance")

    consent = _mapping(root.get("consent"), "consent")
    _exact_fields(consent, {"publication", "scope"}, "consent fields")
    if consent != {"publication": "granted", "scope": "public_repository"}:
        _reject("invalid_manifest", "consent")

    if root.get("operation") not in _OPERATIONS:
        _reject("invalid_manifest", "operation")
    context = _mapping(root.get("device_context"), "device_context")
    _exact_fields(context, {"model_family", "firmware_major"}, "device_context fields")
    _slug(context.get("model_family"), "device_context.model_family", limit=40)
    _slug(context.get("firmware_major"), "device_context.firmware_major", limit=40)
    if provenance["source"] == "synthetic" and not all(
        str(value).startswith("synthetic") for value in context.values()
    ):
        _reject("invalid_manifest", "synthetic device_context")

    redactions = _mapping(root.get("redactions"), "redactions")
    _exact_fields(redactions, _REQUIRED_REDACTIONS, "redactions")
    if any(value is not True for value in redactions.values()):
        _reject("invalid_manifest", "redactions")

    coverage = root.get("coverage")
    if not isinstance(coverage, list) or not coverage:
        _reject("invalid_manifest", "coverage")
    normalized_coverage = []
    for item in coverage:
        name = _slug(item, "coverage item")
        if _normalized_field(name) in _UNSAFE_FIELDS:
            _reject("unsafe_content", "coverage item")
        normalized_coverage.append(name)
    if len(set(normalized_coverage)) != len(normalized_coverage):
        _reject("invalid_manifest", "coverage")

    if root.get("confidence") not in _CONFIDENCE:
        _reject("invalid_manifest", "confidence")
    if (root["confidence"] == "synthetic") != (provenance["source"] == "synthetic"):
        _reject("invalid_manifest", "confidence provenance")
    facts = _mapping(root.get("facts"), "facts")
    if set(facts) != set(normalized_coverage):
        _reject("invalid_manifest", "facts coverage")
    for name, value in facts.items():
        if _normalized_field(name) in _UNSAFE_FIELDS:
            _reject("unsafe_content", "fact name")
        if type(value) not in {bool, str}:
            _reject("invalid_manifest", "fact value")
        if isinstance(value, str):
            _slug(value, "fact value", limit=40)
    return root


def validate_public_claim(claim: object) -> dict[str, Any]:
    """Validate a commit-eligible candidate without granting runtime authority.

    Schema 2 is deliberately operation-specific. It can carry a synthetic candidate or
    a separately reviewed public derivation from private owner evidence, but it cannot
    authorize a Bluetooth operation or assert general hardware support.
    """

    _scan_sensitive(claim)
    root = _claim_mapping(claim, "claim")
    _claim_exact_fields(root, _PUBLIC_CLAIM_FIELDS, "claim fields")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 2:
        _reject("invalid_claim", "schema_version")

    provenance = _claim_mapping(root.get("provenance"), "provenance")
    _claim_exact_fields(
        provenance, {"source", "private_evidence_reference"}, "provenance fields"
    )
    source = provenance.get("source")
    if source not in {"synthetic", "public_derived"}:
        _reject("invalid_claim", "provenance.source")
    expected_reference = "not_applicable" if source == "synthetic" else "withheld"
    if provenance.get("private_evidence_reference") != expected_reference:
        _reject("invalid_claim", "provenance.private_evidence_reference")
    expected_claim_id = (
        "synthetic-vendor-device-info"
        if source == "synthetic"
        else "vendor-device-info-public-candidate"
    )
    if root.get("claim_id") != expected_claim_id:
        _reject("invalid_claim", "claim_id")

    consent = _claim_mapping(root.get("consent"), "consent")
    if not _strict_equal(
        consent, {"publication": "granted", "scope": "public_repository"}
    ):
        _reject("invalid_claim", "consent")
    if root.get("operation") != _DEVICE_INFO_OPERATION:
        _reject("invalid_claim", "operation")

    context = _claim_mapping(root.get("device_context"), "device_context")
    _claim_exact_fields(context, {"model_family", "firmware_major"}, "device context")
    expected_context = (
        {"model_family": "synthetic-ring", "firmware_major": "synthetic"}
        if source == "synthetic"
        else {"model_family": "withheld", "firmware_major": "withheld"}
    )
    if not _strict_equal(context, expected_context):
        _reject("invalid_claim", "provenance device context")

    redactions = _claim_mapping(root.get("redactions"), "redactions")
    _claim_exact_fields(redactions, _PUBLIC_CLAIM_REDACTIONS, "redactions")
    if any(value is not True for value in redactions.values()):
        _reject("invalid_claim", "redactions")

    closed_values = (
        ("protocol", _DEVICE_INFO_PROTOCOL),
        ("effects", _DEVICE_INFO_EFFECTS),
        ("synthetic_vectors", _DEVICE_INFO_VECTORS),
        (
            "maturity",
            "synthetic_candidate"
            if source == "synthetic"
            else "public_derived_candidate",
        ),
        ("review", _CANDIDATE_REVIEW),
        ("runtime_authority", _NO_RUNTIME_AUTHORITY),
    )
    for field, expected in closed_values:
        if not _strict_equal(root.get(field), expected):
            _reject("invalid_claim", field)
    return root


def derive_fixture(manifest: object) -> dict[str, Any]:
    safe = validate_manifest(manifest)
    source = safe["provenance"]["source"]
    coverage = sorted(safe["coverage"])
    return {
        "schema_version": 1,
        "evidence_id": safe["evidence_id"],
        "source": source,
        "synthetic": source == "synthetic",
        "operation": safe["operation"],
        "device_context": {
            "model_family": safe["device_context"]["model_family"],
            "firmware_major": safe["device_context"]["firmware_major"],
        },
        "coverage": coverage,
        "confidence": safe["confidence"],
        "facts": {name: safe["facts"][name] for name in coverage},
    }


def derive_public_claim(claim: object) -> dict[str, Any]:
    safe = validate_public_claim(claim)
    return {
        "schema_version": 2,
        "claim_id": safe["claim_id"],
        "source": safe["provenance"]["source"],
        "operation": safe["operation"],
        "device_context": dict(safe["device_context"]),
        "protocol": dict(safe["protocol"]),
        "effects": dict(safe["effects"]),
        "synthetic_vectors": [dict(item) for item in safe["synthetic_vectors"]],
        "maturity": safe["maturity"],
        "review": {
            "status": safe["review"]["status"],
            "required_gates": list(safe["review"]["required_gates"]),
        },
        "runtime_authority": dict(safe["runtime_authority"]),
    }


def serialize_fixture(fixture: dict[str, Any]) -> str:
    return json.dumps(fixture, indent=2, sort_keys=True) + "\n"


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_size > _MAX_MANIFEST_BYTES:
            _reject("invalid_manifest", "input file")
        with path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except EvidenceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("invalid_manifest", "input file") from exc
    version = manifest.get("schema_version") if isinstance(manifest, dict) else None
    if type(version) is not int:
        _reject("invalid_manifest", "schema_version")
    safe = validate_manifest(manifest) if version == 1 else validate_public_claim(manifest)
    if (
        version == 1
        and safe["provenance"]["source"] == "owner_authorized"
        and details.st_mode & 0o077
    ):
        _reject("unsafe_permissions", "input file")
    return safe


def _repository_files(root: Path) -> list[Path]:
    try:
        if not root.is_dir():
            _reject("invalid_repository", "repository root")
    except OSError as exc:
        raise EvidenceError("invalid_repository", "repository root") from exc
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=False,
            capture_output=True,
        )
    except OSError:
        listed = None
    if listed is not None and listed.returncode == 0:
        candidates = [
            root / os.fsdecode(name)
            for name in listed.stdout.split(b"\0")
            if name
        ]
        return _validate_repository_files(candidates)

    results = []
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in _IGNORED_DIRECTORIES]
        current_path = Path(current)
        for name in files:
            path = current_path / name
            results.append(path)
    return _validate_repository_files(results)


def _validate_repository_files(paths: list[Path]) -> list[Path]:
    for path in paths:
        lowered = path.name.lower()
        if any(marker in lowered for marker in _FORBIDDEN_NAMES):
            _reject("forbidden_artifact", "repository file")
        if path.suffix.lower() in _FORBIDDEN_SUFFIXES:
            _reject("forbidden_artifact", "repository file")
        try:
            details = path.lstat()
            if not stat.S_ISREG(details.st_mode):
                _reject("forbidden_artifact", "repository file")
            if details.st_size > _MAX_REPOSITORY_FILE_BYTES:
                _reject("forbidden_artifact", "repository file")
            content = path.read_bytes()
            header = content[:8]
            if header[:4] in {
                b"\xa1\xb2\xc3\xd4",
                b"\xd4\xc3\xb2\xa1",
                b"\xa1\xb2\x3c\x4d",
                b"\x4d\x3c\xb2\xa1",
                b"\x0a\x0d\x0d\x0a",
            } or header == b"btsnoop\x00":
                _reject("forbidden_artifact", "repository file")
            if any(header.startswith(prefix) for prefix in _FORBIDDEN_MAGIC_PREFIXES):
                _reject("forbidden_artifact", "repository file")
            if any(marker in content for marker in _DECOMPILER_MARKERS):
                _reject("forbidden_artifact", "repository file")
            if any(package in content for package in _VENDOR_JAVA_PACKAGES) and (
                b"public class " in content
            ):
                _reject("forbidden_artifact", "repository file")
            if header.startswith(b"PK") and zipfile.is_zipfile(path):
                _reject("forbidden_artifact", "repository file")
        except EvidenceError:
            raise
        except (OSError, zipfile.BadZipFile) as exc:
            raise EvidenceError("unsafe_content", "repository file") from exc
    return sorted(paths)


def _looks_like_evidence(payload: object) -> bool:
    if not isinstance(payload, dict) or "schema_version" not in payload:
        return False
    fields = set(payload)
    return (
        {"provenance", "redactions"} <= fields
        or {"operation", "protocol", "runtime_authority"} <= fields
    )


def _scan_repository_text(text: str, path: Path) -> None:
    if _EMBEDDED_OWNER_LEDGER.search(text):
        _reject("private_evidence", "repository evidence")
    public_json_claim_markers = (
        re.search(r"(?is)['\"]schema_version['\"]\s*:\s*2\b", text),
        re.search(r"(?is)['\"]provenance['\"]\s*:", text),
        re.search(r"(?is)['\"]runtime_authority['\"]\s*:", text),
        re.search(r"(?is)vendor_main_device_info_canary_v1", text),
    )
    public_python_claim_markers = (
        re.search(r"(?im)\bschema_version\s*=\s*2\b", text),
        re.search(r"(?im)\bprovenance\s*=", text),
        re.search(r"(?im)\bruntime_authority\s*=", text),
        re.search(r"(?is)vendor_main_device_info_canary_v1", text),
    )
    public_yaml_claim_markers = (
        re.search(r"(?im)^\s*schema_version\s*:\s*2\b", text),
        re.search(r"(?im)^\s*provenance\s*:", text),
        re.search(r"(?im)^\s*runtime_authority\s*:", text),
        re.search(r"(?is)vendor_main_device_info_canary_v1", text),
    )
    if any(
        all(markers)
        for markers in (
            public_json_claim_markers,
            public_python_claim_markers,
            public_yaml_claim_markers,
        )
    ):
        _reject("invalid_fixture", "repository evidence")
    if _EMBEDDED_MEASUREMENT.search(text) or _EMBEDDED_RAW_CONSTRUCTOR.search(text):
        _reject("unsafe_content", "repository data")
    if any(pattern.search(text) for pattern in (_MAC, _BLUEZ_PATH, _EMAIL)):
        _reject("unsafe_content", "repository data")
    suffix = path.suffix.casefold()
    source_or_review_text = suffix in {".py", ".md", ".rst"}
    lock_or_workflow = suffix in {".lock", ".toml"} or (
        ".github" in path.parts and "workflows" in path.parts
    )
    if not source_or_review_text and not lock_or_workflow:
        if _PRECISE_TIME.search(text) or _LONG_HEX.search(text):
            _reject("unsafe_content", "repository data")
    elif source_or_review_text and _PERSONAL_TIMESTAMP.search(text):
        _reject("unsafe_content", "repository data")
    if suffix == ".py" and _PYTHON_PRIVATE_VALUE.search(text):
        _reject("unsafe_content", "repository data")
    if suffix in {".md", ".rst"} and _UNSAFE_TEXT_ASSIGNMENT.search(text):
        _reject("unsafe_content", "repository data")
    if not source_or_review_text and _UNSAFE_TEXT_FIELD.search(text):
        _reject("unsafe_content", "repository data")


def scan_repository(root: Path) -> None:
    manifests: dict[Path, dict[str, Any]] = {}
    claims: dict[Path, dict[str, Any]] = {}
    fixtures: dict[Path, object] = {}
    for path in _repository_files(root):
        lowered_name = path.name.casefold()
        reserved_suffix = next(
            (
                suffix
                for suffix in _RESERVED_EVIDENCE_SUFFIXES
                if lowered_name.endswith(suffix)
            ),
            None,
        )
        is_evidence = reserved_suffix is not None and path.name.endswith(
            reserved_suffix
        )
        if reserved_suffix is not None and not is_evidence:
            _reject("invalid_fixture", "repository evidence")

        try:
            text_content = path.read_text(encoding="utf-8")
        except UnicodeError:
            try:
                text_content = path.read_bytes().decode("utf-8", errors="ignore")
            except OSError as exc:
                raise EvidenceError("unsafe_content", "repository data") from exc
        except OSError as exc:
            raise EvidenceError("unsafe_content", "repository data") from exc
        parsed_json: object | None = None
        if text_content is not None and (
            path.suffix.casefold() == ".json"
            or text_content.lstrip().startswith(("{", "["))
        ):
            try:
                parsed_json = json.loads(text_content)
            except json.JSONDecodeError as exc:
                if path.suffix.casefold() == ".json":
                    raise EvidenceError(
                        "unsafe_content", "repository data"
                    ) from exc
        if not is_evidence and _looks_like_evidence(parsed_json):
            provenance = parsed_json.get("provenance")
            if (
                isinstance(provenance, dict)
                and provenance.get("source") == "owner_authorized"
            ):
                _reject("private_evidence", "repository evidence")
            _reject("invalid_fixture", "repository evidence")
        if not is_evidence:
            if parsed_json is not None:
                _scan_sensitive(parsed_json)
            elif text_content is not None:
                if path.suffix.casefold() == ".jsonl":
                    try:
                        for line in text_content.splitlines():
                            if line.strip():
                                _scan_sensitive(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise EvidenceError("unsafe_content", "repository data") from exc
                else:
                    _scan_repository_text(text_content, path)
            continue
        try:
            payload = json.loads(text_content)
        except json.JSONDecodeError as exc:
            raise EvidenceError("invalid_manifest", "repository evidence") from exc
        if path.name.endswith("-manifest.json"):
            manifest = validate_manifest(payload)
            if manifest["provenance"]["source"] == "owner_authorized":
                _reject("private_evidence", "repository evidence")
            manifests[path] = manifest
        elif path.name.endswith("-claim.json"):
            claims[path] = validate_public_claim(payload)
        else:
            _scan_sensitive(payload)
            fixtures[path] = payload
    for path, manifest in manifests.items():
        fixture_path = path.with_name(path.name.replace("-manifest.json", "-fixture.json"))
        if fixture_path not in fixtures or not _strict_equal(
            fixtures[fixture_path], derive_fixture(manifest)
        ):
            _reject("invalid_fixture", "repository evidence")
    for path, claim in claims.items():
        fixture_path = path.with_name(path.name.replace("-claim.json", "-fixture.json"))
        if fixture_path not in fixtures or not _strict_equal(
            fixtures[fixture_path], derive_public_claim(claim)
        ):
            _reject("invalid_fixture", "repository evidence")
    expected_fixtures = {
        path.with_name(path.name.replace("-manifest.json", "-fixture.json"))
        for path in manifests
    } | {
        path.with_name(path.name.replace("-claim.json", "-fixture.json"))
        for path in claims
    }
    if set(fixtures) != expected_fixtures:
        _reject("invalid_fixture", "repository evidence")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate minimal privacy-safe JRing evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "derive"):
        child = subparsers.add_parser(command)
        child.add_argument("manifest", type=Path)
    scan = subparsers.add_parser("scan")
    scan.add_argument("repository", type=Path, nargs="?", default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            scan_repository(args.repository)
            print("Repository evidence scan passed.")
        else:
            manifest = load_manifest(args.manifest)
            if args.command == "validate":
                message = (
                    "Evidence manifest passed fail-closed validation."
                    if manifest["schema_version"] == 1
                    else "Public evidence candidate passed fail-closed validation; "
                    "runtime and hardware authority remain false."
                )
                print(message)
            else:
                derived = (
                    derive_fixture(manifest)
                    if manifest["schema_version"] == 1
                    else derive_public_claim(manifest)
                )
                print(serialize_fixture(derived), end="")
    except EvidenceError as error:
        print(f"evidence: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
