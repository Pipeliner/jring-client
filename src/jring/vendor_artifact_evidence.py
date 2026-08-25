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


class DirectInstructionCountingBasis(str, Enum):
    DIRECT_EXECUTABLE_REFERENCE = "direct_executable_android_bluetooth_reference"


class DirectInstructionReferenceState(str, Enum):
    OBSERVED = "observed"
    ABSENT_IN_OWNED_SCOPE = "absent_in_owned_scope"


class AndroidBluetoothInstructionFamily(str, Enum):
    GATT = "gatt"
    LE_SCAN = "le_scan"
    ADAPTER_DEVICE_MANAGER = "adapter_device_manager"
    CLASSIC_PROFILE_SOCKET = "classic_profile_socket"


class AndroidBluetoothInstructionCategory(str, Enum):
    MTU = "mtu"
    CONNECTION_PRIORITY = "connection_priority"
    REMOTE_RSSI = "remote_rssi"
    SERVICE_DISCOVERY = "service_discovery"
    RFCOMM_SOCKET = "rfcomm_socket"
    CLASSIC_PROFILES = "classic_profiles"
    BONDING = "bonding"
    CLASSIC_DISCOVERY = "classic_discovery"
    LEGACY_LE_SCAN = "legacy_le_scan"
    MODERN_LE_SCAN = "modern_le_scan"
    DESCRIPTOR_WRITE_SETUP = "descriptor_write_setup"
    NOTIFICATION_SETUP = "notification_setup"
    CHARACTERISTIC_READ = "characteristic_read"
    CHARACTERISTIC_WRITE = "characteristic_write"
    GATT_CONNECT_LIFECYCLE = "gatt_connect_lifecycle"
    ADAPTER_POWER = "adapter_power"
    DESCRIPTOR_READ = "descriptor_read"
    PHY = "phy"
    LE_ADVERTISING = "le_advertising"
    L2CAP_CHANNEL = "l2cap_channel"
    GATT_SERVER = "gatt_server"
    HID_DEVICE = "hid_device"


class ActivationReviewState(str, Enum):
    INCONCLUSIVE = "inconclusive"


class OwnedReflectionCategory(str, Enum):
    ANDROID_BOND = "android_bond_hidden_api"
    ANDROID_TELEPHONY = "android_telephony_hidden_api"
    ANDROID_CLASSIC_PROFILE = "android_classic_profile_hidden_api"
    ANDROID_GATT_CACHE = "android_gatt_cache_refresh"


class NativeBindingReviewState(str, Enum):
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"


class NativeRootedBehaviorCategory(str, Enum):
    IMAGE_WALLPAPER_PROCESSING = "image_wallpaper_processing"


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
    counting_basis: str
    exhaustive_instruction_inventory: bool
    semantic_specificity: str


@dataclass(frozen=True, init=False, repr=False)
class AndroidBluetoothInstructionAggregate(_ClosedEvidence):
    scope: OwnedCodeScope
    owned_class_file_denominator: int
    reference_method_count: int
    reference_class_count: int
    overlapping_reference_method_count: int
    overlapping_reference_class_count: int
    unclassified_reference_method_count: int
    unclassified_reference_class_count: int
    counting_basis: DirectInstructionCountingBasis
    family_buckets_overlap: bool
    direct_reference_inventory_complete_within_owned_scope: bool
    semantic_behavior_established: bool
    dependency_or_transitive_review_complete: bool
    runtime_verified: bool
    hardware_eligible: bool
    hardware_verified: bool
    owner_authorized: bool


@dataclass(frozen=True, init=False, repr=False)
class AndroidBluetoothInstructionFamilySurface(_ClosedEvidence):
    scope: OwnedCodeScope
    family: AndroidBluetoothInstructionFamily
    method_count: int
    class_count: int
    counting_basis: DirectInstructionCountingBasis
    overlap_allowed: bool
    semantic_behavior_established: bool
    dependency_or_transitive_review_complete: bool
    runtime_verified: bool
    hardware_eligible: bool
    hardware_verified: bool
    owner_authorized: bool


