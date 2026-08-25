"""Sanitized non-runnable evidence for non-opcode vendor callbacks.

These rows classify Android, network, OTA, transport, and unused callback surfaces.
They contain no callback data and provide no Bluetooth or platform integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CallbackBehaviorCategory(str, Enum):
    AUTHORIZATION_RESULT = "authorization_result"
    ANDROID_GATT_FORWARDER = "android_gatt_forwarder"
    CONNECTION_STATE = "connection_state"
    DEVICE_WIFI_PROJECTION = "device_wifi_projection"
    RSSI_RESULT = "rssi_result"
    OTA_INFO = "ota_info"
    OTA_UPDATE = "ota_update"
    DIAL_METADATA = "dial_metadata"
    FTP_STATE = "ftp_state"
    MEDIA_FILE = "media_file"
    RAW_NOTIFICATION_CONTROL = "raw_notification_control"
    SCAN_RESULT = "scan_result"
    DECLARED_WITHOUT_DISPATCH = "declared_without_dispatch"


class CallbackPrivacyClass(str, Enum):
    GATT_IDENTIFIER = "gatt_identifier"
    RAW_PAYLOAD = "raw_payload"
    NETWORK_IDENTIFIER = "network_identifier"
    NETWORK_CREDENTIAL = "network_credential"
    SIGNAL_STRENGTH = "signal_strength"
    OTA_METADATA = "ota_metadata"
    CLOUD_CONTENT = "cloud_content"
    FILE_REFERENCE = "file_reference"
    BLUETOOTH_ADDRESS = "bluetooth_address"
    DERIVED_ADVERTISEMENT_IDENTIFIERS = "derived_advertisement_identifiers"


class CallbackDispatchOrigin(str, Enum):
    AUTH_DEVICE_PIPELINE = "auth_device_pipeline"
    AUTH_SDK_PIPELINE = "auth_sdk_pipeline"
    ANDROID_GATT_CALLBACK = "android_gatt_callback"
    SDK_CONNECTION_PIPELINE = "sdk_connection_pipeline"
    MAIN_RESPONSE_HANDLER = "main_response_handler"
    OTA_PIPELINE = "ota_pipeline"
    DIAL_PIPELINE = "dial_pipeline"
    FTP_PIPELINE = "ftp_pipeline"
    MEDIA_ACTION_PIPELINE = "media_action_pipeline"
    RAW_CONTROL_PIPELINE = "raw_control_pipeline"
    ANDROID_SCAN_CALLBACK = "android_scan_callback"
    DECLARATION_ONLY = "declaration_only"


class CallbackResultSemantics(str, Enum):
    AUTH_DEVICE_MIXED_TRANSPORT_VENDOR_STATUS = (
        "auth_device_mixed_transport_vendor_status"
    )
    AUTH_SDK_MIXED_TRANSPORT_VENDOR_STATUS = "auth_sdk_mixed_transport_vendor_status"
    GATT_IDENTIFIER_AND_CURRENT_VALUE_COPY = "gatt_identifier_and_current_value_copy"
    GATT_STATUS_AND_CURRENT_VALUE = "gatt_status_and_current_value"
    SDK_GLOBAL_CONNECTION_STATE = "sdk_global_connection_state"
    CONNECTED_WIFI_PROJECTION = "connected_wifi_projection"
    RSSI_WITH_ANDROID_STATUS_DISCARDED = "rssi_with_android_status_discarded"
    NO_RESULT_OBSERVED = "no_result_observed"
    OTA_ELIGIBILITY_METADATA_AND_FILE = "ota_eligibility_metadata_and_file"
    OTA_PHASE_AND_DETAIL_NOT_PERCENTAGE = "ota_phase_and_detail_not_percentage"
    DIAL_JSON_METADATA = "dial_json_metadata"
    FTP_STATE_AND_RETRY_REMAINING = "ftp_state_and_retry_remaining"
    MEDIA_TWO_FILE_REFERENCES = "media_two_file_references"
    RAW_ENABLE_SUBMISSION_ACCEPTANCE = "raw_enable_submission_acceptance"
    SCAN_SELECTION_WITH_DERIVED_IDENTIFIERS = (
        "scan_selection_with_derived_identifiers"
    )


class CallbackSideEffectClass(str, Enum):
    CACHE_READ = "cache_read"
    CACHE_WRITE = "cache_write"
    NETWORK_REQUEST = "network_request"
    LOG_WRITE = "log_write"
    ROUTE_BY_GATT_IDENTIFIER = "route_by_gatt_identifier"
    UNCONDITIONAL_WRITE_COMPLETION_LATCH = "unconditional_write_completion_latch"
    CONNECTION_STATE_MUTATION = "connection_state_mutation"
    CONNECTION_ATTEMPT_TRACKING = "connection_attempt_tracking"
    FILE_DOWNLOAD = "file_download"
    FTP_TRANSFER = "ftp_transfer"
    BROADCAST = "broadcast"
    HARDWARE_TRANSFER_START = "hardware_transfer_start"
    FILE_WRITE_BEFORE_CHECKSUM = "file_write_before_checksum"
    RETRY_OR_RESTART = "retry_or_restart"
    DISCONNECT_SCHEDULE = "disconnect_schedule"
    AUTO_CONNECT = "auto_connect"
    OTA_START = "ota_start"


@dataclass(frozen=True, init=False, repr=False)
class CallbackBehaviorSurface:
    name: str
    category: CallbackBehaviorCategory
    direct_invoke_observed: bool
    dispatch_origins: tuple[CallbackDispatchOrigin, ...]
    result_semantics: CallbackResultSemantics
    privacy_classes: tuple[CallbackPrivacyClass, ...]
    silence_reasons: tuple[str, ...]
    side_effect_classes: tuple[CallbackSideEffectClass, ...]
    payload_semantics_complete: bool
    limitations: tuple[str, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("callback behavior evidence is closed")

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def python_callable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False


def _surface(
    name: str,
    category: CallbackBehaviorCategory,
    result: CallbackResultSemantics,
    *origins: CallbackDispatchOrigin,
    privacy: tuple[CallbackPrivacyClass, ...] = (),
    silence: tuple[str, ...] = (),
    side_effects: tuple[CallbackSideEffectClass, ...] = (),
    invoked: bool = True,
    limitations: tuple[str, ...] = (),
) -> CallbackBehaviorSurface:
    row = object.__new__(CallbackBehaviorSurface)
    object.__setattr__(row, "name", name)
    object.__setattr__(row, "category", category)
    object.__setattr__(row, "direct_invoke_observed", invoked)
    object.__setattr__(row, "dispatch_origins", tuple(origins))
    object.__setattr__(row, "result_semantics", result)
    object.__setattr__(row, "privacy_classes", privacy)
    object.__setattr__(row, "silence_reasons", silence)
    object.__setattr__(row, "side_effect_classes", side_effects)
    object.__setattr__(row, "payload_semantics_complete", False)
    object.__setattr__(
        row,
        "limitations",
        limitations
        + (
            "dispatch_observation_is_not_runtime_reachability",
            "payload_meaning_and_hardware_behavior_are_not_complete",
        ),
    )
    return row


_SURFACES = (
    _surface(
        "onAuthDeviceResult",
        CallbackBehaviorCategory.AUTHORIZATION_RESULT,
        CallbackResultSemantics.AUTH_DEVICE_MIXED_TRANSPORT_VENDOR_STATUS,
        CallbackDispatchOrigin.AUTH_DEVICE_PIPELINE,
        silence=("exception_or_null_result",),
        side_effects=(
            CallbackSideEffectClass.CACHE_READ,
            CallbackSideEffectClass.CACHE_WRITE,
            CallbackSideEffectClass.NETWORK_REQUEST,
            CallbackSideEffectClass.LOG_WRITE,
        ),
    ),
    _surface(
        "onAuthSdkResult",
        CallbackBehaviorCategory.AUTHORIZATION_RESULT,
        CallbackResultSemantics.AUTH_SDK_MIXED_TRANSPORT_VENDOR_STATUS,
        CallbackDispatchOrigin.AUTH_SDK_PIPELINE,
        silence=("exception_or_null_result",),
        side_effects=(
            CallbackSideEffectClass.CACHE_READ,
            CallbackSideEffectClass.CACHE_WRITE,
            CallbackSideEffectClass.NETWORK_REQUEST,
        ),
    ),
    _surface(
        "onCharacteristicChanged",
        CallbackBehaviorCategory.ANDROID_GATT_FORWARDER,
        CallbackResultSemantics.GATT_IDENTIFIER_AND_CURRENT_VALUE_COPY,
        CallbackDispatchOrigin.ANDROID_GATT_CALLBACK,
        privacy=(
            CallbackPrivacyClass.GATT_IDENTIFIER,
            CallbackPrivacyClass.RAW_PAYLOAD,
        ),
        silence=("parse_before_forward_can_suppress", "null_or_exception"),
        side_effects=(
            CallbackSideEffectClass.LOG_WRITE,
            CallbackSideEffectClass.ROUTE_BY_GATT_IDENTIFIER,
        ),
    ),
    _surface(
        "onCharacteristicWrite",
        CallbackBehaviorCategory.ANDROID_GATT_FORWARDER,
        CallbackResultSemantics.GATT_STATUS_AND_CURRENT_VALUE,
        CallbackDispatchOrigin.ANDROID_GATT_CALLBACK,
        privacy=(
            CallbackPrivacyClass.GATT_IDENTIFIER,
            CallbackPrivacyClass.RAW_PAYLOAD,
        ),
        side_effects=(
            CallbackSideEffectClass.UNCONDITIONAL_WRITE_COMPLETION_LATCH,
        ),
    ),
    _surface(
        "onConnectStateChanged",
        CallbackBehaviorCategory.CONNECTION_STATE,
        CallbackResultSemantics.SDK_GLOBAL_CONNECTION_STATE,
        CallbackDispatchOrigin.SDK_CONNECTION_PIPELINE,
        side_effects=(
            CallbackSideEffectClass.CONNECTION_STATE_MUTATION,
            CallbackSideEffectClass.CONNECTION_ATTEMPT_TRACKING,
        ),
        limitations=(
            "state_set_before_callback",
            "unchanged_state_can_reemit",
        ),
    ),
    _surface(
        "onDeviceConnectedWifi",
        CallbackBehaviorCategory.DEVICE_WIFI_PROJECTION,
        CallbackResultSemantics.CONNECTED_WIFI_PROJECTION,
        CallbackDispatchOrigin.MAIN_RESPONSE_HANDLER,
        privacy=(
            CallbackPrivacyClass.NETWORK_IDENTIFIER,
            CallbackPrivacyClass.NETWORK_CREDENTIAL,
            CallbackPrivacyClass.FILE_REFERENCE,
        ),
        silence=(
            "not_connected_state",
            "auto_download_branch",
            "missing_download_file_reference",
        ),
        side_effects=(
            CallbackSideEffectClass.NETWORK_REQUEST,
            CallbackSideEffectClass.FTP_TRANSFER,
            CallbackSideEffectClass.BROADCAST,
        ),
        limitations=("connected_state_only_callback",),
    ),
    _surface(
        "onGetDeviceRssi",
        CallbackBehaviorCategory.RSSI_RESULT,
        CallbackResultSemantics.RSSI_WITH_ANDROID_STATUS_DISCARDED,
        CallbackDispatchOrigin.ANDROID_GATT_CALLBACK,
        privacy=(CallbackPrivacyClass.SIGNAL_STRENGTH,),
    ),
    _surface(
        "onGetDeviceTime",
        CallbackBehaviorCategory.DECLARED_WITHOUT_DISPATCH,
        CallbackResultSemantics.NO_RESULT_OBSERVED,
        CallbackDispatchOrigin.DECLARATION_ONLY,
        invoked=False,
        limitations=("no_direct_invoke_observed",),
    ),
    _surface(
        "onGetOtaInfo",
        CallbackBehaviorCategory.OTA_INFO,
        CallbackResultSemantics.OTA_ELIGIBILITY_METADATA_AND_FILE,
        CallbackDispatchOrigin.OTA_PIPELINE,
        privacy=(
            CallbackPrivacyClass.OTA_METADATA,
            CallbackPrivacyClass.FILE_REFERENCE,
        ),
        silence=("request_or_parse_failure",),
        side_effects=(
            CallbackSideEffectClass.NETWORK_REQUEST,
            CallbackSideEffectClass.CACHE_READ,
            CallbackSideEffectClass.CACHE_WRITE,
            CallbackSideEffectClass.FILE_DOWNLOAD,
            CallbackSideEffectClass.HARDWARE_TRANSFER_START,
        ),
        limitations=(
            "non_200_yields_false_and_empty_file_reference",
            "automatic_branch_can_download_or_start_hardware_transfer",
        ),
    ),
    _surface(
        "onGetOtaUpdate",
        CallbackBehaviorCategory.OTA_UPDATE,
        CallbackResultSemantics.OTA_PHASE_AND_DETAIL_NOT_PERCENTAGE,
        CallbackDispatchOrigin.OTA_PIPELINE,
        CallbackDispatchOrigin.DIAL_PIPELINE,
        privacy=(CallbackPrivacyClass.OTA_METADATA,),
        silence=("state_gate", "duplicate_broadcast_suppression"),
        side_effects=(
            CallbackSideEffectClass.BROADCAST,
            CallbackSideEffectClass.FILE_WRITE_BEFORE_CHECKSUM,
        ),
        limitations=("dial_origin_statically_present_but_runtime_dormant",),
    ),
    _surface(
        "onNotifyDialJsonContent",
        CallbackBehaviorCategory.DIAL_METADATA,
        CallbackResultSemantics.DIAL_JSON_METADATA,
        CallbackDispatchOrigin.DIAL_PIPELINE,
        privacy=(CallbackPrivacyClass.CLOUD_CONTENT,),
        silence=("json_parse_failure",),
        side_effects=(
            CallbackSideEffectClass.CACHE_WRITE,
            CallbackSideEffectClass.NETWORK_REQUEST,
        ),
        limitations=("transport_status_ignored_when_json_is_valid",),
    ),
    _surface(
        "onNotifyFtpStateInfo",
        CallbackBehaviorCategory.FTP_STATE,
        CallbackResultSemantics.FTP_STATE_AND_RETRY_REMAINING,
        CallbackDispatchOrigin.FTP_PIPELINE,
        privacy=(CallbackPrivacyClass.FILE_REFERENCE,),
        silence=("retry_or_restart_branch",),
        side_effects=(CallbackSideEffectClass.RETRY_OR_RESTART,),
        limitations=(
            "duplicate_progress_still_invokes",
            "success_and_error_use_empty_file_reference",
        ),
    ),
    _surface(
        "onNotifyNewMediaInfo",
        CallbackBehaviorCategory.MEDIA_FILE,
        CallbackResultSemantics.MEDIA_TWO_FILE_REFERENCES,
        CallbackDispatchOrigin.MEDIA_ACTION_PIPELINE,
        privacy=(CallbackPrivacyClass.FILE_REFERENCE,),
        silence=("media_action_not_enabled",),
        limitations=("callback_contains_two_file_references",),
    ),
    _surface(
        "onOpenRawDataNotificationState",
        CallbackBehaviorCategory.RAW_NOTIFICATION_CONTROL,
        CallbackResultSemantics.RAW_ENABLE_SUBMISSION_ACCEPTANCE,
        CallbackDispatchOrigin.RAW_CONTROL_PIPELINE,
        silence=(
            "disable_request",
            "raw_channel_missing",
            "queue_submission_rejected",
        ),
        side_effects=(CallbackSideEffectClass.DISCONNECT_SCHEDULE,),
        limitations=(
            "true_is_queue_submission_acceptance_not_descriptor_completion",
            "false_submission_schedules_disconnect",
        ),
    ),
    _surface(
        "onScanCallback",
        CallbackBehaviorCategory.SCAN_RESULT,
        CallbackResultSemantics.SCAN_SELECTION_WITH_DERIVED_IDENTIFIERS,
        CallbackDispatchOrigin.ANDROID_SCAN_CALLBACK,
        privacy=(
            CallbackPrivacyClass.BLUETOOTH_ADDRESS,
            CallbackPrivacyClass.DERIVED_ADVERTISEMENT_IDENTIFIERS,
            CallbackPrivacyClass.SIGNAL_STRENGTH,
        ),
        silence=(
            "null_or_malformed_advertisement",
            "scan_callback_exception",
            "callback_binder_dead",
        ),
        side_effects=(
            CallbackSideEffectClass.AUTO_CONNECT,
            CallbackSideEffectClass.OTA_START,
        ),
        limitations=(
            "selects_name_address_rssi_and_six_derived_identifiers",
            "does_not_forward_raw_advertisement",
        ),
    ),
    _surface(
        "onSendWeather",
        CallbackBehaviorCategory.DECLARED_WITHOUT_DISPATCH,
        CallbackResultSemantics.NO_RESULT_OBSERVED,
        CallbackDispatchOrigin.DECLARATION_ONLY,
        invoked=False,
        limitations=("no_direct_invoke_observed",),
    ),
)


def recovered_callback_behavior_surfaces() -> tuple[CallbackBehaviorSurface, ...]:
    """Return the immutable sanitized non-opcode callback inventory."""

    return _SURFACES


__all__ = [
    "CallbackBehaviorCategory",
    "CallbackBehaviorSurface",
    "CallbackDispatchOrigin",
    "CallbackPrivacyClass",
    "CallbackResultSemantics",
    "CallbackSideEffectClass",
    "recovered_callback_behavior_surfaces",
]
