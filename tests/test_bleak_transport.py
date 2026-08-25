import asyncio
import sys
from types import SimpleNamespace

from jring.bleak_transport import BleakTransport
from jring.uuids import HID_REPORT, HUMAN_INTERFACE_DEVICE_SERVICE, REPORT_REFERENCE_DESCRIPTOR


def test_bleak_one_x_none_return_is_a_successful_connection(monkeypatch):
    class Client:
        def __init__(self, _address, *, timeout):
            self.timeout = timeout
            self.is_connected = False

        async def connect(self):
            self.is_connected = True
            return None

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport("AA:BB:CC:DD:EE:FF", timeout=2)

    asyncio.run(transport.connect())


def test_bleak_gatt_inventory_enumerates_metadata_without_reading_values(monkeypatch):
    class Client:
        def __init__(self, _address, *, timeout):
            self.is_connected = True
            self.services = [
                SimpleNamespace(
                    uuid=HUMAN_INTERFACE_DEVICE_SERVICE.upper(),
                    characteristics=[
                        SimpleNamespace(
                            uuid=HID_REPORT.upper(),
                            properties=["notify"],
                            descriptors=[SimpleNamespace(uuid=REPORT_REFERENCE_DESCRIPTOR.upper())],
                        )
                    ],
                )
            ]

        async def read_gatt_char(self, _uuid):
            raise AssertionError("metadata inventory must not read a value")

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport("AA:BB:CC:DD:EE:FF", timeout=2)

    result = asyncio.run(transport.gatt_characteristics())

    assert result[0].service_uuid == HUMAN_INTERFACE_DEVICE_SERVICE
    assert result[0].uuid == HID_REPORT
    assert result[0].properties == ("notify",)
    assert result[0].descriptor_uuids == (REPORT_REFERENCE_DESCRIPTOR,)
    assert result[0].instance_id == "service-1-characteristic-1"
    assert result[0].descriptor_instance_ids == (
        "service-1-characteristic-1-descriptor-1",
    )


def test_bleak_write_with_response_requests_and_awaits_gatt_response(monkeypatch):
    completed = False

    class Client:
        def __init__(self, _address, *, timeout):
            self.is_connected = True

        async def write_gatt_char(self, characteristic, data, *, response):
            nonlocal completed
            assert characteristic == "characteristic"
            assert data == b"payload"
            assert response is True
            await asyncio.sleep(0)
            completed = True

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport("AA:BB:CC:DD:EE:FF", timeout=2)

    asyncio.run(transport.write_with_response("characteristic", b"payload"))

    assert completed is True


def test_bleak_write_with_response_propagates_response_failure(monkeypatch):
    class ExpectedFailure(Exception):
        pass

    class Client:
        def __init__(self, _address, *, timeout):
            self.is_connected = True

        async def write_gatt_char(self, _characteristic, _data, *, response):
            assert response is True
            raise ExpectedFailure("write response failed")

    monkeypatch.setitem(sys.modules, "bleak", SimpleNamespace(BleakClient=Client))
    transport = BleakTransport("AA:BB:CC:DD:EE:FF", timeout=2)

    try:
        asyncio.run(transport.write_with_response("characteristic", b"payload"))
    except ExpectedFailure as exc:
        assert str(exc) == "write response failed"
    else:
        raise AssertionError("response failures must propagate")
