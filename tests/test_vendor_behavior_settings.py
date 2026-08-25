import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_behavior_settings import (
    AlarmBatchRequest,
    AlarmRequest,
    AlarmWeekdays,
    AntiLostRequest,
    AutoHeartScheduleRequest,
    BEHAVIOR_SETTINGS_SAFETY,
    CameraModeRequest,
    ClockTime,
    DeviceMode,
    DeviceModeRequest,
    GoalStepRequest,
    IdleReminderRequest,
    SleepScheduleRequest,
    VibrationRequest,
)


def _payloads(request):
    return tuple(frame.synthetic_bytes_for_test() for frame in request.frames())


def test_vibration_is_exact_and_rejects_apk_defaulting():
    assert _payloads(VibrationRequest(7)) == (
        bytes((0x04, 0x07)) + bytes(18),
    )
    for invalid in (-1, 11, True, 1.5):
        with pytest.raises((TypeError, ValueError)):
            VibrationRequest(invalid)


def test_boolean_behavior_requests_are_exact_booleans():
    assert _payloads(AntiLostRequest(True)) == (
        bytes((0x05, 0x01)) + bytes(18),
    )
    assert _payloads(AntiLostRequest(False)) == (
        bytes((0x05, 0x00)) + bytes(18),
    )
    assert _payloads(CameraModeRequest(True)) == (
        bytes((0x07, 0x01)) + bytes(18),
    )
    with pytest.raises(TypeError):
        AntiLostRequest(1)
    with pytest.raises(TypeError):
        CameraModeRequest("yes")


def test_idle_reminder_uses_seconds_little_endian_and_closed_factories():
    request = IdleReminderRequest.enabled(
        interval_minutes=10,
        start=ClockTime(9, 15),
        end=ClockTime(17, 45),
    )
    disabled = IdleReminderRequest.disabled(
        start=ClockTime(9, 15),
        end=ClockTime(17, 45),
    )

    assert _payloads(request) == (
        bytes((0x08, 0x58, 0x02, 0x00, 0x00, 9, 15, 17, 45)) + bytes(11),
    )
    assert _payloads(disabled)[0][1:5] == bytes(4)
    with pytest.raises(TypeError):
        IdleReminderRequest()
    with pytest.raises(ValueError):
        IdleReminderRequest.enabled(
            interval_minutes=0,
            start=ClockTime(9, 0),
            end=ClockTime(17, 0),
        )
    with pytest.raises(ValueError):
        IdleReminderRequest.enabled(
            interval_minutes=241,
            start=ClockTime(9, 0),
            end=ClockTime(17, 0),
        )


def test_sleep_schedule_has_two_exact_windows_and_no_implicit_defaults():
    request = SleepScheduleRequest(
        noon_start=ClockTime(13, 5),
        noon_end=ClockTime(14, 10),
        night_start=ClockTime(21, 30),
        night_end=ClockTime(8, 45),
    )

    assert _payloads(request) == (
        bytes((0x09, 13, 5, 14, 10, 21, 30, 8, 45)) + bytes(11),
    )
    with pytest.raises(TypeError):
        SleepScheduleRequest()


def test_clock_time_rejects_wraparound_and_boolean_ints():
    for hour, minute in ((-1, 0), (24, 0), (0, -1), (0, 60)):
        with pytest.raises(ValueError):
            ClockTime(hour, minute)
    with pytest.raises(TypeError):
        ClockTime(True, 0)


def test_alarm_batch_builds_base_and_exact_content_chunks_without_state():
    alarm = AlarmRequest(
        alarm_id=5,
        enabled=True,
        time=ClockTime(7, 30),
        weekdays=AlarmWeekdays(
            sunday=True,
            monday=True,
            tuesday=False,
            wednesday=True,
            thursday=False,
            friday=True,
            saturday=False,
        ),
        single=True,
        content="abcdefghijklmnopqrstu",
    )
    batch = AlarmBatchRequest((alarm,))
    base, first, last = _payloads(batch)

    assert base == bytes((0x0D, 5, 1, 7, 30, 1, 1, 0, 1, 0, 1, 0, 1)) + bytes(7)
    assert first == bytes((0x1C, 0x05)) + b"abcdefghijklmnopqr"
    assert last == bytes((0x1C, 0x95)) + b"stu" + bytes(15)
    assert batch.alarm_count == 1


def test_alarm_content_rejects_truncation_and_accepts_exact_utf8_boundary():
    with pytest.raises(ValueError, match="54 UTF-8 bytes"):
        AlarmRequest(
            alarm_id=1,
            enabled=False,
            time=ClockTime(0, 0),
            weekdays=AlarmWeekdays.none(),
            single=False,
            content="a" * 53 + "€",
        )

    alarm = AlarmRequest(
        alarm_id=1,
        enabled=False,
        time=ClockTime(0, 0),
        weekdays=AlarmWeekdays.none(),
        single=False,
        content="a" * 51 + "€",
    )
    frames = _payloads(AlarmBatchRequest((alarm,)))
    content = b"".join(frame[2:] for frame in frames[1:]).rstrip(b"\x00")

    assert content == b"a" * 51 + "€".encode()
    assert len(frames) == 4
    content.decode("utf-8")


