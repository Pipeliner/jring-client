from dataclasses import FrozenInstanceError, fields
from enum import Enum
import inspect

import pytest

import jring.vendor_callback_surfaces as callback_module
from jring.vendor_callback_surfaces import (
    CallbackBehaviorCategory,
    CallbackDispatchOrigin,
    CallbackPrivacyClass,
    CallbackResultSemantics,
    CallbackSideEffectClass,
    recovered_callback_behavior_surfaces,
)


def test_all_sixteen_non_opcode_callbacks_have_one_closed_behavior_row():
    rows = recovered_callback_behavior_surfaces()
    names = [row.name for row in rows]

    assert len(rows) == 16
    assert len(set(names)) == 16
    assert set(names) == {
        "onAuthDeviceResult", "onAuthSdkResult", "onCharacteristicChanged",
        "onCharacteristicWrite", "onConnectStateChanged", "onDeviceConnectedWifi",
        "onGetDeviceRssi", "onGetDeviceTime", "onGetOtaInfo", "onGetOtaUpdate",
        "onNotifyDialJsonContent", "onNotifyFtpStateInfo", "onNotifyNewMediaInfo",
        "onOpenRawDataNotificationState", "onScanCallback", "onSendWeather",
    }


def test_surface_categories_preserve_transport_and_privacy_boundaries():
    rows = {row.name: row for row in recovered_callback_behavior_surfaces()}

    assert rows["onCharacteristicChanged"].category is (
        CallbackBehaviorCategory.ANDROID_GATT_FORWARDER
    )
    assert rows["onCharacteristicChanged"].privacy_classes == (
        CallbackPrivacyClass.GATT_IDENTIFIER,
        CallbackPrivacyClass.RAW_PAYLOAD,
    )
    assert rows["onCharacteristicWrite"].privacy_classes == (
        CallbackPrivacyClass.GATT_IDENTIFIER,
        CallbackPrivacyClass.RAW_PAYLOAD,
    )
    assert CallbackPrivacyClass.NETWORK_CREDENTIAL in (
        rows["onDeviceConnectedWifi"].privacy_classes
    )
    assert CallbackPrivacyClass.FILE_REFERENCE in (
        rows["onDeviceConnectedWifi"].privacy_classes
    )
    assert CallbackPrivacyClass.BLUETOOTH_ADDRESS in (
        rows["onScanCallback"].privacy_classes
    )
    assert CallbackPrivacyClass.DERIVED_ADVERTISEMENT_IDENTIFIERS in (
        rows["onScanCallback"].privacy_classes
    )
    assert "advertisement_data" not in {
        item.value for item in rows["onScanCallback"].privacy_classes
    }
    assert CallbackPrivacyClass.FILE_REFERENCE in (
        rows["onNotifyNewMediaInfo"].privacy_classes
    )
    assert all(row.payload_semantics_complete is False for row in rows.values())


def test_declared_without_dispatch_is_not_invented_as_runtime_behavior():
    rows = {row.name: row for row in recovered_callback_behavior_surfaces()}

    for name in ("onGetDeviceTime", "onSendWeather"):
        row = rows[name]
        assert row.category is CallbackBehaviorCategory.DECLARED_WITHOUT_DISPATCH
        assert row.direct_invoke_observed is False
        assert row.dispatch_origins == (CallbackDispatchOrigin.DECLARATION_ONLY,)
        assert row.result_semantics is CallbackResultSemantics.NO_RESULT_OBSERVED
        assert row.python_callable is False

    assert all(
        row.direct_invoke_observed is True
        for name, row in rows.items()
        if name not in {"onGetDeviceTime", "onSendWeather"}
    )


