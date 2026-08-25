"""Adversarial RED contracts for the owner-hardware evidence canary.

These tests intentionally describe issue #34's stricter end state.  In particular,
private evidence is a new exclusive file, application terminals are owned only after
the ATT write completes, and cancellation/cleanup share the one overall deadline.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from types import SimpleNamespace
import zlib

import pytest

import jring.owner_hardware_evidence as evidence_module
from jring import cli
import jring.bleak_transport as bleak_transport_module
from jring.bleak_transport import BleakTransport
from jring.owner_hardware_evidence import (
    OwnerEvidenceError,
    OwnerEvidenceStatus,
    OwnerHardwareEvidenceRunner,
    load_private_owner_evidence,
    prepare_owner_evidence_run,
    prepare_owner_evidence_selection,
    prepare_owner_negative_control,
    write_owner_evidence_review,
    write_reviewed_compatibility_row,
)
from jring.transport import GattCharacteristicTarget, GattDescriptorTarget
from jring.uuids import (
    CLIENT_CHARACTERISTIC_CONFIGURATION,
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
)


_ADDRESS = ":".join(("A0", "B1", "C2", "D3", "E4", "F5"))
_OPERATION = "getDeviceInfo"


def _valid_response() -> bytes:
    body = bytes(range(1, 16))
    checksum = zlib.crc32(body, 1_247_391_573) & 0xFFFFFFFF
    return bytes((0x0C,)) + body + checksum.to_bytes(4, "little")


def _bad_integrity_response() -> bytes:
    response = bytearray(_valid_response())
    response[-1] ^= 0x01
    return bytes(response)


def _safe_parent(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _prepare(path: Path, *, timeout: float = 0.04):
    return prepare_owner_evidence_run(
        operation_id=_OPERATION,
        selection=prepare_owner_evidence_selection((_ADDRESS,)),
        allow_connect=True,
        allow_subscribe=True,
        allow_write=True,
        negative_control=prepare_owner_negative_control(_OPERATION),
        timeout=timeout,
        private_output=path,
        model_family="synthetic-family",
        firmware_major="synthetic-major",
    )


def _transaction_plan(tmp_path: Path, *, timeout: float = 0.04):
    """Prepare under either side of the exclusive-output migration.

    File-policy tests below have no fallback.  This compatibility shim keeps the
    transaction tests focused on their own race instead of all failing at plan setup.
    """

    output = _safe_parent(tmp_path) / "owner-evidence.json"
    try:
        return _prepare(output, timeout=timeout), output
    except OwnerEvidenceError as exc:
        if exc.code != "unsafe_private_output":
            raise
        output.write_text("{}", encoding="utf-8")
        output.chmod(0o600)
        return _prepare(output, timeout=timeout), output


def _install_backend(
    monkeypatch,
    *,
    terminal: bytes | None = None,
    terminal_before_write_completion: bool = False,
    unrelated_count: int = 0,
    block_cleanup: str | None = None,
    block_write: bool = False,
    before_terminal=None,
):
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

    class Client:
        instances: list[Client] = []

        def __init__(self, address, *, disconnected_callback, timeout):
            self.address = address
            self.disconnected_callback = disconnected_callback
            self.timeout = timeout
            self.is_connected = False
            self.services = [service]
            self.callback = None
            self.write_entered = asyncio.Event()
            self.release_write = asyncio.Event()
            self.release_cleanup = asyncio.Event()
            self.cleanup_entered = asyncio.Event()
            self.start_count = 0
            self.write_count = 0
            self.stop_count = 0
            self.disconnect_count = 0
            self.__class__.instances.append(self)

        async def connect(self):
            self.is_connected = True

        async def start_notify(self, target, callback):
            assert target is response
            self.start_count += 1
            self.callback = callback
            for _ in range(unrelated_count):
                callback(response, bytes((0x0B, 50, 1)) + bytes(17))

        async def write_gatt_char(self, target, data, *, response: bool):
            assert target is request
            assert response is True
            self.write_count += 1
            self.write_entered.set()
            if terminal_before_write_completion and terminal is not None:
                self.callback(response_target, terminal)
                await asyncio.sleep(0)
            if block_write:
                await self.release_write.wait()
            if not terminal_before_write_completion and terminal is not None:
                def deliver_terminal():
                    if before_terminal is not None:
                        before_terminal()
                    self.callback(response_target, terminal)

                asyncio.get_running_loop().call_soon(deliver_terminal)

        async def stop_notify(self, target):
            assert target is response
            self.stop_count += 1
            self.cleanup_entered.set()
            if block_cleanup == "unsubscribe":
                await self.release_cleanup.wait()

        async def disconnect(self):
            self.disconnect_count += 1
            self.cleanup_entered.set()
            if block_cleanup == "close":
                await self.release_cleanup.wait()
            self.is_connected = False

    response_target = response
    monkeypatch.setitem(
        __import__("sys").modules,
        "bleak",
        SimpleNamespace(BleakClient=Client),
    )
    return Client


def _run(plan):
    return asyncio.run(
        OwnerHardwareEvidenceRunner(transport_factory=BleakTransport).run(plan)
    )


def test_private_output_is_created_exclusively_with_mode_0600(monkeypatch, tmp_path):
    _install_backend(monkeypatch, terminal=_valid_response())
    output = _safe_parent(tmp_path) / "new-owner-evidence.json"
    assert not output.exists()

    result = _run(_prepare(output))

    assert result.status is OwnerEvidenceStatus.SUCCEEDED
    assert output.is_file()
    assert output.stat().st_mode & 0o777 == 0o600
    assert load_private_owner_evidence(output).public_payload() == result.public_payload()


def test_existing_private_destination_is_rejected_without_overwrite(tmp_path):
    output = _safe_parent(tmp_path) / "existing-owner-evidence.json"
    original = b"owner-controlled-existing-content"
    output.write_bytes(original)
    output.chmod(0o600)

    with pytest.raises(OwnerEvidenceError):
        _prepare(output)

    assert output.read_bytes() == original


def test_foreign_stale_temporary_file_is_never_deleted(monkeypatch, tmp_path):
    _install_backend(monkeypatch, terminal=_valid_response())
    parent = _safe_parent(tmp_path)
    output = parent / "owner-evidence.json"
    monkeypatch.setattr(evidence_module.secrets, "token_hex", lambda _size: "collision")
    stale = parent / ".owner-evidence.json.jring-collision.tmp"
    foreign = b"foreign-file-must-survive"
    stale.write_bytes(foreign)
    stale.chmod(0o600)

    result = _run(_prepare(output))

    assert result.status is OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED
    assert not output.exists()
    assert stale.read_bytes() == foreign


def test_bad_integrity_device_info_is_protocol_incompatible_not_success(
    monkeypatch, tmp_path
):
    _install_backend(monkeypatch, terminal=_bad_integrity_response())
    plan, _output = _transaction_plan(tmp_path)

    result = _run(plan)

    assert result.status is OwnerEvidenceStatus.MALFORMED_RESPONSE
    assert result.completeness == "uncertain"
    assert result.replay_allowed is False


def test_terminal_before_att_write_completion_is_quarantined(monkeypatch, tmp_path):
    _install_backend(
        monkeypatch,
        terminal=_valid_response(),
        terminal_before_write_completion=True,
    )
    plan, _output = _transaction_plan(tmp_path, timeout=0.02)

    result = _run(plan)

    assert result.status is OwnerEvidenceStatus.PRECOMPLETION_TERMINAL
    assert result.completeness == "uncertain"
    assert result.replay_allowed is False


@pytest.mark.parametrize("boundary", ("unsubscribe", "close"))
def test_cleanup_awaits_are_bounded_by_the_overall_deadline(
    monkeypatch, tmp_path, boundary
):
    client_type = _install_backend(
        monkeypatch,
        terminal=_valid_response(),
        block_cleanup=boundary,
    )
    plan, _output = _transaction_plan(tmp_path, timeout=0.02)

    async def scenario():
        task = asyncio.create_task(
            OwnerHardwareEvidenceRunner(transport_factory=BleakTransport).run(plan)
        )
        done, _pending = await asyncio.wait({task}, timeout=0.15)
        completed_without_external_cancel = bool(done)
        if not completed_without_external_cancel:
            task.cancel()
        result = await task
        return completed_without_external_cancel, result

    completed, result = asyncio.run(scenario())
    client = client_type.instances[-1]

    assert completed is True
    assert result.status is OwnerEvidenceStatus.CLEANUP_UNCERTAIN
    assert result.completeness == "uncertain"
    assert client.stop_count == 1
    assert client.disconnect_count == 1


def test_cancellation_after_write_dispatch_records_uncertain_after_one_cleanup(
    monkeypatch, tmp_path
):
    client_type = _install_backend(monkeypatch, block_write=True)
    plan, output = _transaction_plan(tmp_path, timeout=1.0)

    async def scenario():
        task = asyncio.create_task(
            OwnerHardwareEvidenceRunner(transport_factory=BleakTransport).run(plan)
        )
        # BleakTransport builds an inert generation-0 client, then replaces it
        # with the generation-1 client used by connect.
        while len(client_type.instances) < 2:
            await asyncio.sleep(0)
        client = client_type.instances[-1]
        await asyncio.sleep(0.15)
        assert client.write_entered.is_set(), task.result()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.5)
        return client

    client = asyncio.run(scenario())
    result = load_private_owner_evidence(output)
    loaded = load_private_owner_evidence(output)

    assert result.status is OwnerEvidenceStatus.CANCELLED
    assert result.completeness == "uncertain"
    assert loaded.completeness == "uncertain"
    assert loaded.replay_allowed is False
    assert client.write_count == 1
    assert client.stop_count == 1
    assert client.disconnect_count == 1
    with pytest.raises(OwnerEvidenceError) as reused:
        _run(plan)
    assert reused.value.code == "stale_plan"


def test_notification_queue_is_finite_under_unrelated_callback_flood(
    monkeypatch, tmp_path
):
    queues = []
    real_queue = asyncio.Queue

    class TrackingQueue(real_queue):
        def __init__(self, maxsize=0):
            super().__init__(maxsize=maxsize)
            self.maximum_observed = 0
            queues.append(self)

        def put_nowait(self, item):
            super().put_nowait(item)
            self.maximum_observed = max(self.maximum_observed, self.qsize())

    monkeypatch.setattr(evidence_module.asyncio, "Queue", TrackingQueue)
    client_type = _install_backend(
        monkeypatch,
        terminal=_valid_response(),
        unrelated_count=4096,
    )
    plan, _output = _transaction_plan(tmp_path, timeout=0.2)

    result = _run(plan)

    assert result.status is OwnerEvidenceStatus.NOTIFICATION_OVERFLOW
    assert result.completeness == "aborted"
    assert client_type.instances[-1].write_count == 0
    assert len(queues) == 1
    assert queues[0].maxsize > 0
    assert queues[0].maximum_observed <= queues[0].maxsize


def _valid_private_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "record_type": "private_owner_hardware_attempt",
        "operation_id": _OPERATION,
        "attempt_status": "succeeded",
        "outcome_status": "succeeded",
        "cleanup_status": "confirmed",
        "evidence_commit_status": "committed",
        "completeness": "succeeded",
        "negative_control": "passed_before_write",
        "route": {
            "route": "main",
            "service": "exact",
            "request": "exact_owned_current_generation",
            "response": "exact_owned_current_generation",
            "cccd": "exact_owned_current_generation",
        },
        "cleanup": {"unsubscribe": 1, "close": 1},
        "cleanup_outcomes": {"unsubscribe": "confirmed", "close": "confirmed"},
        "write_dispatch": "completed",
        "response_terminal": "matched_success",
        "environment": {
            "model_family": "synthetic-family",
            "firmware_major": "synthetic-major",
            "linux_family": "linux",
            "python_minor": "3.13",
            "bluez_major": "5",
            "bleak_major": "0",
        },
        "authority": {
            "repeat": False,
            "runtime": False,
            "input": False,
            "binding": False,
            "network": False,
            "ota": False,
            "publication": False,
        },
        "automatic_retry": "prohibited",
    }


def _write_private_payload(path: Path, payload: object) -> None:
    _safe_parent(path.parent)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


@pytest.mark.parametrize(
    "mutation",
    (
        "boolean_schema_version",
        "success_without_control",
        "success_without_exact_route",
        "success_without_cleanup",
        "dispatched_failure_marked_aborted",
    ),
)
def test_private_schema_rejects_exact_type_and_cross_field_incoherence(
    tmp_path, mutation
):
    payload = _valid_private_payload()
    if mutation == "boolean_schema_version":
        payload["schema_version"] = True
    elif mutation == "success_without_control":
        payload["negative_control"] = "not_reached"
    elif mutation == "success_without_exact_route":
        payload["route"] = {
            "route": "invented",
            "service": "unknown",
            "request": "unknown",
            "response": "unknown",
            "cccd": "unknown",
        }
    elif mutation == "success_without_cleanup":
        payload["cleanup"] = {"unsubscribe": 0, "close": 0}
    else:
        payload["attempt_status"] = "device_rejected"
        payload["outcome_status"] = "device_rejected"
        payload["completeness"] = "aborted"
        payload["response_terminal"] = "matched_failure"
    path = tmp_path / f"{mutation}.json"
    _write_private_payload(path, payload)

    with pytest.raises(OwnerEvidenceError) as raised:
        load_private_owner_evidence(path)

    assert raised.value.code == "invalid_private_evidence"


def test_private_schema_rejects_duplicate_json_members(tmp_path):
    payload = json.dumps(_valid_private_payload())
    payload = payload.replace(
        '"schema_version": 1',
        '"schema_version": 1, "schema_version": 1',
        1,
    )
    path = tmp_path / "duplicate-member.json"
    _safe_parent(path.parent)
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o600)

    with pytest.raises(OwnerEvidenceError) as raised:
        load_private_owner_evidence(path)

    assert raised.value.code == "invalid_private_evidence"


def test_review_receipt_binds_route_and_cleanup_ledger_not_only_public_preview(
    tmp_path
):
    first_payload = _valid_private_payload()
    first_payload.update({
        "attempt_status": "timed_out",
        "outcome_status": "timed_out",
        "completeness": "aborted",
        "negative_control": "not_reached",
        "route": {
            "route": "main",
            "service": "unknown",
            "request": "unknown",
            "response": "unknown",
            "cccd": "unknown",
        },
        "cleanup": {"unsubscribe": 0, "close": 1},
        "cleanup_outcomes": {"unsubscribe": "not_required", "close": "confirmed"},
        "write_dispatch": "not_started",
        "response_terminal": "not_observed",
    })
    second_payload = json.loads(json.dumps(first_payload))
    second_payload["route"] = _valid_private_payload()["route"]
    first = tmp_path / "first" / "attempt.json"
    second = tmp_path / "second" / "attempt.json"
    _write_private_payload(first, first_payload)
    _write_private_payload(second, second_payload)
    receipt = first.parent / "review.json"
    write_owner_evidence_review(
        first,
        receipt,
        review_decision="reject",
        approved_evidence_reference="reviewed-timeout-v1",
    )

    with pytest.raises(OwnerEvidenceError) as raised:
        write_reviewed_compatibility_row(
            second,
            receipt,
            tmp_path / "must-not-exist.json",
        )

    assert raised.value.code == "review_receipt_mismatch"


@pytest.mark.parametrize("boundary", ("unsubscribe", "close"))
def test_cancellation_during_cleanup_is_preserved_and_remaining_cleanup_runs(
    monkeypatch, tmp_path, boundary
):
    client_type = _install_backend(
        monkeypatch,
        terminal=_valid_response(),
        block_cleanup=boundary,
    )
    plan, output = _transaction_plan(tmp_path, timeout=1.0)

    async def scenario():
        task = asyncio.create_task(
            OwnerHardwareEvidenceRunner(transport_factory=BleakTransport).run(plan)
        )
        while len(client_type.instances) < 2:
            await asyncio.sleep(0)
        client = client_type.instances[-1]
        while (
            (boundary == "unsubscribe" and client.stop_count == 0)
            or (boundary == "close" and client.disconnect_count == 0)
        ):
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=0.5)
        return client

    client = asyncio.run(scenario())
    recorded = load_private_owner_evidence(output)

    assert recorded.status is OwnerEvidenceStatus.CANCELLED
    assert recorded.completeness == "uncertain"
    assert client.stop_count == 1
    assert client.disconnect_count == 1


@pytest.mark.parametrize("race", ("destination_created", "parent_swapped"))
def test_output_race_after_plan_is_rejected_before_bleak_construction(
    monkeypatch, tmp_path, race
):
    parent = _safe_parent(tmp_path / "private")
    output = parent / "owner-evidence.json"
    plan = _prepare(output)
    runner = OwnerHardwareEvidenceRunner()
    if race == "destination_created":
        output.write_text("foreign", encoding="utf-8")
        output.chmod(0o600)
    else:
        displaced = tmp_path / "displaced-private"
        parent.rename(displaced)
        _safe_parent(parent)

    constructed = 0

    class ForbiddenBleakTransport:
        def __init__(self, *_args, **_kwargs):
            nonlocal constructed
            constructed += 1
            raise AssertionError("unsafe evidence output reached Bluetooth")

    monkeypatch.setattr(
        bleak_transport_module, "BleakTransport", ForbiddenBleakTransport
    )

    with pytest.raises(OwnerEvidenceError) as raised:
        asyncio.run(runner.run(plan))

    assert raised.value.code in {"private_output_exists", "unsafe_private_output"}
    assert constructed == 0


def test_guided_scan_never_starts_before_selection_independent_gates(
    monkeypatch, tmp_path, capsys
):
    output = _safe_parent(tmp_path) / "already-exists.json"
    output.write_text("foreign", encoding="utf-8")
    output.chmod(0o600)
    scans = 0

    async def forbidden_scan(*_args, **_kwargs):
        nonlocal scans
        scans += 1
        raise AssertionError("unsafe output reached active scan")

    monkeypatch.setattr(cli, "discover_for_selection", forbidden_scan)
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(isatty=lambda: True))

    assert cli.main([
        "verify-device-info", "--select", "--active-scan",
        "--private-output", str(output),
        "--model-family", "synthetic-family",
        "--firmware-major", "synthetic-major",
        "--allow-connect", "--allow-notifications", "--allow-write",
        "--negative-control",
    ]) == 6
    captured = capsys.readouterr()
    assert "private_output_exists" in captured.err
    assert scans == 0


def _fail_after_link(monkeypatch, failure_point: str) -> None:
    real_unlink = os.unlink
    real_fsync = os.fsync

    if failure_point == "temporary_unlink":
        failed_once = False

        def failing_unlink(path, *args, **kwargs):
            nonlocal failed_once
            if (
                not failed_once
                and ".jring-" in os.fspath(path)
                and os.fspath(path).endswith(".tmp")
            ):
                failed_once = True
                raise OSError("synthetic post-link unlink failure")
            return real_unlink(path, *args, **kwargs)

        monkeypatch.setattr(evidence_module.os, "unlink", failing_unlink)
    else:
        def failing_fsync(descriptor):
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("synthetic post-link directory fsync failure")
            return real_fsync(descriptor)

        monkeypatch.setattr(evidence_module.os, "fsync", failing_fsync)


@pytest.mark.parametrize("failure_point", ("temporary_unlink", "directory_fsync"))
def test_failed_private_post_link_commit_leaves_no_promotable_final(
    monkeypatch, tmp_path, failure_point
):
    _install_backend(monkeypatch, terminal=_valid_response())
    plan, output = _transaction_plan(tmp_path)
    _fail_after_link(monkeypatch, failure_point)

    result = _run(plan)

    assert result.status is OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED
    assert not output.exists()


def test_private_commit_rejects_a_post_link_hardlink_race(monkeypatch, tmp_path):
    _install_backend(monkeypatch, terminal=_valid_response())
    plan, output = _transaction_plan(tmp_path)
    real_unlink = os.unlink
    raced = False

    def racing_unlink(path, *args, **kwargs):
        nonlocal raced
        if not raced and ".jring-" in os.fspath(path):
            raced = True
            os.link(
                os.fspath(path),
                "attacker-link",
                src_dir_fd=kwargs.get("dir_fd"),
                dst_dir_fd=kwargs.get("dir_fd"),
                follow_symlinks=False,
            )
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(evidence_module.os, "unlink", racing_unlink)

    result = _run(plan)

    assert raced is True
    assert result.status is OwnerEvidenceStatus.PRIVATE_OUTPUT_FAILED
    assert not output.exists()


@pytest.mark.parametrize("failure_point", ("temporary_unlink", "directory_fsync"))
def test_failed_public_post_link_commit_leaves_no_public_final(
    monkeypatch, tmp_path, failure_point
):
    _install_backend(monkeypatch, terminal=_valid_response())
    plan, private = _transaction_plan(tmp_path / "private")
    assert _run(plan).status is OwnerEvidenceStatus.SUCCEEDED
    receipt = _safe_parent(tmp_path / "review") / "review-receipt.json"
    write_owner_evidence_review(
        private,
        receipt,
        review_decision="reject",
        approved_evidence_reference="reviewed-device-info-canary-v1",
    )
    public = _safe_parent(tmp_path / "public") / "reviewed-row.json"
    _fail_after_link(monkeypatch, failure_point)

    with pytest.raises(OwnerEvidenceError) as raised:
        write_reviewed_compatibility_row(
            private,
            receipt,
            public,
        )

    assert raised.value.code == "unsafe_public_output"
    assert not public.exists()


def test_terminal_completed_at_exact_work_deadline_is_rejected(
    monkeypatch, tmp_path
):
    clock = SimpleNamespace(now=0.0)
    # Replace only this module's clock reference; patching the process-wide
    # ``time.monotonic`` would also freeze asyncio's timeout clock.
    monkeypatch.setattr(
        evidence_module,
        "time",
        SimpleNamespace(monotonic=lambda: clock.now),
    )
    _install_backend(
        monkeypatch,
        terminal=_valid_response(),
        before_terminal=lambda: setattr(clock, "now", 0.8),
    )
    plan, _output = _transaction_plan(tmp_path, timeout=1.0)

    result = _run(plan)

    assert result.status is OwnerEvidenceStatus.TIMED_OUT
    assert result.completeness == "uncertain"
    assert result.public_payload()["response_terminal"] == "not_observed"


def test_live_owner_entrypoints_reject_reconstructed_and_stale_targets(
    monkeypatch, tmp_path
):
    client_type = _install_backend(monkeypatch, terminal=_valid_response())
    original_subscribe = BleakTransport._owner_evidence_subscribe
    original_write = BleakTransport._owner_evidence_write
    checked = {"subscribe": False, "write": False}

    async def guarded_subscribe(
        transport,
        response_target,
        descriptor_target,
        callback,
        authority,
        dispatch_started,
        setup_cleanup_timeout,
    ):
        forged_response = GattCharacteristicTarget(
            response_target.connection_generation,
            response_target.service_uuid,
            response_target.uuid,
            response_target.instance_id,
        )
        forged_descriptor = GattDescriptorTarget(
            descriptor_target.connection_generation,
            descriptor_target.service_uuid,
            descriptor_target.characteristic_uuid,
            descriptor_target.characteristic_instance_id,
            descriptor_target.uuid,
            descriptor_target.instance_id,
        )
        before = client_type.instances[-1].start_count
        for candidate_response, candidate_descriptor in (
            (forged_response, descriptor_target),
            (response_target, forged_descriptor),
        ):
            with pytest.raises(PermissionError):
                await original_subscribe(
                    transport,
                    candidate_response,
                    candidate_descriptor,
                    callback,
                    authority,
                    dispatch_started,
                    setup_cleanup_timeout,
                )
        assert client_type.instances[-1].start_count == before
        checked["subscribe"] = True
        return await original_subscribe(
            transport,
            response_target,
            descriptor_target,
            callback,
            authority,
            dispatch_started,
            setup_cleanup_timeout,
        )

    async def guarded_write(
        transport,
        request_target,
        data,
        authority,
        dispatch_started,
        dispatch_completed,
    ):
        stale_request = GattCharacteristicTarget(
            request_target.connection_generation - 1,
            request_target.service_uuid,
            request_target.uuid,
            request_target.instance_id,
        )
        forged_request = GattCharacteristicTarget(
            request_target.connection_generation,
            request_target.service_uuid,
            request_target.uuid,
            request_target.instance_id,
        )
        before = client_type.instances[-1].write_count
        for candidate in (stale_request, forged_request):
            with pytest.raises(PermissionError):
                await original_write(
                    transport,
                    candidate,
                    data,
                    authority,
                    dispatch_started,
                    dispatch_completed,
                )
        assert client_type.instances[-1].write_count == before
        checked["write"] = True
        return await original_write(
            transport,
            request_target,
            data,
            authority,
            dispatch_started,
            dispatch_completed,
        )

    monkeypatch.setattr(
        BleakTransport, "_owner_evidence_subscribe", guarded_subscribe
    )
    monkeypatch.setattr(BleakTransport, "_owner_evidence_write", guarded_write)

    result = _run(_prepare(_safe_parent(tmp_path) / "owner-evidence.json"))

    assert result.status is OwnerEvidenceStatus.SUCCEEDED
    assert checked == {"subscribe": True, "write": True}
    assert client_type.instances[-1].start_count == 1
    assert client_type.instances[-1].write_count == 1


def test_environment_captures_linux_bluez_and_bleak_majors(monkeypatch):
    monkeypatch.setattr("importlib.metadata.version", lambda _name: "0.22.3")
    monkeypatch.setattr(
        evidence_module.platform,
        "freedesktop_os_release",
        lambda: {"ID": "Fedora"},
    )
    monkeypatch.setattr(shutil, "which", lambda _name: "/usr/bin/bluetoothctl")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="bluetoothctl: 5.79\n", stderr="", returncode=0
        ),
    )
    monkeypatch.setitem(
        __import__("sys").modules,
        "bleak",
        SimpleNamespace(__version__="0.22.3"),
    )

    linux, _python, bluez, bleak = evidence_module._environment()

    assert linux == "fedora"
    assert bluez == "5"
    assert bleak == "0"


def test_environment_uses_unknown_when_bluez_probe_is_unavailable(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    assert evidence_module._environment()[2] == "unknown"


@pytest.mark.parametrize(
    "argv,operation",
    (
        (["review-owner-evidence", "--json"], "review_owner_evidence"),
        (["derive-owner-evidence", "--json"], "derive_owner_evidence"),
    ),
)
def test_offline_json_usage_errors_keep_private_local_source(
    argv, operation, capsys
):
    assert cli.main(argv) == 2

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert payload["operation"] == operation
    assert payload["source"] == "private_local"
    assert payload["error"]["code"] == "usage"


def test_offline_json_unsafe_private_input_is_permission_denied_and_redacted(
    tmp_path, capsys
):
    private = tmp_path / "private-path-sentinel"

    assert cli.main([
        "review-owner-evidence",
        "--private-input", str(private),
        "--json",
    ]) == 6

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert captured.err == ""
    assert payload["source"] == "private_local"
    assert payload["error"]["code"] == "unsafe_private_output"
    assert str(private) not in captured.out


def test_canary_json_interruption_is_nonretryable_and_warns_about_dispatch(
    monkeypatch, tmp_path, capsys
):
    address_file = tmp_path / "selected-ring"
    address_file.write_text(_ADDRESS + "\n", encoding="utf-8")
    address_file.chmod(0o600)
    output = _safe_parent(tmp_path / "private") / "attempt.json"

    interrupted_payload = {
        "schema_version": 1,
        "operation_id": _OPERATION,
        "attempt_status": "cancelled",
        "outcome_status": "cancelled",
        "cleanup_status": "confirmed",
        "evidence_commit_status": "committed",
        "completeness": "uncertain",
        "negative_control": "passed_before_write",
        "firmware_support": "unknown",
        "vendor_authorization": "unknown",
        "hardware_verified": False,
        "live_eligible": False,
        "replay_allowed": False,
        "automatic_retry": "prohibited",
        "write_dispatch": "started",
        "response_terminal": "not_observed",
        "cleanup": {"unsubscribe": "confirmed", "close": "confirmed"},
    }

    class InterruptedResult:
        def public_payload(self):
            return dict(interrupted_payload)

    class InterruptedRunner:
        def __init__(self, **_kwargs):
            self.interrupted_result = InterruptedResult()

        async def run(self, _plan):
            raise asyncio.CancelledError

    monkeypatch.setattr(cli, "OwnerHardwareEvidenceRunner", InterruptedRunner)

    assert cli.main([
        "verify-device-info", "--address-file", str(address_file),
        "--private-output", str(output),
        "--model-family", "synthetic-family",
        "--firmware-major", "synthetic-major",
        "--allow-connect", "--allow-notifications", "--allow-write",
        "--negative-control", "--json",
    ]) == 130
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "owner_evidence_interrupted"
    assert payload["error"]["retryable"] is False
    assert "may have been dispatched" in payload["error"]["message"]
    assert payload["attempt_status"] == "cancelled"
    assert payload["write_dispatch"] == "started"
    assert payload["evidence_commit_status"] == "committed"