@dataclass(frozen=True, init=False, repr=False)
class AndroidBluetoothInstructionCategorySurface(_ClosedEvidence):
    scope: OwnedCodeScope
    category: AndroidBluetoothInstructionCategory
    method_count: int
    class_count: int
    reference_state: DirectInstructionReferenceState
    counting_basis: DirectInstructionCountingBasis
    overlap_allowed: bool
    semantic_behavior_established: bool
    dependency_or_transitive_review_complete: bool
    runtime_verified: bool
    hardware_eligible: bool
    hardware_verified: bool
    owner_authorized: bool
    unsupported_established: bool
    limitations: tuple[str, ...]


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
    all_packaged_jni_roots_reviewed: bool
    rooted_transitive_call_graph_reviewed: bool
    rooted_jni_entry_count: int
    rooted_indirect_jni_call_count: int
    named_undefined_import_count: int
    needed_library_count: int
    runtime_initializer_count: int
    rooted_behavior_category: NativeRootedBehaviorCategory
    rooted_bluetooth_transport_edge_observed: bool
    rooted_dial_transfer_edge_observed: bool
    rooted_java_reflection_edge_observed: bool
    rooted_jni_registration_edge_observed: bool
    rooted_module_loading_edge_observed: bool
    sdk_ordinary_name_binding_state: NativeBindingReviewState
    sdk_any_possible_runtime_binding_state: NativeBindingReviewState
    native_instruction_review_completed: bool
    native_bluetooth_absence_established: bool


@dataclass(frozen=True, init=False, repr=False)
class OwnedReflectionSurface(_ClosedEvidence):
    category: OwnedReflectionCategory
    method_count: int
    invoke_count: int
    constant_target: bool
    dial_transfer_activation_observed: bool


@dataclass(frozen=True, init=False, repr=False)
class DynamicActivationSurfaceEvidence(_ClosedEvidence):
    review_state: ActivationReviewState
    direct_external_dial_construction_observed: bool
    application_reflective_method_file_count: int
    embedded_sdk_reflective_method_file_count: int
    owned_reflective_method_count: int
    owned_reflective_invoke_count: int
    owned_constant_reflective_target_count: int
    owned_reflection_targets_resolved: bool
    owned_reflection_dial_activation_observed: bool
    reflection_surfaces: tuple[OwnedReflectionSurface, ...]
    owned_common_dynamic_class_construction_file_count: int
    standalone_dial_descriptor_reference_file_count: int
    standalone_dial_external_descriptor_reference_count: int
    standalone_dial_dotted_name_reference_count: int
    standalone_dial_manifest_component_count: int
    reviewed_relevant_resource_xml_count: int
    resource_on_click_or_navigation_edge_count: int
    app_owned_explicit_launch_site_count: int
    standalone_dial_explicit_launch_count: int
    binder_stub_class_count: int
    binder_proxy_class_count: int
    binder_transact_file_count: int
    binder_on_transact_method_count: int
    direct_owned_service_binding_call_observed: bool
    standalone_dial_service_binding_observed: bool
    relevant_binder_request_transaction_count: int
    app_relevant_binder_outbound_invoke_count: int
    relevant_callback_transaction_count: int
    generic_ota_service_construction_observed: bool
    standalone_dial_binder_construction_observed: bool
    standalone_dial_static_activation_observed: bool
    resource_dial_tokens_present: bool
    resource_activation_resolved: bool
    native_dial_identifier_evidence: bool
    exhaustive_dynamic_activation_review: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True, init=False, repr=False)
class PackagedDexScopeEvidence(_ClosedEvidence):
    """Aggregate inventory classification, never semantic DEX review evidence."""

    inventory_unit_count: int
    owned_application_or_sdk_scope_unit_count: int
    no_owned_application_or_sdk_scope_unit_count: int
    unclassified_unit_count: int
    complete_semantic_source_review_completed: bool
    complete_smali_review_completed: bool
    complete_dex_instruction_review_completed: bool
    semantic_correctness_established: bool

    @property
    def classified_unit_count(self) -> int:
        return (
            self.owned_application_or_sdk_scope_unit_count
            + self.no_owned_application_or_sdk_scope_unit_count
        )

    @property
    def inventory_scope_classification_complete(self) -> bool:
        return (
            self.unclassified_unit_count == 0
            and self.classified_unit_count == self.inventory_unit_count
        )

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

    @property
    def owner_authorized(self) -> bool:
        return False