def test_alarm_header_ids_and_batch_shape_are_strictly_bounded():
    def alarm(alarm_id):
        return AlarmRequest(
            alarm_id=alarm_id,
            enabled=True,
            time=ClockTime(12, 0),
            weekdays=AlarmWeekdays.every_day(),
            single=False,
            content="",
        )

    with pytest.raises(ValueError):
        alarm(-1)
    with pytest.raises(ValueError):
        alarm(16)
    with pytest.raises(ValueError, match="at least one"):
        AlarmBatchRequest(())
    with pytest.raises(ValueError, match="unique"):
        AlarmBatchRequest((alarm(1), alarm(1)))
    with pytest.raises(TypeError):
        AlarmBatchRequest([alarm(1)])


@pytest.mark.parametrize(
    "mode,magic",
    [
        (DeviceMode.NORMAL, bytes.fromhex("12 34 56 78 fe dc ba 98")),
        (DeviceMode.LOW_POWER, bytes.fromhex("fe dc ba 98 76 54 32 10")),
        (DeviceMode.RESTART, bytes.fromhex("12 34 56 78 9a bc de f0")),
        (DeviceMode.RESET, bytes.fromhex("12 34 12 34 12 34 12 34")),
    ],
)
def test_device_mode_is_a_closed_enum_and_never_emits_invalid_zero_magic(mode, magic):
    assert _payloads(DeviceModeRequest(mode)) == (
        bytes((0x0E,)) + magic + bytes(11),
    )
    with pytest.raises(TypeError):
        DeviceModeRequest(mode.value)


def test_auto_heart_omits_ignored_argument_and_rejects_modulo_wrap():
    request = AutoHeartScheduleRequest(
        enabled=True,
        start=ClockTime(0, 5),
        end=ClockTime(23, 59),
        interval_minutes=30,
    )

    assert _payloads(request) == (
        bytes((0x19, 0, 5, 23, 59, 1, 30, 1)) + bytes(12),
    )
    for invalid in (0, 255, -1):
        with pytest.raises(ValueError):
            AutoHeartScheduleRequest(
                enabled=True,
                start=ClockTime(0, 0),
                end=ClockTime(23, 59),
                interval_minutes=invalid,
            )


def test_goal_steps_use_strict_ui_proven_bounds_and_little_endian():
    assert _payloads(GoalStepRequest(20_000)) == (
        bytes((0x1A, 0x20, 0x4E, 0x00, 0x00)) + bytes(15),
    )
    for invalid in (999, 1_500, 21_000, True):
        with pytest.raises((TypeError, ValueError)):
            GoalStepRequest(invalid)


def test_every_public_plan_and_frame_is_static_only_redacted_and_hardware_ineligible():
    alarm = AlarmRequest(
        alarm_id=2,
        enabled=True,
        time=ClockTime(6, 45),
        weekdays=AlarmWeekdays.every_day(),
        single=False,
        content="private reminder",
    )
    requests = (
        VibrationRequest(3),
        AntiLostRequest(True),
        CameraModeRequest(True),
        IdleReminderRequest.enabled(
            interval_minutes=10,
            start=ClockTime(9, 0),
            end=ClockTime(17, 0),
        ),
        SleepScheduleRequest(
            noon_start=ClockTime(13, 0),
            noon_end=ClockTime(14, 0),
            night_start=ClockTime(21, 0),
            night_end=ClockTime(8, 0),
        ),
        AlarmBatchRequest((alarm,)),
        DeviceModeRequest(DeviceMode.RESTART),
        AutoHeartScheduleRequest(
            enabled=True,
            start=ClockTime(0, 0),
            end=ClockTime(23, 59),
            interval_minutes=30,
        ),
        GoalStepRequest(4_000),
    )

    for request in requests:
        assert request.hardware_eligible is False
        assert request.maturity == "static_apk_only"
        rendered = repr(request)
        assert "private reminder" not in rendered
        assert "06:45" not in rendered
        for frame in request.frames():
            assert frame.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
            assert frame.hardware_eligible is False
            assert frame.maturity == "static_apk_only"
            assert frame.synthetic_bytes_for_test().hex() not in repr(frame)


def test_safety_metadata_refuses_unsafe_apk_runtime_behaviors():
    assert BEHAVIOR_SETTINGS_SAFETY.hardware_eligible is False
    assert BEHAVIOR_SETTINGS_SAFETY.maturity == "static_apk_only"
    assert BEHAVIOR_SETTINGS_SAFETY.retains_alarm_list is False
    assert BEHAVIOR_SETTINGS_SAFETY.allows_partial_send is False
    assert BEHAVIOR_SETTINGS_SAFETY.truncates_alarm_content is False
    assert BEHAVIOR_SETTINGS_SAFETY.logs_raw_frames is False
    assert BEHAVIOR_SETTINGS_SAFETY.retries is False
    assert BEHAVIOR_SETTINGS_SAFETY.invalid_device_mode_fallback is False
