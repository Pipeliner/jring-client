"""RED contract for the first owner-hardware vendor evidence canary.

The integration tests use the production ``BleakTransport`` over a fake Bleak backend.
They do not use ``ScriptedVendorFakeTransport`` and therefore constrain the future live
adapter boundary rather than adding another simulator-only implementation.
"""

from __future__ import annotations

import asyncio
import builtins
import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import zlib

import pytest

from jring.bleak_transport import BleakTransport
from jring import cli
from jring.owner_hardware_evidence import (
    OwnerEvidenceError,
    OwnerEvidenceStatus,
    OwnerHardwareEvidenceRunner,
    load_private_owner_evidence,
    prepare_owner_evidence_run,
    prepare_owner_evidence_selection,
    prepare_owner_negative_control,
    render_approved_compatibility_row,
    write_owner_evidence_review,
    write_reviewed_compatibility_row,
)
from jring.uuids import (
    CLIENT_CHARACTERISTIC_CONFIGURATION,
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
)


_PRIVATE_ADDRESS = ":".join(("A0", "B1", "C2", "D3", "E4", "F5"))
_OPERATION = "getDeviceInfo"


def _valid_device_info_response() -> bytes:
    body = bytes(range(1, 16))
    checksum = zlib.crc32(body, 1_247_391_573) & 0xFFFFFFFF
    return bytes((0x0C,)) + body + checksum.to_bytes(4, "little")


def _private_output(tmp_path: Path, *, mode: int = 0o600) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    tmp_path.chmod(0o700)
    path = tmp_path / "owner-evidence.json"
    if mode != 0o600:
        path.write_text("{}", encoding="utf-8")
        path.chmod(mode)
    return path


def _selection():
    return prepare_owner_evidence_selection((_PRIVATE_ADDRESS,))


def _control():
    return prepare_owner_negative_control(_OPERATION)


def _plan(
    tmp_path: Path,
    *,
    selection=None,
    operation_id: str = _OPERATION,
    allow_connect: bool = True,
    allow_subscribe: bool = True,
    allow_write: bool = True,
    negative_control=None,
    private_output: Path | None = None,
    timeout: float = 0.25,
    model_family: str = "synthetic-family",
    firmware_major: str = "synthetic-major",
):
    return prepare_owner_evidence_run(
        operation_id=operation_id,
        selection=_selection() if selection is None else selection,
        allow_connect=allow_connect,
        allow_subscribe=allow_subscribe,
        allow_write=allow_write,
        negative_control=_control() if negative_control is None else negative_control,
        timeout=timeout,
        private_output=(
            _private_output(tmp_path) if private_output is None else private_output
        ),
        model_family=model_family,
        firmware_major=firmware_major,
    )


def _vendor_service():
    request = SimpleNamespace(
        uuid=VENDOR_CHARACTERISTIC_33F3,
        properties=["write"],
        descriptors=[],
    )
    cccd = SimpleNamespace(uuid=CLIENT_CHARACTERISTIC_CONFIGURATION)
    response = SimpleNamespace(
        uuid=VENDOR_CHARACTERISTIC_33F4,
        properties=["notify"],
        descriptors=[cccd],
    )
    service = SimpleNamespace(
        uuid=VENDOR_SERVICE_56FF,
        characteristics=[request, response],
    )
    return service, request, response, cccd


