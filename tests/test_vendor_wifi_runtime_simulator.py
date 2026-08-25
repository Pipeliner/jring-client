import asyncio
import ast
import copy
import inspect
import json
from dataclasses import asdict, fields, replace

import pytest

import jring.vendor_wifi_runtime_simulator as wifi_runtime
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
)
from jring.vendor_main_commands import (
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
)
from jring.vendor_runtime_fake import ScriptGate, ScriptedVendorFakeTransport
from jring.vendor_wifi_runtime_simulator import (
    FakeVendorWifiScanSimulator,
    WifiScanCompleteness,
    WifiScanSimulationTaintedError,
    WifiScanSimulationReason,
)


def run(coro):
    return asyncio.run(coro)


def test_fake_wifi_runtime_has_no_host_network_or_distro_service_imports():
    tree = ast.parse(inspect.getsource(wifi_runtime))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 0
    }

    assert imported_roots.isdisjoint(
        {"bleak", "dbus", "evdev", "os", "pathlib", "pydbus", "socket", "subprocess"}
    )


def _count(value: int) -> bytes:
    return bytes((0x54, 0x09, value)) + bytes(17)


def _fragment(flags: int, signal: int, content: bytes) -> bytes:
    return bytes((0x54, 0x0A, flags, signal & 0xFF)) + content.ljust(16, b"\x00")


def _request() -> NoArgumentMainCommandRequest:
    return NoArgumentMainCommandRequest(NoArgumentMainCommand.SCAN_WIFI)


def test_advertised_count_is_diagnostic_unknown_not_wire_completion():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _count(1))
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            _fragment(0x25, -91, b"Private"),
        )
        fake.emit(
            VENDOR_CHARACTERISTIC_33F4,
            _fragment(0xE5, -91, b"%20Net"),
        )

    transport.before_write = emit
    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        frame_limit=8,
        quiet_timeout=0.1,
    ))

    assert result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.advertised_count == 1
    assert result.accepted_frame_count == 3
    assert result.assembled_entry_count == 1
    assert result.projections == (
        ("onGetWifiSsidCount", 1, "wire_frame"),
        ("onGetWifiSsid", 1, "assembled_wire_fragments"),
    )
    assert result.wire_terminal_observed is False
    assert result.protocol_delivery == "unknown"
    assert result.application_acknowledgement_observed is False
    assert result.write_invoked is True
    assert result.fake_write_call_completed is True
    assert result.transport_call_uncertain is False
    assert result.locally_observed_count_matches is True
    assert result.quiet_means_success is False
    assert result.simulation_only is True
    assert result.live_available is False
    assert result.owner_authorized is False
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    assert result.host_network_accessed is False
    assert result.host_network_modified is False
    assert result.input_eligible is False
    assert result.provenance == "caller_supplied_offline_fake_frames"
    fixed_safety_fields = {
        "protocol_delivery",
        "application_acknowledgement_observed",
        "wire_terminal_observed",
        "quiet_means_success",
        "simulation_only",
        "live_available",
        "owner_authorized",
        "hardware_eligible",
        "hardware_verified",
        "host_network_accessed",
        "host_network_modified",
        "input_eligible",
        "provenance",
        "host_network_action",
    }
    result_fields = {item.name: item for item in fields(type(result))}
    assert fixed_safety_fields <= set(result_fields)
    assert all(
        not result_fields[name].init for name in fixed_safety_fields
    )
    assert transport.subscription_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F4
    assert transport.response_write_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F3
    assert transport.response_write_calls[0].data_for_test() == bytes((0x54, 0x08)) + bytes(18)
    assert transport.unsubscribe_count == 1
    assert transport.targeted_write_count == 1
    assert transport.targeted_subscribe_count == 1
    assert transport.targeted_unsubscribe_count == 1
    assert transport.response_write_calls[0].target_instance_id is not None
    assert transport.close_count == 1

    ssid = result.ssids_for_explicit_local_test_use()[0]
    assert ssid.ssid_for_explicit_local_use() == "Private%20Net"
    rendered = repr(result)
    assert "Private" not in rendered
    assert "-91" not in rendered
    assert "current_id" not in rendered
    assert "part_id" not in rendered
    assert "raw" not in rendered
    assert "ssids=<redacted>" in rendered
    copied = copy.deepcopy(result)
    assert copied.assembled_entry_count == result.assembled_entry_count
    assert (
        copied.ssids_for_explicit_local_test_use()[0].ssid_for_explicit_local_use()
        == "Private%20Net"
    )
    with pytest.raises((TypeError, ValueError), match="InitVar"):
        replace(result)
    replaced = replace(
        result, _ssids_init=result.ssids_for_explicit_local_test_use()
    )
    assert (
        replaced.ssids_for_explicit_local_test_use()[0].ssid_for_explicit_local_use()
        == "Private%20Net"
    )
    public_result = asdict(result)
    assert "_ssids" not in public_result
    public_serialization = json.dumps(public_result, sort_keys=True)
    assert "Private" not in public_serialization
    assert "-91" not in public_serialization
    assert "current_id" not in public_serialization
    assert "part_id" not in public_serialization
    assert '"_ssid":' not in public_serialization
    assert "fake_write_call_completed" in public_serialization
    assert "command_written" not in public_serialization
    assert "protocol delivery is unknown" in result.user_guidance


