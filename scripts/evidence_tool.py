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
_OWNER_AUTHORIZED_SOURCE = "owner_" + "authorized"
_PRIVATE_DEVICE_INFO_KIND = "private_owner_" + "device_info_observation"
_EMBEDDED_OWNER_LEDGER = re.compile(
    r"(?im)['\"]?source['\"]?\s*"
    r"(?::|(?<![=!])=(?!=))\s*['\"]?"
    + re.escape(_OWNER_AUTHORIZED_SOURCE)
    + r"['\"]?"
)
_EMBEDDED_PRIVATE_DEVICE_INFO = re.compile(
    r"(?im)['\"]?manifest_kind['\"]?\s*"
    r"(?::|(?<![=!])=(?!=))\s*['\"]?"
    + re.escape(_PRIVATE_DEVICE_INFO_KIND)
    + r"['\"]?"
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
_SOURCES = {"synthetic", _OWNER_AUTHORIZED_SOURCE}
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
_PRIVATE_DEVICE_INFO_FIELDS = {
    "schema_version",
    "manifest_kind",
    "evidence_id",
    "provenance",
    "consent",
    "evidence_scope",
    "operation",
    "route_observation",
    "dispatch_observation",
    "response_observation",
    "cleanup_observation",
    "attempt_outcome",
    "redactions",
    "authority",
}
_PRIVATE_DEVICE_INFO_PROVENANCE = {
    "source": _OWNER_AUTHORIZED_SOURCE,
    "collection_method": "self_declared_historical_record",
    "original_retained": False,
}
_PRIVATE_DEVICE_INFO_CONSENT = {
    "collection": "granted_for_observed_single_attempt",
    "operation_execution": "granted_for_observed_single_attempt",
    "repeat_execution": "not_granted",
    "publication": "not_granted",
}
_PRIVATE_DEVICE_INFO_OPERATION = {
    "operation_id": _DEVICE_INFO_OPERATION,
    "route": "main",
    "write_kind": "gatt_write_with_response",
    "terminal_rule": "single_matched_response",
    "retry_policy": "none",
}
_PRIVATE_DEVICE_INFO_REDACTIONS = {
    "bluetooth_addresses",
    "bluez_paths",
    "account_identifiers",
    "precise_timestamps",
    "unique_device_identifiers",
    "exact_model",
    "exact_firmware",
    "raw_requests",
    "raw_responses",
    "decoded_device_information",
    "health_measurements",
}
_PRIVATE_DEVICE_INFO_AUTHORITY = {
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
_PREFLIGHT_CODES = {
    "structurally_ready",
    "invalid_connection_generation",
    "malformed_service_inventory",
    "malformed_metadata",
    "service_not_advertised",
    "request_endpoint_missing",
    "response_endpoint_missing",
    "request_endpoint_ambiguous",
    "response_endpoint_ambiguous",
    "request_endpoint_wrong_service",
    "response_endpoint_wrong_service",
    "response_write_unavailable",
    "notify_unavailable",
    "cccd_not_advertised",
    "cccd_ambiguous",
    "target_identity_missing",
    "target_identity_ambiguous",
    "target_generation_mismatch",
    "target_metadata_mismatch",
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
        provenance["source"] == _OWNER_AUTHORIZED_SOURCE
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


def validate_private_device_info_manifest(manifest: object) -> dict[str, Any]:
    """Validate one historical, private device-info observation.

    This validates internal consistency only. It authenticates neither the owner nor
    the observation and never grants authority for another Bluetooth attempt.
    """

    _scan_sensitive(manifest)
    root = _mapping(manifest, "private manifest")
    _exact_fields(root, _PRIVATE_DEVICE_INFO_FIELDS, "private manifest fields")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 2:
        _reject("invalid_manifest", "schema_version")
    if root.get("manifest_kind") != _PRIVATE_DEVICE_INFO_KIND:
        _reject("invalid_manifest", "manifest_kind")
    if root.get("evidence_id") != "withheld":
        _reject("invalid_manifest", "evidence_id")

    for field, expected in (
        ("provenance", _PRIVATE_DEVICE_INFO_PROVENANCE),
        ("consent", _PRIVATE_DEVICE_INFO_CONSENT),
        ("operation", _PRIVATE_DEVICE_INFO_OPERATION),
        ("authority", _PRIVATE_DEVICE_INFO_AUTHORITY),
    ):
        if not _strict_equal(root.get(field), expected):
            _reject("invalid_manifest", field)

    scope = _mapping(root.get("evidence_scope"), "evidence_scope")
    _exact_fields(
        scope,
        {
            "observation_scope",
            "generation_ref",
            "model_family",
            "firmware_major",
            "model_scope",
            "firmware_scope",
            "protocol_evidence_contract",
            "generalization",
        },
        "evidence_scope fields",
    )
    fixed_scope = {
        "observation_scope": "single_attempt_single_generation",
        "generation_ref": "manifest_local_generation_1",
        "model_family": "withheld",
        "firmware_major": "withheld",
        "model_scope": "not_recorded",
        "firmware_scope": "not_recorded",
        "protocol_evidence_contract": "device_info_static_aggregate_v1",
        "generalization": "none",
    }
    if any(scope.get(name) != value for name, value in fixed_scope.items()):
        _reject("invalid_manifest", "evidence_scope")

    route = _mapping(root.get("route_observation"), "route_observation")
    _exact_fields(
        route,
        {
            "generation_ref",
            "connection_attempt_count",
            "connection_outcome",
            "metadata_snapshot",
            "preflight_result",
            "request_target_ownership",
            "response_target_ownership",
            "values_read",
        },
        "route_observation fields",
    )
    if route.get("generation_ref") != scope["generation_ref"]:
        _reject("invalid_manifest", "route_observation.generation_ref")
    if type(route.get("connection_attempt_count")) is not int or route[
        "connection_attempt_count"
    ] not in {0, 1}:
        _reject("invalid_manifest", "route_observation.connection_attempt_count")
    if route.get("connection_outcome") not in {
        "not_attempted",
        "failed",
        "connected",
        "outcome_unknown",
    }:
        _reject("invalid_manifest", "route_observation.connection_outcome")
    if (route["connection_attempt_count"] == 0) != (
        route["connection_outcome"] == "not_attempted"
    ):
        _reject("invalid_manifest", "route_observation connection count")
    if route.get("metadata_snapshot") not in {
        "not_evaluated",
        "complete",
        "unavailable",
        "timed_out",
    }:
        _reject("invalid_manifest", "route_observation.metadata_snapshot")
    if route.get("preflight_result") not in _PREFLIGHT_CODES | {"not_evaluated"}:
        _reject("invalid_manifest", "route_observation.preflight_result")
    ownership = {"not_established", "confirmed_current_generation"}
    if route.get("request_target_ownership") not in ownership or route.get(
        "response_target_ownership"
    ) not in ownership:
        _reject("invalid_manifest", "route_observation target ownership")
    if route.get("values_read") is not False:
        _reject("invalid_manifest", "route_observation.values_read")

    connected = route["connection_outcome"] == "connected"
    connection_unknown = route["connection_outcome"] == "outcome_unknown"
    ready = route["preflight_result"] == "structurally_ready"
    targets_owned = (
        route["request_target_ownership"] == "confirmed_current_generation"
        and route["response_target_ownership"] == "confirmed_current_generation"
    )
    if ready != (connected and route["metadata_snapshot"] == "complete" and targets_owned):
        _reject("invalid_manifest", "route_observation readiness")
    if not ready and any(
        route[name] != "not_established"
        for name in ("request_target_ownership", "response_target_ownership")
    ):
        _reject("invalid_manifest", "route_observation target ownership")
    if not connected and (
        route["metadata_snapshot"] != "not_evaluated"
        or route["preflight_result"] != "not_evaluated"
    ):
        _reject("invalid_manifest", "route_observation connection")
    if connected and route["metadata_snapshot"] != "complete" and route[
        "preflight_result"
    ] != "not_evaluated":
        _reject("invalid_manifest", "route_observation metadata")

    dispatch = _mapping(root.get("dispatch_observation"), "dispatch_observation")
    _exact_fields(
        dispatch,
        {
            "subscription_attempt_count",
            "subscription_outcome",
            "cccd_acknowledgement",
            "write_attempt_count",
            "write_outcome",
            "write_order",
            "retry_count",
        },
        "dispatch_observation fields",
    )
    for name in ("subscription_attempt_count", "write_attempt_count"):
        if type(dispatch.get(name)) is not int or dispatch[name] not in {0, 1}:
            _reject("invalid_manifest", f"dispatch_observation.{name}")
    if type(dispatch.get("retry_count")) is not int or dispatch["retry_count"] != 0:
        _reject("invalid_manifest", "dispatch_observation.retry_count")
    subscription_states = {
        "not_attempted",
        "transport_call_completed",
        "failed_before_completion",
        "outcome_unknown",
    }
    write_states = {
        "not_attempted",
        "att_write_response_completed",
        "definitely_not_dispatched",
        "outcome_unknown",
    }
    if dispatch.get("subscription_outcome") not in subscription_states:
        _reject("invalid_manifest", "dispatch_observation.subscription_outcome")
    if dispatch.get("write_outcome") not in write_states:
        _reject("invalid_manifest", "dispatch_observation.write_outcome")
    if dispatch.get("cccd_acknowledgement") != "not_independently_observed":
        _reject("invalid_manifest", "dispatch_observation.cccd_acknowledgement")
    if (dispatch["subscription_attempt_count"] == 0) != (
        dispatch["subscription_outcome"] == "not_attempted"
    ):
        _reject("invalid_manifest", "dispatch_observation subscription count")
    if (dispatch["write_attempt_count"] == 0) != (
        dispatch["write_outcome"] == "not_attempted"
    ):
        _reject("invalid_manifest", "dispatch_observation write count")
    expected_write_order = (
        "not_applicable"
        if dispatch["write_attempt_count"] == 0
        else "after_subscription_completion"
    )
    if dispatch.get("write_order") != expected_write_order:
        _reject("invalid_manifest", "dispatch_observation.write_order")
    if not ready and (
        dispatch["subscription_attempt_count"] != 0
        or dispatch["write_attempt_count"] != 0
    ):
        _reject("invalid_manifest", "dispatch_observation route gate")
    if dispatch["write_attempt_count"] and dispatch[
        "subscription_outcome"
    ] != "transport_call_completed":
        _reject("invalid_manifest", "dispatch_observation subscription gate")

    response = _mapping(root.get("response_observation"), "response_observation")
    _exact_fields(
        response,
        {
            "terminal_outcome",
            "matched_terminal_count",
            "callback_projection",
            "parser_outcome",
            "integrity_outcome",
            "identifier_projection",
            "decoded_projection",
            "generation_match",
            "terminal_acceptance",
            "absence_reason",
        },
        "response_observation fields",
    )
    terminal = response.get("terminal_outcome")
    response_matrix = {
        "not_observed": (0, "not_observed", "not_attempted", {"not_evaluated"}),
        "success_response": (1, "accepted", "accepted", {"valid", "invalid"}),
        "device_failure": (
            1,
            "suppressed_failure",
            "not_attempted",
            {"not_evaluated"},
        ),
        "malformed_response": (
            1,
            "suppressed_malformed",
            "rejected",
            {"not_evaluated"},
        ),
    }
    if terminal not in response_matrix:
        _reject("invalid_manifest", "response_observation.terminal_outcome")
    count, callback, parser, integrities = response_matrix[terminal]
    if (
        type(response.get("matched_terminal_count")) is not int
        or response["matched_terminal_count"] != count
        or response.get("callback_projection") != callback
        or response.get("parser_outcome") != parser
        or response.get("integrity_outcome") not in integrities
    ):
        _reject("invalid_manifest", "response_observation state")
    if response.get("identifier_projection") != "not_materialized" or response.get(
        "decoded_projection"
    ) != "not_retained":
        _reject("invalid_manifest", "response_observation privacy")
    absence_reasons = {
        "write_not_dispatched",
        "deadline_elapsed_after_possible_dispatch",
        "cancelled_after_possible_dispatch",
        "disconnected_after_possible_dispatch",
        "unrelated_notifications_only",
        "callback_overflow",
    }
    if terminal == "not_observed":
        if response.get("generation_match") != "not_observed" or response.get(
            "terminal_acceptance"
        ) != "not_applicable":
            _reject("invalid_manifest", "response_observation acceptance")
        if response.get("absence_reason") not in absence_reasons:
            _reject("invalid_manifest", "response_observation.absence_reason")
    else:
        expected_acceptance = (
            "after_write_completion_current_generation"
            if dispatch["write_outcome"] == "att_write_response_completed"
            else "observed_current_generation_write_completion_unconfirmed"
        )
        if (
            response.get("generation_match") != "confirmed_current_generation"
            or response.get("terminal_acceptance") != expected_acceptance
            or response.get("absence_reason") != "not_applicable"
        ):
            _reject("invalid_manifest", "response_observation acceptance")
    if terminal != "not_observed" and (
        dispatch["write_attempt_count"] != 1
        or dispatch["write_outcome"]
        not in {"att_write_response_completed", "outcome_unknown"}
    ):
        _reject("invalid_manifest", "response_observation dispatch gate")
    if (
        dispatch["write_outcome"] in {"not_attempted", "definitely_not_dispatched"}
        and terminal != "not_observed"
    ):
        _reject("invalid_manifest", "response_observation dispatch outcome")
    possible_dispatch = dispatch["write_outcome"] in {
        "att_write_response_completed",
        "outcome_unknown",
    }
    if terminal == "not_observed" and (
        (response["absence_reason"] == "write_not_dispatched") == possible_dispatch
    ):
        _reject("invalid_manifest", "response_observation absence dispatch")

    cleanup = _mapping(root.get("cleanup_observation"), "cleanup_observation")
    _exact_fields(
        cleanup,
        {
            "callback_acceptance",
            "unsubscribe_attempt_count",
            "unsubscribe_outcome",
            "disconnect_attempt_count",
            "disconnect_outcome",
            "late_callback_disposition",
            "cleanup_sequence",
            "cleanup_outcome",
        },
        "cleanup_observation fields",
    )
    if cleanup.get("callback_acceptance") not in {
        "disabled_before_cleanup",
        "not_confirmed",
    }:
        _reject("invalid_manifest", "cleanup_observation.callback_acceptance")
    for name in ("unsubscribe_attempt_count", "disconnect_attempt_count"):
        if type(cleanup.get(name)) is not int or cleanup[name] not in {0, 1}:
            _reject("invalid_manifest", f"cleanup_observation.{name}")
    unsubscribe_actions = {
        "completed",
        "failed",
        "outcome_unknown",
    }
    disconnect_actions = {
        "completed",
        "failed",
        "outcome_unknown",
        "already_disconnected",
    }
    if cleanup.get("unsubscribe_outcome") not in unsubscribe_actions | {
        "not_required"
    } or cleanup.get("disconnect_outcome") not in disconnect_actions | {
        "not_required"
    }:
        _reject("invalid_manifest", "cleanup_observation action outcome")
    if cleanup.get("late_callback_disposition") not in {
        "none_observed",
        "discarded",
        "not_observable",
    }:
        _reject("invalid_manifest", "cleanup_observation late callback")
    if dispatch["subscription_attempt_count"] == 0 and cleanup[
        "late_callback_disposition"
    ] != "none_observed":
        _reject("invalid_manifest", "cleanup_observation late callback")
    if cleanup["callback_acceptance"] == "not_confirmed" and cleanup[
        "late_callback_disposition"
    ] != "not_observable":
        _reject("invalid_manifest", "cleanup_observation callback visibility")
    if cleanup["callback_acceptance"] == "disabled_before_cleanup" and cleanup[
        "late_callback_disposition"
    ] == "not_observable":
        _reject("invalid_manifest", "cleanup_observation callback visibility")
    if cleanup.get("cleanup_outcome") not in {
        "confirmed",
        "failed",
        "outcome_unknown",
        "not_required",
    }:
        _reject("invalid_manifest", "cleanup_observation.cleanup_outcome")
    if (dispatch["subscription_attempt_count"] == 0) != (
        cleanup["unsubscribe_attempt_count"] == 0
        and cleanup["unsubscribe_outcome"] == "not_required"
    ):
        _reject("invalid_manifest", "cleanup_observation unsubscribe")
    if dispatch["subscription_attempt_count"] == 1 and (
        cleanup["unsubscribe_attempt_count"] != 1
        or cleanup["unsubscribe_outcome"] == "not_required"
    ):
        _reject("invalid_manifest", "cleanup_observation unsubscribe")
    must_disconnect = connected or connection_unknown
    if must_disconnect != (cleanup["disconnect_attempt_count"] == 1):
        _reject("invalid_manifest", "cleanup_observation disconnect count")
    if must_disconnect == (cleanup["disconnect_outcome"] == "not_required"):
        _reject("invalid_manifest", "cleanup_observation disconnect")
    if cleanup["unsubscribe_attempt_count"] == 0:
        expected_sequence = (
            "disconnect_only"
            if cleanup["disconnect_attempt_count"] == 1
            else "no_cleanup_actions"
        )
    else:
        expected_sequence = "unsubscribe_then_disconnect"
    if cleanup.get("cleanup_sequence") != expected_sequence:
        _reject("invalid_manifest", "cleanup_observation.cleanup_sequence")

    action_states = (cleanup["unsubscribe_outcome"], cleanup["disconnect_outcome"])
    unsubscribe_confirmed = cleanup["unsubscribe_outcome"] in {
        "not_required",
        "completed",
    }
    disconnect_confirmed = cleanup["disconnect_outcome"] in {
        "not_required",
        "completed",
        "already_disconnected",
    }
    action_confirmed = (
        unsubscribe_confirmed
        and disconnect_confirmed
        and cleanup["callback_acceptance"] == "disabled_before_cleanup"
    )
    if action_confirmed:
        expected_cleanup = (
            "not_required"
            if all(state == "not_required" for state in action_states)
            else "confirmed"
        )
    elif "failed" in action_states:
        expected_cleanup = "failed"
    else:
        expected_cleanup = "outcome_unknown"
    if cleanup["cleanup_outcome"] != expected_cleanup:
        _reject("invalid_manifest", "cleanup_observation aggregate")

    if connection_unknown:
        expected_attempt = "uncertain"
    elif dispatch["write_outcome"] == "outcome_unknown":
        expected_attempt = "uncertain"
    elif (
        dispatch["write_outcome"] == "att_write_response_completed"
        and terminal == "success_response"
        and response["integrity_outcome"] == "valid"
        and cleanup["cleanup_outcome"] == "confirmed"
    ):
        expected_attempt = "succeeded"
    elif terminal == "device_failure" and cleanup["cleanup_outcome"] == "confirmed":
        expected_attempt = "device_rejected"
    elif (
        terminal == "success_response"
        and response["integrity_outcome"] == "invalid"
        and cleanup["cleanup_outcome"] == "confirmed"
    ):
        expected_attempt = "rejected_bad_integrity"
    elif terminal == "malformed_response" and cleanup["cleanup_outcome"] == "confirmed":
        expected_attempt = "rejected_malformed_response"
    elif (
        dispatch["write_outcome"] in {"not_attempted", "definitely_not_dispatched"}
        and terminal == "not_observed"
        and cleanup["cleanup_outcome"] in {"confirmed", "not_required"}
    ):
        expected_attempt = "aborted"
    else:
        expected_attempt = "uncertain"
    if root.get("attempt_outcome") != expected_attempt:
        _reject("invalid_manifest", "attempt_outcome")

    redactions = _mapping(root.get("redactions"), "redactions")
    _exact_fields(redactions, _PRIVATE_DEVICE_INFO_REDACTIONS, "redactions")
    if any(value is not True for value in redactions.values()):
        _reject("invalid_manifest", "redactions")
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


def _artifact_kind(payload: object) -> str:
    if not isinstance(payload, dict):
        _reject("invalid_manifest", "artifact kind")
    version = payload.get("schema_version")
    if type(version) is not int:
        _reject("invalid_manifest", "schema_version")
    if version == 1:
        return "legacy_manifest"
    if version != 2:
        _reject("invalid_manifest", "schema_version")
    if "manifest_kind" in payload:
        if payload.get("manifest_kind") != _PRIVATE_DEVICE_INFO_KIND:
            _reject("invalid_manifest", "manifest_kind")
        if "claim_id" in payload:
            _reject("invalid_manifest", "artifact kind")
        return "private_device_info_observation"
    if "claim_id" in payload:
        return "public_claim"
    _reject("invalid_manifest", "artifact kind")


def _read_artifact(path: Path) -> tuple[object, os.stat_result]:
    flags = os.O_RDONLY | os.O_NONBLOCK
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > _MAX_MANIFEST_BYTES:
            _reject("invalid_manifest", "input file")
        chunks = []
        remaining = _MAX_MANIFEST_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > _MAX_MANIFEST_BYTES:
            _reject("invalid_manifest", "input file")
        artifact = json.loads(content.decode("utf-8"))
    except EvidenceError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("invalid_manifest", "input file") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return artifact, details


def load_manifest(path: Path) -> dict[str, Any]:
    artifact, details = _read_artifact(path)
    kind = _artifact_kind(artifact)
    validators = {
        "legacy_manifest": validate_manifest,
        "public_claim": validate_public_claim,
        "private_device_info_observation": validate_private_device_info_manifest,
    }
    safe = validators[kind](artifact)
    private = kind == "private_device_info_observation" or (
        kind == "legacy_manifest"
        and safe["provenance"]["source"] == _OWNER_AUTHORIZED_SOURCE
    )
    if private and (
        details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) not in {0o400, 0o600}
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
        "manifest_kind" in fields
        or {"provenance", "redactions"} <= fields
        or {"operation", "protocol", "runtime_authority"} <= fields
    )


def _is_private_evidence(payload: object) -> bool:
    if isinstance(payload, str):
        return _contains_embedded_private_evidence(payload)
    if isinstance(payload, list):
        return any(_is_private_evidence(item) for item in payload)
    if not isinstance(payload, dict):
        return False
    if payload.get("manifest_kind") == _PRIVATE_DEVICE_INFO_KIND:
        return True
    provenance = payload.get("provenance")
    if isinstance(provenance, dict) and provenance.get("source") == (
        _OWNER_AUTHORIZED_SOURCE
    ):
        return True
    return any(_is_private_evidence(value) for value in payload.values())


def _contains_embedded_private_evidence(text: str) -> bool:
    return bool(
        _EMBEDDED_OWNER_LEDGER.search(text)
        or _EMBEDDED_PRIVATE_DEVICE_INFO.search(text)
    )


def _scan_repository_text(text: str, path: Path) -> None:
    if _contains_embedded_private_evidence(text):
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
        has_case_variant_evidence_suffix = (
            reserved_suffix is not None and not is_evidence
        )

        try:
            text_content = path.read_text(encoding="utf-8")
        except UnicodeError:
            try:
                text_content = path.read_bytes().decode("utf-8", errors="ignore")
            except OSError as exc:
                raise EvidenceError("unsafe_content", "repository data") from exc
        except OSError as exc:
            raise EvidenceError("unsafe_content", "repository data") from exc
        if _contains_embedded_private_evidence(text_content):
            _reject("private_evidence", "repository evidence")
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
        if _is_private_evidence(parsed_json):
            _reject("private_evidence", "repository evidence")
        if has_case_variant_evidence_suffix:
            _reject("invalid_fixture", "repository evidence")
        if not is_evidence and _looks_like_evidence(parsed_json):
            _reject("invalid_fixture", "repository evidence")
        if not is_evidence:
            if parsed_json is not None:
                _scan_sensitive(parsed_json)
            elif text_content is not None:
                if path.suffix.casefold() == ".jsonl":
                    try:
                        for line in text_content.splitlines():
                            if line.strip():
                                item = json.loads(line)
                                if _is_private_evidence(item):
                                    _reject("private_evidence", "repository evidence")
                                _scan_sensitive(item)
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
            if manifest["provenance"]["source"] == _OWNER_AUTHORIZED_SOURCE:
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
        child.add_argument("artifact", type=Path)
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
            artifact = load_manifest(args.artifact)
            kind = _artifact_kind(artifact)
            if args.command == "validate":
                if kind == "legacy_manifest":
                    message = "Evidence manifest passed fail-closed validation."
                elif kind == "public_claim":
                    message = (
                        "Public evidence candidate passed fail-closed validation; "
                        "runtime and hardware authority remain false."
                    )
                else:
                    message = (
                        "Private owner device-info observation manifest passed local "
                        "validation; validation performed no Bluetooth operation; "
                        "not publishable."
                    )
                print(message)
            else:
                if kind == "private_device_info_observation":
                    _reject("private_evidence", "private observation")
                derived = derive_fixture(artifact) if kind == "legacy_manifest" else (
                    derive_public_claim(artifact)
                )
                print(serialize_fixture(derived), end="")
    except EvidenceError as error:
        print(f"evidence: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
