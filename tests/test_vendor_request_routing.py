from collections import Counter
from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_request_routing as routing_module
from jring.vendor_coverage import static_vendor_operation_coverage
from jring.vendor_request_routing import (
    RequestPacketShape,
    RequestRouteRole,
    recovered_request_routing_evidence,
)


def test_all_112_requests_have_one_mutually_exclusive_packet_route():
    evidence = recovered_request_routing_evidence()
    rows = evidence.requests

    assert len(rows) == 112
    assert len({row.name for row in rows}) == 112
    assert {row.name for row in rows} == {
        row.name for row in static_vendor_operation_coverage()
    }
    assert Counter(row.packet_shape for row in rows) == {
        RequestPacketShape.DETERMINISTIC_MAIN: 79,
        RequestPacketShape.DETERMINISTIC_RAW: 6,
        RequestPacketShape.STATEFUL_SHARED_PREFLIGHT: 1,
        RequestPacketShape.CALLER_DIRECTED_DYNAMIC: 1,
        RequestPacketShape.DESCRIPTOR_CONTROL: 1,
        RequestPacketShape.INTERNAL_DFU: 1,
        RequestPacketShape.NO_FIXED_PACKET: 23,
    }


def test_main_raw_and_exception_routes_have_exact_roles():
    rows = {row.name: row for row in recovered_request_routing_evidence().requests}
    main = [row for row in rows.values() if row.packet_shape is RequestPacketShape.DETERMINISTIC_MAIN]
    raw = [row for row in rows.values() if row.packet_shape is RequestPacketShape.DETERMINISTIC_RAW]

    assert len(main) == 79
    assert all(row.route_role is RequestRouteRole.MAIN_TX_RX for row in main)
    assert all(row.queue_type == 0 for row in main)
    assert all(row.standalone_deterministic_offline_codec is True for row in main)
    assert len(raw) == 6
    assert all(row.route_role is RequestRouteRole.RAW_TX_RX for row in raw)
    assert all(row.queue_type == 1 for row in raw)

    assert rows["getOtaInfo"].packet_shape is RequestPacketShape.STATEFUL_SHARED_PREFLIGHT
    assert rows["getOtaInfo"].packet_layout_statically_identifiable is True
    assert rows["getOtaInfo"].standalone_deterministic_offline_codec is False
    assert rows["writeCharacteristic"].route_role is RequestRouteRole.CALLER_SELECTED
    assert rows["openRawDataNotification"].route_role is RequestRouteRole.RAW_DESCRIPTOR
    assert rows["startFileOta"].route_role is RequestRouteRole.DFU_INTERNAL


def test_routing_counts_do_not_authorize_live_queue_reproduction():
    evidence = recovered_request_routing_evidence()

    assert evidence.standalone_deterministic_offline_count == 85
    assert evidence.statically_identifiable_layout_count == 86
    assert evidence.main_layout_count == 79
    assert evidence.raw_layout_count == 6
    assert evidence.stateful_shared_layout_count == 1
    assert evidence.dynamic_payload_count == 1
    assert evidence.descriptor_control_count == 1
    assert evidence.internal_dfu_count == 1
    assert evidence.no_fixed_packet_count == 23
    assert "write_callback_status_is_ignored" in evidence.session_constraints
    assert "automatic_retry_is_not_safe" in evidence.python_safety_rules
    assert evidence.runnable is False
    assert evidence.python_callable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert evidence.owner_authorized is False


def test_request_routing_evidence_is_closed_and_sanitized():
    evidence = recovered_request_routing_evidence()

    with pytest.raises(TypeError):
        type(evidence)()
    with pytest.raises(TypeError):
        type(evidence.requests[0])()
    with pytest.raises(FrozenInstanceError):
        evidence.requests = ()
    forbidden = {
        "source", "path", "descriptor", "prototype", "fingerprint",
        "instruction_offset", "dex_digest", "payload", "frame",
    }
    for model in (type(evidence), type(evidence.requests[0])):
        assert forbidden.isdisjoint(field.name for field in fields(model))
    serialized = json.dumps(asdict(evidence), sort_keys=True).lower()
    assert "sha256" not in serialized
    assert ".smali" not in serialized
    source = inspect.getsource(routing_module).lower()
    assert "bleak" not in source
    assert "import subprocess" not in source
    assert "open(" not in source
