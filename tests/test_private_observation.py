"""RED contracts for the private owner-observation planning boundary."""

from __future__ import annotations

from pathlib import Path

import pytest

from jring.private_observation import ObservationError, begin_observation, prepare_observation_plan


def test_observation_plan_requires_all_explicit_consents_before_io(tmp_path: Path):
    tmp_path.chmod(0o700)

    with pytest.raises(ObservationError, match="missing_observation_consent"):
        prepare_observation_plan(
            address="synthetic-selected-ring",
            allow_connect=True,
            allow_notifications=True,
            allow_observation=False,
            timeout=5.0,
            max_records=4,
            private_output=tmp_path / "observation.json",
        )


def test_observation_plan_public_payload_is_value_free_and_bounded(tmp_path: Path):
    tmp_path.chmod(0o700)
    plan = prepare_observation_plan(
        address="synthetic-selected-ring",
        allow_connect=True,
        allow_notifications=True,
        allow_observation=True,
        timeout=5.0,
        max_records=4,
        private_output=tmp_path / "observation.json",
    )

    assert plan.public_payload() == {
        "consent": ["connect", "observe", "subscribe"],
        "deadline": "bounded",
        "max_records": 4,
        "private_output": "mode_0600",
        "single_use": True,
    }
    assert "synthetic-selected-ring" not in repr(plan)


def test_observation_recorder_writes_only_private_records(tmp_path: Path):
    tmp_path.chmod(0o700)
    plan = prepare_observation_plan(address="synthetic-selected-ring", allow_connect=True,
        allow_notifications=True, allow_observation=True, timeout=5.0, max_records=1,
        private_output=tmp_path / "observation.json")
    recorder = begin_observation(plan)
    recorder.record(b"\x01")
    assert recorder.finish() == {"capture_status": "bounded_recorded", "record_count": 1,
        "private_output": "mode_0600", "runtime_authorized": False}
    assert (tmp_path / "observation.json").stat().st_mode & 0o777 == 0o600
