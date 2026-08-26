"""RED contracts for the private owner-observation planning boundary."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from jring.private_observation import (
    ObservationError,
    PrivateObservationRunner,
    begin_observation,
    prepare_observation_authority,
    prepare_observation_plan,
    require_observation_authority,
    select_observation_target,
)
from jring.transport import (
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
    GattDescriptorTarget,
)
from jring.uuids import CLIENT_CHARACTERISTIC_CONFIGURATION


def _metadata(*, properties=("notify",), generation=1, instance_id="candidate-1"):
    target = GattCharacteristicTarget(
        generation, "service-candidate", "characteristic-candidate", instance_id
    )
    descriptor = GattDescriptorTarget(
        generation,
        "service-candidate",
        "characteristic-candidate",
        instance_id,
        CLIENT_CHARACTERISTIC_CONFIGURATION,
        f"{instance_id}-cccd",
    )
    return GattCharacteristicMetadata(
        "service-candidate",
        "characteristic-candidate",
        properties,
        (CLIENT_CHARACTERISTIC_CONFIGURATION,),
        instance_id,
        (f"{instance_id}-cccd",),
        target,
        (descriptor,),
    )


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
    assert recorder.finish() == {"capture_status": "completed", "record_count": 1,
        "private_output": "mode_0600", "runtime_authorized": False}
    assert (tmp_path / "observation.json").stat().st_mode & 0o777 == 0o600


def test_observation_authority_is_exact_generation_target_and_single_use(tmp_path: Path):
    tmp_path.chmod(0o700)
    plan = prepare_observation_plan(address="synthetic-selected-ring", allow_connect=True,
        allow_notifications=True, allow_observation=True, timeout=5.0, max_records=1,
        private_output=tmp_path / "observation.json")
    target = object()
    authority = prepare_observation_authority(plan, connection_generation=1, target=target)
    with pytest.raises(ObservationError, match="observation_authority_mismatch"):
        require_observation_authority(authority, connection_generation=2, target=target)
    with pytest.raises(ObservationError, match="observation_authority_mismatch"):
        require_observation_authority(authority, connection_generation=1, target=object())
    require_observation_authority(authority, connection_generation=1, target=target)
    with pytest.raises(ObservationError, match="stale_observation_authority"):
        require_observation_authority(authority, connection_generation=1, target=target)


def test_observation_target_is_exact_current_metadata_notify_endpoint():
    candidate = _metadata()
    assert select_observation_target(
        (candidate,),
        connection_generation=1,
        service_uuid="service-candidate",
        characteristic_uuid="characteristic-candidate",
        instance_id="candidate-1",
    ) is candidate.target


@pytest.mark.parametrize(
    "metadata,generation,code",
    [
        ((_metadata(properties=("read",)),), 1, "unsupported_observation_target"),
        ((_metadata(generation=2),), 1, "unsupported_observation_target"),
        ((_metadata(), _metadata()), 1, "ambiguous_observation_target"),
    ],
)
def test_observation_target_rejects_non_notify_stale_and_ambiguous_metadata(
    metadata, generation, code
):
    with pytest.raises(ObservationError, match=code):
        select_observation_target(
            metadata,
            connection_generation=generation,
            service_uuid="service-candidate",
            characteristic_uuid="characteristic-candidate",
            instance_id="candidate-1",
        )


def test_private_observation_runner_collects_one_bounded_private_record_without_write(
    monkeypatch, tmp_path: Path
):
    characteristic = SimpleNamespace(
        uuid="characteristic-candidate",
        properties=["notify"],
        descriptors=[SimpleNamespace(uuid=CLIENT_CHARACTERISTIC_CONFIGURATION)],
    )
    service = SimpleNamespace(uuid="service-candidate", characteristics=[characteristic])

    class Client:
        instances = []

        def __init__(self, _address, *, disconnected_callback, timeout):
            self.disconnected_callback = disconnected_callback
            self.timeout = timeout
            self.is_connected = False
            self.services = [service]
            self.calls = []
            self.__class__.instances.append(self)

        async def connect(self):
            self.is_connected = True
            self.calls.append("connect")

        async def start_notify(self, target, callback):
            assert target is characteristic
            self.calls.append("start_notify")
            asyncio.get_running_loop().call_soon(callback, target, b"private-frame")

        async def stop_notify(self, target):
            assert target is characteristic
            self.calls.append("stop_notify")

        async def disconnect(self):
            self.calls.append("disconnect")
            self.is_connected = False
            self.disconnected_callback(self)

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    tmp_path.chmod(0o700)
    plan = prepare_observation_plan(
        address="synthetic-selected-ring",
        allow_connect=True,
        allow_notifications=True,
        allow_observation=True,
        timeout=2.0,
        max_records=1,
        private_output=tmp_path / "observation.json",
    )

    result = asyncio.run(
        PrivateObservationRunner().run(
            plan,
            service_uuid="service-candidate",
            characteristic_uuid="characteristic-candidate",
            instance_id="service-1-characteristic-1",
        )
    )

    assert result.public_payload() == {
        "capture_status": "completed",
        "record_count": 1,
        "cleanup": {"unsubscribe": "confirmed", "close": "confirmed"},
        "runtime_authorized": False,
        "decoder": "none",
    }
    assert "private-frame" not in repr(result)
    assert Client.instances[-1].calls == ["connect", "start_notify", "stop_notify", "disconnect"]
    assert json.loads((tmp_path / "observation.json").read_text(encoding="utf-8"))["records"] == ["707269766174652d6672616d65"]