def _install_bleak_backend(monkeypatch, *, behavior: str = "success"):
    service, request, response, cccd = _vendor_service()

    class Client:
        instances = []

        def __init__(self, address, *, disconnected_callback, timeout):
            self.address = address
            self.disconnected_callback = disconnected_callback
            self.timeout = timeout
            self.is_connected = False
            self.services = [service]
            self.callback = None
            self.control_delivered = False
            self.calls = []
            self.write_count = 0
            self.stop_count = 0
            self.disconnect_count = 0
            self.__class__.instances.append(self)

        async def connect(self):
            self.calls.append("connect")
            self.is_connected = True

        async def start_notify(self, target, callback):
            assert target is response
            self.calls.append(("start_notify", target))
            self.callback = callback
            # An unrelated MAIN frame is delivered after setup returns.  The runner
            # must cross its required pre-write negative-control barrier before it is
            # allowed to issue the canary write.
            def deliver_control():
                self.control_delivered = True
                self.calls.append("negative_control_callback")
                callback(response, bytes((0x0B, 50, 1)) + bytes(17))

            asyncio.get_running_loop().call_soon(deliver_control)

        async def write_gatt_char(self, target, data, *, response: bool):
            assert target is request
            assert response is True
            assert type(data) is bytes and len(data) == 20 and data[0] == 0x0C
            assert self.control_delivered is True
            self.calls.append(("write_gatt_char", target, response))
            self.write_count += 1
            if behavior == "timeout":
                return
            if behavior == "disconnect":
                self.is_connected = False
                asyncio.get_running_loop().call_soon(
                    self.disconnected_callback, self
                )
                return
            payload = (
                bytes((0x0C,))
                if behavior == "malformed"
                else _valid_device_info_response()
            )
            asyncio.get_running_loop().call_soon(self.callback, response_target, payload)

        async def stop_notify(self, target):
            assert target is response
            self.calls.append(("stop_notify", target))
            self.stop_count += 1
            if behavior == "cleanup_unknown":
                raise TimeoutError("synthetic cleanup uncertainty")

        async def disconnect(self):
            self.calls.append("disconnect")
            self.disconnect_count += 1
            self.is_connected = False
            self.disconnected_callback(self)

    response_target = response
    monkeypatch.setitem(
        __import__("sys").modules,
        "bleak",
        SimpleNamespace(BleakClient=Client),
    )
    return Client, request, response, cccd


def _run(plan):
    return asyncio.run(
        OwnerHardwareEvidenceRunner(transport_factory=BleakTransport).run(plan)
    )


def test_production_bleak_path_uses_exact_main_targets_barrier_and_cleanup(
    monkeypatch, tmp_path
):
    client_type, request, response, _cccd = _install_bleak_backend(monkeypatch)

    result = _run(_plan(tmp_path))
    client = client_type.instances[-1]

    assert result.status is OwnerEvidenceStatus.SUCCEEDED
    assert result.completeness == "succeeded"
    assert result.negative_control == "passed_before_write"
    assert client.address == _PRIVATE_ADDRESS
    assert client.calls == [
        "connect",
        ("start_notify", response),
        "negative_control_callback",
        ("write_gatt_char", request, True),
        ("stop_notify", response),
        "disconnect",
    ]
    assert client.write_count == 1
    assert client.stop_count == 1
    assert client.disconnect_count == 1
    assert result.route_observation == {
        "route": "main",
        "service": "exact",
        "request": "exact_owned_current_generation",
        "response": "exact_owned_current_generation",
        "cccd": "exact_owned_current_generation",
    }


@pytest.mark.parametrize(
    "missing",
    ("selection", "connect", "subscribe", "write", "negative_control"),
)
def test_each_independent_authority_gate_is_required_before_transport_io(
    monkeypatch, tmp_path, missing
):
    constructed = 0

    def forbidden_transport(_address, **_kwargs):
        nonlocal constructed
        constructed += 1
        raise AssertionError("invalid evidence plan must not construct a transport")

    kwargs = dict(
        operation_id=_OPERATION,
        selection=_selection(),
        allow_connect=True,
        allow_subscribe=True,
        allow_write=True,
        negative_control=_control(),
        timeout=0.25,
        private_output=_private_output(tmp_path),
    )
    if missing == "selection":
        kwargs["selection"] = None
    elif missing == "negative_control":
        kwargs["negative_control"] = None
    else:
        kwargs[f"allow_{missing}"] = False

    with pytest.raises(OwnerEvidenceError) as raised:
        plan = prepare_owner_evidence_run(**kwargs)
        asyncio.run(
            OwnerHardwareEvidenceRunner(
                transport_factory=forbidden_transport
            ).run(plan)
        )

    expected = {
        "selection": "missing_selection",
        "connect": "missing_connect_consent",
        "subscribe": "missing_subscribe_consent",
        "write": "missing_write_consent",
        "negative_control": "missing_negative_control",
    }
    assert raised.value.code == expected[missing]
    assert constructed == 0


def test_ambiguous_selection_is_rejected_without_echo_or_transport(monkeypatch):
    first = "private-first-candidate"
    second = "private-second-candidate"

    with pytest.raises(OwnerEvidenceError) as raised:
        prepare_owner_evidence_selection((first, second))

    assert raised.value.code == "ambiguous_selection"
    assert first not in str(raised.value)
    assert second not in str(raised.value)


