from dataclasses import FrozenInstanceError

import pytest

from jring.vendor_local_operations import (
    ArgumentPrivacy,
    BluetoothBehavior,
    CloudAuthorization,
    LocalBleOperation,
    PersistedState,
    PythonAnalogue,
    static_local_ble_operations,
)


def _by_operation():
    return {item.operation: item for item in static_local_ble_operations()}


def test_all_fourteen_local_ble_or_dynamic_gatt_requests_are_accounted_once():
    inventory = static_local_ble_operations()

    assert len(inventory) == 14
    assert {item.operation for item in inventory} == set(LocalBleOperation)
    assert len({item.operation for item in inventory}) == len(inventory)
    assert all(item.maturity == "static_apk_only" for item in inventory)
    assert all(item.hardware_eligible is False for item in inventory)
    assert all(item.hardware_verified is False for item in inventory)
    assert all(item.python_callable is False for item in inventory)
    assert all(item.python_grants_arbitrary_write_authority is False for item in inventory)
    assert all(item.evidence_scope == "android_sdk_behavior_inventory" for item in inventory)
    assert all(item.known_limitations for item in inventory)


def test_connection_lifecycle_distinguishes_close_disconnect_and_retained_target():
    items = _by_operation()
    close = items[LocalBleOperation.CLOSE_CONNECTION]
    connect = items[LocalBleOperation.CONNECT_BT]
    disconnect = items[LocalBleOperation.DISCONNECT_BT]

    assert close.bluetooth_behavior is BluetoothBehavior.GATT_CLOSE
    assert close.persisted_state is PersistedState.CLEARS_ADDRESS_ONLY
    assert close.python_analogue is PythonAnalogue.TRANSPORT_CLOSE
    assert connect.bluetooth_behavior is BluetoothBehavior.GATT_CONNECT_WITH_RECONNECT
    assert connect.argument_privacy == (
        ArgumentPrivacy.DEVICE_NAME,
        ArgumentPrivacy.BLUETOOTH_ADDRESS,
    )
    assert connect.persisted_state is PersistedState.STORES_NAME_AND_ADDRESS
    assert connect.cloud_authorization is CloudAuthorization.REQUIRES_STATUS_200
    assert "raw_address" in connect.unsafe_logging
    assert disconnect.bluetooth_behavior is BluetoothBehavior.GATT_DISCONNECT
    assert disconnect.argument_privacy == (ArgumentPrivacy.FORGET_TARGET_POLICY,)
    assert disconnect.persisted_state is PersistedState.CONDITIONAL_ADDRESS_CLEAR
    assert "false_retains_target_for_reconnect" in disconnect.static_findings


def test_connected_device_is_a_private_local_getter_not_a_radio_query():
    item = _by_operation()[LocalBleOperation.GET_CONNECTED_DEVICE]

    assert item.bluetooth_behavior is BluetoothBehavior.LOCAL_STATE_QUERY
    assert item.returns_privacy is ArgumentPrivacy.BLUETOOTH_ADDRESS
    assert item.python_analogue is PythonAnalogue.PRIVATE_SELECTION_ONLY
    assert "returns_raw_address" in item.static_findings


def test_connected_rssi_is_an_async_android_gatt_read_with_callback_result():
    item = _by_operation()[LocalBleOperation.GET_DEVICE_RSSI]

    assert item.bluetooth_behavior is BluetoothBehavior.REMOTE_RSSI_READ
    assert item.cloud_authorization is CloudAuthorization.NONE
    assert item.python_analogue is PythonAnalogue.DISCOVERY_RSSI_ONLY
    assert "result_arrives_via_callback" in item.static_findings
    assert "immediate_return_is_not_rssi" in item.static_findings


def test_authorization_status_is_only_a_local_view_of_vendor_cloud_state():
    item = _by_operation()[LocalBleOperation.IS_AUTHORIZE]

    assert item.bluetooth_behavior is BluetoothBehavior.LOCAL_STATE_QUERY
    assert item.cloud_authorization is CloudAuthorization.RETURNS_CACHED_STATUS
    assert item.python_analogue is PythonAnalogue.NO_VENDOR_CLOUD_AUTH
    assert "does_not_authorize_or_contact_cloud" in item.static_findings


def test_connection_boolean_uses_broad_sdk_state_not_android_is_connected():
    item = _by_operation()[LocalBleOperation.IS_CONNECT_BT]

    assert item.bluetooth_behavior is BluetoothBehavior.LOCAL_STATE_QUERY
    assert item.python_analogue is PythonAnalogue.CONTEXT_MANAGED_CONNECTION
    assert "true_for_every_sdk_state_other_than_zero_or_one" in item.static_findings


def test_sdk_logging_is_a_local_filesystem_privacy_hazard():
    item = _by_operation()[LocalBleOperation.OPEN_SDK_LOG]

    assert item.bluetooth_behavior is BluetoothBehavior.NONE
    assert item.argument_privacy == (ArgumentPrivacy.LOG_DESTINATION,)
    assert item.persisted_state is PersistedState.RUNTIME_LOG_CONFIGURATION
    assert item.python_analogue is PythonAnalogue.REDACTED_DIAGNOSTICS
    assert set(item.unsafe_logging) >= {
        "raw_address",
        "raw_gatt_payload",
        "sdk_credentials_and_authorization_body",
        "personal_and_environment_values",
        "caller_selected_file_destination",
    }
    assert "returns_constant_one" in item.static_findings


