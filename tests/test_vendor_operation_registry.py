from collections import Counter
from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_operation_registry as registry_module
from jring.vendor_coverage import static_vendor_operation_coverage
from jring.vendor_operation_registry import (
    OperationCapabilityFamily,
    OperationTerminalStatus,
    VendorOperationRegistryError,
    operation_registry_entry,
    recovered_vendor_operation_registry,
    require_hardware_verified_operation,
)
from jring.vendor_request_callback_correlation import (
    recovered_request_callback_correlations,
)
from jring.vendor_request_routing import recovered_request_routing_evidence


def test_registry_accounts_for_all_112_requests_once_with_closed_terminal_status():
    registry = recovered_vendor_operation_registry()
    coverage = static_vendor_operation_coverage()

    assert registry.schema_version == 1
    assert len(registry.operations) == 112
    assert len({row.operation_id for row in registry.operations}) == 112
    assert {row.operation_id for row in registry.operations} == {
        row.name for row in coverage
    }
    assert Counter(row.terminal_status for row in registry.operations) == {
        OperationTerminalStatus.OFFLINE_ONLY: 101,
        OperationTerminalStatus.UNSAFE: 2,
        OperationTerminalStatus.EXCLUDED_NON_RING: 9,
    }
    assert all(type(row.terminal_status) is OperationTerminalStatus for row in registry.operations)


def test_registry_classifies_non_ring_and_generic_transport_without_a_fallback():
    rows = {row.operation_id: row for row in recovered_vendor_operation_registry().operations}
    excluded = {
        "getDialServerInfo",
        "openSDKLog",
        "registerCallback",
        "registerCallback2",
        "saveFileToSystemAlbum",
        "setOption",
        "setScanMode",
        "translateBmpToBin",
        "unregisterCallback",
    }
    unsafe = {"setUuid", "writeCharacteristic"}

    assert {
        name for name, row in rows.items()
        if row.terminal_status is OperationTerminalStatus.EXCLUDED_NON_RING
    } == excluded
    assert {
        name for name, row in rows.items()
        if row.terminal_status is OperationTerminalStatus.UNSAFE
    } == unsafe
    assert all(rows[name].ring_facing is False for name in excluded)
    assert all(rows[name].ring_facing is True for name in unsafe)
    assert all(
        rows[name].capability_family is OperationCapabilityFamily.PLATFORM_NON_RING
        for name in excluded
    )
    assert all(
        rows[name].capability_family is OperationCapabilityFamily.TRANSPORT
        for name in unsafe
    )


def test_registry_preserves_route_endpoint_and_response_terminal_evidence():
    registry = {row.operation_id: row for row in recovered_vendor_operation_registry().operations}
    routes = {
        row.name: row for row in static_vendor_operation_coverage()
    }
    routing = {
        row.name: row for row in recovered_request_routing_evidence().requests
    }
    correlations = {
        row.request: row
        for row in recovered_request_callback_correlations().rows
    }

    assert all(registry[name].interface_route == row.route for name, row in routes.items())
    assert all(
        registry[name].endpoint_role == routing[name].route_role.value
        for name in registry
    )
    assert all(
        registry[name].response_terminal_rule == correlations[name].terminal_rule
        for name in correlations
    )
    assert all(
        registry[name].response_terminal_rule == "not_applicable_no_deterministic_codec"
        for name in set(registry) - set(correlations)
    )
    assert registry["getDeviceInfo"].response_terminal_rule == "single_matched_response"
    assert registry["setAlarm"].response_terminal_rule == "per_frame_only"
    assert registry["getOxygenOfflineData"].response_terminal_rule == "local_quiet_unknown"


def test_registry_has_exact_capability_privacy_idempotence_and_consent_types():
    registry = recovered_vendor_operation_registry()

    assert set(OperationCapabilityFamily) == {
        OperationCapabilityFamily.TRANSPORT,
        OperationCapabilityFamily.DEVICE_QUERY,
        OperationCapabilityFamily.SENSOR,
        OperationCapabilityFamily.HISTORY,
        OperationCapabilityFamily.DEVICE_SETTING,
        OperationCapabilityFamily.SCHEDULE,
        OperationCapabilityFamily.CONTENT_SYNC,
        OperationCapabilityFamily.HOST_ACTION,
        OperationCapabilityFamily.RAW_AI_AUDIO,
        OperationCapabilityFamily.NETWORK_FILE,
        OperationCapabilityFamily.CUSTOMIZATION,
        OperationCapabilityFamily.BINDING,
        OperationCapabilityFamily.FIRMWARE,
        OperationCapabilityFamily.FACTORY_SERVICE,
        OperationCapabilityFamily.PLATFORM_NON_RING,
    }
    for row in registry.operations:
        assert type(row.capability_family) is OperationCapabilityFamily
        assert type(row.privacy_class).__name__ == "OperationPrivacyClass"
        assert type(row.idempotence).__name__ == "OperationIdempotence"
        assert type(row.consent_level).__name__ == "OperationConsentLevel"
        assert row.firmware_scope == "untested"
        assert row.hardware_evidence_reference is None
        assert row.live_eligible is False
        assert row.hardware_verified is False
    rows = {row.operation_id: row for row in registry.operations}
    assert rows["sendPhoneCallState"].privacy_class.value == "private_content"
    assert rows["sendPhoneVolume"].privacy_class.value == "private_content"
    assert rows["setGoalStep"].privacy_class.value == "fitness_data"
    assert rows["setUserInfo"].privacy_class.value == "health_data"
    assert rows["setPhoneMac"].privacy_class.value == "device_identifier"


def test_registry_is_immutable_sanitized_and_cannot_construct_runtime_authority():
    registry = recovered_vendor_operation_registry()
    row = registry.operations[0]

    with pytest.raises(TypeError):
        type(row)()
    with pytest.raises(TypeError):
        type(registry)()
    with pytest.raises(FrozenInstanceError):
        row.live_eligible = True
    with pytest.raises(VendorOperationRegistryError) as raised:
        require_hardware_verified_operation("getDeviceInfo")
    assert raised.value.code == "operation_not_hardware_verified"
    assert "getDeviceInfo" not in str(raised.value)

    serialized = json.dumps(asdict(registry), sort_keys=True).lower()
    for forbidden in (
        "bluetooth_address",
        "raw_payload",
        "raw_frame",
        "private_evidence",
        "credential",
        "measurement",
    ):
        assert forbidden not in serialized
    forbidden_fields = {
        "address", "payload", "frame", "value", "path", "target", "credential",
    }
    assert forbidden_fields.isdisjoint(field.name for field in fields(type(row)))
    source = inspect.getsource(registry_module).lower()
    assert "bleak" not in source
    assert "subprocess" not in source
    assert "jring.input" not in source


def test_registry_lookup_is_exact_and_rejects_unknown_names_without_echo():
    row = operation_registry_entry("getDeviceInfo")
    assert row.operation_id == "getDeviceInfo"

    secret = "unknown-owner-operation"
    with pytest.raises(VendorOperationRegistryError) as raised:
        operation_registry_entry(secret)
    assert raised.value.code == "unknown_operation"
    assert secret not in str(raised.value)