def test_selection_and_plan_are_single_use_and_stale_before_new_transport_io(
    monkeypatch, tmp_path,
):
    selection = _selection()
    first = _plan(tmp_path, selection=selection)

    with pytest.raises(OwnerEvidenceError) as raised:
        _plan(
            tmp_path,
            selection=selection,
            private_output=_private_output(tmp_path / "second"),
        )
    assert raised.value.code == "stale_selection"

    # A plan is consumed even when the attempt fails.  No retry can inherit its
    # operation-specific consent or negative control.
    client_type, _request, _response, _cccd = _install_bleak_backend(monkeypatch)

    async def fail_connect(_self):
        raise ConnectionError("synthetic connect failure")

    monkeypatch.setattr(client_type, "connect", fail_connect)
    runner = OwnerHardwareEvidenceRunner()
    failed = asyncio.run(runner.run(first))
    assert failed.status is OwnerEvidenceStatus.CONNECTION_FAILED
    with pytest.raises(OwnerEvidenceError) as reused:
        asyncio.run(runner.run(first))
    assert reused.value.code == "stale_plan"


def test_stale_expected_connection_generation_closes_without_subscribe_or_write(
    monkeypatch, tmp_path
):
    client_type, _request, _response, _cccd = _install_bleak_backend(monkeypatch)
    stale = prepare_owner_evidence_selection(
        (_PRIVATE_ADDRESS,), expected_connection_generation=2
    )

    result = _run(_plan(tmp_path, selection=stale))
    client = client_type.instances[-1]

    assert result.status is OwnerEvidenceStatus.STALE_GENERATION
    assert client.write_count == 0
    assert client.stop_count == 0
    assert client.disconnect_count == 1


def test_unregistered_operation_is_rejected_before_transport_without_echo(tmp_path):
    secret = "private-unregistered-operation"
    with pytest.raises(OwnerEvidenceError) as raised:
        _plan(tmp_path, operation_id=secret)

    assert raised.value.code == "unregistered_operation"
    assert secret not in str(raised.value)


def test_initial_live_evidence_surface_rejects_other_registered_operations_before_io(
    tmp_path,
):
    with pytest.raises(OwnerEvidenceError) as raised:
        _plan(
            tmp_path,
            operation_id="getDeviceBatery",
            negative_control=prepare_owner_negative_control("getDeviceBatery"),
        )

    assert raised.value.code == "unsupported_evidence_operation"


@pytest.mark.parametrize("mode", (0o000, 0o400, 0o440, 0o640, 0o644, 0o660))
def test_private_output_must_be_new_before_transport_io(
    tmp_path, mode
):
    output = _private_output(tmp_path, mode=mode)

    with pytest.raises(OwnerEvidenceError) as raised:
        _plan(tmp_path, private_output=output)

    assert raised.value.code == "private_output_exists"
    assert output.name not in str(raised.value)


def test_absent_or_wrong_operation_negative_control_is_rejected_before_io(tmp_path):
    wrong = prepare_owner_negative_control("getDeviceBatery")

    with pytest.raises(OwnerEvidenceError) as raised:
        _plan(tmp_path, negative_control=wrong)

    assert raised.value.code == "invalid_negative_control"


def test_negative_control_is_fresh_single_use_authority(tmp_path):
    control = _control()
    _plan(tmp_path, negative_control=control)

    with pytest.raises(OwnerEvidenceError) as raised:
        _plan(
            tmp_path / "second",
            negative_control=control,
            private_output=_private_output(tmp_path / "second"),
        )

    assert raised.value.code == "stale_negative_control"


def test_runner_rejects_nonproduction_transport_factory():
    with pytest.raises(TypeError):
        OwnerHardwareEvidenceRunner(transport_factory=lambda _address: object())


@pytest.mark.parametrize(
    "behavior,status,completeness",
    (
        ("timeout", OwnerEvidenceStatus.TIMED_OUT, "uncertain"),
        ("disconnect", OwnerEvidenceStatus.DISCONNECTED, "uncertain"),
        ("malformed", OwnerEvidenceStatus.MALFORMED_RESPONSE, "uncertain"),
        ("cleanup_unknown", OwnerEvidenceStatus.CLEANUP_UNCERTAIN, "uncertain"),
    ),
)
def test_terminal_failures_cleanup_once_and_never_replay(
    monkeypatch, tmp_path, behavior, status, completeness
):
    client_type, _request, _response, _cccd = _install_bleak_backend(
        monkeypatch, behavior=behavior
    )

    result = _run(_plan(tmp_path, timeout=0.03))
    client = client_type.instances[-1]

    assert result.status is status
    assert result.completeness == completeness
    assert result.replay_allowed is False
    assert result.automatic_retry == "prohibited"
    assert client.write_count == 1
    assert client.stop_count <= 1
    assert client.disconnect_count <= 1
    assert result.cleanup_calls == {"unsubscribe": 1, "close": 1}
    assert sum(
        call[0] == "write_gatt_char" for call in client.calls if isinstance(call, tuple)
    ) == 1


