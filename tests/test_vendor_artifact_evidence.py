from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_artifact_evidence as artifact_module
from jring.vendor_artifact_evidence import (
    ActivationReviewState,
    AndroidBluetoothApiFamily,
    ClassifiedMethodSurfaceKind,
    NativeBindingReviewState,
    NativeRootedBehaviorCategory,
    OwnedCodeScope,
    OwnedReflectionCategory,
    recovered_artifact_surface_evidence,
)
from jring.vendor_coverage import (
    static_vendor_callback_coverage,
    static_vendor_operation_coverage,
)


def test_all_dex_interface_declarations_exactly_match_public_ledgers():
    evidence = recovered_artifact_surface_evidence()
    parity = evidence.interface_parity

    assert evidence.dex_unit_count == 3
    assert evidence.scoped_dex_unit_count == 1
    assert evidence.application_smali_class_file_count == 1_094
    assert evidence.embedded_sdk_smali_class_file_count == 138
    assert parity.request_declaration_count == 112
    assert parity.request_implementation_count == 112
    assert parity.public_request_row_count == 112
    assert parity.callback_declaration_count == 105
    assert parity.callback_implementation_count == 105
    assert parity.public_callback_row_count == 105
    assert parity.missing_public_row_count == 0
    assert parity.extra_public_row_count == 0
    assert parity.overloaded_declaration_count == 0
    assert len(static_vendor_operation_coverage()) == 112
    assert len(static_vendor_callback_coverage()) == 105


def test_all_packaged_dex_units_have_sanitized_scope_classification_only():
    evidence = recovered_artifact_surface_evidence()
    scope = evidence.packaged_dex_scope

    assert scope.inventory_unit_count == evidence.dex_unit_count == 3
    assert (
        scope.owned_application_or_sdk_scope_unit_count
        == evidence.scoped_dex_unit_count
        == 1
    )
    assert scope.no_owned_application_or_sdk_scope_unit_count == 2
    assert scope.unclassified_unit_count == 0
    assert scope.classified_unit_count == scope.inventory_unit_count
    assert scope.inventory_scope_classification_complete is True
    assert scope.complete_semantic_source_review_completed is False
    assert scope.complete_smali_review_completed is False
    assert scope.complete_dex_instruction_review_completed is False
    assert scope.semantic_correctness_established is False
    assert scope.runnable is False
    assert scope.python_callable is False
    assert scope.hardware_eligible is False
    assert scope.hardware_verified is False
    assert scope.owner_authorized is False


def test_call_and_dispatch_links_are_evidence_not_new_interface_rows():
    links = recovered_artifact_surface_evidence().interface_links

    assert links.application_request_invoke_count == 152
    assert links.application_request_unique_edge_count == 130
    assert links.application_request_caller_method_count == 86
    assert links.application_request_caller_class_count == 48
    assert links.application_distinct_request_target_count == 51
    assert links.sdk_callback_invoke_count == 181
    assert links.sdk_callback_unique_edge_count == 126
    assert links.sdk_callback_caller_method_count == 34
    assert links.sdk_callback_caller_class_count == 17
    assert links.sdk_distinct_callback_target_count == 103
    assert links.unledgered_target_count == 0
    assert links.declared_callback_without_direct_dispatch_count == 2


def test_exclusive_owned_method_classification_reconciles_without_inflating_ledgers():
    evidence = recovered_artifact_surface_evidence()
    surfaces = {item.kind: item for item in evidence.method_surfaces}

    assert surfaces[ClassifiedMethodSurfaceKind.REQUEST_INTERFACE].method_count == 112
    assert surfaces[ClassifiedMethodSurfaceKind.CALLBACK_INTERFACE].method_count == 105
    assert surfaces[ClassifiedMethodSurfaceKind.SDK_REQUEST_IMPLEMENTATION].method_count == 112
    assert surfaces[ClassifiedMethodSurfaceKind.APP_CALLBACK_IMPLEMENTATION].method_count == 105
    assert surfaces[ClassifiedMethodSurfaceKind.INTERNAL_OTA].method_count == 188
    assert sum(item.method_count for item in surfaces.values()) == 903
    assert evidence.exclusive_classified_method_count == 903
    assert evidence.exclusive_classified_class_count == 125
    assert evidence.interface_entries is False


def test_android_bluetooth_references_stay_platform_plumbing_categories():
    records = {
        (item.scope, item.family): item
        for item in recovered_artifact_surface_evidence().android_api_surfaces
    }

    assert records[(OwnedCodeScope.APPLICATION, AndroidBluetoothApiFamily.GATT)].method_count == 48
    assert records[
        (OwnedCodeScope.APPLICATION, AndroidBluetoothApiFamily.LE_SCAN)
    ].method_count == 12
    assert records[
        (OwnedCodeScope.APPLICATION, AndroidBluetoothApiFamily.ADAPTER_DEVICE_BOND)
    ].method_count == 61
    assert records[
        (OwnedCodeScope.APPLICATION, AndroidBluetoothApiFamily.CLASSIC_PROFILE_SOCKET)
    ].method_count == 15
    assert records[
        (OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.GATT)
    ].method_count == 37
    assert records[
        (OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.LE_SCAN)
    ].method_count == 9
    assert records[
        (OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.ADAPTER_DEVICE_BOND)
    ].method_count == 9
    assert records[
        (OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.CLASSIC_PROFILE_SOCKET)
    ].method_count == 2
    assert records[
        (OwnedCodeScope.EMBEDDED_SDK, AndroidBluetoothApiFamily.CLASSIC_PROFILE_SOCKET)
    ].class_count == 1


