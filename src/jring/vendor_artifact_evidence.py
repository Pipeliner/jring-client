"""Sanitized aggregate evidence for whole-artifact Bluetooth surface review.

This module contains counts and bounded conclusions only. It has no APK, DEX,
manifest, resource, native-library, filesystem, subprocess, or runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OwnedCodeScope(str, Enum):
    APPLICATION = "application"
    EMBEDDED_SDK = "embedded_sdk"


class ClassifiedMethodSurfaceKind(str, Enum):
    REQUEST_INTERFACE = "request_interface"
    CALLBACK_INTERFACE = "callback_interface"
    SDK_REQUEST_IMPLEMENTATION = "sdk_request_implementation"
    APP_CALLBACK_IMPLEMENTATION = "app_callback_implementation"
    INTERNAL_OTA = "internal_ota"
    APP_REQUEST_CALL_SITE = "app_request_call_site"
    SDK_CALLBACK_DISPATCH_SITE = "sdk_callback_dispatch_site"
    APP_ANDROID_BLUETOOTH_HELPER = "app_android_bluetooth_helper"
    SDK_ANDROID_BLUETOOTH_HELPER = "sdk_android_bluetooth_helper"


class AndroidBluetoothApiFamily(str, Enum):
    GATT = "gatt"
    LE_SCAN = "le_scan"
    ADAPTER_DEVICE_BOND = "adapter_device_bond"
    CLASSIC_PROFILE_SOCKET = "classic_profile_socket"


class ActivationReviewState(str, Enum):
    INCONCLUSIVE = "inconclusive"


def _closed_instance(model: type, **values: object) -> object:
    instance = object.__new__(model)
    for name, value in values.items():
        object.__setattr__(instance, name, value)
    return instance


class _ClosedEvidence:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("artifact surface evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class InterfaceParityEvidence(_ClosedEvidence):
    request_declaration_count: int
    request_implementation_count: int
    public_request_row_count: int
    callback_declaration_count: int
    callback_implementation_count: int
    public_callback_row_count: int
    missing_public_row_count: int
    extra_public_row_count: int
    overloaded_declaration_count: int


@dataclass(frozen=True, init=False, repr=False)
class InterfaceLinkEvidence(_ClosedEvidence):
    application_request_invoke_count: int
    application_request_unique_edge_count: int
    application_request_caller_method_count: int
    application_request_caller_class_count: int
    application_distinct_request_target_count: int
    sdk_callback_invoke_count: int
    sdk_callback_unique_edge_count: int
    sdk_callback_caller_method_count: int
    sdk_callback_caller_class_count: int
    sdk_distinct_callback_target_count: int
    unledgered_target_count: int
    declared_callback_without_direct_dispatch_count: int


@dataclass(frozen=True, init=False, repr=False)
class ClassifiedMethodSurface(_ClosedEvidence):
    kind: ClassifiedMethodSurfaceKind
    method_count: int
    class_count: int
    interface_entries: bool


@dataclass(frozen=True, init=False, repr=False)
class AndroidBluetoothReferenceSurface(_ClosedEvidence):
    scope: OwnedCodeScope
    family: AndroidBluetoothApiFamily
    method_count: int
    class_count: int
    interface_entries: bool


@dataclass(frozen=True, init=False, repr=False)
class ManifestSurfaceEvidence(_ClosedEvidence):
    xapk_apk_count: int
    locale_split_count: int
    density_split_count: int
    abi_split_count: int
    permission_count: int
    feature_count: int
    service_count: int
    receiver_count: int
    activity_count: int
    provider_count: int
    legacy_bluetooth_permission_count: int
    modern_scan_permission_declared: bool
    modern_connect_permission_declared: bool
    advertise_permission_declared: bool
    connected_device_foreground_permission_declared: bool
    ble_hardware_required: bool
    app_owned_service_count: int
    all_app_owned_services_non_exported: bool
    app_owned_ble_foreground_service_count: int
    app_owned_static_receiver_count: int
    static_android_bluetooth_action_count: int
    non_exported_ota_activity_count: int
    app_owned_exported_activity_count: int
    exported_bluetooth_controller_activity_count: int
    boot_receiver_declared: bool
    companion_device_service_declared: bool
    decoded_manifest_independently_corroborated: bool


@dataclass(frozen=True, init=False, repr=False)
class DynamicReceiverSurfaceEvidence(_ClosedEvidence):
    registration_file_count: int
    bluetooth_filter_file_count: int
    process_local_filter_file_count: int
    system_context_filter_file_count: int
    primary_unique_android_bluetooth_action_count: int
    primary_duplicate_action_registration_count: int
    primary_handled_action_count: int
    primary_unhandled_action_count: int
    system_receiver_action_count: int
    system_receiver_ble_related_app_action_count: int
    system_action_bridge_observed: bool
    system_receiver_exported_on_current_api: bool
    system_receiver_sender_permission_required: bool
    system_receiver_matching_unregister_observed: bool
    runtime_behavior_verified: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True, init=False, repr=False)
class ResourceSurfaceEvidence(_ClosedEvidence):
    decoded_base_xml_file_count: int
    keyword_matching_xml_file_count: int
    keyword_matching_named_entry_count: int
    named_entries_are_capabilities: bool
    credential_bearing_sdk_configuration_asset_count: int
    credential_material_exposed: bool
    resource_payload_review_completed: bool
    locale_payload_review_completed: bool


@dataclass(frozen=True, init=False, repr=False)
class NativeSurfaceEvidence(_ClosedEvidence):
    packaged_library_count: int
    packaged_abi_count: int
    owned_library_load_site_count: int
    native_declaration_count: int
    application_native_declaration_count: int
    embedded_sdk_native_declaration_count: int
    dependency_native_declaration_count: int
    jni_export_count: int
    matched_jni_export_count: int
    unmatched_jni_export_count: int
    unresolved_native_declaration_count: int
    unresolved_sdk_native_declaration_count: int
    bluetooth_gatt_hid_or_dial_symbol_count: int
    dynamic_jni_registration_symbol_observed: bool
    dynamic_library_loader_symbol_observed: bool
    native_instruction_review_completed: bool
    native_bluetooth_absence_established: bool


@dataclass(frozen=True, init=False, repr=False)
class DynamicActivationSurfaceEvidence(_ClosedEvidence):
    review_state: ActivationReviewState
    direct_external_dial_construction_observed: bool
    application_reflective_method_file_count: int
    embedded_sdk_reflective_method_file_count: int
    owned_common_dynamic_class_construction_file_count: int
    binder_stub_class_count: int
    binder_proxy_class_count: int
    binder_transact_file_count: int
    binder_on_transact_method_count: int
    direct_owned_service_binding_call_observed: bool
    resource_dial_tokens_present: bool
    resource_activation_resolved: bool
    native_dial_identifier_evidence: bool
    exhaustive_dynamic_activation_review: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True, init=False, repr=False)
class RecoveredArtifactSurfaceEvidence(_ClosedEvidence):
    dex_unit_count: int
    scoped_dex_unit_count: int
    application_smali_class_file_count: int
    embedded_sdk_smali_class_file_count: int
    exclusive_classified_method_count: int
    exclusive_classified_class_count: int
    interface_parity: InterfaceParityEvidence
    interface_links: InterfaceLinkEvidence
    method_surfaces: tuple[ClassifiedMethodSurface, ...]
    android_api_surfaces: tuple[AndroidBluetoothReferenceSurface, ...]
    manifest_surface: ManifestSurfaceEvidence
    dynamic_receiver_surface: DynamicReceiverSurfaceEvidence
    resource_surface: ResourceSurfaceEvidence
    native_surface: NativeSurfaceEvidence
    dynamic_activation_surface: DynamicActivationSurfaceEvidence

    @property
    def source_recovery_completeness(self) -> str:
        return "not_established"

    @property
    def complete_artifact_coverage(self) -> bool:
        return False

    @property
    def reflection_or_dynamic_activation_exhaustively_disproved(self) -> bool:
        return False

    @property
    def semantic_correctness_established(self) -> bool:
        return False

    @property
    def interface_entries(self) -> bool:
        return False

    @property
    def evidence_scope(self) -> str:
        return "sanitized_artifact_surface_audit"

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
    kind: ClassifiedMethodSurfaceKind, methods: int, classes: int
) -> ClassifiedMethodSurface:
    return _closed_instance(
        ClassifiedMethodSurface,
        kind=kind,
        method_count=methods,
        class_count=classes,
        interface_entries=False,
    )


_METHOD_SURFACES = (
    _surface(ClassifiedMethodSurfaceKind.REQUEST_INTERFACE, 112, 1),
    _surface(ClassifiedMethodSurfaceKind.CALLBACK_INTERFACE, 105, 1),
    _surface(ClassifiedMethodSurfaceKind.SDK_REQUEST_IMPLEMENTATION, 112, 1),
    _surface(ClassifiedMethodSurfaceKind.APP_CALLBACK_IMPLEMENTATION, 105, 1),
    _surface(ClassifiedMethodSurfaceKind.INTERNAL_OTA, 188, 23),
    _surface(ClassifiedMethodSurfaceKind.APP_REQUEST_CALL_SITE, 80, 47),
    _surface(ClassifiedMethodSurfaceKind.SDK_CALLBACK_DISPATCH_SITE, 23, 12),
    _surface(ClassifiedMethodSurfaceKind.APP_ANDROID_BLUETOOTH_HELPER, 133, 39),
    _surface(ClassifiedMethodSurfaceKind.SDK_ANDROID_BLUETOOTH_HELPER, 45, 7),
)


def _android_surface(
    scope: OwnedCodeScope,
    family: AndroidBluetoothApiFamily,
    methods: int,
    classes: int,
) -> AndroidBluetoothReferenceSurface:
    return _closed_instance(
        AndroidBluetoothReferenceSurface,
        scope=scope,
        family=family,
        method_count=methods,
        class_count=classes,
        interface_entries=False,
    )


_ANDROID_SURFACES = (
    _android_surface(OwnedCodeScope.APPLICATION, AndroidBluetoothApiFamily.GATT, 48, 12),
    _android_surface(OwnedCodeScope.APPLICATION, AndroidBluetoothApiFamily.LE_SCAN, 12, 6),
    _android_surface(
        OwnedCodeScope.APPLICATION,
        AndroidBluetoothApiFamily.ADAPTER_DEVICE_BOND,
        61,
        30,
    ),
    _android_surface(
        OwnedCodeScope.APPLICATION,
        AndroidBluetoothApiFamily.CLASSIC_PROFILE_SOCKET,
        15,
        4,
    ),
    _android_surface(OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.GATT, 37, 4),
    _android_surface(OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.LE_SCAN, 9, 3),
    _android_surface(
        OwnedCodeScope.EMBEDDED_SDK,
        AndroidBluetoothApiFamily.ADAPTER_DEVICE_BOND,
        9,
        3,
    ),
    _android_surface(
        OwnedCodeScope.EMBEDDED_SDK,
        AndroidBluetoothApiFamily.CLASSIC_PROFILE_SOCKET,
        0,
        0,
    ),
)


_INTERFACE_PARITY = _closed_instance(
    InterfaceParityEvidence,
    request_declaration_count=112,
    request_implementation_count=112,
    public_request_row_count=112,
    callback_declaration_count=105,
    callback_implementation_count=105,
    public_callback_row_count=105,
    missing_public_row_count=0,
    extra_public_row_count=0,
    overloaded_declaration_count=0,
)

_INTERFACE_LINKS = _closed_instance(
    InterfaceLinkEvidence,
    application_request_invoke_count=152,
    application_request_unique_edge_count=130,
    application_request_caller_method_count=86,
    application_request_caller_class_count=48,
    application_distinct_request_target_count=51,
    sdk_callback_invoke_count=181,
    sdk_callback_unique_edge_count=126,
    sdk_callback_caller_method_count=34,
    sdk_callback_caller_class_count=17,
    sdk_distinct_callback_target_count=103,
    unledgered_target_count=0,
    declared_callback_without_direct_dispatch_count=2,
)

_MANIFEST = _closed_instance(
    ManifestSurfaceEvidence,
    xapk_apk_count=20,
    locale_split_count=17,
    density_split_count=1,
    abi_split_count=1,
    permission_count=35,
    feature_count=9,
    service_count=6,
    receiver_count=2,
    activity_count=79,
    provider_count=8,
    legacy_bluetooth_permission_count=2,
    modern_scan_permission_declared=True,
    modern_connect_permission_declared=True,
    advertise_permission_declared=False,
    connected_device_foreground_permission_declared=True,
    ble_hardware_required=True,
    app_owned_service_count=3,
    all_app_owned_services_non_exported=True,
    app_owned_ble_foreground_service_count=1,
    app_owned_static_receiver_count=0,
    static_android_bluetooth_action_count=0,
    non_exported_ota_activity_count=3,
    app_owned_exported_activity_count=2,
    exported_bluetooth_controller_activity_count=1,
    boot_receiver_declared=False,
    companion_device_service_declared=False,
    decoded_manifest_independently_corroborated=False,
)

_DYNAMIC_RECEIVERS = _closed_instance(
    DynamicReceiverSurfaceEvidence,
    registration_file_count=25,
    bluetooth_filter_file_count=17,
    process_local_filter_file_count=16,
    system_context_filter_file_count=1,
    primary_unique_android_bluetooth_action_count=7,
    primary_duplicate_action_registration_count=1,
    primary_handled_action_count=4,
    primary_unhandled_action_count=3,
    system_receiver_action_count=12,
    system_receiver_ble_related_app_action_count=2,
    system_action_bridge_observed=False,
    system_receiver_exported_on_current_api=True,
    system_receiver_sender_permission_required=False,
    system_receiver_matching_unregister_observed=False,
    runtime_behavior_verified=False,
    limitations=(
        "process_local_filters_do_not_receive_android_system_broadcasts_without_a_bridge",
        "three_registered_profile_actions_have_no_observed_receiver_case",
        "dynamic_system_receiver_has_no_observed_sender_permission",
        "receiver_teardown_uses_a_different_registration_domain",
    ),
)

_RESOURCES = _closed_instance(
    ResourceSurfaceEvidence,
    decoded_base_xml_file_count=1_107,
    keyword_matching_xml_file_count=24,
    keyword_matching_named_entry_count=733,
    named_entries_are_capabilities=False,
    credential_bearing_sdk_configuration_asset_count=1,
    credential_material_exposed=False,
    resource_payload_review_completed=False,
    locale_payload_review_completed=False,
)

_NATIVE = _closed_instance(
    NativeSurfaceEvidence,
    packaged_library_count=1,
    packaged_abi_count=1,
    owned_library_load_site_count=2,
    native_declaration_count=10,
    application_native_declaration_count=3,
    embedded_sdk_native_declaration_count=6,
    dependency_native_declaration_count=1,
    jni_export_count=3,
    matched_jni_export_count=3,
    unmatched_jni_export_count=0,
    unresolved_native_declaration_count=7,
    unresolved_sdk_native_declaration_count=6,
    bluetooth_gatt_hid_or_dial_symbol_count=0,
    dynamic_jni_registration_symbol_observed=False,
    dynamic_library_loader_symbol_observed=False,
    native_instruction_review_completed=False,
    native_bluetooth_absence_established=False,
)

_DYNAMIC_ACTIVATION = _closed_instance(
    DynamicActivationSurfaceEvidence,
    review_state=ActivationReviewState.INCONCLUSIVE,
    direct_external_dial_construction_observed=False,
    application_reflective_method_file_count=2,
    embedded_sdk_reflective_method_file_count=3,
    owned_common_dynamic_class_construction_file_count=0,
    binder_stub_class_count=19,
    binder_proxy_class_count=13,
    binder_transact_file_count=25,
    binder_on_transact_method_count=23,
    direct_owned_service_binding_call_observed=False,
    resource_dial_tokens_present=True,
    resource_activation_resolved=False,
    native_dial_identifier_evidence=False,
    exhaustive_dynamic_activation_review=False,
    limitations=(
        "reflective_method_dispatch_not_excluded",
        "binder_framework_wrapper_or_dependency_activation_not_excluded",
        "resource_entries_not_semantically_resolved",
        "opaque_native_behavior_not_exhaustively_disproved",
        "direct_reference_absence_does_not_establish_runtime_dormancy",
    ),
)

_EVIDENCE = _closed_instance(
    RecoveredArtifactSurfaceEvidence,
    dex_unit_count=3,
    scoped_dex_unit_count=1,
    application_smali_class_file_count=1_094,
    embedded_sdk_smali_class_file_count=138,
    exclusive_classified_method_count=903,
    exclusive_classified_class_count=125,
    interface_parity=_INTERFACE_PARITY,
    interface_links=_INTERFACE_LINKS,
    method_surfaces=_METHOD_SURFACES,
    android_api_surfaces=_ANDROID_SURFACES,
    manifest_surface=_MANIFEST,
    dynamic_receiver_surface=_DYNAMIC_RECEIVERS,
    resource_surface=_RESOURCES,
    native_surface=_NATIVE,
    dynamic_activation_surface=_DYNAMIC_ACTIVATION,
)


def recovered_artifact_surface_evidence() -> RecoveredArtifactSurfaceEvidence:
    """Return immutable sanitized artifact-surface evidence."""

    return _EVIDENCE


__all__ = [
    "ActivationReviewState",
    "AndroidBluetoothApiFamily",
    "AndroidBluetoothReferenceSurface",
    "ClassifiedMethodSurface",
    "ClassifiedMethodSurfaceKind",
    "DynamicActivationSurfaceEvidence",
    "DynamicReceiverSurfaceEvidence",
    "InterfaceLinkEvidence",
    "InterfaceParityEvidence",
    "ManifestSurfaceEvidence",
    "NativeSurfaceEvidence",
    "OwnedCodeScope",
    "RecoveredArtifactSurfaceEvidence",
    "ResourceSurfaceEvidence",
    "recovered_artifact_surface_evidence",
]
