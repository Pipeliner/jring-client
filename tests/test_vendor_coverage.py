from collections import Counter

from jring.vendor_coverage import static_vendor_operation_coverage


def test_static_vendor_operation_coverage_accounts_for_all_112_requests_once():
    coverage = static_vendor_operation_coverage()
    names = [entry.name for entry in coverage]

    assert len(names) == 112
    assert len(set(names)) == 112
    assert Counter(entry.route for entry in coverage) == {
        "main_command": 79,
        "main_then_cloud": 1,
        "raw_command": 6,
        "raw_notification_control": 1,
        "local_ble_or_dynamic_gatt": 14,
        "cloud_or_cache": 3,
        "local_phone_network": 1,
        "local_filesystem_or_conversion": 2,
        "dfu": 1,
        "no_op_stub": 4,
    }


def test_only_seven_operations_have_offline_request_and_response_codecs():
    coverage = static_vendor_operation_coverage()
    implemented = {
        entry.name
        for entry in coverage
        if entry.python_state == "offline_request_and_response_codec"
    }

    assert implemented == {
        "getAdvSensorOfflineData",
        "getBandFunction",
        "getCurSportData",
        "getDeviceBatery",
        "getDeviceInfo",
        "getMultipleSportData",
        "getOxygenOfflineData",
    }


def test_static_coverage_never_promotes_an_operation_to_hardware():
    coverage = static_vendor_operation_coverage()

    assert all(entry.maturity == "static_apk_only" for entry in coverage)
    assert all(entry.hardware_eligible is False for entry in coverage)
    assert all(entry.python_state != "live_vendor" for entry in coverage)


def test_sensitive_and_destructive_surfaces_remain_visibly_unimplemented():
    by_name = {entry.name: entry for entry in static_vendor_operation_coverage()}

    for name in (
        "setContactInfo",
        "setWifiHotSpotInfo",
        "setChatgptContent",
        "setDeviceMode",
        "startFactoryTestMode",
        "startFileOta",
        "writeCharacteristic",
    ):
        assert by_name[name].python_state == "not_reproduced"
        assert by_name[name].hardware_eligible is False
