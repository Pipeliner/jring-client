from dataclasses import FrozenInstanceError, fields
from enum import Enum
import inspect

import pytest

import jring.vendor_callback_surfaces as callback_module
from jring.vendor_callback_surfaces import (
    CallbackBehaviorCategory,
    CallbackPrivacyClass,
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
    assert CallbackPrivacyClass.BLUETOOTH_ADDRESS in (
        rows["onScanCallback"].privacy_classes
    )
    assert CallbackPrivacyClass.FILE_REFERENCE in (
        rows["onNotifyNewMediaInfo"].privacy_classes
    )
    assert all(row.payload_semantics_complete is False for row in rows.values())


def test_declared_without_dispatch_is_not_invented_as_runtime_behavior():
    rows = {row.name: row for row in recovered_callback_behavior_surfaces()}

    for name in ("onGetDeviceTime", "onSendWeather"):
        row = rows[name]
        assert row.category is CallbackBehaviorCategory.DECLARED_WITHOUT_DISPATCH
        assert row.direct_dispatch_observed is False
        assert row.python_callable is False

    assert all(
        row.direct_dispatch_observed is True
        for name, row in rows.items()
        if name not in {"onGetDeviceTime", "onSendWeather"}
    )


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
    assert all(
        all(type(item) is CallbackPrivacyClass for item in row.privacy_classes)
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
        for value in (row.category, *row.privacy_classes)
    )