def test_matching_terminal_during_negative_control_aborts_before_write(
    monkeypatch, tmp_path
):
    client_type, _request, response, _cccd = _install_bleak_backend(monkeypatch)
    original = client_type.start_notify

    async def matching_control(self, target, callback):
        await original(self, target, callback)
        asyncio.get_running_loop().call_soon(
            callback, response, _valid_device_info_response()
        )

    monkeypatch.setattr(client_type, "start_notify", matching_control)

    result = _run(_plan(tmp_path))
    client = client_type.instances[-1]

    assert result.status is OwnerEvidenceStatus.NEGATIVE_CONTROL_FAILED
    assert result.completeness == "aborted"
    assert client.write_count == 0
    assert client.stop_count == 1
    assert client.disconnect_count == 1


def test_disconnect_alone_never_proves_firmware_or_authorization_state(
    monkeypatch, tmp_path
):
    _install_bleak_backend(monkeypatch, behavior="disconnect")

    result = _run(_plan(tmp_path))
    public = result.public_payload()

    assert public["attempt_status"] == "disconnected"
    assert public["firmware_support"] == "unknown"
    assert public["vendor_authorization"] == "unknown"
    assert public["hardware_verified"] is False


def test_public_payload_and_repr_redact_private_runtime_material(monkeypatch, tmp_path):
    _install_bleak_backend(monkeypatch)
    output = _private_output(tmp_path)

    result = _run(_plan(tmp_path, private_output=output))
    rendered = repr(result) + json.dumps(result.public_payload(), sort_keys=True)
    private_file = output.read_text(encoding="utf-8")

    for secret in (
        _PRIVATE_ADDRESS,
        VENDOR_SERVICE_56FF,
        VENDOR_CHARACTERISTIC_33F3,
        VENDOR_CHARACTERISTIC_33F4,
        _valid_device_info_response().hex(),
        str(output),
    ):
        assert secret not in rendered
        assert secret not in private_file
    assert "raw_payload" not in rendered
    assert "decoded_value" not in rendered


def test_private_record_commit_is_atomic_and_reloadable_for_later_review(
    monkeypatch, tmp_path
):
    _install_bleak_backend(monkeypatch)
    output = _private_output(tmp_path)
    assert not output.exists()

    result = _run(_plan(tmp_path, private_output=output))
    loaded = load_private_owner_evidence(output)

    assert result.status is OwnerEvidenceStatus.SUCCEEDED
    assert output.is_file()
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert loaded.public_payload() == result.public_payload()
    assert "owner-evidence.json" not in repr(loaded)


def test_private_output_rejects_symlink_hardlink_and_unsafe_parent(tmp_path):
    original = tmp_path / "original"
    original.write_text("existing", encoding="utf-8")
    original.chmod(0o600)
    symlink = tmp_path / "linked-output"
    symlink.symlink_to(original)
    hardlink = tmp_path / "hard-output"
    os.link(original, hardlink)
    unsafe_parent = tmp_path / "unsafe-parent"
    unsafe_parent.mkdir(mode=0o755)
    unsafe = unsafe_parent / "owner-evidence.json"

    for output, expected in (
        (symlink, "private_output_exists"),
        (hardlink, "private_output_exists"),
        (unsafe, "unsafe_private_output"),
    ):
        with pytest.raises(OwnerEvidenceError) as raised:
            _plan(tmp_path / output.name, private_output=output)
        assert raised.value.code == expected
        assert output.name not in str(raised.value)


