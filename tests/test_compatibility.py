import copy
import json
from pathlib import Path

import pytest

from scripts.compatibility_matrix import (
    CompatibilityError,
    generate_synthetic_report,
    merge_reports,
    serialize_matrix,
    validate_report,
)


FIXTURES = Path(__file__).parent / "fixtures" / "compatibility"
SYNTHETIC_ADDRESS = ":".join(("DE", "AD", "BE", "EF", "00", "01"))
SYNTHETIC_TIMESTAMP = "2026-08-" + "24T13:00:00Z"
SYNTHETIC_PAYLOAD = "00112233" + "445566778899"


def report(name="synthetic-python310.json"):
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.parametrize(
    "field,value,secret",
    [
        ("device_address", SYNTHETIC_ADDRESS, "DE:AD"),
        ("observed_at", SYNTHETIC_TIMESTAMP, "13:00"),
        ("heart_rate", 72, "72"),
        ("raw_payload", SYNTHETIC_PAYLOAD, "001122"),
    ],
)
def test_compatibility_report_rejects_sensitive_values_without_echo(field, value, secret):
    unsafe = report()
    unsafe[field] = value

    with pytest.raises(CompatibilityError) as raised:
        validate_report(unsafe)

    assert raised.value.code == "unsafe_report"
    assert secret not in str(raised.value)


def test_untested_dimensions_cannot_claim_compatibility():
    impossible = report()
    impossible["compatibility_state"] = "connected"

    with pytest.raises(CompatibilityError) as raised:
        validate_report(impossible)
    assert raised.value.code == "invalid_report"

    impossible["compatibility_state"] = "compatible"
    with pytest.raises(CompatibilityError):
        validate_report(impossible)


def test_synthetic_reports_merge_deterministically():
    first = report("synthetic-python310.json")
    second = report("synthetic-python313.json")

    forward = merge_reports([first, second])
    reverse = merge_reports([second, first])

    assert serialize_matrix(forward) == serialize_matrix(reverse)
    assert [row["report_id"] for row in forward["rows"]] == [
        "synthetic-ci-python310",
        "synthetic-ci-python313",
    ]
    assert forward["matrix_state"] == "synthetic_only"
    assert forward["summary"] == {
        "report_count": 2,
        "owner_hardware_reports": 0,
        "synthetic_ci_reports": 2,
    }


def test_zero_failure_synthetic_report_names_hardware_as_untested(monkeypatch):
    monkeypatch.setattr("scripts.compatibility_matrix.platform.system", lambda: "Linux")
    monkeypatch.setattr("scripts.compatibility_matrix.platform.python_version_tuple", lambda: ("3", "13", "9"))

    generated = generate_synthetic_report()

    assert generated["compatibility_state"] == "untested"
    assert generated["dimensions"] == {
        "prerequisites": "untested",
        "connection": "untested",
        "standard_reads": "untested",
        "hid": "untested",
        "motion": "untested",
    }
    assert generated["checks"] == ["schema"]
    assert "compatible" not in json.dumps(generated)


def test_duplicate_report_ids_are_rejected():
    duplicate = report()
    with pytest.raises(CompatibilityError) as raised:
        merge_reports([duplicate, copy.deepcopy(duplicate)])
    assert raised.value.code == "duplicate_report"


@pytest.mark.parametrize("version", [True, 1.0, "1"])
def test_compatibility_schema_version_requires_an_exact_integer(version):
    candidate = report()
    candidate["schema_version"] = version

    with pytest.raises(CompatibilityError) as raised:
        validate_report(candidate)
    assert raised.value.code == "invalid_report"
