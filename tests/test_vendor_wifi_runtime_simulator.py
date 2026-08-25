import asyncio

import pytest

from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
)
from jring.vendor_main_commands import (
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
)
from jring.vendor_runtime_fake import ScriptedVendorFakeTransport
from jring.vendor_wifi_runtime_simulator import (
    FakeVendorWifiScanSimulator,
    WifiScanCompleteness,
    WifiScanSimulationReason,
)


def run(coro):
    return asyncio.run(coro)


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
    assert result.locally_observed_count_matches is True
    assert result.quiet_means_success is False
    assert result.simulation_only is True
    assert result.hardware_eligible is False
    assert transport.subscription_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F4
    assert transport.response_write_calls[0].characteristic_uuid == VENDOR_CHARACTERISTIC_33F3
    assert transport.response_write_calls[0].data_for_test() == bytes((0x54, 0x08)) + bytes(18)
    assert transport.unsubscribe_count == 1
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