@dataclass(frozen=True, init=False, repr=False)
class RecoveredArtifactSurfaceEvidence(_ClosedEvidence):
    dex_unit_count: int
    scoped_dex_unit_count: int
    packaged_dex_scope: PackagedDexScopeEvidence
    application_smali_class_file_count: int
    embedded_sdk_smali_class_file_count: int
    exclusive_classified_method_count: int
    exclusive_classified_class_count: int
    interface_parity: InterfaceParityEvidence
    interface_links: InterfaceLinkEvidence
    method_surfaces: tuple[ClassifiedMethodSurface, ...]
    android_api_surfaces: tuple[AndroidBluetoothReferenceSurface, ...]
    android_instruction_aggregates: tuple[AndroidBluetoothInstructionAggregate, ...]
    android_instruction_family_surfaces: tuple[
        AndroidBluetoothInstructionFamilySurface, ...
    ]
    android_instruction_category_surfaces: tuple[
        AndroidBluetoothInstructionCategorySurface, ...
    ]
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
        counting_basis="broad_source_reference_scan",
        exhaustive_instruction_inventory=False,
        semantic_specificity="underspecified",
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
        2,
        1,
    ),
)


def _instruction_aggregate(
    scope: OwnedCodeScope,
    denominator: int,
    methods: int,
    classes: int,
    overlap_methods: int,
    overlap_classes: int,
) -> AndroidBluetoothInstructionAggregate:
    return _closed_instance(
        AndroidBluetoothInstructionAggregate,
        scope=scope,
        owned_class_file_denominator=denominator,
        reference_method_count=methods,
        reference_class_count=classes,
        overlapping_reference_method_count=overlap_methods,
        overlapping_reference_class_count=overlap_classes,
        unclassified_reference_method_count=0,
        unclassified_reference_class_count=0,
        counting_basis=DirectInstructionCountingBasis.DIRECT_EXECUTABLE_REFERENCE,
        family_buckets_overlap=True,
        direct_reference_inventory_complete_within_owned_scope=True,
        semantic_behavior_established=False,
        dependency_or_transitive_review_complete=False,
        runtime_verified=False,
        hardware_eligible=False,
        hardware_verified=False,
        owner_authorized=False,
    )


_ANDROID_INSTRUCTION_AGGREGATES = (
    _instruction_aggregate(OwnedCodeScope.APPLICATION, 1_094, 128, 42, 16, 8),
    _instruction_aggregate(OwnedCodeScope.EMBEDDED_SDK, 138, 108, 21, 10, 5),
)


def _instruction_family_surface(
    scope: OwnedCodeScope,
    family: AndroidBluetoothInstructionFamily,
    methods: int,
    classes: int,
) -> AndroidBluetoothInstructionFamilySurface:
    return _closed_instance(
        AndroidBluetoothInstructionFamilySurface,
        scope=scope,
        family=family,
        method_count=methods,
        class_count=classes,
        counting_basis=DirectInstructionCountingBasis.DIRECT_EXECUTABLE_REFERENCE,
        overlap_allowed=True,
        semantic_behavior_established=False,
        dependency_or_transitive_review_complete=False,
        runtime_verified=False,
        hardware_eligible=False,
        hardware_verified=False,
        owner_authorized=False,
    )


