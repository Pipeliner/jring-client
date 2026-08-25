from datetime import date

import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_personal_settings import (
    PersonalSettingOperation,
    encode_bp_adjust,
    encode_device_dial_state,
    encode_device_wallpaper_state,
    encode_edit_device_dial_custom,
    encode_female_reminder,
    encode_reminder,
    encode_reminder_text,
)


def _frame(request):
    return request.synthetic_bytes_for_test()


def test_reminder_uses_the_exact_twenty_byte_schedule_layout():
    request = encode_reminder(
        interval_seconds=1_200,
        start_hour=9,
        start_minute=30,
        end_hour=17,
        end_minute=45,
        neutral_1=1,
        neutral_2=1,
    )

    assert _frame(request) == (
        bytes((0x31,))
        + (1_200).to_bytes(4, "little")
        + bytes((9, 30, 17, 45, 1, 1))
        + bytes(9)
    )


@pytest.mark.parametrize("interval", [1, 59, 61, 14_460, -1, 2**32, True])
def test_reminder_interval_accepts_only_the_observed_disabled_or_minute_range(interval):
    with pytest.raises((TypeError, ValueError)):
        encode_reminder(
            interval_seconds=interval,
            start_hour=9,
            start_minute=0,
            end_hour=17,
            end_minute=0,
            neutral_1=1,
            neutral_2=1,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_hour", 24),
        ("start_minute", 60),
        ("end_hour", -1),
        ("end_minute", True),
        ("neutral_1", 256),
        ("neutral_2", -1),
    ],
)
def test_reminder_fields_reject_wrap_and_out_of_range_values(field, value):
    arguments = dict(
        interval_seconds=0,
        start_hour=9,
        start_minute=0,
        end_hour=17,
        end_minute=0,
        neutral_1=1,
        neutral_2=1,
    )
    arguments[field] = value
    with pytest.raises((TypeError, ValueError)):
        encode_reminder(**arguments)


def test_reminder_does_not_invent_start_before_end_validation():
    request = encode_reminder(
        interval_seconds=0,
        start_hour=22,
        start_minute=30,
        end_hour=6,
        end_minute=15,
        neutral_1=2,
        neutral_2=2,
    )

    assert _frame(request)[5:11] == bytes((22, 30, 6, 15, 2, 2))


def test_reminder_text_is_deterministic_utf8_without_byte_truncation():
    request = encode_reminder_text(index=7, text="café")
    encoded = "café".encode("utf-8")

    assert _frame(request) == bytes((0x32, 7)) + encoded + bytes(18 - len(encoded))


@pytest.mark.parametrize("text", ["x" * 19, "a" * 17 + "é", "contains\x00nul"])
def test_reminder_text_rejects_oversize_split_or_padding_ambiguous_text(text):
    with pytest.raises(ValueError):
        encode_reminder_text(index=0, text=text)


@pytest.mark.parametrize("index", [-1, 256, True])
def test_reminder_text_index_is_a_neutral_u8(index):
    with pytest.raises((TypeError, ValueError)):
        encode_reminder_text(index=index, text="safe")


def test_bp_adjust_uses_two_little_endian_u16_values():
    request = encode_bp_adjust(systolic=120, diastolic=80)

    assert _frame(request) == bytes((0x33, 120, 0, 80, 0)) + bytes(15)


@pytest.mark.parametrize(
    "systolic,diastolic",
    [(59, 50), (250, 80), (120, 29), (100, 101), (True, 80), (120, 2**16)],
)
def test_bp_adjust_enforces_observed_picker_ranges_and_order(systolic, diastolic):
    with pytest.raises((TypeError, ValueError)):
        encode_bp_adjust(systolic=systolic, diastolic=diastolic)


def test_dial_wallpaper_and_custom_fields_stay_neutral_u8_values():
    dial = encode_device_dial_state(state=3)
    wallpaper = encode_device_wallpaper_state(state=4)
    custom = encode_edit_device_dial_custom(
        neutral_1=1,
        neutral_2=2,
        neutral_3=254,
        neutral_4=255,
    )

    assert _frame(dial) == bytes((0x35, 3)) + bytes(18)
    assert _frame(wallpaper) == bytes((0x36, 4)) + bytes(18)
    assert _frame(custom) == bytes((0x41, 1, 2, 254, 255)) + bytes(15)


