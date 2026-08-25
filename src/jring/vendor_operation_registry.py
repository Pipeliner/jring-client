"""Closed runtime-eligibility registry for the recovered request surface.

The registry joins sanitized static ledgers.  It is not a command registry: no row
contains a payload, target object, address, or authority token, and every current
ring-facing operation remains non-live until operation-specific owner evidence is
approved in a later Symphony slice.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from .vendor_coverage import static_vendor_operation_coverage
from .vendor_request_callback_correlation import (
    recovered_request_callback_correlations,
)
from .vendor_request_routing import recovered_request_routing_evidence


class OperationTerminalStatus(str, Enum):
    OFFLINE_ONLY = "offline_only"
    HARDWARE_VERIFIED = "hardware_verified"
    PROVEN_UNAVAILABLE = "proven_unavailable"
    BLOCKED_VENDOR_AUTHORIZATION = "blocked_vendor_authorization"
    UNSAFE = "unsafe"
    EXCLUDED_NON_RING = "excluded_non_ring"


class OperationCapabilityFamily(str, Enum):
    TRANSPORT = "transport"
    DEVICE_QUERY = "device_query"
    SENSOR = "sensor"
    HISTORY = "history"
    DEVICE_SETTING = "device_setting"
    SCHEDULE = "schedule"
    CONTENT_SYNC = "content_sync"
    HOST_ACTION = "host_action"
    RAW_AI_AUDIO = "raw_ai_audio"
    NETWORK_FILE = "network_file"
    CUSTOMIZATION = "customization"
    BINDING = "binding"
    FIRMWARE = "firmware"
    FACTORY_SERVICE = "factory_service"
    PLATFORM_NON_RING = "platform_non_ring"


class OperationPrivacyClass(str, Enum):
    NONE = "none"
    PUBLIC_DEVICE_STATE = "public_device_state"
    FITNESS_DATA = "fitness_data"
    HEALTH_DATA = "health_data"
    PRIVATE_CONTENT = "private_content"
    DEVICE_IDENTIFIER = "device_identifier"
    NETWORK_DATA = "network_data"
    AUDIO_DATA = "audio_data"
    FIRMWARE_ARTIFACT = "firmware_artifact"
    GENERIC_TRANSPORT = "generic_transport"


class OperationIdempotence(str, Enum):
    READ_ONLY = "read_only"
    STATE_SETTER = "state_setter"
    EVENT_PROJECTION = "event_projection"
    STREAM_CONTROL = "stream_control"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"
    LOCAL_ONLY = "local_only"


class OperationConsentLevel(str, Enum):
    LOCAL_ONLY = "local_only"
    CONNECT = "connect"
    READ = "read"
    SUBSCRIBE = "subscribe"
    WRITE = "write"
    PRIVATE_WRITE = "private_write"
    NETWORK_MUTATION = "network_mutation"
    DESTRUCTIVE = "destructive"


class VendorOperationRegistryError(LookupError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, init=False, repr=False)
class VendorOperationRegistryEntry:
    schema_version: int
    operation_id: str
    capability_family: OperationCapabilityFamily
    interface_route: str
    ring_facing: bool
    endpoint_role: str
    request_evidence_locator: str | None
    response_terminal_rule: str
    privacy_class: OperationPrivacyClass
    idempotence: OperationIdempotence
    consent_level: OperationConsentLevel
    terminal_status: OperationTerminalStatus
    firmware_scope: str
    hardware_evidence_reference: str | None
    live_eligible: bool
    hardware_verified: bool
    known_limitations: tuple[str, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor operation registry entries are closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredVendorOperationRegistry:
    schema_version: int
    operations: tuple[VendorOperationRegistryEntry, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor operation registry is closed")

    @property
    def terminal_status_counts(self) -> tuple[tuple[str, int], ...]:
        counts = Counter(row.terminal_status.value for row in self.operations)
        return tuple(sorted(counts.items()))

    @property
    def ring_facing_count(self) -> int:
        return sum(row.ring_facing for row in self.operations)

    @property
    def live_eligible_count(self) -> int:
        return sum(row.live_eligible for row in self.operations)

    @property
    def hardware_verified_count(self) -> int:
        return sum(row.hardware_verified for row in self.operations)


_FAMILY_MEMBERS: dict[OperationCapabilityFamily, frozenset[str]] = {
    OperationCapabilityFamily.PLATFORM_NON_RING: frozenset({
        "getDialServerInfo", "openSDKLog", "registerCallback", "registerCallback2",
        "saveFileToSystemAlbum", "setOption", "setScanMode", "translateBmpToBin",
        "unregisterCallback",
    }),
    OperationCapabilityFamily.TRANSPORT: frozenset({
        "closeConnection", "connectBt", "disconnectBt", "getConnectedDevice",
        "getDeviceRssi", "isAuthrize", "isConnectBt", "scanDevice", "setUuid",
        "writeCharacteristic",
    }),
    OperationCapabilityFamily.DEVICE_QUERY: frozenset({
        "SetScreenLightTime", "getBandFunction", "getDeviceBatery", "getDeviceCode",
        "getDeviceInfo", "getDeviceSystemStateInfo", "getEqInfo",
    }),
    OperationCapabilityFamily.SENSOR: frozenset({
        "getCurSportData", "setAutoHeartMode", "setBloodOxygenMode",
        "setBloodPressureMode", "setBPAdjust", "setDeviceHeartRateArea",
        "setEcgMode", "setGSensorIndState", "setHeartRateMode", "setPressureMode",
        "setSpoMode", "setSugarMode", "setTemperatureMode", "setTouchMode",
    }),
    OperationCapabilityFamily.HISTORY: frozenset({
        "getAdvSensorOfflineData", "getDataByDay", "getEcgHistory",
        "getMultipleSportData", "getOxygenOfflineData",
    }),
    OperationCapabilityFamily.DEVICE_SETTING: frozenset({
        "sendVibrationSignal", "setAntiLost", "setDeviceCode", "setDeviceInfo",
        "setDeviceMode", "setDeviceName", "setDeviceTime", "setEqInfo2",
        "setGoalStep", "setHourFormat", "setLanguage", "setPhontMode", "setUserInfo",
    }),
    OperationCapabilityFamily.SCHEDULE: frozenset({
        "setAlarm", "setFemaleReminder", "setIdleTime", "setReminder",
        "setReminderText", "setSleepTime", "setWorshipInfo",
    }),
    OperationCapabilityFamily.CONTENT_SYNC: frozenset({
        "sendWeather", "setAppId", "setAppState", "setChatgptContent",
        "setContactCrc", "setContactInfo", "setECardInfoContent", "setECardInfoCrc",
        "setNotify", "setPhoneMac", "setSmsRspInfoContent", "setSmsRspInfoCrc",
        "setSmsRspSendAck",
    }),
    OperationCapabilityFamily.HOST_ACTION: frozenset({
        "sendPhoneCallState", "sendPhoneVolume",
    }),
    OperationCapabilityFamily.RAW_AI_AUDIO: frozenset({
        "connectAiServerNotification", "openAiAudioState", "openAiState",
        "openRawDataNotification", "queryAiState", "queryOfflineSpeechRecognitionState",
        "setAILang", "setAiChatState", "setAiCommandType", "setAiConnectionMethod",
        "setAiExtraAction", "setOfflineSpeechRecognitionState",
    }),
    OperationCapabilityFamily.NETWORK_FILE: frozenset({
        "connectFtp", "getDeviceFileState", "getMediaFileState", "getWifiState",
        "notifyDownloadFtpFileCompleted", "openWifiApMode", "scanWifi",
        "setDeviceFileState", "setWifiHotSpotInfo", "setWifiHotSpotInfoEx",
        "startFtpDownloadTask",
    }),
    OperationCapabilityFamily.CUSTOMIZATION: frozenset({
        "editDeviceDialCustom", "getDeviceDial", "getDeviceDialCustom",
        "setDeviceDialState", "setDeviceWallpaperState",
    }),
    OperationCapabilityFamily.BINDING: frozenset({"setBindedInfo"}),
    OperationCapabilityFamily.FIRMWARE: frozenset({"getOtaInfo", "startFileOta"}),
    OperationCapabilityFamily.FACTORY_SERVICE: frozenset({"startFactoryTestMode"}),
}

_EXCLUDED_NON_RING = _FAMILY_MEMBERS[OperationCapabilityFamily.PLATFORM_NON_RING]
_UNSAFE_GENERIC_TRANSPORT = frozenset({"setUuid", "writeCharacteristic"})
_READ_ONLY_FAMILIES = frozenset({
    OperationCapabilityFamily.DEVICE_QUERY,
    OperationCapabilityFamily.HISTORY,
})
_PRIVATE_FAMILIES = frozenset({
    OperationCapabilityFamily.SCHEDULE,
    OperationCapabilityFamily.CONTENT_SYNC,
    OperationCapabilityFamily.HOST_ACTION,
    OperationCapabilityFamily.BINDING,
})
_FITNESS_OPERATIONS = frozenset({"setGoalStep"})
_HEALTH_OPERATIONS = frozenset({
    "getAdvSensorOfflineData", "getEcgHistory", "getOxygenOfflineData",
    "setAutoHeartMode", "setBloodOxygenMode", "setBloodPressureMode", "setBPAdjust",
    "setDeviceHeartRateArea", "setEcgMode", "setHeartRateMode", "setPressureMode",
    "setSpoMode", "setSugarMode", "setTemperatureMode", "setUserInfo",
})
_IDENTIFIER_OPERATIONS = frozenset({
    "getDeviceCode", "getDeviceInfo", "setAppId", "setBindedInfo", "setDeviceCode",
    "setDeviceInfo", "setDeviceName", "setPhoneMac",
})


def _family_index() -> dict[str, OperationCapabilityFamily]:
    result: dict[str, OperationCapabilityFamily] = {}
    for family, names in _FAMILY_MEMBERS.items():
        for name in names:
            if name in result:
                raise RuntimeError("duplicate operation capability classification")
            result[name] = family
    return result


def _privacy(name: str, family: OperationCapabilityFamily) -> OperationPrivacyClass:
    if name in _IDENTIFIER_OPERATIONS:
        return OperationPrivacyClass.DEVICE_IDENTIFIER
    if name in _HEALTH_OPERATIONS:
        return OperationPrivacyClass.HEALTH_DATA
    if name in _FITNESS_OPERATIONS or family in {
        OperationCapabilityFamily.SENSOR,
        OperationCapabilityFamily.HISTORY,
    }:
        return OperationPrivacyClass.FITNESS_DATA
    if family in _PRIVATE_FAMILIES:
        return OperationPrivacyClass.PRIVATE_CONTENT
    if family is OperationCapabilityFamily.NETWORK_FILE:
        return OperationPrivacyClass.NETWORK_DATA
    if family is OperationCapabilityFamily.RAW_AI_AUDIO:
        return OperationPrivacyClass.AUDIO_DATA
    if family is OperationCapabilityFamily.FIRMWARE:
        return OperationPrivacyClass.FIRMWARE_ARTIFACT
    if family is OperationCapabilityFamily.TRANSPORT:
        return OperationPrivacyClass.GENERIC_TRANSPORT
    if family is OperationCapabilityFamily.PLATFORM_NON_RING:
        return OperationPrivacyClass.NONE
    return OperationPrivacyClass.PUBLIC_DEVICE_STATE


def _idempotence(
    name: str, family: OperationCapabilityFamily,
) -> OperationIdempotence:
    if family is OperationCapabilityFamily.PLATFORM_NON_RING:
        return OperationIdempotence.LOCAL_ONLY
    if family in _READ_ONLY_FAMILIES or name == "getCurSportData":
        return OperationIdempotence.READ_ONLY
    if family in {
        OperationCapabilityFamily.DEVICE_SETTING,
        OperationCapabilityFamily.SCHEDULE,
        OperationCapabilityFamily.CUSTOMIZATION,
        OperationCapabilityFamily.BINDING,
    }:
        return OperationIdempotence.STATE_SETTER
    if family in {
        OperationCapabilityFamily.CONTENT_SYNC,
        OperationCapabilityFamily.HOST_ACTION,
    }:
        return OperationIdempotence.EVENT_PROJECTION
    if family in {
        OperationCapabilityFamily.SENSOR,
        OperationCapabilityFamily.RAW_AI_AUDIO,
    }:
        return OperationIdempotence.STREAM_CONTROL
    if family in {
        OperationCapabilityFamily.FIRMWARE,
        OperationCapabilityFamily.FACTORY_SERVICE,
    }:
        return OperationIdempotence.DESTRUCTIVE
    return OperationIdempotence.UNKNOWN


def _consent(
    name: str, family: OperationCapabilityFamily,
) -> OperationConsentLevel:
    if family is OperationCapabilityFamily.PLATFORM_NON_RING:
        return OperationConsentLevel.LOCAL_ONLY
    if name in _UNSAFE_GENERIC_TRANSPORT:
        return OperationConsentLevel.DESTRUCTIVE
    if family is OperationCapabilityFamily.TRANSPORT:
        return OperationConsentLevel.CONNECT
    if family in _READ_ONLY_FAMILIES or name == "getCurSportData":
        return OperationConsentLevel.READ
    if family is OperationCapabilityFamily.RAW_AI_AUDIO:
        return OperationConsentLevel.SUBSCRIBE
    if family in _PRIVATE_FAMILIES:
        return OperationConsentLevel.PRIVATE_WRITE
    if family is OperationCapabilityFamily.NETWORK_FILE:
        return OperationConsentLevel.NETWORK_MUTATION
    if family in {
        OperationCapabilityFamily.FIRMWARE,
        OperationCapabilityFamily.FACTORY_SERVICE,
    }:
        return OperationConsentLevel.DESTRUCTIVE
    return OperationConsentLevel.WRITE


def _terminal_status(name: str) -> OperationTerminalStatus:
    if name in _EXCLUDED_NON_RING:
        return OperationTerminalStatus.EXCLUDED_NON_RING
    if name in _UNSAFE_GENERIC_TRANSPORT:
        return OperationTerminalStatus.UNSAFE
    return OperationTerminalStatus.OFFLINE_ONLY


def _make_entry(
    *,
    name: str,
    family: OperationCapabilityFamily,
    interface_route: str,
    endpoint_role: str,
    evidence_locator: str | None,
    response_terminal_rule: str,
    known_limitations: tuple[str, ...],
) -> VendorOperationRegistryEntry:
    status = _terminal_status(name)
    row = object.__new__(VendorOperationRegistryEntry)
    values = {
        "schema_version": 1,
        "operation_id": name,
        "capability_family": family,
        "interface_route": interface_route,
        "ring_facing": status is not OperationTerminalStatus.EXCLUDED_NON_RING,
        "endpoint_role": endpoint_role,
        "request_evidence_locator": evidence_locator,
        "response_terminal_rule": response_terminal_rule,
        "privacy_class": _privacy(name, family),
        "idempotence": _idempotence(name, family),
        "consent_level": _consent(name, family),
        "terminal_status": status,
        "firmware_scope": "untested",
        "hardware_evidence_reference": None,
        "live_eligible": False,
        "hardware_verified": False,
        "known_limitations": known_limitations,
    }
    for field, value in values.items():
        object.__setattr__(row, field, value)
    return row


def _build_registry() -> RecoveredVendorOperationRegistry:
    coverage = static_vendor_operation_coverage()
    family_by_name = _family_index()
    names = {row.name for row in coverage}
    if set(family_by_name) != names:
        raise RuntimeError("operation capability classifications do not match coverage")
    routing = {
        row.name: row for row in recovered_request_routing_evidence().requests
    }
    if set(routing) != names:
        raise RuntimeError("operation routing evidence does not match coverage")
    correlations = {
        row.request: row
        for row in recovered_request_callback_correlations().rows
    }
    if not set(correlations) <= names:
        raise RuntimeError("operation correlation evidence exceeds coverage")

    rows = tuple(
        _make_entry(
            name=operation.name,
            family=family_by_name[operation.name],
            interface_route=operation.route,
            endpoint_role=routing[operation.name].route_role.value,
            evidence_locator=operation.evidence_locator,
            response_terminal_rule=(
                correlations[operation.name].terminal_rule
                if operation.name in correlations
                else "not_applicable_no_deterministic_codec"
            ),
            known_limitations=operation.known_limitations,
        )
        for operation in coverage
    )
    registry = object.__new__(RecoveredVendorOperationRegistry)
    object.__setattr__(registry, "schema_version", 1)
    object.__setattr__(registry, "operations", rows)
    return registry


_REGISTRY = _build_registry()
_INDEX = {row.operation_id: row for row in _REGISTRY.operations}


def recovered_vendor_operation_registry() -> RecoveredVendorOperationRegistry:
    """Return the immutable sanitized registry without granting runtime authority."""

    return _REGISTRY


def operation_registry_entry(operation_id: str) -> VendorOperationRegistryEntry:
    if type(operation_id) is not str or operation_id not in _INDEX:
        raise VendorOperationRegistryError("unknown_operation")
    return _INDEX[operation_id]


def require_hardware_verified_operation(
    operation_id: str,
) -> VendorOperationRegistryEntry:
    row = operation_registry_entry(operation_id)
    if (
        row.terminal_status is not OperationTerminalStatus.HARDWARE_VERIFIED
        or not row.live_eligible
        or not row.hardware_verified
        or row.firmware_scope == "untested"
        or row.hardware_evidence_reference is None
    ):
        raise VendorOperationRegistryError("operation_not_hardware_verified")
    return row


def vendor_operation_registry_payload() -> dict[str, object]:
    """Return deterministic JSON-safe inspection data with no runtime authority."""

    registry = recovered_vendor_operation_registry()
    return {
        "schema_version": registry.schema_version,
        "operation_count": len(registry.operations),
        "ring_facing_count": registry.ring_facing_count,
        "live_eligible_count": registry.live_eligible_count,
        "hardware_verified_count": registry.hardware_verified_count,
        "terminal_status_counts": dict(registry.terminal_status_counts),
        "operations": [
            {
                "schema_version": row.schema_version,
                "operation_id": row.operation_id,
                "capability_family": row.capability_family.value,
                "interface_route": row.interface_route,
                "ring_facing": row.ring_facing,
                "endpoint_role": row.endpoint_role,
                "request_evidence_locator": row.request_evidence_locator,
                "response_terminal_rule": row.response_terminal_rule,
                "privacy_class": row.privacy_class.value,
                "idempotence": row.idempotence.value,
                "consent_level": row.consent_level.value,
                "terminal_status": row.terminal_status.value,
                "firmware_scope": row.firmware_scope,
                "hardware_evidence_reference": row.hardware_evidence_reference,
                "live_eligible": row.live_eligible,
                "hardware_verified": row.hardware_verified,
                "known_limitations": list(row.known_limitations),
            }
            for row in registry.operations
        ],
    }


__all__ = [
    "OperationCapabilityFamily",
    "OperationConsentLevel",
    "OperationIdempotence",
    "OperationPrivacyClass",
    "OperationTerminalStatus",
    "RecoveredVendorOperationRegistry",
    "VendorOperationRegistryEntry",
    "VendorOperationRegistryError",
    "operation_registry_entry",
    "recovered_vendor_operation_registry",
    "require_hardware_verified_operation",
    "vendor_operation_registry_payload",
]
