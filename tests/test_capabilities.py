import asyncio
import json

import pytest

from jring import cli
from jring.client import CapabilityInventory, JRingClient
from jring.transport import (
    FakeTransport,
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
)
from jring.uuids import (
    CLIENT_CHARACTERISTIC_CONFIGURATION,
    HID_INFORMATION,
    HID_REPORT,
    HUMAN_INTERFACE_DEVICE_SERVICE,
    REPORT_REFERENCE_DESCRIPTOR,
    SUOTA_PATCH_DATA,
    SUOTA_VERSION,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F5,
    VENDOR_CHARACTERISTIC_33F6,
    VENDOR_SERVICE_FEF5,
    VENDOR_SERVICE_56FF,
)


def vendor_route_metadata():
    rows = []
    for route, request_uuid, response_uuid in (
        ("main", VENDOR_CHARACTERISTIC_33F3, VENDOR_CHARACTERISTIC_33F4),
        ("raw", VENDOR_CHARACTERISTIC_33F5, VENDOR_CHARACTERISTIC_33F6),
    ):
        request_id = f"{route}-request"
        response_id = f"{route}-response"
        rows.extend(
            (
                GattCharacteristicMetadata(
                    VENDOR_SERVICE_56FF,
                    request_uuid,
                    ("write",),
                    (),
                    request_id,
                    (),
                    GattCharacteristicTarget(
                        1, VENDOR_SERVICE_56FF, request_uuid, request_id
                    ),
                ),
                GattCharacteristicMetadata(
                    VENDOR_SERVICE_56FF,
                    response_uuid,
                    ("notify",),
                    (CLIENT_CHARACTERISTIC_CONFIGURATION,),
                    response_id,
                    (f"{response_id}-cccd",),
                    GattCharacteristicTarget(
                        1, VENDOR_SERVICE_56FF, response_uuid, response_id
                    ),
                ),
            )
        )
    return tuple(rows)


def run(coro):
    return asyncio.run(coro)


def feature_states(inventory):
    return {feature.name: feature.state for feature in inventory.characteristics}


def test_capability_inventory_preserves_legacy_positional_field_order():
    async def scenario():
        async with JRingClient(FakeTransport.standard_hid_ring()) as client:
            source = await client.capability_inventory()
        reconstructed = CapabilityInventory(
            source.inventory_state,
            source.metadata_state,
            source.hid_service_state,
            source.characteristics,
            source.report_reference_state,
            source.standard_heart_rate,
            source.vendor_gatt,
            source.hid_report_instances,
            source.usability_state,
            source.os_attachment_state,
            source.neutral_event_state,
            source.neutral_events,
        )
        assert reconstructed.hid_report_instances == source.hid_report_instances
        assert reconstructed.usability_state == source.usability_state
        assert reconstructed.neutral_events == source.neutral_events
        assert reconstructed.vendor_routes == ()

    run(scenario())


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
            assert inventory.report_reference_state == "all"
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
            report_feature = next(
                item for item in inventory.characteristics if item.name == "report"
            )
            assert report_feature.instance_count == 2
            assert report_feature.instance_resolution_state == "uuid_ambiguous"
            assert report_feature.state == "multiple_mixed"
            assert report_feature.instance_states == (
                "advertised",
                "read_property_advertised",
            )
            assert inventory.report_reference_state == "mixed"
            first, second = inventory.hid_report_instances
            assert first.instance == 1
            assert first.characteristic_instance_id == "inventory-report-1"
            assert first.characteristic_identity_state == "inventory_only"
            assert first.state == "advertised"
            assert first.report_reference_state == "advertised"
            assert first.report_reference_instance_ids == (
                "inventory-report-1-descriptor-1",
            )
            assert first.targeting_state == "metadata_only_not_targetable"
            assert first.value_state == "not_read"
            assert second.instance == 2
            assert second.characteristic_instance_id == "inventory-report-2"
            assert second.state == "read_property_advertised"
            assert second.report_reference_state == "unsupported"
            assert second.report_reference_instance_ids == ()
            assert second.targeting_state == "metadata_only_not_targetable"
            assert second.value_state == "not_read"

    run(scenario())


