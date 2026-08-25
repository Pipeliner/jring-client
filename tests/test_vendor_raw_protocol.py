import pytest

from jring.protocol import ProtocolError
from jring.uuids import VENDOR_CHARACTERISTIC_33F5, VENDOR_CHARACTERISTIC_33F6
from jring.vendor_raw_protocol import (
    StaticRawCommand,
    encode_raw_ai_audio_state,
    encode_raw_ai_command_type,
    encode_raw_ai_extra_action,
    encode_raw_ai_server_notification,
    encode_raw_ai_state,
    encode_raw_ai_state_query,
    parse_raw_vendor_notification,
)


@pytest.mark.parametrize(
    "raw_request,command_type,argument",
    [
        (encode_raw_ai_server_notification(True), 0x0001, 0x02),
        (encode_raw_ai_server_notification(False), 0x0001, 0x04),
        (encode_raw_ai_extra_action(0xAB), 0x0004, 0xAB),
        (encode_raw_ai_state(True), 0x0005, 1),
        (encode_raw_ai_state(False), 0x0005, 0),
        (encode_raw_ai_state_query(), 0x0007, 0),
        (encode_raw_ai_audio_state(True), 0x0008, 1),
        (encode_raw_ai_command_type(0xCD), 0x000A, 0xCD),
    ],
)
def test_static_raw_requests_share_the_exact_twenty_byte_envelope(
    raw_request, command_type, argument
):
    expected = (
        command_type.to_bytes(2, "little")
        + bytes((1, 0, 1, 0, 1, 0, argument))
        + bytes(11)
    )

    assert raw_request.synthetic_bytes_for_test() == expected
    assert raw_request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F5
    assert raw_request.maturity == "static_apk_only"
    assert raw_request.hardware_eligible is False


@pytest.mark.parametrize("value", [-1, 256, True, 1.5])
def test_raw_integer_arguments_must_fit_one_unsigned_byte(value):
    with pytest.raises((TypeError, ValueError)):
        encode_raw_ai_extra_action(value)
    with pytest.raises((TypeError, ValueError)):
        encode_raw_ai_command_type(value)


def test_raw_request_repr_does_not_expose_frame_bytes():
    request = encode_raw_ai_extra_action(0xAB)

    assert isinstance(request, StaticRawCommand)
    assert "010001000100ab" not in repr(request).lower()


@pytest.mark.parametrize(
    "raw_type,kind,value",
    [
        (0x0001, "ai_action", 7),
        (0x0009, "voice_command_confirmation", 8),
        (0x000A, "ai_command_type", 9),
    ],
)
def test_raw_single_value_notifications(raw_type, kind, value):
    result = parse_raw_vendor_notification(
        raw_type.to_bytes(2, "little") + bytes(6) + bytes((value, 0xEE))
    )

    assert result.kind == kind
    assert result.value == value
    assert result.trailing_bytes_ignored == 1
    assert result.endpoint_uuid == VENDOR_CHARACTERISTIC_33F6
    assert result.hardware_verified is False


def test_raw_ai_state_notification_requires_two_state_bytes():
    result = parse_raw_vendor_notification(
        (0x0006).to_bytes(2, "little") + bytes(6) + bytes((3, 4, 5))
    )

    assert result.first_value == 3
    assert result.second_value == 4
    assert result.trailing_bytes_ignored == 1


@pytest.mark.parametrize("raw_type,kind", [(0x0002, "audio"), (0x0003, "image")])
def test_raw_payload_notification_is_bounded_and_hidden_from_repr(raw_type, kind):
    private_synthetic_payload = bytes((0xAA, 0xBB, 0xCC))
    data = (
        raw_type.to_bytes(2, "little")
        + (10).to_bytes(2, "little")
        + (20).to_bytes(2, "little")
        + len(private_synthetic_payload).to_bytes(2, "little")
        + private_synthetic_payload
    )

    result = parse_raw_vendor_notification(data)

    assert result.kind == kind
    assert result.first_value == 10
    assert result.second_value == 20
    assert result.declared_length == 3
    assert result.payload_for_explicit_local_use() == private_synthetic_payload
    assert "aabbcc" not in repr(result).lower()
    assert result.hardware_verified is False


@pytest.mark.parametrize(
    "data",
    [
        bytes(7),
        (0xFFFF).to_bytes(2, "little") + bytes(6),
        (0x0001).to_bytes(2, "little") + bytes(6),
        (0x0006).to_bytes(2, "little") + bytes(7),
        (0x0002).to_bytes(2, "little") + bytes(4) + (3).to_bytes(2, "little") + bytes(2),
    ],
)
def test_raw_notification_decoder_rejects_short_unknown_and_truncated_data(data):
    with pytest.raises(ProtocolError):
        parse_raw_vendor_notification(data)


def test_raw_payload_decoder_enforces_explicit_size_bound():
    payload = bytes(4)
    data = (
        (0x0002).to_bytes(2, "little")
        + bytes(4)
        + len(payload).to_bytes(2, "little")
        + payload
    )

    with pytest.raises(ProtocolError):
        parse_raw_vendor_notification(data, max_payload_bytes=3)
