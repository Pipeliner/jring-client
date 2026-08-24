#!/usr/bin/env python3
"""Build reviewable compatibility reports without contacting hardware."""

from __future__ import annotations

import argparse
import json
import platform
import re
import stat
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_tool import EvidenceError, _scan_sensitive
except ModuleNotFoundError:  # Direct `python3 scripts/compatibility_matrix.py` execution.
    from evidence_tool import EvidenceError, _scan_sensitive


_FIELDS = {
    "schema_version",
    "report_id",
    "source",
    "evidence_id",
    "device_context",
    "environment",
    "compatibility_state",
    "dimensions",
    "checks",
}
_CONTEXT_FIELDS = {"model_family", "firmware_major"}
_ENVIRONMENT_FIELDS = {
    "linux_family",
    "python_minor",
    "bluez_major",
    "bleak_major",
}
_DIMENSION_FIELDS = {"prerequisites", "connection", "standard_reads", "hid", "motion"}
_SUMMARY_STATES = {
    "untested",
    "prerequisites_only",
    "connected",
    "standard_reads_verified",
    "hid_advertised",
    "motion_verified",
    "incompatible",
}
_CHECKS = {"schema", "simulator", "unit_tests", "passive_prerequisites", "owner_hardware"}
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MAX_REPORT_BYTES = 64 * 1024


class CompatibilityError(ValueError):
    def __init__(self, code: str, field: str):
        self.code = code
        self.field = field
        super().__init__(f"{code}: compatibility report rejected at {field}")


def _reject(code: str, field: str) -> None:
    raise CompatibilityError(code, field)


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _reject("invalid_report", field)
    return value


def _exact(value: dict[str, Any], fields: set[str], field: str) -> None:
    if set(value) != fields:
        _reject("invalid_report", field)


def _slug(value: object, field: str) -> str:
    if not isinstance(value, str) or not _SLUG.fullmatch(value):
        _reject("invalid_report", field)
    return value


def _validate_dimensions(dimensions: dict[str, Any]) -> None:
    allowed = {
        "prerequisites": {"untested", "verified", "incompatible"},
        "connection": {"untested", "verified", "incompatible"},
        "standard_reads": {"untested", "verified", "incompatible"},
        "hid": {"untested", "advertised", "not_advertised", "incompatible"},
        "motion": {"untested", "verified", "incompatible"},
    }
    for name, choices in allowed.items():
        if dimensions[name] not in choices:
            _reject("invalid_report", f"dimensions.{name}")


def _validate_progression(state: str, dimensions: dict[str, Any]) -> None:
    requirements = {
        "untested": {name: "untested" for name in _DIMENSION_FIELDS},
        "prerequisites_only": {
            "prerequisites": "verified",
            "connection": "untested",
            "standard_reads": "untested",
            "hid": "untested",
            "motion": "untested",
        },
        "connected": {"prerequisites": "verified", "connection": "verified"},
        "standard_reads_verified": {
            "prerequisites": "verified",
            "connection": "verified",
            "standard_reads": "verified",
        },
        "hid_advertised": {
            "prerequisites": "verified",
            "connection": "verified",
            "hid": "advertised",
        },
        "motion_verified": {
            "prerequisites": "verified",
            "connection": "verified",
            "motion": "verified",
        },
    }
    if state == "incompatible":
        if "incompatible" not in dimensions.values():
            _reject("invalid_report", "compatibility_state")
        return
    if any(dimensions[name] != value for name, value in requirements[state].items()):
        _reject("invalid_report", "compatibility progression")