def test_repeated_hid_aggregate_is_order_independent_and_preserves_malformed_peer():
    records = (
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
            ("not-a-uuid",),
        ),
    )

    async def inventory(metadata):
        async with JRingClient(
            FakeTransport(
                {}, {HUMAN_INTERFACE_DEVICE_SERVICE}, gatt_metadata=metadata
            )
        ) as client:
            return await client.capability_inventory()

    first = run(inventory(records))
    reversed_order = run(inventory(tuple(reversed(records))))
    first_report = next(item for item in first.characteristics if item.name == "report")
    reversed_report = next(
        item for item in reversed_order.characteristics if item.name == "report"
    )

    assert first_report.state == reversed_report.state == "multiple_mixed"
    assert first_report.instance_count == reversed_report.instance_count == 2
    assert first_report.instance_states == reversed_report.instance_states == (
        "advertised",
        "read_property_advertised",
    )
    assert first.report_reference_state == "malformed_mixed"
    assert reversed_order.report_reference_state == "malformed_mixed"
    assert len({row.characteristic_instance_id for row in first.hid_report_instances}) == 2
    assert all(row.value_state == "not_read" for row in first.hid_report_instances)
    assert all(
        row.targeting_state == "metadata_only_not_targetable"
        for row in first.hid_report_instances
    )


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
            assert all(
                row.service_inventory_state == "available"
                and row.metadata_inventory_state == "unavailable"
                and row.structural_state == "not_evaluated"
                and row.structurally_ready is False
                and row.transport_target_state == "not_evaluated"
                for row in inventory.vendor_routes
            )

    run(scenario())


def test_timed_out_vendor_metadata_is_not_misreported_as_missing_endpoints():
    class SlowMetadataTransport(FakeTransport):
        async def gatt_characteristics(self):
            await asyncio.sleep(1)
            return ()

    transport = SlowMetadataTransport({}, {VENDOR_SERVICE_56FF})

    async def scenario():
        async with JRingClient(transport, timeout=0.01) as client:
            inventory = await client.capability_inventory()
            assert inventory.inventory_state == "partial"
            assert all(
                row.service_inventory_state == "available"
                and row.metadata_inventory_state == "timed_out"
                and row.structural_state == "not_evaluated"
                and row.structurally_ready is False
                and row.transport_target_state == "not_evaluated"
                for row in inventory.vendor_routes
            )

    run(scenario())


def test_timed_out_service_inventory_does_not_run_vendor_preflight():
    class SlowServicesTransport(FakeTransport):
        async def service_uuids(self):
            await asyncio.sleep(1)
            return set()

    transport = SlowServicesTransport({}, set())

    async def scenario():
        async with JRingClient(transport, timeout=0.01) as client:
            inventory = await client.capability_inventory()
            assert inventory.inventory_state == "partial"
            assert tuple(row.route for row in inventory.vendor_routes) == (
                "main",
                "raw",
            )
            assert all(
                row.service_inventory_state == "timed_out"
                and row.metadata_inventory_state == "available"
                and row.structural_state == "not_evaluated"
                and row.structurally_ready is False
                and row.transport_target_state == "not_evaluated"
                for row in inventory.vendor_routes
            )

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


def test_vendor_route_readiness_uses_metadata_and_current_target_ownership_only():
    class CurrentSnapshotTransport(FakeTransport):
        def __init__(self):
            metadata = vendor_route_metadata()
            super().__init__(
                {}, {VENDOR_SERVICE_56FF}, gatt_metadata=metadata
            )
            self.expected_targets = tuple(
                row.target for row in metadata if row.target is not None
            )
            self.ownership_checks = 0

        def owns_target(self, target):
            self.ownership_checks += 1
            return self.connected and any(
                target is expected for expected in self.expected_targets
            )

        async def read(self, _characteristic):
            raise AssertionError("route inventory must not read values")

        async def write(self, _characteristic, _data):
            raise AssertionError("route inventory must not write")

        async def write_with_response(self, _characteristic, _data):
            raise AssertionError("route inventory must not write")

        async def subscribe(self, _characteristic, _callback):
            raise AssertionError("route inventory must not subscribe")

    transport = CurrentSnapshotTransport()

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert transport.ownership_checks == 4
            assert tuple(row.route for row in inventory.vendor_routes) == (
                "main",
                "raw",
            )
            assert all(
                row.structural_state == "structurally_ready"
                for row in inventory.vendor_routes
            )
            assert all(row.structurally_ready for row in inventory.vendor_routes)
            assert all(
                row.transport_target_state == "current_snapshot_owned"
                for row in inventory.vendor_routes
            )
            assert all(row.metadata_only for row in inventory.vendor_routes)
            assert all(row.values_read is False for row in inventory.vendor_routes)
            assert all(
                row.subscription_attempted is False
                for row in inventory.vendor_routes
            )
            assert all(row.write_attempted is False for row in inventory.vendor_routes)
            assert all(row.runnable is False for row in inventory.vendor_routes)
            assert all(row.live_eligible is False for row in inventory.vendor_routes)
            assert all(row.owner_authorized is False for row in inventory.vendor_routes)
            assert all(
                row.hardware_eligible is False for row in inventory.vendor_routes
            )
            assert all(
                row.hardware_verified is False for row in inventory.vendor_routes
            )

    run(scenario())


