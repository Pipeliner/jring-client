import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_main_commands import (
    CommandRole,
    DayDataKind,
    DayDataRequest,
    EcgHistoryRequest,
    MainCommandOperation,
    NoArgumentMainCommand,
    NoArgumentMainCommandRequest,
    PhoneVolumeRequest,
    ScreenLightTimeRequest,
)


def _payload(request):
    frames = request.frames()
    assert len(frames) == 1
    return frames[0].synthetic_bytes_for_test()


def test_screen_light_time_is_a_strict_single_byte_setting():
    request = ScreenLightTimeRequest(17)

    assert _payload(request) == bytes((0x78, 0x0A, 17)) + bytes(17)
    assert request.role is CommandRole.SETTING
    for invalid in (-1, 256, True, 1.5):
        with pytest.raises((TypeError, ValueError)):
            ScreenLightTimeRequest(invalid)


@pytest.mark.parametrize(
    "kind,opcode",
    [
        (DayDataKind.SDK_TYPE_1, 0x10),
        (DayDataKind.SDK_TYPE_2, 0x16),
        (DayDataKind.SDK_TYPE_12, 0x39),
        (DayDataKind.SDK_TYPE_13, 0x40),
    ],
)
def test_day_data_selector_is_closed_and_day_offset_does_not_wrap(kind, opcode):
    request = DayDataRequest(kind=kind, day_offset=6)

    assert _payload(request) == bytes((opcode, 6)) + bytes(18)
    assert request.role is CommandRole.PARAMETERIZED_QUERY
    with pytest.raises(TypeError):
        DayDataRequest(kind=kind.value, day_offset=6)
    with pytest.raises(ValueError):
        DayDataRequest(kind=kind, day_offset=256)


@pytest.mark.parametrize(
    "query,prefix,role",
    [
        (NoArgumentMainCommand.DEVICE_CODE, bytes((0x1F,)), CommandRole.NO_ARGUMENT_QUERY),
        (NoArgumentMainCommand.DEVICE_DIAL, bytes((0x34,)), CommandRole.NO_ARGUMENT_QUERY),
        (NoArgumentMainCommand.DEVICE_DIAL_CUSTOM, bytes((0x42,)), CommandRole.NO_ARGUMENT_QUERY),
        (
            NoArgumentMainCommand.DEVICE_SYSTEM_STATE,
            bytes((0x54, 0x11)),
            CommandRole.NO_ARGUMENT_QUERY,
        ),
        (NoArgumentMainCommand.EQ_INFO, bytes((0x53, 0x01)), CommandRole.NO_ARGUMENT_QUERY),
        (
            NoArgumentMainCommand.MEDIA_FILE_STATE,
            bytes((0x54, 0x05)),
            CommandRole.NO_ARGUMENT_QUERY,
        ),
        (
            NoArgumentMainCommand.OFFLINE_SPEECH_STATE,
            bytes((0x78, 0x0C)),
            CommandRole.NO_ARGUMENT_QUERY,
        ),
        (NoArgumentMainCommand.SCAN_WIFI, bytes((0x54, 0x08)), CommandRole.NO_ARGUMENT_ACTION),
    ],
)
def test_no_argument_commands_are_real_closed_vendor_writes(query, prefix, role):
    request = NoArgumentMainCommandRequest(query)

    assert _payload(request) == prefix + bytes(20 - len(prefix))
    assert request.role is role
    with pytest.raises(TypeError):
        NoArgumentMainCommandRequest(query.prefix)


def test_wifi_scan_is_an_active_network_action_not_a_read_only_query():
    request = NoArgumentMainCommandRequest(NoArgumentMainCommand.SCAN_WIFI)

    assert request.operation is MainCommandOperation.SCAN_WIFI
    assert request.role is CommandRole.NO_ARGUMENT_ACTION
    assert request.privacy_class == "network_discovery"
    assert request.risk_class == "network_scan_action"