_ANDROID_INSTRUCTION_FAMILY_SURFACES = (
    _instruction_family_surface(
        OwnedCodeScope.APPLICATION, AndroidBluetoothInstructionFamily.GATT, 43, 12
    ),
    _instruction_family_surface(
        OwnedCodeScope.APPLICATION, AndroidBluetoothInstructionFamily.LE_SCAN, 9, 3
    ),
    _instruction_family_surface(
        OwnedCodeScope.APPLICATION,
        AndroidBluetoothInstructionFamily.ADAPTER_DEVICE_MANAGER,
        79,
        36,
    ),
    _instruction_family_surface(
        OwnedCodeScope.APPLICATION,
        AndroidBluetoothInstructionFamily.CLASSIC_PROFILE_SOCKET,
        13,
        4,
    ),
    _instruction_family_surface(
        OwnedCodeScope.EMBEDDED_SDK,
        AndroidBluetoothInstructionFamily.GATT,
        70,
        14,
    ),
    _instruction_family_surface(
        OwnedCodeScope.EMBEDDED_SDK,
        AndroidBluetoothInstructionFamily.LE_SCAN,
        8,
        2,
    ),
    _instruction_family_surface(
        OwnedCodeScope.EMBEDDED_SDK,
        AndroidBluetoothInstructionFamily.ADAPTER_DEVICE_MANAGER,
        39,
        14,
    ),
    _instruction_family_surface(
        OwnedCodeScope.EMBEDDED_SDK,
        AndroidBluetoothInstructionFamily.CLASSIC_PROFILE_SOCKET,
        2,
        1,
    ),
)


_ANDROID_INSTRUCTION_CATEGORY_COUNTS = {
    AndroidBluetoothInstructionCategory.MTU: ((1, 1), (2, 2)),
    AndroidBluetoothInstructionCategory.CONNECTION_PRIORITY: ((0, 0), (1, 1)),
    AndroidBluetoothInstructionCategory.REMOTE_RSSI: ((0, 0), (2, 2)),
    AndroidBluetoothInstructionCategory.SERVICE_DISCOVERY: ((3, 2), (3, 3)),
    AndroidBluetoothInstructionCategory.RFCOMM_SOCKET: ((2, 1), (2, 1)),
    AndroidBluetoothInstructionCategory.CLASSIC_PROFILES: ((11, 3), (0, 0)),
    AndroidBluetoothInstructionCategory.BONDING: ((6, 6), (0, 0)),
    AndroidBluetoothInstructionCategory.CLASSIC_DISCOVERY: ((1, 1), (0, 0)),
    AndroidBluetoothInstructionCategory.LEGACY_LE_SCAN: ((9, 3), (1, 1)),
    AndroidBluetoothInstructionCategory.MODERN_LE_SCAN: ((0, 0), (7, 2)),
    AndroidBluetoothInstructionCategory.DESCRIPTOR_WRITE_SETUP: ((6, 3), (6, 4)),
    AndroidBluetoothInstructionCategory.NOTIFICATION_SETUP: ((2, 1), (3, 2)),
    AndroidBluetoothInstructionCategory.CHARACTERISTIC_READ: ((1, 1), (1, 1)),
    AndroidBluetoothInstructionCategory.CHARACTERISTIC_WRITE: ((6, 1), (9, 2)),
    AndroidBluetoothInstructionCategory.GATT_CONNECT_LIFECYCLE: ((5, 5), (11, 7)),
    AndroidBluetoothInstructionCategory.ADAPTER_POWER: ((2, 2), (2, 2)),
    AndroidBluetoothInstructionCategory.DESCRIPTOR_READ: ((0, 0), (0, 0)),
    AndroidBluetoothInstructionCategory.PHY: ((0, 0), (0, 0)),
    AndroidBluetoothInstructionCategory.LE_ADVERTISING: ((0, 0), (0, 0)),
    AndroidBluetoothInstructionCategory.L2CAP_CHANNEL: ((0, 0), (0, 0)),
    AndroidBluetoothInstructionCategory.GATT_SERVER: ((0, 0), (0, 0)),
    AndroidBluetoothInstructionCategory.HID_DEVICE: ((0, 0), (0, 0)),
}


