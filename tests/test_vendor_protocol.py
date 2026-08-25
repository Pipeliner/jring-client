import pytest

from jring.uuids import VENDOR_CHARACTERISTIC_33F3
from jring.vendor_protocol import (
    StaticQuery,
    StaticVendorRequest,
    encode_day_query,
    encode_static_query,
)


@pytest.mark.parametrize(
    "operation,opcode",
    [
        (StaticQuery.CURRENT_SPORT, 0x03),
        (StaticQuery.BATTERY, 0x0B),
        (StaticQuery.DEVICE_INFO, 0x0C),
        (StaticQuery.BAND_FUNCTIONS, 0x20),
    ],
)
def test_static_zero_argument_query_vectors(operation, opcode):
    request = encode_static_query(operation)

    assert request.synthetic_bytes_for_test() == bytes((opcode,)) + bytes(19)
    assert request.endpoint_uuid == VENDOR_CHARACTERISTIC_33F3
    assert request.maturity == "static_apk_only"
    assert request.hardware_eligible is False


@pytest.mark.parametrize(
    "operation,opcode",
    [
        (StaticQuery.MULTI_SPORT_DAY, 0x25),
        (StaticQuery.OXYGEN_DAY, 0x40),
        (StaticQuery.ADVANCED_SENSOR_DAY, 0x55),
    ],
)
def test_static_day_query_vectors(operation, opcode):
    request = encode_day_query(operation, day_offset=7)

    assert request.synthetic_bytes_for_test() == bytes((opcode, 7)) + bytes(18)
    assert request.hardware_eligible is False


@pytest.mark.parametrize("day_offset", [-1, 256, True, 1.5])
def test_day_query_rejects_values_not_representable_as_one_unsigned_byte(day_offset):
    with pytest.raises((TypeError, ValueError)):
        encode_day_query(StaticQuery.OXYGEN_DAY, day_offset=day_offset)


def test_query_kinds_cannot_be_used_with_the_wrong_encoder():
    with pytest.raises(ValueError):
        encode_static_query(StaticQuery.OXYGEN_DAY)
    with pytest.raises(ValueError):
        encode_day_query(StaticQuery.BATTERY, day_offset=1)


def test_static_request_repr_never_contains_frame_bytes():
    request = encode_static_query(StaticQuery.BATTERY)

    assert "0b00" not in repr(request).lower()
    assert "frame" not in repr(request).lower()


def test_static_request_cannot_be_constructed_as_hardware_eligible():
    with pytest.raises(TypeError):
        StaticVendorRequest(
            StaticQuery.BATTERY,
            b"",
            hardware_eligible=True,
        )


def test_client_has_no_vendor_transmission_api():
    from jring.client import JRingClient

    assert not hasattr(JRingClient, "send_vendor_request")
    assert not hasattr(JRingClient, "write_vendor_frame")