def test_scan_toggle_is_cloud_gated_active_radio_work_but_python_scan_is_bounded():
    item = _by_operation()[LocalBleOperation.SCAN_DEVICE]

    assert item.bluetooth_behavior is BluetoothBehavior.ACTIVE_SCAN_TOGGLE
    assert item.argument_privacy == (ArgumentPrivacy.SCAN_ENABLE_STATE,)
    assert item.cloud_authorization is CloudAuthorization.REQUIRES_STATUS_200
    assert item.python_analogue is PythonAnalogue.BOUNDED_REDACTED_DISCOVERY
    assert "android_scan_timers_and_retry_counter" in item.android_local_side_effects


def test_option_only_caches_sensitive_android_models_and_does_not_write():
    item = _by_operation()[LocalBleOperation.SET_OPTION]

    assert item.bluetooth_behavior is BluetoothBehavior.NONE
    assert item.argument_privacy == (ArgumentPrivacy.PROFILE_AND_WEATHER_MODELS,)
    assert item.persisted_state is PersistedState.RUNTIME_PROFILE_CACHE
    assert item.cloud_authorization is CloudAuthorization.REQUIRES_STATUS_200
    assert item.recovered_sdk_performs_gatt_write is False
    assert item.python_analogue is PythonAnalogue.TYPED_OFFLINE_MODELS_ONLY
    assert "later_commands_consume_cached_values" in item.static_findings


def test_scan_mode_is_unvalidated_runtime_configuration_not_a_scan_itself():
    item = _by_operation()[LocalBleOperation.SET_SCAN_MODE]

    assert item.bluetooth_behavior is BluetoothBehavior.SCAN_CONFIGURATION
    assert item.argument_privacy == (ArgumentPrivacy.SCAN_POLICY_CODE,)
    assert item.persisted_state is PersistedState.RUNTIME_SCAN_CONFIGURATION
    assert item.cloud_authorization is CloudAuthorization.NONE
    assert item.python_analogue is PythonAnalogue.NO_PUBLIC_SCAN_MODE
    assert "sdk_does_not_validate_mode" in item.static_findings


def test_dynamic_uuid_configuration_controls_future_subscriptions_and_write_lookup():
    item = _by_operation()[LocalBleOperation.SET_UUID]

    assert item.bluetooth_behavior is BluetoothBehavior.DYNAMIC_GATT_CONFIGURATION
    assert item.argument_privacy == (
        ArgumentPrivacy.DYNAMIC_GATT_UUIDS,
        ArgumentPrivacy.BROADCAST_SUPPRESSION_POLICY,
    )
    assert item.persisted_state is PersistedState.RUNTIME_DYNAMIC_GATT_CONFIGURATION
    assert item.python_analogue is PythonAnalogue.PASSIVE_GATT_INVENTORY_ONLY
    assert "future_notification_enable_disable" in item.android_local_side_effects
    assert "future_arbitrary_write_lookup" in item.android_local_side_effects
    assert "raw_callback_still_receives_values_when_broadcast_is_suppressed" in (
        item.static_findings
    )


def test_unregister_ignores_callback_identity_and_clears_the_global_callback():
    item = _by_operation()[LocalBleOperation.UNREGISTER_CALLBACK]

    assert item.bluetooth_behavior is BluetoothBehavior.NONE
    assert item.argument_privacy == (ArgumentPrivacy.CALLBACK_REFERENCE,)
    assert item.persisted_state is PersistedState.RUNTIME_CALLBACK_SLOT
    assert item.python_analogue is PythonAnalogue.SCOPED_SUBSCRIPTION_CLEANUP
    assert "callback_argument_identity_is_ignored" in item.static_findings


def test_dynamic_characteristic_write_is_documented_but_never_exposed():
    item = _by_operation()[LocalBleOperation.WRITE_CHARACTERISTIC]

    assert item.bluetooth_behavior is BluetoothBehavior.ARBITRARY_GATT_WRITE
    assert item.argument_privacy == (
        ArgumentPrivacy.DYNAMIC_GATT_UUIDS,
        ArgumentPrivacy.RAW_GATT_PAYLOAD,
    )
    assert item.recovered_sdk_performs_gatt_write is True
    assert item.recovered_sdk_grants_arbitrary_write_authority is True
    assert item.python_grants_arbitrary_write_authority is False
    assert item.cloud_authorization is CloudAuthorization.NONE
    assert item.python_analogue is PythonAnalogue.NO_PUBLIC_ARBITRARY_WRITE
    assert item.recovered_sdk_callback_exposes_raw_payload is True
    assert "bypasses_vendor_command_queue" in item.static_findings
    assert "same_uuid_is_used_for_service_map_and_characteristic_lookup" in (
        item.static_findings
    )
    assert "returns_sdk_status_even_when_android_write_returns_false" in item.static_findings


def test_inventory_is_immutable_value_only_schema_without_argument_slots():
    inventory = static_local_ble_operations()
    assert inventory is static_local_ble_operations()
    assert not hasattr(inventory[0], "address")
    assert not hasattr(inventory[0], "payload")
    assert not hasattr(inventory[0], "uuid")

    with pytest.raises(FrozenInstanceError):
        inventory[0].python_callable = True
