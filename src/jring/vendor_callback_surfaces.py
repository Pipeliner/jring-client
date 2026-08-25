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
    OTA_INFO_OR_PROGRESS = "ota_info_or_progress"
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
    ADVERTISEMENT_DATA = "advertisement_data"


@dataclass(frozen=True, init=False, repr=False)
class CallbackBehaviorSurface:
    name: str
    category: CallbackBehaviorCategory
    direct_dispatch_observed: bool
    privacy_classes: tuple[CallbackPrivacyClass, ...]
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
    *privacy: CallbackPrivacyClass,
    dispatched: bool = True,
    limitations: tuple[str, ...] = (),
) -> CallbackBehaviorSurface:
    row = object.__new__(CallbackBehaviorSurface)
    object.__setattr__(row, "name", name)
    object.__setattr__(row, "category", category)
    object.__setattr__(row, "direct_dispatch_observed", dispatched)
    object.__setattr__(row, "privacy_classes", tuple(privacy))
    object.__setattr__(row, "payload_semantics_complete", False)
    object.__setattr__(
        row,
        "limitations",
        limitations
        or (
            "dispatch_observation_is_not_runtime_reachability",
            "payload_meaning_and_hardware_behavior_are_not_complete",
        ),
    )
    return row


_SURFACES = (
    _surface("onAuthDeviceResult", CallbackBehaviorCategory.AUTHORIZATION_RESULT),
    _surface("onAuthSdkResult", CallbackBehaviorCategory.AUTHORIZATION_RESULT),
    _surface(
        "onCharacteristicChanged",
        CallbackBehaviorCategory.ANDROID_GATT_FORWARDER,
        CallbackPrivacyClass.GATT_IDENTIFIER,
        CallbackPrivacyClass.RAW_PAYLOAD,
    ),
    _surface(
        "onCharacteristicWrite",
        CallbackBehaviorCategory.ANDROID_GATT_FORWARDER,
        CallbackPrivacyClass.GATT_IDENTIFIER,
        CallbackPrivacyClass.RAW_PAYLOAD,
    ),
    _surface("onConnectStateChanged", CallbackBehaviorCategory.CONNECTION_STATE),
    _surface(
        "onDeviceConnectedWifi",
        CallbackBehaviorCategory.DEVICE_WIFI_PROJECTION,
        CallbackPrivacyClass.NETWORK_IDENTIFIER,
        CallbackPrivacyClass.NETWORK_CREDENTIAL,
    ),
    _surface(
        "onGetDeviceRssi",
        CallbackBehaviorCategory.RSSI_RESULT,
        CallbackPrivacyClass.SIGNAL_STRENGTH,
    ),
    _surface(
        "onGetDeviceTime",
        CallbackBehaviorCategory.DECLARED_WITHOUT_DISPATCH,
        dispatched=False,
        limitations=("no_direct_dispatch_observed",),
    ),
    _surface(
        "onGetOtaInfo",
        CallbackBehaviorCategory.OTA_INFO_OR_PROGRESS,
        CallbackPrivacyClass.OTA_METADATA,
    ),
    _surface(
        "onGetOtaUpdate",
        CallbackBehaviorCategory.OTA_INFO_OR_PROGRESS,
        CallbackPrivacyClass.OTA_METADATA,
    ),
    _surface(
        "onNotifyDialJsonContent",
        CallbackBehaviorCategory.DIAL_METADATA,
        CallbackPrivacyClass.CLOUD_CONTENT,
    ),
    _surface(
        "onNotifyFtpStateInfo",
        CallbackBehaviorCategory.FTP_STATE,
        CallbackPrivacyClass.FILE_REFERENCE,
    ),
    _surface(
        "onNotifyNewMediaInfo",
        CallbackBehaviorCategory.MEDIA_FILE,
        CallbackPrivacyClass.FILE_REFERENCE,
    ),
    _surface(
        "onOpenRawDataNotificationState",
        CallbackBehaviorCategory.RAW_NOTIFICATION_CONTROL,
    ),
    _surface(
        "onScanCallback",
        CallbackBehaviorCategory.SCAN_RESULT,
        CallbackPrivacyClass.BLUETOOTH_ADDRESS,
        CallbackPrivacyClass.ADVERTISEMENT_DATA,
        CallbackPrivacyClass.SIGNAL_STRENGTH,
    ),
    _surface(
        "onSendWeather",
        CallbackBehaviorCategory.DECLARED_WITHOUT_DISPATCH,
        dispatched=False,
        limitations=("no_direct_dispatch_observed",),
    ),
)


def recovered_callback_behavior_surfaces() -> tuple[CallbackBehaviorSurface, ...]:
    """Return the immutable sanitized non-opcode callback inventory."""

    return _SURFACES


__all__ = [
    "CallbackBehaviorCategory",
    "CallbackBehaviorSurface",
    "CallbackPrivacyClass",
    "recovered_callback_behavior_surfaces",
]