def test_approved_compatibility_row_is_coarse_and_does_not_promote_runtime(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "jring.owner_hardware_evidence._environment",
        lambda: ("synthetic-linux", "3.13", "5", "0"),
    )
    _install_bleak_backend(monkeypatch)
    result = _run(_plan(tmp_path))

    row = render_approved_compatibility_row(
        result,
        review_decision="promote",
        approved_evidence_reference="reviewed-device-info-canary-v1",
    )

    assert set(row) == {
        "schema_version",
        "record_type",
        "declared_model_family",
        "declared_firmware_major",
        "scope_provenance",
        "linux_family",
        "python_minor",
        "bluez_major",
        "bleak_major",
        "operation_id",
        "operation_status",
        "approved_evidence_reference",
        "review_decision",
        "authority",
    }
    assert row["operation_id"] == _OPERATION
    assert row["operation_status"] == "candidate_success"
    assert row["approved_evidence_reference"] == "reviewed-device-info-canary-v1"
    assert row["review_decision"] == "promote"
    assert _PRIVATE_ADDRESS not in json.dumps(row, sort_keys=True)


def test_review_decision_is_explicit_and_cannot_promote_uncertain_attempt(
    monkeypatch, tmp_path
):
    _install_bleak_backend(monkeypatch, behavior="timeout")
    result = _run(_plan(tmp_path, timeout=0.03))

    with pytest.raises(OwnerEvidenceError) as raised:
        render_approved_compatibility_row(
            result,
            review_decision="promote",
            approved_evidence_reference="reviewed-timeout-v1",
        )
    assert raised.value.code == "invalid_promotion_decision"

    rejected = render_approved_compatibility_row(
        result,
        review_decision="reject",
        approved_evidence_reference="reviewed-timeout-v1",
    )
    assert rejected["review_decision"] == "reject"
    assert rejected["operation_status"] == "uncertain"


def test_success_with_unknown_environment_dimensions_cannot_be_promoted(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "jring.owner_hardware_evidence._environment",
        lambda: ("synthetic-linux", "3.13", "unknown", "0"),
    )
    _install_bleak_backend(monkeypatch)
    result = _run(_plan(tmp_path))

    with pytest.raises(OwnerEvidenceError) as raised:
        render_approved_compatibility_row(
            result,
            review_decision="promote",
            approved_evidence_reference="reviewed-device-info-canary-v1",
        )

    assert raised.value.code == "incomplete_promotion_scope"


