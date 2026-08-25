from jring.vendor_platform_surface import (
    PlatformBehaviorClass,
    PlatformPrivacyClass,
    PlatformSideEffectClass,
    PlatformSurfaceOperation,
    static_platform_surface,
)


def test_ten_non_bluetooth_requests_are_closed_and_accounted_once():
    surface = static_platform_surface()

    assert len(surface) == 10
    assert {item.operation for item in surface} == set(PlatformSurfaceOperation)
    assert all(item.touches_bluetooth is False for item in surface)
    assert all(item.python_callable is False for item in surface)
    assert all(item.hardware_eligible is False for item in surface)
    assert all(item.hardware_verified is False for item in surface)
    assert all(item.evidence_scope == "android_platform_behavior_inventory" for item in surface)
    assert all(item.known_limitations for item in surface)


def test_four_declared_stubs_are_not_presented_as_features():
    by_operation = {item.operation: item for item in static_platform_surface()}

    for operation in (
        PlatformSurfaceOperation.CONNECT_FTP,
        PlatformSurfaceOperation.GET_DEVICE_FILE_STATE,
        PlatformSurfaceOperation.GET_WIFI_STATE,
        PlatformSurfaceOperation.SET_DEVICE_FILE_STATE,
    ):
        item = by_operation[operation]
        assert item.behavior_class is PlatformBehaviorClass.CONSTANT_NO_OP_STUB
        assert item.side_effect_class is PlatformSideEffectClass.NONE


def test_platform_and_network_work_remains_distinct_from_ring_bluetooth():
    by_operation = {item.operation: item for item in static_platform_surface()}

    assert by_operation[PlatformSurfaceOperation.GET_DIAL_SERVER_INFO].behavior_class == (
        PlatformBehaviorClass.CACHE_THEN_VENDOR_NETWORK
    )
    assert by_operation[PlatformSurfaceOperation.START_FTP_DOWNLOAD].side_effect_class == (
        PlatformSideEffectClass.PHONE_NETWORK_AND_FILESYSTEM
    )
    assert by_operation[PlatformSurfaceOperation.SAVE_TO_SYSTEM_ALBUM].privacy_class == (
        PlatformPrivacyClass.LOCAL_FILE_PATH
    )
    assert by_operation[PlatformSurfaceOperation.TRANSLATE_BMP_TO_BIN].behavior_class == (
        PlatformBehaviorClass.LOCAL_BITMAP_CONVERSION
    )


def test_callback_registration_is_local_state_with_authorization_side_effects():
    by_operation = {item.operation: item for item in static_platform_surface()}

    for operation in (
        PlatformSurfaceOperation.REGISTER_CALLBACK,
        PlatformSurfaceOperation.REGISTER_CALLBACK_WITH_CREDENTIALS,
    ):
        item = by_operation[operation]
        assert item.behavior_class is (
            PlatformBehaviorClass.CALLBACK_REGISTRATION_AND_SDK_AUTHORIZATION
        )
        assert item.privacy_class is PlatformPrivacyClass.APP_OR_SDK_CREDENTIALS
        assert item.side_effect_class is (
            PlatformSideEffectClass.ANDROID_STATE_AND_VENDOR_NETWORK
        )
        assert "Bluetooth" not in repr(item)