def test_manifest_surface_separates_declared_features_from_dynamic_receivers():
    manifest = recovered_artifact_surface_evidence().manifest_surface

    assert manifest.xapk_apk_count == 20
    assert manifest.locale_split_count == 17
    assert manifest.density_split_count == 1
    assert manifest.abi_split_count == 1
    assert manifest.permission_count == 35
    assert manifest.feature_count == 9
    assert manifest.legacy_bluetooth_permission_count == 2
    assert manifest.modern_scan_permission_declared is True
    assert manifest.modern_connect_permission_declared is True
    assert manifest.advertise_permission_declared is False
    assert manifest.ble_hardware_required is True
    assert manifest.app_owned_ble_foreground_service_count == 1
    assert manifest.all_app_owned_services_non_exported is True
    assert manifest.app_owned_static_receiver_count == 0
    assert manifest.static_android_bluetooth_action_count == 0
    assert manifest.app_owned_exported_activity_count == 2
    assert manifest.exported_bluetooth_controller_activity_count == 1
    assert manifest.boot_receiver_declared is False
    assert manifest.companion_device_service_declared is False


def test_dynamic_receiver_mismatches_are_blockers_not_capabilities():
    dynamic = recovered_artifact_surface_evidence().dynamic_receiver_surface

    assert dynamic.registration_file_count == 25
    assert dynamic.bluetooth_filter_file_count == 17
    assert dynamic.process_local_filter_file_count == 16
    assert dynamic.system_context_filter_file_count == 1
    assert dynamic.primary_unique_android_bluetooth_action_count == 7
    assert dynamic.primary_handled_action_count == 4
    assert dynamic.primary_unhandled_action_count == 3
    assert dynamic.system_action_bridge_observed is False
    assert dynamic.system_receiver_sender_permission_required is False
    assert dynamic.system_receiver_matching_unregister_observed is False
    assert dynamic.runtime_behavior_verified is False


def test_resource_keyword_counts_never_become_capability_counts():
    resources = recovered_artifact_surface_evidence().resource_surface

    assert resources.decoded_base_xml_file_count == 1_107
    assert resources.keyword_matching_xml_file_count == 24
    assert resources.keyword_matching_named_entry_count == 733
    assert resources.named_entries_are_capabilities is False
    assert resources.credential_bearing_sdk_configuration_asset_count == 1
    assert resources.credential_material_exposed is False
    assert resources.resource_payload_review_completed is False


def test_native_false_positive_is_corrected_without_claiming_native_absence():
    native = recovered_artifact_surface_evidence().native_surface

    assert native.packaged_library_count == 1
    assert native.packaged_abi_count == 1
    assert native.native_declaration_count == 10
    assert native.application_native_declaration_count == 3
    assert native.embedded_sdk_native_declaration_count == 6
    assert native.dependency_native_declaration_count == 1
    assert native.jni_export_count == 3
    assert native.matched_jni_export_count == 3
    assert native.unmatched_jni_export_count == 0
    assert native.unresolved_native_declaration_count == 7
    assert native.unresolved_sdk_native_declaration_count == 6
    assert native.bluetooth_gatt_hid_or_dial_symbol_count == 0
    assert native.all_packaged_jni_roots_reviewed is True
    assert native.rooted_transitive_call_graph_reviewed is True
    assert native.rooted_jni_entry_count == 3
    assert native.rooted_indirect_jni_call_count == 30
    assert native.named_undefined_import_count == 43
    assert native.needed_library_count == 4
    assert native.runtime_initializer_count == 2
    assert (
        native.rooted_behavior_category
        is NativeRootedBehaviorCategory.IMAGE_WALLPAPER_PROCESSING
    )
    assert native.rooted_bluetooth_transport_edge_observed is False
    assert native.rooted_dial_transfer_edge_observed is False
    assert native.rooted_java_reflection_edge_observed is False
    assert native.rooted_jni_registration_edge_observed is False
    assert native.rooted_module_loading_edge_observed is False
    assert (
        native.sdk_ordinary_name_binding_state
        is NativeBindingReviewState.CONTRADICTED
    )
    assert (
        native.sdk_any_possible_runtime_binding_state
        is NativeBindingReviewState.INCONCLUSIVE
    )
    assert native.native_instruction_review_completed is False
    assert native.native_bluetooth_absence_established is False