def test_vendor_route_readiness_fails_closed_without_owned_current_targets():
    metadata = vendor_route_metadata()
    transport = FakeTransport(
        {}, {VENDOR_SERVICE_56FF}, gatt_metadata=metadata
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert all(row.structurally_ready for row in inventory.vendor_routes)
            assert all(
                row.transport_target_state == "not_current_snapshot_owned"
                for row in inventory.vendor_routes
            )

    run(scenario())


@pytest.mark.parametrize("owned_index", (0, 1))
def test_vendor_route_requires_both_exact_current_target_objects(owned_index):
    metadata = vendor_route_metadata()[:2]

    class PartiallyOwnedTransport(FakeTransport):
        def owns_target(self, target):
            return target is metadata[owned_index].target

    transport = PartiallyOwnedTransport(
        {}, {VENDOR_SERVICE_56FF}, gatt_metadata=metadata
    )

    async def scenario():
        async with JRingClient(transport) as client:
            main, raw = (await client.capability_inventory()).vendor_routes
            assert main.structurally_ready is True
            assert main.transport_target_state == "not_current_snapshot_owned"
            assert raw.structurally_ready is False
            assert raw.transport_target_state == "not_evaluated"

    run(scenario())


def test_stale_vendor_targets_fail_generation_before_ownership():
    stale = tuple(
        GattCharacteristicMetadata(
            row.service_uuid,
            row.uuid,
            row.properties,
            row.descriptor_uuids,
            row.instance_id,
            row.descriptor_instance_ids,
            GattCharacteristicTarget(
                2,
                row.target.service_uuid,
                row.target.uuid,
                row.target.instance_id,
            ),
        )
        for row in vendor_route_metadata()
    )
    transport = FakeTransport(
        {}, {VENDOR_SERVICE_56FF}, gatt_metadata=stale
    )

    async def scenario():
        async with JRingClient(transport) as client:
            routes = (await client.capability_inventory()).vendor_routes
            assert all(
                row.structural_state == "target_generation_mismatch"
                and row.structurally_ready is False
                and row.transport_target_state == "not_evaluated"
                for row in routes
            )

    run(scenario())


def test_vendor_route_readiness_reports_stable_preflight_failure_without_targets():
    rows = vendor_route_metadata()
    duplicate = GattCharacteristicMetadata(
        rows[0].service_uuid,
        rows[0].uuid,
        rows[0].properties,
        rows[0].descriptor_uuids,
        "main-request-duplicate",
        (),
        GattCharacteristicTarget(
            1,
            rows[0].service_uuid,
            rows[0].uuid,
            "main-request-duplicate",
        ),
    )

    class CurrentSnapshotTransport(FakeTransport):
        def owns_target(self, target):
            return self.connected and any(
                target is row.target for row in (*rows, duplicate)
            )

    transport = CurrentSnapshotTransport(
        {}, {VENDOR_SERVICE_56FF}, gatt_metadata=(rows[0], duplicate, *rows[1:])
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            main, raw = inventory.vendor_routes
            assert main.route == "main"
            assert main.structural_state == "request_endpoint_ambiguous"
            assert main.structurally_ready is False
            assert main.transport_target_state == "not_evaluated"
            assert raw.route == "raw"
            assert raw.structural_state == "structurally_ready"
            assert raw.structurally_ready is True
            assert raw.transport_target_state == "current_snapshot_owned"

    run(scenario())


def test_malformed_vendor_metadata_is_sanitized_instead_of_raising():
    malformed = GattCharacteristicMetadata(
        object(),
        VENDOR_CHARACTERISTIC_33F3,
        ("write",),
        (),
    )
    class MalformedMetadataTransport(FakeTransport):
        async def gatt_characteristics(self):
            return (malformed,)

    transport = MalformedMetadataTransport({}, {VENDOR_SERVICE_56FF})

    async def scenario():
        async with JRingClient(transport) as client:
            routes = (await client.capability_inventory()).vendor_routes
            assert all(
                row.structural_state == "malformed_metadata"
                and row.structurally_ready is False
                and row.transport_target_state == "not_evaluated"
                for row in routes
            )

    run(scenario())


def test_public_route_state_names_the_request_write_property_correctly():
    rows = vendor_route_metadata()
    request = rows[0]
    no_response_write = GattCharacteristicMetadata(
        request.service_uuid,
        request.uuid,
        ("write-without-response",),
        request.descriptor_uuids,
        request.instance_id,
        request.descriptor_instance_ids,
        request.target,
    )

    class NoOwnershipCheckTransport(FakeTransport):
        def owns_target(self, _target):
            raise AssertionError("failed structural preflight must not check ownership")

    transport = NoOwnershipCheckTransport(
        {},
        {VENDOR_SERVICE_56FF},
        gatt_metadata=(no_response_write, *rows[1:]),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            main, _raw = (await client.capability_inventory()).vendor_routes
            assert main.structural_state == "request_write_unavailable"
            assert main.structurally_ready is False
            assert main.transport_target_state == "not_evaluated"

    run(scenario())


def test_transport_without_generation_contract_fails_closed_in_inventory():
    inner = FakeTransport({}, {VENDOR_SERVICE_56FF})

    class LegacyTransport:
        async def connect(self):
            await inner.connect()

        async def close(self):
            await inner.close()

        async def service_uuids(self):
            return await inner.service_uuids()

        async def gatt_characteristics(self):
            return await inner.gatt_characteristics()

        def owns_target(self, target):
            return inner.owns_target(target)

    async def scenario():
        async with JRingClient(LegacyTransport()) as client:
            routes = (await client.capability_inventory()).vendor_routes
            assert all(
                row.structural_state == "invalid_connection_generation"
                and row.structurally_ready is False
                and row.transport_target_state == "not_evaluated"
                for row in routes
            )

    run(scenario())


def test_suota_uuid_roles_are_discoverable_only_as_vendor_metadata():
    class MetadataOnlyTransport(FakeTransport):
        async def read(self, _characteristic):
            raise AssertionError("SUOTA inventory must not read values")

        async def write(self, _characteristic, _data):
            raise AssertionError("SUOTA inventory must not write")

        async def subscribe(self, _characteristic, _callback):
            raise AssertionError("SUOTA inventory must not subscribe")

    transport = MetadataOnlyTransport(
        {},
        {VENDOR_SERVICE_FEF5},
        gatt_metadata=(
            GattCharacteristicMetadata(
                VENDOR_SERVICE_FEF5, SUOTA_PATCH_DATA, ("write-without-response",), ()
            ),
            GattCharacteristicMetadata(
                VENDOR_SERVICE_FEF5, SUOTA_VERSION, ("read",), ()
            ),
        ),
    )

    async def scenario():
        async with JRingClient(transport) as client:
            inventory = await client.capability_inventory()
            assert {
                (item.uuid, item.observed_as, item.meaning)
                for item in inventory.vendor_gatt
            } == {
                (VENDOR_SERVICE_FEF5, "service", "unknown"),
                (SUOTA_PATCH_DATA, "characteristic", "unknown"),
                (SUOTA_VERSION, "characteristic", "unknown"),
            }

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
            assert all(
                row.service_inventory_state == "unavailable"
                and row.metadata_inventory_state == "available"
                and row.structural_state == "not_evaluated"
                and row.transport_target_state == "not_evaluated"
                for row in inventory.vendor_routes
            )

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
    assert [row["route"] for row in result["vendor_routes"]] == ["main", "raw"]
    assert all(
        row["structural_state"] == "service_not_advertised"
        for row in result["vendor_routes"]
    )
    assert all(
        row["transport_target_state"] == "not_evaluated"
        for row in result["vendor_routes"]
    )
    expected_route_keys = {
        "route",
        "service_inventory_state",
        "metadata_inventory_state",
        "structural_state",
        "structurally_ready",
        "transport_target_state",
        "metadata_only",
        "values_read",
        "subscription_attempted",
        "write_attempted",
        "runnable",
        "live_eligible",
        "owner_authorized",
        "hardware_eligible",
        "hardware_verified",
    }
    assert all(set(row) == expected_route_keys for row in result["vendor_routes"])
    assert all(row["metadata_only"] is True for row in result["vendor_routes"])
    assert all(row["live_eligible"] is False for row in result["vendor_routes"])
    assert all(row["owner_authorized"] is False for row in result["vendor_routes"])
    assert all(row["hardware_eligible"] is False for row in result["vendor_routes"])
    assert all(row["hardware_verified"] is False for row in result["vendor_routes"])
    assert "AA:BB" not in serialized
    route_json = json.dumps(result["vendor_routes"], sort_keys=True)
    assert all(
        private not in route_json
        for private in (
            "instance_id",
            "connection_generation",
            "backend",
            "path",
            "address",
            "payload",
            "frame",
            "descriptor_instance",
        )
    )
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
    assert "Vendor main route: service not advertised; targets not evaluated" in output
    assert "Vendor raw route: service not advertised; targets not evaluated" in output
    assert (
        "Vendor routes are metadata only: values not read; subscriptions not attempted; "
        "writes disabled" in output
    )
    assert (
        "Route readiness grants no live eligibility, owner authorization, or hardware "
        "eligibility" in output
    )
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
