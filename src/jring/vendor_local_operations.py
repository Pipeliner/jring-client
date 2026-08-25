"""Offline inventory for Android-local and dynamic-GATT SDK requests.

The records in this module contain no runtime arguments and cannot execute an
operation.  In particular, the dynamic UUID and characteristic-write entries document
unsafe SDK authority without recreating it in the Python client.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LocalBleOperation(str, Enum):
    CLOSE_CONNECTION = "closeConnection"
    CONNECT_BT = "connectBt"
    DISCONNECT_BT = "disconnectBt"
    GET_CONNECTED_DEVICE = "getConnectedDevice"
    GET_DEVICE_RSSI = "getDeviceRssi"
    IS_AUTHORIZE = "isAuthrize"
    IS_CONNECT_BT = "isConnectBt"
    OPEN_SDK_LOG = "openSDKLog"
    SCAN_DEVICE = "scanDevice"
    SET_OPTION = "setOption"
    SET_SCAN_MODE = "setScanMode"
    SET_UUID = "setUuid"
    UNREGISTER_CALLBACK = "unregisterCallback"
    WRITE_CHARACTERISTIC = "writeCharacteristic"


class ArgumentPrivacy(str, Enum):
    DEVICE_NAME = "device_name"
    BLUETOOTH_ADDRESS = "bluetooth_address"
    FORGET_TARGET_POLICY = "forget_target_policy"
    LOG_DESTINATION = "log_destination"
    SCAN_ENABLE_STATE = "scan_enable_state"
    PROFILE_AND_WEATHER_MODELS = "profile_and_weather_models"
    SCAN_POLICY_CODE = "scan_policy_code"
    DYNAMIC_GATT_UUIDS = "dynamic_gatt_uuids"
    BROADCAST_SUPPRESSION_POLICY = "broadcast_suppression_policy"
    CALLBACK_REFERENCE = "callback_reference"
    RAW_GATT_PAYLOAD = "raw_gatt_payload"


class BluetoothBehavior(str, Enum):
    NONE = "none"
    GATT_CLOSE = "gatt_close"
    GATT_CONNECT_WITH_RECONNECT = "gatt_connect_with_reconnect"
    GATT_DISCONNECT = "gatt_disconnect"
    LOCAL_STATE_QUERY = "local_state_query"
    REMOTE_RSSI_READ = "remote_rssi_read"
    ACTIVE_SCAN_TOGGLE = "active_scan_toggle"
    SCAN_CONFIGURATION = "scan_configuration"
    DYNAMIC_GATT_CONFIGURATION = "dynamic_gatt_configuration"
    ARBITRARY_GATT_WRITE = "arbitrary_gatt_write"


class PersistedState(str, Enum):
    NONE = "none"
    CLEARS_ADDRESS_ONLY = "clears_address_only"
    STORES_NAME_AND_ADDRESS = "stores_name_and_address"
    CONDITIONAL_ADDRESS_CLEAR = "conditional_address_clear"
    RUNTIME_LOG_CONFIGURATION = "runtime_log_configuration"
    RUNTIME_PROFILE_CACHE = "runtime_profile_cache"
    RUNTIME_SCAN_CONFIGURATION = "runtime_scan_configuration"
    RUNTIME_DYNAMIC_GATT_CONFIGURATION = "runtime_dynamic_gatt_configuration"
    RUNTIME_CALLBACK_SLOT = "runtime_callback_slot"


class CloudAuthorization(str, Enum):
    NONE = "none"
    REQUIRES_STATUS_200 = "requires_cached_status_200"
    RETURNS_CACHED_STATUS = "returns_cached_status"


class PythonAnalogue(str, Enum):
    TRANSPORT_CLOSE = "transport_close"
    EXPLICIT_PRIVATE_CONNECT = "explicit_private_connect"
    TRANSPORT_CLOSE_NO_RETAIN_POLICY = "transport_close_no_retain_policy"
    PRIVATE_SELECTION_ONLY = "private_selection_only"
    DISCOVERY_RSSI_ONLY = "discovery_rssi_only"
    NO_VENDOR_CLOUD_AUTH = "no_vendor_cloud_auth"
    CONTEXT_MANAGED_CONNECTION = "context_managed_connection"
    REDACTED_DIAGNOSTICS = "redacted_diagnostics"
    BOUNDED_REDACTED_DISCOVERY = "bounded_redacted_discovery"
    TYPED_OFFLINE_MODELS_ONLY = "typed_offline_models_only"
    NO_PUBLIC_SCAN_MODE = "no_public_scan_mode"
    PASSIVE_GATT_INVENTORY_ONLY = "passive_gatt_inventory_only"
    SCOPED_SUBSCRIPTION_CLEANUP = "scoped_subscription_cleanup"
    NO_PUBLIC_ARBITRARY_WRITE = "no_public_arbitrary_write"


@dataclass(frozen=True)
class StaticLocalBleOperation:
    operation: LocalBleOperation
    argument_privacy: tuple[ArgumentPrivacy, ...]
    returns_privacy: ArgumentPrivacy | None
    android_local_side_effects: tuple[str, ...]
    bluetooth_behavior: BluetoothBehavior
    unsafe_logging: tuple[str, ...]
    persisted_state: PersistedState
    cloud_authorization: CloudAuthorization
    python_analogue: PythonAnalogue
    static_findings: tuple[str, ...]
    recovered_sdk_performs_gatt_write: bool = False
    recovered_sdk_grants_arbitrary_write_authority: bool = False
    recovered_sdk_callback_exposes_raw_payload: bool = False
    python_callable: bool = False
    python_grants_arbitrary_write_authority: bool = False
    evidence_scope: str = "android_sdk_behavior_inventory"
    known_limitations: tuple[str, ...] = (
        "no_runtime_execution",
        "no_owner_hardware_verification",
    )
    maturity: str = "static_apk_only"
    hardware_eligible: bool = False
    hardware_verified: bool = False


def _item(
    operation: LocalBleOperation,
    *,
    arguments: tuple[ArgumentPrivacy, ...] = (),
    returns: ArgumentPrivacy | None = None,
    effects: tuple[str, ...] = (),
    bluetooth: BluetoothBehavior = BluetoothBehavior.NONE,
    logging: tuple[str, ...] = (),
    persisted: PersistedState = PersistedState.NONE,
    authorization: CloudAuthorization = CloudAuthorization.NONE,
    analogue: PythonAnalogue,
    findings: tuple[str, ...] = (),
    performs_write: bool = False,
    sdk_arbitrary_write: bool = False,
    callback_raw_payload: bool = False,
) -> StaticLocalBleOperation:
    return StaticLocalBleOperation(
        operation=operation,
        argument_privacy=arguments,
        returns_privacy=returns,
        android_local_side_effects=effects,
        bluetooth_behavior=bluetooth,
        unsafe_logging=logging,
        persisted_state=persisted,
        cloud_authorization=authorization,
        python_analogue=analogue,
        static_findings=findings,
        recovered_sdk_performs_gatt_write=performs_write,
        recovered_sdk_grants_arbitrary_write_authority=sdk_arbitrary_write,
        recovered_sdk_callback_exposes_raw_payload=callback_raw_payload,
    )


_INVENTORY = (
    _item(
        LocalBleOperation.CLOSE_CONNECTION,
        effects=(
            "sets_user_disconnected",
            "clears_in_memory_name_and_address",
            "releases_notification_state",
            "resets_connection_state",
        ),
        bluetooth=BluetoothBehavior.GATT_CLOSE,
        persisted=PersistedState.CLEARS_ADDRESS_ONLY,
        analogue=PythonAnalogue.TRANSPORT_CLOSE,
        findings=(
            "persisted_device_name_is_not_cleared",
            "closes_android_gatt_object",
        ),
    ),
    _item(
        LocalBleOperation.CONNECT_BT,
        arguments=(ArgumentPrivacy.DEVICE_NAME, ArgumentPrivacy.BLUETOOTH_ADDRESS),
        effects=(
            "stores_current_target",
            "clears_user_disconnected",
            "starts_sdk_reconnect_flow",
        ),
        bluetooth=BluetoothBehavior.GATT_CONNECT_WITH_RECONNECT,
        logging=("raw_address",),
        persisted=PersistedState.STORES_NAME_AND_ADDRESS,
        authorization=CloudAuthorization.REQUIRES_STATUS_200,
        analogue=PythonAnalogue.EXPLICIT_PRIVATE_CONNECT,
        findings=(
            "persists_raw_name_and_address",
            "python_selection_keeps_address_private_and_does_not_persist_it",
        ),
    ),
    _item(
        LocalBleOperation.DISCONNECT_BT,
        arguments=(ArgumentPrivacy.FORGET_TARGET_POLICY,),
        effects=(
            "sets_user_disconnect_policy",
            "conditionally_clears_in_memory_target",
            "releases_notification_state",
        ),
        bluetooth=BluetoothBehavior.GATT_DISCONNECT,
        persisted=PersistedState.CONDITIONAL_ADDRESS_CLEAR,
        analogue=PythonAnalogue.TRANSPORT_CLOSE_NO_RETAIN_POLICY,
        findings=(
            "false_retains_target_for_reconnect",
            "true_clears_persisted_address_but_not_persisted_name",
        ),
    ),
    _item(
        LocalBleOperation.GET_CONNECTED_DEVICE,
        returns=ArgumentPrivacy.BLUETOOTH_ADDRESS,
        bluetooth=BluetoothBehavior.LOCAL_STATE_QUERY,
        analogue=PythonAnalogue.PRIVATE_SELECTION_ONLY,
        findings=(
            "returns_raw_address",
            "returns_remembered_field_without_android_radio_query",
        ),
    ),
    _item(
        LocalBleOperation.GET_DEVICE_RSSI,
        effects=("schedules_rssi_callback",),
        bluetooth=BluetoothBehavior.REMOTE_RSSI_READ,
        analogue=PythonAnalogue.DISCOVERY_RSSI_ONLY,
        findings=(
            "result_arrives_via_callback",
            "immediate_return_is_not_rssi",
            "common_sdk_gate_does_not_use_cloud_authorization_field",
        ),
    ),
    _item(
        LocalBleOperation.IS_AUTHORIZE,
        effects=("reads_cached_sdk_authorization_code",),
        bluetooth=BluetoothBehavior.LOCAL_STATE_QUERY,
        authorization=CloudAuthorization.RETURNS_CACHED_STATUS,
        analogue=PythonAnalogue.NO_VENDOR_CLOUD_AUTH,
        findings=(
            "does_not_authorize_or_contact_cloud",
            "authorization_is_sdk_vendor_status_not_ring_owner_state",
        ),
    ),
    _item(
        LocalBleOperation.IS_CONNECT_BT,
        effects=("reads_sdk_connection_state",),
        bluetooth=BluetoothBehavior.LOCAL_STATE_QUERY,
        analogue=PythonAnalogue.CONTEXT_MANAGED_CONNECTION,
        findings=("true_for_every_sdk_state_other_than_zero_or_one",),
    ),
    _item(
        LocalBleOperation.OPEN_SDK_LOG,
        arguments=(ArgumentPrivacy.LOG_DESTINATION,),
        effects=(
            "toggles_sdk_file_logging",
            "sets_runtime_log_subdirectory_and_filename",
            "writes_future_sdk_logs_under_app_files_directory",
        ),
        logging=(
            "raw_address",
            "raw_gatt_payload",
            "sdk_credentials_and_authorization_body",
            "personal_and_environment_values",
            "caller_selected_file_destination",
        ),
        persisted=PersistedState.RUNTIME_LOG_CONFIGURATION,
        analogue=PythonAnalogue.REDACTED_DIAGNOSTICS,
        findings=(
            "returns_constant_one",
            "path_and_filename_are_not_safely_validated",
            "enables_capture_of_existing_unredacted_sdk_logs",
        ),
    ),
    _item(
        LocalBleOperation.SCAN_DEVICE,
        arguments=(ArgumentPrivacy.SCAN_ENABLE_STATE,),
        effects=("android_scan_timers_and_retry_counter",),
        bluetooth=BluetoothBehavior.ACTIVE_SCAN_TOGGLE,
        logging=("raw_discovery_identifiers",),
        authorization=CloudAuthorization.REQUIRES_STATUS_200,
        analogue=PythonAnalogue.BOUNDED_REDACTED_DISCOVERY,
        findings=(
            "start_and_stop_share_one_boolean_method",
            "python_discovery_has_an_explicit_bounded_timeout",
        ),
    ),
    _item(
        LocalBleOperation.SET_OPTION,
        arguments=(ArgumentPrivacy.PROFILE_AND_WEATHER_MODELS,),
        effects=(
            "caches_user_profile",
            "caches_device_profile",
            "caches_alarm_list",
            "caches_weather_list",
        ),
        persisted=PersistedState.RUNTIME_PROFILE_CACHE,
        authorization=CloudAuthorization.REQUIRES_STATUS_200,
        analogue=PythonAnalogue.TYPED_OFFLINE_MODELS_ONLY,
        findings=(
            "later_commands_consume_cached_values",
            "does_not_itself_write_bluetooth",
            "cache_can_retain_body_schedule_alarm_and_environment_values",
        ),
    ),
    _item(
        LocalBleOperation.SET_SCAN_MODE,
        arguments=(ArgumentPrivacy.SCAN_POLICY_CODE,),
        effects=("sets_android_scan_settings_mode_for_future_scans",),
        bluetooth=BluetoothBehavior.SCAN_CONFIGURATION,
        persisted=PersistedState.RUNTIME_SCAN_CONFIGURATION,
        analogue=PythonAnalogue.NO_PUBLIC_SCAN_MODE,
        findings=(
            "sdk_does_not_validate_mode",
            "does_not_itself_start_a_scan",
        ),
    ),
    _item(
        LocalBleOperation.SET_UUID,
        arguments=(
            ArgumentPrivacy.DYNAMIC_GATT_UUIDS,
            ArgumentPrivacy.BROADCAST_SUPPRESSION_POLICY,
        ),
        effects=(
            "future_notification_enable_disable",
            "future_arbitrary_write_lookup",
            "configures_raw_local_broadcast_suppression",
        ),
        bluetooth=BluetoothBehavior.DYNAMIC_GATT_CONFIGURATION,
        persisted=PersistedState.RUNTIME_DYNAMIC_GATT_CONFIGURATION,
        analogue=PythonAnalogue.PASSIVE_GATT_INVENTORY_ONLY,
        findings=(
            "uuid_arrays_are_not_validated_or_copied",
            "raw_callback_still_receives_values_when_broadcast_is_suppressed",
            "does_not_itself_subscribe_or_write",
        ),
    ),
    _item(
        LocalBleOperation.UNREGISTER_CALLBACK,
        arguments=(ArgumentPrivacy.CALLBACK_REFERENCE,),
        effects=("clears_single_global_callback_slot",),
        persisted=PersistedState.RUNTIME_CALLBACK_SLOT,
        analogue=PythonAnalogue.SCOPED_SUBSCRIPTION_CLEANUP,
        findings=(
            "callback_argument_identity_is_ignored",
            "can_clear_a_callback_registered_by_a_different_caller",
        ),
    ),
    _item(
        LocalBleOperation.WRITE_CHARACTERISTIC,
        arguments=(ArgumentPrivacy.DYNAMIC_GATT_UUIDS, ArgumentPrivacy.RAW_GATT_PAYLOAD),
        effects=(
            "looks_up_dynamic_service_and_characteristic",
            "sets_characteristic_value",
            "returns_write_result_via_global_callback",
        ),
        bluetooth=BluetoothBehavior.ARBITRARY_GATT_WRITE,
        logging=("raw_characteristic_uuid",),
        analogue=PythonAnalogue.NO_PUBLIC_ARBITRARY_WRITE,
        findings=(
            "bypasses_vendor_command_queue",
            "bypasses_cloud_authorization_gate",
            "same_uuid_is_used_for_service_map_and_characteristic_lookup",
            "returns_sdk_status_even_when_android_write_returns_false",
            "missing_service_returns_one_which_can_be_mistaken_for_success",
        ),
        performs_write=True,
        sdk_arbitrary_write=True,
        callback_raw_payload=True,
    ),
)


def static_local_ble_operations() -> tuple[StaticLocalBleOperation, ...]:
    """Return immutable behavior evidence without accepting runtime arguments."""

    return _INVENTORY


__all__ = [
    "ArgumentPrivacy",
    "BluetoothBehavior",
    "CloudAuthorization",
    "LocalBleOperation",
    "PersistedState",
    "PythonAnalogue",
    "StaticLocalBleOperation",
    "static_local_ble_operations",
]