def test_result_meaning_silence_and_side_effects_are_operation_specific():
    rows = {row.name: row for row in recovered_callback_behavior_surfaces()}

    changed = rows["onCharacteristicChanged"]
    assert changed.dispatch_origins == (CallbackDispatchOrigin.ANDROID_GATT_CALLBACK,)
    assert changed.result_semantics is (
        CallbackResultSemantics.GATT_IDENTIFIER_AND_CURRENT_VALUE_COPY
    )
    assert "parse_before_forward_can_suppress" in changed.silence_reasons
    assert CallbackSideEffectClass.ROUTE_BY_GATT_IDENTIFIER in (
        changed.side_effect_classes
    )

    written = rows["onCharacteristicWrite"]
    assert written.result_semantics is (
        CallbackResultSemantics.GATT_STATUS_AND_CURRENT_VALUE
    )
    assert CallbackSideEffectClass.UNCONDITIONAL_WRITE_COMPLETION_LATCH in (
        written.side_effect_classes
    )

    rssi = rows["onGetDeviceRssi"]
    assert rssi.result_semantics is (
        CallbackResultSemantics.RSSI_WITH_ANDROID_STATUS_DISCARDED
    )

    ota_info = rows["onGetOtaInfo"]
    ota_update = rows["onGetOtaUpdate"]
    assert ota_info.category is CallbackBehaviorCategory.OTA_INFO
    assert ota_update.category is CallbackBehaviorCategory.OTA_UPDATE
    assert ota_update.result_semantics is (
        CallbackResultSemantics.OTA_PHASE_AND_DETAIL_NOT_PERCENTAGE
    )
    assert CallbackSideEffectClass.FILE_WRITE_BEFORE_CHECKSUM in (
        ota_update.side_effect_classes
    )

    raw = rows["onOpenRawDataNotificationState"]
    assert raw.result_semantics is (
        CallbackResultSemantics.RAW_ENABLE_SUBMISSION_ACCEPTANCE
    )
    assert {
        "disable_request",
        "raw_channel_missing",
        "queue_submission_rejected",
    } <= set(raw.silence_reasons)
    assert CallbackSideEffectClass.DISCONNECT_SCHEDULE in raw.side_effect_classes

    scan = rows["onScanCallback"]
    assert scan.result_semantics is (
        CallbackResultSemantics.SCAN_SELECTION_WITH_DERIVED_IDENTIFIERS
    )
    assert CallbackSideEffectClass.AUTO_CONNECT in scan.side_effect_classes


def test_callback_surface_evidence_is_closed_static_and_non_runnable():
    rows = recovered_callback_behavior_surfaces()
    model = type(rows[0])

    with pytest.raises(TypeError):
        model()
    with pytest.raises(FrozenInstanceError):
        rows[0].name = "changed"
    assert all(row.maturity == "static_apk_only" for row in rows)
    assert all(row.runnable is False for row in rows)
    assert all(row.python_callable is False for row in rows)
    assert all(row.hardware_eligible is False for row in rows)
    assert all(row.hardware_verified is False for row in rows)
    assert all(type(row.category) is CallbackBehaviorCategory for row in rows)
    assert all(type(row.result_semantics) is CallbackResultSemantics for row in rows)
    assert all(
        all(type(item) is CallbackDispatchOrigin for item in row.dispatch_origins)
        for row in rows
    )
    assert all(
        all(type(item) is CallbackPrivacyClass for item in row.privacy_classes)
        for row in rows
    )
    assert all(
        all(type(item) is CallbackSideEffectClass for item in row.side_effect_classes)
        for row in rows
    )

    forbidden = {
        "source", "path", "descriptor", "prototype", "fingerprint",
        "instruction_offset", "payload", "uuid", "address", "credential",
    }
    assert forbidden.isdisjoint(field.name for field in fields(model))
    source = inspect.getsource(callback_module).lower()
    assert "import pathlib" not in source
    assert "import subprocess" not in source
    assert "open(" not in source
    assert not any(
        isinstance(value, Enum) and value.name == "LIVE"
        for row in rows
        for value in (
            row.category,
            row.result_semantics,
            *row.dispatch_origins,
            *row.privacy_classes,
            *row.side_effect_classes,
        )
    )