def test_zero_advertised_count_stays_unknown_and_does_not_invent_ssid_callback():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _count(0)
    )

    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        quiet_timeout=0.1,
    ))

    assert result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.projections == (("onGetWifiSsidCount", 1, "wire_frame"),)
    assert result.assembled_entry_count == 0
    assert result.wire_terminal_observed is False
    assert result.protocol_delivery == "unknown"
    assert result.application_acknowledgement_observed is False


def test_partial_entry_then_local_quiet_is_unknown_and_not_projected():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _count(2))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _fragment(0x06, -70, b"Secret"))

    transport.before_write = emit
    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        frame_limit=8,
        quiet_timeout=0.01,
    ))

    assert result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.accepted_frame_count == 2
    assert result.assembled_entry_count == 0
    assert result.projections == (("onGetWifiSsidCount", 1, "wire_frame"),)
    assert result.locally_observed_count_matches is False
    assert "Secret" not in repr(result)


def test_fragment_before_count_is_matching_malformed_and_aborted():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _fragment(0x81, -50, b"Hidden")
    )

    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        quiet_timeout=0.1,
    ))

    assert result.reason is WifiScanSimulationReason.MALFORMED_FRAME
    assert result.completeness is WifiScanCompleteness.ABORTED
    assert result.accepted_frame_count == 0
    assert result.projections == ()
    assert result.ssids_for_explicit_local_test_use() == ()


def test_unrelated_frames_do_not_count_or_become_success():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, bytes((0x0B, 80)) + bytes(18)
    )

    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        quiet_timeout=0.01,
    ))

    assert result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.accepted_frame_count == 0
    assert result.unrelated_frame_count == 1
    assert result.projections == ()


def test_selectorless_shared_54_is_unrelated_and_does_not_rollback_count():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _count(1))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x54,)))

    transport.before_write = emit
    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(), quiet_timeout=0.01
    ))

    assert result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.advertised_count == 1
    assert result.accepted_frame_count == 1
    assert result.unrelated_frame_count == 1


def test_prewrite_notifications_are_not_owned_by_the_scan_attempt():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_subscribe = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _count(7)
    )
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _count(0)
    )

    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(), quiet_timeout=0.01
    ))

    assert result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.advertised_count == 0
    assert result.accepted_frame_count == 1


def test_local_frame_limit_is_unknown_not_a_fabricated_end():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _count(2)
    )

    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        frame_limit=1,
        quiet_timeout=0.1,
    ))

    assert result.reason is WifiScanSimulationReason.LIMIT_REACHED
    assert result.completeness is WifiScanCompleteness.UNKNOWN
    assert result.advertised_count == 2
    assert result.assembled_entry_count == 0
    assert result.wire_terminal_observed is False


def test_delayed_queue_overflow_cannot_be_masked_by_the_frame_limit():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit_later(fake, _call):
        loop = asyncio.get_running_loop()

        def overflow():
            for value in range(4):
                fake.emit(VENDOR_CHARACTERISTIC_33F4, _count(value))

        loop.call_later(0.001, overflow)

    transport.before_write = emit_later
    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(), frame_limit=1, quiet_timeout=0.1
    ))

    assert result.reason is WifiScanSimulationReason.QUEUE_OVERFLOW
    assert result.completeness is WifiScanCompleteness.ABORTED
    assert result.accepted_frame_count == 0


def test_collector_accepts_only_exact_fake_and_exact_scan_request():
    class UnsafeFakeSubclass(ScriptedVendorFakeTransport):
        pass

    exact = ScriptedVendorFakeTransport.vendor_route()
    subclass = UnsafeFakeSubclass(
        services=set(),
        metadata=(),
    )

    with pytest.raises(TypeError, match="exact ScriptedVendorFakeTransport"):
        FakeVendorWifiScanSimulator(subclass)

    simulator = FakeVendorWifiScanSimulator(exact)
    with pytest.raises(TypeError, match="exact scan Wi-Fi request"):
        run(simulator.collect(request=object()))
    with pytest.raises(TypeError, match="exact scan Wi-Fi request"):
        run(simulator.collect(
            request=NoArgumentMainCommandRequest(NoArgumentMainCommand.DEVICE_CODE)
        ))