def validate_report(report: object) -> dict[str, Any]:
    try:
        _scan_sensitive(report)
    except EvidenceError as exc:
        raise CompatibilityError("unsafe_report", "sensitive content") from exc
    root = _mapping(report, "report")
    _exact(root, _FIELDS, "report fields")
    if root.get("schema_version") != 1:
        _reject("invalid_report", "schema_version")
    _slug(root.get("report_id"), "report_id")
    if root.get("source") not in {"synthetic_ci", "owner_hardware"}:
        _reject("invalid_report", "source")

    evidence_id = root.get("evidence_id")
    if root["source"] == "synthetic_ci":
        if evidence_id is not None:
            _reject("invalid_report", "evidence_id")
    else:
        _slug(evidence_id, "evidence_id")

    context = _mapping(root.get("device_context"), "device_context")
    _exact(context, _CONTEXT_FIELDS, "device_context fields")
    for name, value in context.items():
        _slug(value, f"device_context.{name}")
    if root["source"] == "synthetic_ci" and not all(
        value.startswith("synthetic") for value in context.values()
    ):
        _reject("invalid_report", "synthetic device_context")

    environment = _mapping(root.get("environment"), "environment")
    _exact(environment, _ENVIRONMENT_FIELDS, "environment fields")
    for name, value in environment.items():
        _slug(value, f"environment.{name}")

    state = root.get("compatibility_state")
    if state not in _SUMMARY_STATES:
        _reject("invalid_report", "compatibility_state")
    dimensions = _mapping(root.get("dimensions"), "dimensions")
    _exact(dimensions, _DIMENSION_FIELDS, "dimension fields")
    _validate_dimensions(dimensions)
    _validate_progression(state, dimensions)
    if root["source"] == "synthetic_ci" and (
        state not in {"untested", "prerequisites_only"}
        or any(dimensions[name] != "untested" for name in ("connection", "standard_reads", "hid", "motion"))
    ):
        _reject("invalid_report", "synthetic hardware claim")

    checks = root.get("checks")
    if not isinstance(checks, list) or not checks or any(check not in _CHECKS for check in checks):
        _reject("invalid_report", "checks")
    if checks != sorted(set(checks)):
        _reject("invalid_report", "checks")
    if root["source"] == "owner_hardware" and "owner_hardware" not in checks:
        _reject("invalid_report", "owner checks")
    return root


def merge_reports(reports: list[object]) -> dict[str, Any]:
    if not reports:
        _reject("invalid_report", "empty report set")
    rows = [validate_report(report) for report in reports]
    ids = [row["report_id"] for row in rows]
    if len(ids) != len(set(ids)):
        _reject("duplicate_report", "report_id")
    ordered = sorted(rows, key=lambda row: row["report_id"])
    owner_count = sum(row["source"] == "owner_hardware" for row in ordered)
    return {
        "schema_version": 1,
        "matrix_state": "owner_evidence_present" if owner_count else "synthetic_only",
        "summary": {
            "report_count": len(ordered),
            "owner_hardware_reports": owner_count,
            "synthetic_ci_reports": len(ordered) - owner_count,
        },
        "rows": ordered,
    }


def serialize_matrix(matrix: dict[str, Any]) -> str:
    return json.dumps(matrix, indent=2, sort_keys=True) + "\n"


def generate_synthetic_report() -> dict[str, Any]:
    major, minor, _patch = platform.python_version_tuple()
    report = {
        "schema_version": 1,
        "report_id": f"synthetic-local-python{major}{minor}",
        "source": "synthetic_ci",
        "evidence_id": None,
        "device_context": {
            "model_family": "synthetic-ring",
            "firmware_major": "synthetic",
        },
        "environment": {
            "linux_family": platform.system().lower() or "unknown",
            "python_minor": f"{major}.{minor}",
            "bluez_major": "not_checked",
            "bleak_major": "not_checked",
        },
        "compatibility_state": "untested",
        "dimensions": {name: "untested" for name in _DIMENSION_FIELDS},
        "checks": ["schema"],
    }
    return validate_report(report)


def load_report(path: Path) -> dict[str, Any]:
    try:
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_size > _MAX_REPORT_BYTES:
            _reject("invalid_report", "input file")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except CompatibilityError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CompatibilityError("invalid_report", "input file") from exc
    report = validate_report(payload)
    if report["source"] == "owner_hardware" and details.st_mode & 0o077:
        _reject("unsafe_permissions", "owner report")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build privacy-safe JRing compatibility data")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("generate-synthetic")
    validate = subparsers.add_parser("validate")
    validate.add_argument("report", type=Path)
    merge = subparsers.add_parser("merge")
    merge.add_argument("reports", type=Path, nargs="+")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "generate-synthetic":
            print(serialize_matrix(generate_synthetic_report()), end="")
        elif args.command == "validate":
            validate_report(load_report(args.report))
            print("Compatibility report passed fail-closed validation.")
        else:
            print(serialize_matrix(merge_reports([load_report(path) for path in args.reports])), end="")
    except CompatibilityError as error:
        print(f"compatibility: error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