def _instruction_category_surface(
    scope: OwnedCodeScope,
    category: AndroidBluetoothInstructionCategory,
    methods: int,
    classes: int,
) -> AndroidBluetoothInstructionCategorySurface:
    observed = methods > 0
    limitations: list[str] = []
    if not observed:
        limitations.append("direct_instruction_reference_absent_not_unsupported")
    if category is AndroidBluetoothInstructionCategory.RFCOMM_SOCKET:
        limitations.extend(
            (
                "construct_and_close_references_only",
                "no_connect_read_or_write_instruction_reference_observed",
            )
        )
    if (
        scope is OwnedCodeScope.EMBEDDED_SDK
        and category is AndroidBluetoothInstructionCategory.LEGACY_LE_SCAN
    ):
        limitations.append("no_start_or_stop_instruction_reference_observed")
    return _closed_instance(
        AndroidBluetoothInstructionCategorySurface,
        scope=scope,
        category=category,
        method_count=methods,
        class_count=classes,
        reference_state=(
            DirectInstructionReferenceState.OBSERVED
            if observed
            else DirectInstructionReferenceState.ABSENT_IN_OWNED_SCOPE
        ),
        counting_basis=DirectInstructionCountingBasis.DIRECT_EXECUTABLE_REFERENCE,
        overlap_allowed=True,
        semantic_behavior_established=False,
        dependency_or_transitive_review_complete=False,
        runtime_verified=False,
        hardware_eligible=False,
        hardware_verified=False,
        owner_authorized=False,
        unsupported_established=False,
        limitations=tuple(limitations),
    )


_ANDROID_INSTRUCTION_CATEGORY_SURFACES = tuple(
    _instruction_category_surface(
        scope,
        category,
        *_ANDROID_INSTRUCTION_CATEGORY_COUNTS[category][scope_index],
    )
    for scope_index, scope in enumerate(OwnedCodeScope)
    for category in AndroidBluetoothInstructionCategory
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
    all_packaged_jni_roots_reviewed=True,
    rooted_transitive_call_graph_reviewed=True,
    rooted_jni_entry_count=3,
    rooted_indirect_jni_call_count=30,
    named_undefined_import_count=43,
    needed_library_count=4,
    runtime_initializer_count=2,
    rooted_behavior_category=NativeRootedBehaviorCategory.IMAGE_WALLPAPER_PROCESSING,
    rooted_bluetooth_transport_edge_observed=False,
    rooted_dial_transfer_edge_observed=False,
    rooted_java_reflection_edge_observed=False,
    rooted_jni_registration_edge_observed=False,
    rooted_module_loading_edge_observed=False,
    sdk_ordinary_name_binding_state=NativeBindingReviewState.CONTRADICTED,
    sdk_any_possible_runtime_binding_state=NativeBindingReviewState.INCONCLUSIVE,
    native_instruction_review_completed=False,
    native_bluetooth_absence_established=False,
)


def _reflection(
    category: OwnedReflectionCategory,
    methods: int,
    invokes: int,
) -> OwnedReflectionSurface:
    return _closed_instance(
        OwnedReflectionSurface,
        category=category,
        method_count=methods,
        invoke_count=invokes,
        constant_target=True,
        dial_transfer_activation_observed=False,
    )


_REFLECTION_SURFACES = (
    _reflection(OwnedReflectionCategory.ANDROID_BOND, 3, 3),
    _reflection(OwnedReflectionCategory.ANDROID_TELEPHONY, 1, 2),
    _reflection(OwnedReflectionCategory.ANDROID_CLASSIC_PROFILE, 3, 3),
    _reflection(OwnedReflectionCategory.ANDROID_GATT_CACHE, 3, 3),
)