def test_invalid_utf8_completed_entry_is_malformed_and_never_projected():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _count(1))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _fragment(0x81, -40, b"\xff"))

    transport.before_write = emit
    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(),
        quiet_timeout=0.1,
    ))

    assert result.reason is WifiScanSimulationReason.MALFORMED_FRAME
    assert result.completeness is WifiScanCompleteness.ABORTED
    assert result.accepted_frame_count == 1
    assert result.assembled_entry_count == 0
    assert result.projections == (("onGetWifiSsidCount", 1, "wire_frame"),)
    assert result.ssids_for_explicit_local_test_use() == ()


def test_frame_limit_has_a_conservative_memory_bound():
    simulator = FakeVendorWifiScanSimulator(
        ScriptedVendorFakeTransport.vendor_route()
    )

    with pytest.raises(ValueError, match="between 1 and 4096"):
        run(simulator.collect(request=_request(), frame_limit=4097))


def test_setup_and_cleanup_stages_are_bounded():
    connect_blocked = ScriptedVendorFakeTransport.vendor_route(
        connect_gate=ScriptGate.blocked()
    )
    result = run(FakeVendorWifiScanSimulator(connect_blocked).collect(
        request=_request(),
        stage_timeout=0.01,
    ))
    assert result.reason is WifiScanSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is WifiScanCompleteness.ABORTED

    setup_failed = ScriptedVendorFakeTransport.vendor_route(
        connect_error=RuntimeError("unexpected connect failure")
    )
    result = run(FakeVendorWifiScanSimulator(setup_failed).collect(
        request=_request(),
    ))
    assert result.reason is WifiScanSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is WifiScanCompleteness.ABORTED

    cleanup_blocked = ScriptedVendorFakeTransport.vendor_route(
        unsubscribe_gate=ScriptGate.blocked()
    )
    cleanup_blocked.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _count(0)
    )
    result = run(FakeVendorWifiScanSimulator(cleanup_blocked).collect(
        request=_request(),
        frame_limit=1,
        stage_timeout=0.01,
    ))
    assert result.reason is WifiScanSimulationReason.CLEANUP_FAILURE
    assert result.completeness is WifiScanCompleteness.UNCERTAIN
    assert result.cleanup_succeeded is False
    assert result.tainted is True
    assert "tainted and must not be reused" in result.user_guidance

    close_failed = ScriptedVendorFakeTransport.vendor_route(
        close_error=RuntimeError("unexpected close failure")
    )
    result = run(FakeVendorWifiScanSimulator(close_failed).collect(
        request=_request(),
        quiet_timeout=0.01,
    ))
    assert result.reason is WifiScanSimulationReason.CLEANUP_FAILURE
    assert result.completeness is WifiScanCompleteness.UNCERTAIN
    assert result.cleanup_succeeded is False
    assert result.tainted is True


def test_invoked_write_failure_is_uncertain_tainted_and_not_reusable():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_error=RuntimeError("private backend detail")
    )
    simulator = FakeVendorWifiScanSimulator(transport)

    result = run(simulator.collect(request=_request()))

    assert result.reason is WifiScanSimulationReason.WRITE_FAILURE
    assert result.completeness is WifiScanCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert "private backend detail" not in repr(result)
    assert "invoked without a confirmed return" in result.user_guidance
    assert "must not be reused" in result.user_guidance
    with pytest.raises(WifiScanSimulationTaintedError, match="tainted"):
        run(simulator.collect(request=_request()))


def test_disconnect_during_invoked_write_is_uncertain_and_taints_reuse():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.before_write = lambda fake, _call: fake.emit_disconnect(
        ConnectionError("private disconnect detail")
    )
    simulator = FakeVendorWifiScanSimulator(transport)

    result = run(simulator.collect(request=_request()))

    assert result.reason is WifiScanSimulationReason.DISCONNECTED
    assert result.completeness is WifiScanCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True
    assert "private disconnect detail" not in repr(result)


def test_prewrite_cleanup_failure_is_aborted_but_taints_reuse():
    transport = ScriptedVendorFakeTransport.vendor_route(
        subscribe_error=RuntimeError("private subscribe detail"),
        close_error=RuntimeError("private close detail"),
    )
    simulator = FakeVendorWifiScanSimulator(transport)

    result = run(simulator.collect(request=_request()))

    assert result.reason is WifiScanSimulationReason.CLEANUP_FAILURE
    assert result.completeness is WifiScanCompleteness.ABORTED
    assert result.write_invoked is False
    assert result.transport_call_uncertain is False
    assert result.cleanup_succeeded is False
    assert result.tainted is True
    assert "private" not in repr(result)
    assert "tainted and must not be reused" in result.user_guidance
    with pytest.raises(WifiScanSimulationTaintedError, match="tainted"):
        run(simulator.collect(request=_request()))


