import asyncio
import sys
from types import SimpleNamespace

from jring.bleak_transport import BleakTransport


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
