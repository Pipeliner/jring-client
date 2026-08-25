"""Closed inventory of SDK requests that are not ring Bluetooth operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PlatformSurfaceOperation(str, Enum):
    GET_DIAL_SERVER_INFO = "getDialServerInfo"
    REGISTER_CALLBACK = "registerCallback"
    REGISTER_CALLBACK_WITH_CREDENTIALS = "registerCallback2"
    START_FTP_DOWNLOAD = "startFtpDownloadTask"
    SAVE_TO_SYSTEM_ALBUM = "saveFileToSystemAlbum"
    TRANSLATE_BMP_TO_BIN = "translateBmpToBin"
    CONNECT_FTP = "connectFtp"
    GET_DEVICE_FILE_STATE = "getDeviceFileState"
    GET_WIFI_STATE = "getWifiState"
    SET_DEVICE_FILE_STATE = "setDeviceFileState"


class PlatformBehaviorClass(str, Enum):
    CACHE_THEN_VENDOR_NETWORK = "cache_then_vendor_network"
    CALLBACK_REGISTRATION_AND_SDK_VALIDATION = (
        "callback_registration_and_sdk_validation"
    )
    PHONE_MANAGED_FTP_DOWNLOAD = "phone_managed_ftp_download"
    ANDROID_MEDIA_STORE_AND_BROADCAST = "android_media_store_and_broadcast"
    LOCAL_BITMAP_CONVERSION = "local_bitmap_conversion"
    CONSTANT_NO_OP_STUB = "constant_no_op_stub"


class PlatformPrivacyClass(str, Enum):
    DEVICE_MODEL_OR_DIAL_REQUEST = "device_model_or_dial_request"
    BUNDLED_SDK_CREDENTIALS = "bundled_sdk_credentials"
    CALLER_PROVIDED_SDK_CREDENTIALS = "caller_provided_sdk_credentials"
    REMOTE_CREDENTIALS_AND_LOCAL_PATH = "remote_credentials_and_local_path"
    LOCAL_FILE_PATH = "local_file_path"
    LOCAL_FILE_PATHS_AND_IMAGE = "local_file_paths_and_image"
    NONE = "none"


class PlatformSideEffectClass(str, Enum):
    ANDROID_CACHE_AND_VENDOR_NETWORK = "android_cache_and_vendor_network"
    ANDROID_CALLBACK_STATE_CACHE_OR_VENDOR_NETWORK = (
        "android_callback_state_cache_or_vendor_network"
    )
    PHONE_NETWORK_AND_FILESYSTEM = "phone_network_and_filesystem"
    PHONE_FILESYSTEM_AND_BROADCAST = "phone_filesystem_and_broadcast"
    PHONE_FILESYSTEM_AND_CONVERSION = "phone_filesystem_and_conversion"
    NONE = "none"


class CallbackCredentialSource(str, Enum):
    NONE = "none"
    BUNDLED_CONFIGURATION = "bundled_configuration"
    CALLER_ARGUMENTS = "caller_arguments"


class SdkValidationPath(str, Enum):
    NONE = "none"
    FRESH_CACHE_OR_VENDOR_NETWORK = "fresh_cache_or_vendor_network"


class FutureCallbackScope(str, Enum):
    NONE = "none"
    GLOBAL_SERVICE_EVENTS_INCLUDING_BLUETOOTH = (
        "global_service_events_including_bluetooth"
    )


@dataclass(frozen=True)
class StaticPlatformSurface:
    operation: PlatformSurfaceOperation
    behavior_class: PlatformBehaviorClass
    privacy_class: PlatformPrivacyClass
    side_effect_class: PlatformSideEffectClass
    callback_credential_source: CallbackCredentialSource = (
        CallbackCredentialSource.NONE
    )
    sdk_validation_path: SdkValidationPath = SdkValidationPath.NONE
    future_callback_scope: FutureCallbackScope = FutureCallbackScope.NONE
    static_findings: tuple[str, ...] = ()
    directly_touches_bluetooth: bool = False
    establishes_owner_authorization: bool = False
    python_callable: bool = False
    hardware_eligible: bool = False
    hardware_verified: bool = False
    maturity: str = "static_apk_only"
    evidence_scope: str = "android_platform_behavior_inventory"
    known_limitations: tuple[str, ...] = (
        "not_behavioral_parity",
        "no_runtime_execution",
    )


_SURFACE = (
    StaticPlatformSurface(
        PlatformSurfaceOperation.GET_DIAL_SERVER_INFO,
        PlatformBehaviorClass.CACHE_THEN_VENDOR_NETWORK,
        PlatformPrivacyClass.DEVICE_MODEL_OR_DIAL_REQUEST,
        PlatformSideEffectClass.ANDROID_CACHE_AND_VENDOR_NETWORK,
    ),
    StaticPlatformSurface(
        PlatformSurfaceOperation.REGISTER_CALLBACK,
        PlatformBehaviorClass.CALLBACK_REGISTRATION_AND_SDK_VALIDATION,
        PlatformPrivacyClass.BUNDLED_SDK_CREDENTIALS,
        PlatformSideEffectClass.ANDROID_CALLBACK_STATE_CACHE_OR_VENDOR_NETWORK,
        callback_credential_source=CallbackCredentialSource.BUNDLED_CONFIGURATION,
        sdk_validation_path=SdkValidationPath.FRESH_CACHE_OR_VENDOR_NETWORK,
        future_callback_scope=(
            FutureCallbackScope.GLOBAL_SERVICE_EVENTS_INCLUDING_BLUETOOTH
        ),
        static_findings=(
            "installs_one_shared_service_callback_slot",
            "fresh_validation_cache_reports_current_shared_sdk_status",
            "stale_validation_cache_starts_vendor_network_request",
            "registration_does_not_establish_device_gear_policy",
            "registration_does_not_establish_owner_authorization",
        ),
    ),
    StaticPlatformSurface(
        PlatformSurfaceOperation.REGISTER_CALLBACK_WITH_CREDENTIALS,
        PlatformBehaviorClass.CALLBACK_REGISTRATION_AND_SDK_VALIDATION,
        PlatformPrivacyClass.CALLER_PROVIDED_SDK_CREDENTIALS,
        PlatformSideEffectClass.ANDROID_CALLBACK_STATE_CACHE_OR_VENDOR_NETWORK,
        callback_credential_source=CallbackCredentialSource.CALLER_ARGUMENTS,
        sdk_validation_path=SdkValidationPath.FRESH_CACHE_OR_VENDOR_NETWORK,
        future_callback_scope=(
            FutureCallbackScope.GLOBAL_SERVICE_EVENTS_INCLUDING_BLUETOOTH
        ),
        static_findings=(
            "installs_one_shared_service_callback_slot",
            "fresh_validation_cache_reports_current_shared_sdk_status",
            "stale_validation_cache_starts_vendor_network_request",
            "registration_does_not_establish_device_gear_policy",
            "registration_does_not_establish_owner_authorization",
        ),
    ),
    StaticPlatformSurface(
        PlatformSurfaceOperation.START_FTP_DOWNLOAD,
        PlatformBehaviorClass.PHONE_MANAGED_FTP_DOWNLOAD,
        PlatformPrivacyClass.REMOTE_CREDENTIALS_AND_LOCAL_PATH,
        PlatformSideEffectClass.PHONE_NETWORK_AND_FILESYSTEM,
    ),
    StaticPlatformSurface(
        PlatformSurfaceOperation.SAVE_TO_SYSTEM_ALBUM,
        PlatformBehaviorClass.ANDROID_MEDIA_STORE_AND_BROADCAST,
        PlatformPrivacyClass.LOCAL_FILE_PATH,
        PlatformSideEffectClass.PHONE_FILESYSTEM_AND_BROADCAST,
    ),
    StaticPlatformSurface(
        PlatformSurfaceOperation.TRANSLATE_BMP_TO_BIN,
        PlatformBehaviorClass.LOCAL_BITMAP_CONVERSION,
        PlatformPrivacyClass.LOCAL_FILE_PATHS_AND_IMAGE,
        PlatformSideEffectClass.PHONE_FILESYSTEM_AND_CONVERSION,
    ),
    *(
        StaticPlatformSurface(
            operation,
            PlatformBehaviorClass.CONSTANT_NO_OP_STUB,
            PlatformPrivacyClass.NONE,
            PlatformSideEffectClass.NONE,
        )
        for operation in (
            PlatformSurfaceOperation.CONNECT_FTP,
            PlatformSurfaceOperation.GET_DEVICE_FILE_STATE,
            PlatformSurfaceOperation.GET_WIFI_STATE,
            PlatformSurfaceOperation.SET_DEVICE_FILE_STATE,
        )
    ),
)


def static_platform_surface() -> tuple[StaticPlatformSurface, ...]:
    """Return immutable static evidence without performing platform work."""

    return _SURFACE