def test_dynamic_dial_activation_remains_inconclusive_across_all_surfaces():
    dynamic = recovered_artifact_surface_evidence().dynamic_activation_surface

    assert dynamic.review_state is ActivationReviewState.INCONCLUSIVE
    assert dynamic.direct_external_dial_construction_observed is False
    assert dynamic.application_reflective_method_file_count == 2
    assert dynamic.embedded_sdk_reflective_method_file_count == 3
    assert dynamic.owned_reflective_method_count == 10
    assert dynamic.owned_reflective_invoke_count == 11
    assert dynamic.owned_constant_reflective_target_count == 9
    assert dynamic.owned_reflection_targets_resolved is True
    assert dynamic.owned_reflection_dial_activation_observed is False
    assert dynamic.owned_common_dynamic_class_construction_file_count == 0
    assert dynamic.standalone_dial_descriptor_reference_file_count == 3
    assert dynamic.standalone_dial_external_descriptor_reference_count == 0
    assert dynamic.standalone_dial_dotted_name_reference_count == 0
    assert dynamic.standalone_dial_manifest_component_count == 0
    assert dynamic.reviewed_relevant_resource_xml_count == 11
    assert dynamic.resource_on_click_or_navigation_edge_count == 0
    assert dynamic.app_owned_explicit_launch_site_count == 6
    assert dynamic.standalone_dial_explicit_launch_count == 0
    assert dynamic.binder_stub_class_count == 19
    assert dynamic.binder_proxy_class_count == 13
    assert dynamic.binder_transact_file_count == 25
    assert dynamic.binder_on_transact_method_count == 23
    assert dynamic.direct_owned_service_binding_call_observed is True
    assert dynamic.standalone_dial_service_binding_observed is False
    assert dynamic.relevant_binder_request_transaction_count == 9
    assert dynamic.app_relevant_binder_outbound_invoke_count == 0
    assert dynamic.relevant_callback_transaction_count == 7
    assert dynamic.generic_ota_service_construction_observed is True
    assert dynamic.standalone_dial_binder_construction_observed is False
    assert dynamic.standalone_dial_static_activation_observed is False
    assert dynamic.resource_dial_tokens_present is True
    assert dynamic.resource_activation_resolved is True
    assert dynamic.native_dial_identifier_evidence is False
    assert dynamic.exhaustive_dynamic_activation_review is False

    reflection = {item.category: item for item in dynamic.reflection_surfaces}
    assert reflection[OwnedReflectionCategory.ANDROID_BOND].invoke_count == 3
    assert reflection[OwnedReflectionCategory.ANDROID_TELEPHONY].invoke_count == 2
    assert reflection[OwnedReflectionCategory.ANDROID_CLASSIC_PROFILE].invoke_count == 3
    assert reflection[OwnedReflectionCategory.ANDROID_GATT_CACHE].invoke_count == 3
    assert sum(item.invoke_count for item in reflection.values()) == 11
    assert all(item.dial_transfer_activation_observed is False for item in reflection.values())


def test_artifact_evidence_is_closed_sanitized_and_without_runtime_authority():
    evidence = recovered_artifact_surface_evidence()

    assert evidence is recovered_artifact_surface_evidence()
    assert evidence.source_recovery_completeness == "not_established"
    assert evidence.complete_artifact_coverage is False
    assert evidence.reflection_or_dynamic_activation_exhaustively_disproved is False
    assert evidence.semantic_correctness_established is False
    assert evidence.runnable is False
    assert evidence.python_callable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    with pytest.raises(FrozenInstanceError):
        evidence.method_surfaces = ()

    for model in (
        type(evidence), type(evidence.packaged_dex_scope),
        type(evidence.interface_parity), type(evidence.interface_links),
        type(evidence.method_surfaces[0]), type(evidence.android_api_surfaces[0]),
        type(evidence.manifest_surface), type(evidence.dynamic_receiver_surface),
        type(evidence.resource_surface), type(evidence.native_surface),
        type(evidence.dynamic_activation_surface),
        type(evidence.dynamic_activation_surface.reflection_surfaces[0]),
    ):
        with pytest.raises(TypeError):
            model()

    forbidden = {
        "path", "source", "class_name", "method_name", "descriptor", "prototype",
        "digest", "fingerprint", "offset", "resource_name", "action_name",
        "unit_name", "unit_ordinal", "locator",
    }
    for model in (
        type(evidence), type(evidence.packaged_dex_scope),
        type(evidence.interface_parity), type(evidence.interface_links),
        type(evidence.method_surfaces[0]), type(evidence.android_api_surfaces[0]),
        type(evidence.manifest_surface), type(evidence.dynamic_receiver_surface),
        type(evidence.resource_surface), type(evidence.native_surface),
        type(evidence.dynamic_activation_surface),
        type(evidence.dynamic_activation_surface.reflection_surfaces[0]),
    ):
        assert forbidden.isdisjoint(item.name for item in fields(model))

    serialized = json.dumps(asdict(evidence), sort_keys=True).lower()
    for private_token in (
        "sha256", "sha-256", "classes.dex", "classes2.dex", "classes3.dex",
        ".smali", "androidmanifest.xml", "libnative-lib", "com.jaga", "com.sxr",
    ):
        assert private_token not in serialized
    source = inspect.getsource(artifact_module).lower()
    assert "import pathlib" not in source
    assert "import subprocess" not in source
    assert "open(" not in source
