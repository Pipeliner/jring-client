import asyncio
import json

from jring import cli
from jring.client import JRingClient
from jring.transport import FakeTransport, GattCharacteristicMetadata
from jring.uuids import (
    HID_INFORMATION,
    HID_REPORT,
    HUMAN_INTERFACE_DEVICE_SERVICE,
)


def run(coro):
    return asyncio.run(coro)


def feature_states(inventory):
    return {feature.name: feature.state for feature in inventory.characteristics}


def test_hid_advertisement_is_not_called_usable():
    transport = FakeTransport({}, {HUMAN_INTERFACE_DEVICE_SERVICE})

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert inventory.hid_service_state == "advertised"
            assert inventory.usability_state == "not_verified"
            assert inventory.os_attachment_state == "not_checked"
            assert set(feature_states(inventory).values()) == {"unsupported"}

    run(scenario())


def test_standard_hid_metadata_has_explicit_states():
    transport = FakeTransport.standard_hid_ring()

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            states = feature_states(inventory)
            assert inventory.inventory_state == "available"
            assert inventory.hid_service_state == "advertised"
            assert states["hid_information"] == "readable"
            assert states["report_map"] == "readable"
            assert states["report"] == "advertised"
            assert inventory.report_reference_state == "advertised"
            assert inventory.neutral_event_state == "unsupported"
            assert inventory.neutral_events == ()

    run(scenario())


def test_malformed_optional_descriptor_preserves_inventory():
    transport = FakeTransport(
        {},
        {HUMAN_INTERFACE_DEVICE_SERVICE},
        gatt_metadata=(
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE, HID_INFORMATION, ("read",), ()
            ),
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE, HID_REPORT, ("notify",), ("not-a-uuid",)
            ),
        ),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert feature_states(inventory)["hid_information"] == "readable"
            assert feature_states(inventory)["report"] == "advertised"
            assert inventory.report_reference_state == "malformed"

    run(scenario())


def test_metadata_failure_preserves_advertised_service_state():
    class MissingMetadataTransport(FakeTransport):
        async def gatt_characteristics(self):
            raise OSError("metadata unavailable")

    transport = MissingMetadataTransport({}, {HUMAN_INTERFACE_DEVICE_SERVICE})

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert inventory.inventory_state == "partial"
            assert inventory.hid_service_state == "advertised"
            assert inventory.metadata_state == "unavailable"
            assert set(feature_states(inventory).values()) == {"unavailable"}

    run(scenario())


def test_capability_inventory_performs_no_reads_or_subscriptions():
    class MetadataOnlyTransport(FakeTransport):
        async def read(self, _characteristic):
            raise AssertionError("inventory must not read values")

        async def subscribe(self, _characteristic, _callback):
            raise AssertionError("inventory must not subscribe")

    source = FakeTransport.standard_hid_ring()
    transport = MetadataOnlyTransport({}, source.services, gatt_metadata=source.gatt_metadata)

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert inventory.hid_service_state == "advertised"

    run(scenario())


def test_cli_capability_inventory_is_private(capsys):
    assert cli.main(["capabilities", "--simulate", "--json"]) == 0
    serialized = capsys.readouterr().out
    result = json.loads(serialized)
    assert result["schema_version"] == 1
    assert result["operation"] == "capabilities"
    assert result["source"] == "simulator"
    assert result["ok"] is True
    assert result["standard_hid"]["service_state"] == "advertised"
    assert result["standard_hid"]["usability_state"] == "not_verified"
    assert result["standard_hid"]["os_attachment_state"] == "not_checked"
    assert result["neutral_events"] == {"events": [], "state": "unsupported"}
    assert "AA:BB" not in serialized
    assert "report_map_value" not in serialized
    assert '"usable"' not in serialized


def test_cli_capability_inventory_human_copy_is_honest(capsys):
    assert cli.main(["capabilities", "--simulate"]) == 0
    output = capsys.readouterr().out
    assert "SIMULATION — no ring contacted" in output
    assert "Standard HID service: advertised" in output
    assert "HID usability: not verified" in output
    assert "OS attachment: not checked" in output
    assert "Report Map contents: not read" in output
    assert "Verified hardware events: none (unsupported)" in output