def test_cli_owner_evidence_canary_is_task_first_explicit_and_private(
    monkeypatch, tmp_path, capsys
):
    client_type, _request, _response, _cccd = _install_bleak_backend(monkeypatch)
    address_file = tmp_path / "selected-ring"
    address_file.write_text(_PRIVATE_ADDRESS + "\n", encoding="utf-8")
    address_file.chmod(0o600)
    output = _private_output(tmp_path)

    assert cli.main([
        "verify-device-info",
        "--address-file", str(address_file),
        "--private-output", str(output),
        "--model-family", "synthetic-family",
        "--firmware-major", "synthetic-major",
        "--allow-connect",
        "--allow-notifications",
        "--allow-write",
        "--negative-control",
        "--json",
    ]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "owner_hardware_evidence"
    assert payload["attempt_status"] == "succeeded"
    assert payload["ok"] is True
    assert client_type.instances[-1].write_count == 1
    serialized = json.dumps(payload, sort_keys=True)
    assert _PRIVATE_ADDRESS not in serialized
    assert str(output) not in serialized


def test_cli_review_and_public_derivation_are_separate_offline_no_overwrite_steps(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        "jring.owner_hardware_evidence._environment",
        lambda: ("synthetic-linux", "3.13", "5", "0"),
    )
    client_type, _request, _response, _cccd = _install_bleak_backend(monkeypatch)
    private = _private_output(tmp_path)
    _run(_plan(tmp_path, private_output=private))
    hardware_instances = len(client_type.instances)

    assert cli.main([
        "review-owner-evidence", "--private-input", str(private),
        "--decision", "promote",
        "--evidence-reference", "reviewed-device-info-canary-v1",
        "--json",
    ]) == 0
    review = json.loads(capsys.readouterr().out)
    assert review["operation"] == "review_owner_evidence"
    assert review["ok"] is True
    assert review["hardware_verified"] is False
    assert review["candidate_public_row"]["scope_provenance"] == "owner_declared"

    receipt = private.parent / "review-receipt.json"
    assert cli.main([
        "review-owner-evidence", "--private-input", str(private),
        "--decision", "promote",
        "--evidence-reference", "reviewed-device-info-canary-v1",
        "--review-output", str(receipt),
        "--allow-review-decision",
        "--json",
    ]) == 0
    sealed_review = json.loads(capsys.readouterr().out)
    assert sealed_review["review_receipt_created"] is True

    public = tmp_path / "approved-owner-evidence.json"
    assert cli.main([
        "derive-owner-evidence",
        "--private-input", str(private),
        "--review-receipt", str(receipt),
        "--public-output", str(public),
        "--allow-public-evidence",
        "--json",
    ]) == 0
    derived = json.loads(capsys.readouterr().out)
    assert derived["operation"] == "derive_owner_evidence"
    assert derived["operation_status"] == "candidate_success"
    assert json.loads(public.read_text(encoding="utf-8")) == {
        key: value
        for key, value in derived.items()
        if key not in {"operation", "source", "ok"}
    }
    before = public.read_bytes()
    assert cli.main([
        "derive-owner-evidence",
        "--private-input", str(private),
        "--review-receipt", str(receipt),
        "--public-output", str(public),
        "--allow-public-evidence",
        "--json",
    ]) == 6
    exists_error = json.loads(capsys.readouterr().out)
    assert exists_error["error"]["code"] == "public_output_exists"
    assert public.read_bytes() == before
    assert len(client_type.instances) == hardware_instances


def test_public_derivation_rejects_receipt_bound_to_a_different_private_record(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        "jring.owner_hardware_evidence._environment",
        lambda: ("synthetic-linux", "3.13", "5", "0"),
    )
    _install_bleak_backend(monkeypatch)
    first = _private_output(tmp_path / "first")
    _run(_plan(tmp_path / "first", private_output=first))
    receipt = first.parent / "review-receipt.json"
    write_owner_evidence_review(
        first,
        receipt,
        review_decision="reject",
        approved_evidence_reference="reviewed-device-info-canary-v1",
    )
    second = _private_output(tmp_path / "second")
    _install_bleak_backend(monkeypatch, behavior="timeout")
    _run(_plan(tmp_path / "second", private_output=second, timeout=0.03))

    with pytest.raises(OwnerEvidenceError) as raised:
        write_reviewed_compatibility_row(
            second,
            receipt,
            tmp_path / "must-not-exist.json",
        )

    assert raised.value.code == "review_receipt_mismatch"


@pytest.mark.parametrize(
    "missing",
    ("--allow-connect", "--allow-notifications", "--allow-write", "--negative-control"),
)
def test_cli_missing_canary_authority_fails_before_bleak(
    monkeypatch, tmp_path, capsys, missing
):
    constructed = 0

    def forbidden_transport(*_args, **_kwargs):
        nonlocal constructed
        constructed += 1
        raise AssertionError("missing authority must fail before Bleak")

    monkeypatch.setattr(cli, "BleakTransport", forbidden_transport)
    address_file = tmp_path / "selected-ring"
    address_file.write_text(_PRIVATE_ADDRESS + "\n", encoding="utf-8")
    address_file.chmod(0o600)
    output = _private_output(tmp_path)
    argv = [
        "verify-device-info",
        "--address-file", str(address_file),
        "--private-output", str(output),
        "--model-family", "synthetic-family",
        "--firmware-major", "synthetic-major",
        "--allow-connect", "--allow-notifications", "--allow-write",
        "--negative-control", "--json",
    ]
    argv.remove(missing)

    assert cli.main(argv) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "usage"
    assert constructed == 0


def test_cli_address_file_failure_redacts_private_path(tmp_path, capsys):
    private_path = tmp_path / "private-owner-path-sentinel"
    output = _private_output(tmp_path)

    assert cli.main([
        "verify-device-info",
        "--address-file", str(private_path),
        "--private-output", str(output),
        "--model-family", "synthetic-family",
        "--firmware-major", "synthetic-major",
        "--allow-connect", "--allow-notifications", "--allow-write",
        "--negative-control", "--json",
    ]) == 6

    rendered = capsys.readouterr().out
    assert str(private_path) not in rendered
    assert "address file is unavailable or unsafe" in rendered


def test_policy_preparation_does_not_import_bleak_or_uinput(monkeypatch, tmp_path):
    real_import = builtins.__import__
    forbidden = []

    def guarded_import(name, *args, **kwargs):
        if name == "bleak" or name.startswith("evdev") or name == "jring.input":
            forbidden.append(name)
            raise AssertionError("pure policy preparation imported a live dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    plan = _plan(tmp_path)

    assert plan.operation_id == _OPERATION
    assert plan.public_payload() == {
        "operation_id": _OPERATION,
        "consent": ["connect", "subscribe", "write"],
        "negative_control": "required",
        "deadline": "bounded",
        "private_output": "mode_0600",
        "single_use": True,
    }
    assert forbidden == []
