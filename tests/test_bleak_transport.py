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