def test_ecg_history_adds_explicit_raw_timezone_offset_little_endian():
    request = EcgHistoryRequest(
        epoch_seconds=1_700_000_000,
        raw_utc_offset_seconds=19_800,
    )
    device_epoch = 1_700_019_800

    assert _payload(request) == bytes((0x2C,)) + device_epoch.to_bytes(4, "little") + bytes(15)
    assert request.device_epoch_seconds == device_epoch
    assert request.role is CommandRole.PARAMETERIZED_QUERY


def test_ecg_history_never_uses_ambient_timezone_or_java_integer_wrap():
    with pytest.raises(TypeError):
        EcgHistoryRequest(epoch_seconds=123)
    with pytest.raises(ValueError):
        EcgHistoryRequest(epoch_seconds=-1, raw_utc_offset_seconds=0)
    with pytest.raises(ValueError, match="offset"):
        EcgHistoryRequest(epoch_seconds=0, raw_utc_offset_seconds=86_401)
    with pytest.raises(ValueError, match="device epoch"):
        EcgHistoryRequest(epoch_seconds=0xFFFFFFFF, raw_utc_offset_seconds=1)


def test_phone_volume_is_a_strict_host_state_projection():
    request = PhoneVolumeRequest(
        current_music=7,
        maximum_music=15,
        current_call=3,
        maximum_call=5,
    )

    assert _payload(request) == bytes((0x49, 7, 15, 3, 5)) + bytes(15)
    assert request.role is CommandRole.HOST_STATE_PROJECTION
    with pytest.raises(ValueError, match="current music"):
        PhoneVolumeRequest(16, 15, 3, 5)
    with pytest.raises(ValueError, match="maximum call"):
        PhoneVolumeRequest(7, 15, 0, 0)
    with pytest.raises(TypeError):
        PhoneVolumeRequest(True, 15, 3, 5)


def test_all_requests_and_frames_are_redacted_static_and_hardware_ineligible():
    requests = (
        ScreenLightTimeRequest(17),
        DayDataRequest(DayDataKind.SDK_TYPE_13, 6),
        NoArgumentMainCommandRequest(NoArgumentMainCommand.DEVICE_CODE),
        EcgHistoryRequest(1_700_000_000, 19_800),
        PhoneVolumeRequest(7, 15, 3, 5),
    )

    for request in requests:
        assert request.maturity == "static_apk_only"
        assert request.hardware_verified is False
        assert request.hardware_eligible is False
        rendered = repr(request)
        assert "1700000000" not in rendered
        assert "19800" not in rendered
        assert "7, 15, 3, 5" not in rendered
        for frame in request.frames():
            assert frame.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
            assert frame.maturity == "static_apk_only"
            assert frame.hardware_verified is False
            assert frame.hardware_eligible is False
            assert frame.synthetic_bytes_for_test().hex() not in repr(frame)


def test_every_main_operation_has_closed_privacy_and_risk_metadata():
    requests = (
        ScreenLightTimeRequest(17),
        DayDataRequest(DayDataKind.SDK_TYPE_1, 0),
        *(NoArgumentMainCommandRequest(command) for command in NoArgumentMainCommand),
        EcgHistoryRequest(0, 0),
        PhoneVolumeRequest(0, 1, 0, 1),
    )

    assert {request.operation for request in requests} == set(MainCommandOperation)
    assert all(request.privacy_class for request in requests)
    assert all(request.risk_class for request in requests)
    assert all(request.hardware_eligible is False for request in requests)


def test_frame_construction_is_closed_and_no_request_exposes_transport_actions():
    from jring.vendor_main_commands import VendorMainCommandFrame

    with pytest.raises(TypeError):
        VendorMainCommandFrame()
    request = NoArgumentMainCommandRequest(NoArgumentMainCommand.SCAN_WIFI)
    assert not hasattr(request, "send")
    assert not hasattr(request, "write")
    assert not hasattr(request, "retry")