_DYNAMIC_ACTIVATION = _closed_instance(
    DynamicActivationSurfaceEvidence,
    review_state=ActivationReviewState.INCONCLUSIVE,
    direct_external_dial_construction_observed=False,
    application_reflective_method_file_count=2,
    embedded_sdk_reflective_method_file_count=3,
    owned_reflective_method_count=10,
    owned_reflective_invoke_count=11,
    owned_constant_reflective_target_count=9,
    owned_reflection_targets_resolved=True,
    owned_reflection_dial_activation_observed=False,
    reflection_surfaces=_REFLECTION_SURFACES,
    owned_common_dynamic_class_construction_file_count=0,
    standalone_dial_descriptor_reference_file_count=3,
    standalone_dial_external_descriptor_reference_count=0,
    standalone_dial_dotted_name_reference_count=0,
    standalone_dial_manifest_component_count=0,
    reviewed_relevant_resource_xml_count=11,
    resource_on_click_or_navigation_edge_count=0,
    app_owned_explicit_launch_site_count=6,
    standalone_dial_explicit_launch_count=0,
    binder_stub_class_count=19,
    binder_proxy_class_count=13,
    binder_transact_file_count=25,
    binder_on_transact_method_count=23,
    direct_owned_service_binding_call_observed=True,
    standalone_dial_service_binding_observed=False,
    relevant_binder_request_transaction_count=9,
    app_relevant_binder_outbound_invoke_count=0,
    relevant_callback_transaction_count=7,
    generic_ota_service_construction_observed=True,
    standalone_dial_binder_construction_observed=False,
    standalone_dial_static_activation_observed=False,
    resource_dial_tokens_present=True,
    resource_activation_resolved=True,
    native_dial_identifier_evidence=False,
    exhaustive_dynamic_activation_review=False,
    limitations=(
        "owned_reflection_review_is_bounded_to_the_five_observed_files",
        "binder_and_resource_review_is_bounded_to_dial_transfer_activation",
        "runtime_generated_or_encrypted_activation_not_excluded",
        "packaged_jni_roots_reviewed_but_whole_elf_behavior_not_exhaustively_disproved",
        "external_or_runtime_sdk_native_binding_not_excluded",
        "direct_reference_absence_does_not_establish_runtime_dormancy",
    ),
)

_PACKAGED_DEX_SCOPE = _closed_instance(
    PackagedDexScopeEvidence,
    inventory_unit_count=3,
    owned_application_or_sdk_scope_unit_count=1,
    no_owned_application_or_sdk_scope_unit_count=2,
    unclassified_unit_count=0,
    complete_semantic_source_review_completed=False,
    complete_smali_review_completed=False,
    complete_dex_instruction_review_completed=False,
    semantic_correctness_established=False,
)

_EVIDENCE = _closed_instance(
    RecoveredArtifactSurfaceEvidence,
    dex_unit_count=3,
    scoped_dex_unit_count=1,
    packaged_dex_scope=_PACKAGED_DEX_SCOPE,
    application_smali_class_file_count=1_094,
    embedded_sdk_smali_class_file_count=138,
    exclusive_classified_method_count=903,
    exclusive_classified_class_count=125,
    interface_parity=_INTERFACE_PARITY,
    interface_links=_INTERFACE_LINKS,
    method_surfaces=_METHOD_SURFACES,
    android_api_surfaces=_ANDROID_SURFACES,
    android_instruction_aggregates=_ANDROID_INSTRUCTION_AGGREGATES,
    android_instruction_family_surfaces=_ANDROID_INSTRUCTION_FAMILY_SURFACES,
    android_instruction_category_surfaces=_ANDROID_INSTRUCTION_CATEGORY_SURFACES,
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
    "AndroidBluetoothInstructionAggregate",
    "AndroidBluetoothInstructionCategory",
    "AndroidBluetoothInstructionCategorySurface",
    "AndroidBluetoothInstructionFamily",
    "AndroidBluetoothInstructionFamilySurface",
    "AndroidBluetoothReferenceSurface",
    "ClassifiedMethodSurface",
    "ClassifiedMethodSurfaceKind",
    "DynamicActivationSurfaceEvidence",
    "DynamicReceiverSurfaceEvidence",
    "DirectInstructionCountingBasis",
    "DirectInstructionReferenceState",
    "InterfaceLinkEvidence",
    "InterfaceParityEvidence",
    "ManifestSurfaceEvidence",
    "NativeBindingReviewState",
    "NativeRootedBehaviorCategory",
    "NativeSurfaceEvidence",
    "OwnedCodeScope",
    "OwnedReflectionCategory",
    "OwnedReflectionSurface",
    "PackagedDexScopeEvidence",
    "RecoveredArtifactSurfaceEvidence",
    "ResourceSurfaceEvidence",
    "recovered_artifact_surface_evidence",
]