@pytest.mark.parametrize("value", [-1, 256, True, 1.5])
def test_unproven_dial_and_custom_fields_reject_implicit_wrapping(value):
    with pytest.raises((TypeError, ValueError)):
        encode_device_dial_state(state=value)
    with pytest.raises((TypeError, ValueError)):
        encode_device_wallpaper_state(state=value)
    with pytest.raises((TypeError, ValueError)):
        encode_edit_device_dial_custom(
            neutral_1=value,
            neutral_2=0,
            neutral_3=0,
            neutral_4=0,
        )


def test_female_reminder_uses_exact_sensitive_calendar_layout():
    request = encode_female_reminder(
        enabled=True,
        year=2024,
        month=2,
        day=29,
        length=3,
        period=30,
        as_of=date(2026, 8, 25),
    )

    assert _frame(request) == (
        bytes((0x44,))
        + (2024).to_bytes(2, "little")
        + bytes((2, 29, 3, 30, 1))
        + bytes(12)
    )


@pytest.mark.parametrize(
    "values",
    [
        {"year": 1999},
        {"year": 2027},
        {"month": 13},
        {"day": 31, "month": 4},
        {"day": 29, "month": 2, "year": 2023},
        {"length": 2},
        {"length": 16},
        {"period": 16},
        {"period": 61},
        {"enabled": 1},
    ],
)
def test_female_reminder_enforces_observed_ui_and_calendar_bounds(values):
    arguments = dict(
        enabled=True,
        year=2024,
        month=2,
        day=29,
        length=3,
        period=30,
        as_of=date(2026, 8, 25),
    )
    arguments.update(values)
    with pytest.raises((TypeError, ValueError)):
        encode_female_reminder(**arguments)


def test_female_reminder_requires_an_explicit_validation_date():
    with pytest.raises(TypeError):
        encode_female_reminder(
            enabled=False,
            year=2024,
            month=1,
            day=1,
            length=3,
            period=30,
            as_of="2026-08-25",
        )


def test_requests_are_closed_offline_private_and_never_hardware_eligible():
    requests = (
        encode_reminder(
            interval_seconds=0,
            start_hour=9,
            start_minute=0,
            end_hour=17,
            end_minute=0,
            neutral_1=1,
            neutral_2=1,
        ),
        encode_reminder_text(index=1, text="private reminder"),
        encode_bp_adjust(systolic=120, diastolic=80),
        encode_device_dial_state(state=1),
        encode_device_wallpaper_state(state=2),
        encode_edit_device_dial_custom(
            neutral_1=1,
            neutral_2=2,
            neutral_3=3,
            neutral_4=4,
        ),
        encode_female_reminder(
            enabled=False,
            year=2024,
            month=1,
            day=1,
            length=3,
            period=30,
            as_of=date(2026, 8, 25),
        ),
    )

    assert tuple(request.operation for request in requests) == (
        PersonalSettingOperation.REMINDER,
        PersonalSettingOperation.REMINDER_TEXT,
        PersonalSettingOperation.BP_ADJUST,
        PersonalSettingOperation.DEVICE_DIAL_STATE,
        PersonalSettingOperation.DEVICE_WALLPAPER_STATE,
        PersonalSettingOperation.EDIT_DEVICE_DIAL_CUSTOM,
        PersonalSettingOperation.FEMALE_REMINDER,
    )
    for request in requests:
        assert request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
        assert request.maturity == "static_apk_only"
        assert request.hardware_eligible is False
        assert request.safety.transport_integration is False
        assert request.safety.apk_queue_clearing_reproduced is False
        assert request.safety.apk_write_retry_reproduced is False
        assert request.synthetic_bytes_for_test().hex() not in repr(request)

    assert "private reminder" not in repr(requests[1])
    assert "120" not in repr(requests[2])
    assert "2024" not in repr(requests[6])


def test_request_constructor_cannot_create_an_arbitrary_operation_or_frame():
    request_type = type(encode_device_dial_state(state=0))

    with pytest.raises(TypeError):
        request_type()
    with pytest.raises(TypeError):
        request_type(PersonalSettingOperation.DEVICE_DIAL_STATE, bytes(20))
