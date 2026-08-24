import asyncio
import json

import pytest

from jring.client import JRingClient
from jring.transport import FakeTransport
from jring.uuids import HUMAN_INTERFACE_DEVICE_SERVICE


def run(coro):
    return asyncio.run(coro)


def test_simulated_safe_reads_and_capabilities():
    transport = FakeTransport.standard_ring()

    async def scenario():
        async with JRingClient(transport, timeout=0.1) as client:
            assert await client.battery() == 84
            info = await client.device_info()
            assert info.manufacturer == "Simulated"
            caps = await client.capabilities()
            assert caps.heart_rate
            assert not caps.vendor_writes

    run(scenario())

def test_live_heart_rate_notification_and_clean_stop():
    transport = FakeTransport.standard_ring()

    async def scenario():
        async with JRingClient(transport, timeout=0.1) as client:
            stream = client.heart_rate_events()
            task = asyncio.create_task(anext(stream))
            await asyncio.sleep(0)
            transport.emit("00002a37-0000-1000-8000-00805f9b34fb", b"\x00\x48")
            assert (await task).bpm == 72
            await stream.aclose()
        assert transport.closed

    run(scenario())


def test_history_export_is_deterministic(tmp_path):
    transport = FakeTransport.standard_ring()

    async def scenario():
        async with JRingClient(transport) as client:
            records = await client.history()
            client.export_history(records, tmp_path / "history.jsonl")

    run(scenario())
    text = (tmp_path / "history.jsonl").read_text()
    assert '"kind": "heart_rate"' in text
    assert "device" not in text.lower()


def test_history_export_rejects_ambiguous_suffix(tmp_path):
    transport = FakeTransport.standard_ring()
    with pytest.raises(ValueError, match=".csv or .jsonl"):
        JRingClient.export_history(transport.records, tmp_path / "history.txt")


def test_history_export_requires_force_to_replace(tmp_path):
    destination = tmp_path / "history.jsonl"
    destination.write_text("keep me\n")
    records = FakeTransport.standard_ring().records

    with pytest.raises(FileExistsError):
        JRingClient.export_history(records, destination, source="simulator")
    assert destination.read_text() == "keep me\n"

    JRingClient.export_history(records, destination, source="simulator", force=True)
    row = json.loads(destination.read_text())
    assert row["source"] == "simulator"
    assert row["synthetic"] is True


def test_timeout_fails_closed():
    transport = FakeTransport.standard_ring(read_delay=0.1)

    async def scenario():
        async with JRingClient(transport, timeout=0.001) as client:
            with pytest.raises(TimeoutError):
                await client.battery()

    run(scenario())


def test_standard_hid_service_is_reported():
    transport = FakeTransport.standard_ring()
    transport.services.add(HUMAN_INTERFACE_DEVICE_SERVICE)

    async def scenario():
        async with JRingClient(transport) as client:
            capabilities = await client.capabilities()
            assert capabilities.hid

    run(scenario())


def test_missing_battery_still_reports_hid():
    transport = FakeTransport.standard_ring()
    transport.values.pop("00002a19-0000-1000-8000-00805f9b34fb")
    transport.services.add(HUMAN_INTERFACE_DEVICE_SERVICE)

    async def scenario():
        async with JRingClient(transport) as client:
            status = await client.status()
            assert status.battery_percent is None
            assert not status.battery_available
            assert status.capabilities.hid

    run(scenario())