def test_overall_deadline_covers_an_invoked_blocked_write():
    transport = ScriptedVendorFakeTransport.vendor_route(
        write_gate=ScriptGate.blocked()
    )
    simulator = FakeVendorWifiScanSimulator(transport)

    result = run(simulator.collect(
        request=_request(), overall_timeout=0.01, stage_timeout=1.0
    ))

    assert result.reason is WifiScanSimulationReason.OVERALL_TIMEOUT
    assert result.completeness is WifiScanCompleteness.UNCERTAIN
    assert result.write_invoked is True
    assert result.fake_write_call_completed is False
    assert result.transport_call_uncertain is True
    assert result.tainted is True


def test_revoked_target_after_structural_preflight_fails_closed():
    transport = ScriptedVendorFakeTransport.vendor_route()
    transport.owns_target = lambda _target: False

    result = run(FakeVendorWifiScanSimulator(transport).collect(request=_request()))

    assert result.reason is WifiScanSimulationReason.PREFLIGHT_FAILURE
    assert result.completeness is WifiScanCompleteness.ABORTED
    assert result.command_written is False
    assert transport.targeted_subscribe_count == 0
    assert transport.targeted_write_count == 0
    assert transport.close_count == 1


def test_concurrent_collection_is_rejected_and_sequential_reuse_is_safe():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(connect_gate=gate)
    simulator = FakeVendorWifiScanSimulator(transport)

    async def scenario():
        first = asyncio.create_task(simulator.collect(
            request=_request(), quiet_timeout=0.01, stage_timeout=0.1
        ))
        await gate.wait_until_entered()
        with pytest.raises(RuntimeError, match="already in progress"):
            await simulator.collect(request=_request())
        gate.release()
        first_result = await first
        second_result = await simulator.collect(
            request=_request(), quiet_timeout=0.01
        )
        return first_result, second_result

    first_result, second_result = run(scenario())
    assert first_result.reason is WifiScanSimulationReason.LOCAL_QUIET
    assert second_result.reason is WifiScanSimulationReason.LOCAL_QUIET


def test_cleanup_deactivates_callback_drains_queue_and_bounds_large_frames():
    transport = ScriptedVendorFakeTransport.vendor_route()

    def emit(fake, _call):
        fake.emit(VENDOR_CHARACTERISTIC_33F4, _count(1))
        fake.emit(VENDOR_CHARACTERISTIC_33F4, bytes((0x54, 0x0A)) + bytes(100_000))

    transport.before_write = emit
    result = run(FakeVendorWifiScanSimulator(transport).collect(
        request=_request(), frame_limit=1
    ))
    callback = transport.subscription_calls[0].callback
    retained_queues = [
        cell.cell_contents
        for cell in (callback.__closure__ or ())
        if isinstance(cell.cell_contents, asyncio.Queue)
    ]

    assert result.reason is WifiScanSimulationReason.LIMIT_REACHED
    assert len(retained_queues) == 1
    assert retained_queues[0].qsize() == 0
    transport.emit_stale(0, _fragment(0x81, -40, b"Private"))
    assert retained_queues[0].qsize() == 0


def test_cancellation_during_write_cleans_up_once_and_taints_reuse():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(write_gate=gate)
    simulator = FakeVendorWifiScanSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.collect(
            request=_request(), stage_timeout=0.1
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        gate.release()
        with pytest.raises(WifiScanSimulationTaintedError, match="tainted"):
            await simulator.collect(request=_request(), quiet_timeout=0.01)

    run(scenario())
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1


def test_cancellation_during_postwrite_unsubscribe_finishes_close_and_taints():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(unsubscribe_gate=gate)
    transport.before_write = lambda fake, _call: fake.emit(
        VENDOR_CHARACTERISTIC_33F4, _count(0)
    )
    simulator = FakeVendorWifiScanSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.collect(
            request=_request(), frame_limit=1, stage_timeout=0.02
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert simulator.tainted is True
    assert transport.unsubscribe_count == 1
    assert transport.close_count == 1
    assert transport.connected is False


def test_cancellation_during_prewrite_close_is_bounded_and_taints():
    gate = ScriptGate.blocked()
    transport = ScriptedVendorFakeTransport.vendor_route(
        connect_error=RuntimeError("private setup detail"),
        close_gate=gate,
    )
    simulator = FakeVendorWifiScanSimulator(transport)

    async def scenario():
        task = asyncio.create_task(simulator.collect(
            request=_request(), stage_timeout=0.02
        ))
        await gate.wait_until_entered()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert simulator.tainted is True
    assert transport.write_count == 0
    assert transport.close_count == 1
