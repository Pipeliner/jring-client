import asyncio
import json

import pytest

from jring import cli
from jring.client import JRingClient
from jring.transport import FakeTransport, GattCharacteristicMetadata
from jring.uuids import (
    HID_INFORMATION,
    HID_REPORT,
    HUMAN_INTERFACE_DEVICE_SERVICE,
    REPORT_REFERENCE_DESCRIPTOR,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_SERVICE_56FF,
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
            assert states["hid_information"] == "read_property_advertised"
            assert states["report_map"] == "read_property_advertised"
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
            assert feature_states(inventory)["hid_information"] == (
                "read_property_advertised"
            )
            assert feature_states(inventory)["report"] == "advertised"
            assert inventory.report_reference_state == "malformed"

    run(scenario())


def test_repeated_hid_reports_preserve_instance_and_descriptor_metadata():
    transport = FakeTransport(
        {},
        {HUMAN_INTERFACE_DEVICE_SERVICE},
        gatt_metadata=(
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE,
                HID_REPORT,
                ("notify",),
                (REPORT_REFERENCE_DESCRIPTOR,),
            ),
            GattCharacteristicMetadata(
                HUMAN_INTERFACE_DEVICE_SERVICE,
                HID_REPORT,
                ("read",),
                (),
            ),
        ),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert len(inventory.hid_report_instances) == 2
            first, second = inventory.hid_report_instances
            assert first.instance == 1
            assert first.state == "advertised"
            assert first.report_reference_state == "advertised"
            assert first.value_state == "not_read"
            assert second.instance == 2
            assert second.state == "read_property_advertised"
            assert second.report_reference_state == "unsupported"
            assert second.value_state == "not_read"

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


def test_vendor_characteristic_only_uuid_is_reported_without_inferred_meaning():
    transport = FakeTransport(
        {},
        set(),
        gatt_metadata=(
            GattCharacteristicMetadata(
                VENDOR_SERVICE_56FF,
                VENDOR_CHARACTERISTIC_33F4,
                ("write",),
                (),
            ),
        ),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            observations = {
                (item.uuid, item.observed_as, item.meaning)
                for item in inventory.vendor_gatt
            }
            assert observations == {
                (VENDOR_SERVICE_56FF, "service", "unknown"),
                (VENDOR_CHARACTERISTIC_33F4, "characteristic", "unknown"),
            }

    run(scenario())


def test_vendor_inventory_is_metadata_only_even_for_writable_characteristic():
    class MetadataOnlyTransport(FakeTransport):
        async def read(self, _characteristic):
            raise AssertionError("vendor inventory must not read values")

        async def write(self, _characteristic, _data):
            raise AssertionError("vendor inventory must not write")

        async def subscribe(self, _characteristic, _callback):
            raise AssertionError("vendor inventory must not subscribe")

    transport = MetadataOnlyTransport(
        {},
        {VENDOR_SERVICE_56FF},
        gatt_metadata=(
            GattCharacteristicMetadata(
                VENDOR_SERVICE_56FF,
                VENDOR_CHARACTERISTIC_33F4,
                ("write",),
                (),
            ),
        ),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert len(inventory.vendor_gatt) == 2

    run(scenario())


def test_vendor_metadata_survives_service_inventory_failure_as_partial():
    class MissingServicesTransport(FakeTransport):
        async def service_uuids(self):
            raise OSError("service inventory unavailable")

    transport = MissingServicesTransport(
        {},
        set(),
        gatt_metadata=(
            GattCharacteristicMetadata(
                VENDOR_SERVICE_56FF,
                VENDOR_CHARACTERISTIC_33F4,
                ("write",),
                (),
            ),
        ),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert inventory.inventory_state == "partial"
            assert {(item.uuid, item.observed_as) for item in inventory.vendor_gatt} == {
                (VENDOR_SERVICE_56FF, "service"),
                (VENDOR_CHARACTERISTIC_33F4, "characteristic"),
            }

    run(scenario())


def test_cli_capability_inventory_is_private(capsys):
    assert cli.main(["capabilities", "--simulate", "--json"]) == 0
    serialized = capsys.readouterr().out
    result = json.loads(serialized)
    assert result["schema_version"] == 1
    assert result["operation"] == "capabilities"
    assert result["source"] == "simulator"
    assert result["simulator_profile"] == "basic"
    assert result["ok"] is True
    assert result["standard_hid"]["service_state"] == "unsupported"
    assert result["standard_hid"]["report_instances"] == []
    assert result["neutral_events"] == {"events": [], "state": "unsupported"}
    assert result["vendor_gatt"] == []
    assert "AA:BB" not in serialized
    assert "report_map_value" not in serialized
    assert '"usable"' not in serialized


def test_cli_capability_inventory_human_copy_is_honest(capsys):
    assert cli.main([
        "capabilities", "--simulate", "--simulate-profile", "hid",
    ]) == 0
    output = capsys.readouterr().out
    assert "SIMULATION — no ring contacted" in output
    assert "Simulator profile: hid" in output
    assert "Standard HID service: advertised" in output
    assert "HID usability: not verified" in output
    assert "OS attachment: not checked" in output
    assert "Report Map contents: not read" in output
    assert "HID Report instances: 1" in output
    assert "Report instance 1: advertised; Report Reference advertised; value not read" in output
    assert "Verified hardware events: none (unsupported)" in output
    assert "Known vendor UUID observations: none" in output
    assert "Vendor meanings: unknown; values not read; writes disabled" in output


@pytest.mark.parametrize(
    "profile, advertised, service_state",
    (("basic", False, "unsupported"), ("hid", True, "advertised")),
)
def test_simulator_profile_is_consistent_between_status_and_capabilities(
    profile, advertised, service_state, capsys
):
    assert cli.main([
        "status", "--simulate", "--simulate-profile", profile, "--json",
    ]) == 0
    status = json.loads(capsys.readouterr().out)

    assert cli.main([
        "capabilities", "--simulate", "--simulate-profile", profile, "--json",
    ]) == 0
    capabilities = json.loads(capsys.readouterr().out)

    assert status["simulator_profile"] == capabilities["simulator_profile"] == profile
    assert status["capabilities"]["hid_service_advertised"] is advertised
    assert capabilities["standard_hid"]["service_state"] == service_state
    assert len(capabilities["standard_hid"]["report_instances"]) == (
        1 if advertised else 0
    )
