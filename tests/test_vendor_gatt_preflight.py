from __future__ import annotations

import pytest

from jring.transport import GattCharacteristicMetadata, GattCharacteristicTarget
from jring.uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F5,
    VENDOR_CHARACTERISTIC_33F6,
    VENDOR_SERVICE_56FF,
    uuid16,
)
from jring.vendor_gatt_preflight import (
    VendorGattPreflightCode,
    VendorGattRoute,
    resolve_vendor_gatt_route,
)


CCCD = uuid16(0x2902)
OTHER_SERVICE = uuid16(0x180A)
GENERATION = 7


def _metadata(
    service_uuid: str,
    characteristic_uuid: str,
    properties: tuple[str, ...],
    descriptors: tuple[str, ...],
    instance_id: str,
    *,
    generation: int = GENERATION,
    target_service_uuid: str | None = None,
    target_uuid: str | None = None,
    target_instance_id: str | None = None,
    include_target: bool = True,
) -> GattCharacteristicMetadata:
    target = (
        GattCharacteristicTarget(
            connection_generation=generation,
            service_uuid=target_service_uuid or service_uuid,
            uuid=target_uuid or characteristic_uuid,
            instance_id=target_instance_id or instance_id,
        )
        if include_target
        else None
    )
    return GattCharacteristicMetadata(
        service_uuid=service_uuid,
        uuid=characteristic_uuid,
        properties=properties,
        descriptor_uuids=descriptors,
        instance_id=instance_id,
        target=target,
    )


def _route_metadata(
    route: VendorGattRoute,
) -> tuple[GattCharacteristicMetadata, GattCharacteristicMetadata]:
    if route is VendorGattRoute.MAIN:
        request_uuid = VENDOR_CHARACTERISTIC_33F3
        response_uuid = VENDOR_CHARACTERISTIC_33F4
    else:
        request_uuid = VENDOR_CHARACTERISTIC_33F5
        response_uuid = VENDOR_CHARACTERISTIC_33F6
    return (
        _metadata(
            VENDOR_SERVICE_56FF,
            request_uuid,
            ("write",),
            (),
            f"{route.value}-request",
        ),
        _metadata(
            VENDOR_SERVICE_56FF,
            response_uuid,
            ("notify",),
            (CCCD,),
            f"{route.value}-response",
        ),
    )


@pytest.mark.parametrize("route", tuple(VendorGattRoute))
def test_closed_main_and_raw_routes_resolve_connection_scoped_targets(route):
    metadata = _route_metadata(route)

    result = resolve_vendor_gatt_route(
        route,
        services={VENDOR_SERVICE_56FF},
        metadata=metadata,
        connection_generation=GENERATION,
    )

    assert result.code is VendorGattPreflightCode.STRUCTURALLY_READY
    assert result.structurally_ready is True
    assert result.route is route
    assert result.request_target is metadata[0].target
    assert result.response_target is metadata[1].target
    assert result.cccd_advertised is True
    assert result.runnable is False
    assert result.hardware_eligible is False
    assert result.hardware_verified is False
    assert result.owner_authorized is False


def test_preflight_is_pure_metadata_and_exposes_no_runtime_authority():
    services = {VENDOR_SERVICE_56FF}
    metadata = _route_metadata(VendorGattRoute.MAIN)
    original_services = set(services)
    original_metadata = tuple(metadata)

    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services=services,
        metadata=metadata,
        connection_generation=GENERATION,
    )

    assert services == original_services
    assert metadata == original_metadata
    assert all(
        not hasattr(result, name)
        for name in ("connect", "execute", "read", "write", "subscribe", "unsubscribe")
    )
    rendered = repr(result)
    assert "payload" not in rendered
    assert "frame" not in rendered
    assert "hardware_eligible=False" in rendered


@pytest.mark.parametrize(
    ("services", "metadata", "generation", "expected"),
    [
        (set(), _route_metadata(VendorGattRoute.MAIN), GENERATION,
         VendorGattPreflightCode.SERVICE_NOT_ADVERTISED),
        ({"not-a-uuid"}, _route_metadata(VendorGattRoute.MAIN), GENERATION,
         VendorGattPreflightCode.MALFORMED_SERVICE_INVENTORY),
        ({VENDOR_SERVICE_56FF}, _route_metadata(VendorGattRoute.MAIN), 0,
         VendorGattPreflightCode.INVALID_CONNECTION_GENERATION),
        ({VENDOR_SERVICE_56FF}, _route_metadata(VendorGattRoute.MAIN), True,
         VendorGattPreflightCode.INVALID_CONNECTION_GENERATION),
    ],
)
def test_top_level_preflight_failures_have_stable_reason_codes(
    services, metadata, generation, expected
):
    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services=services,
        metadata=metadata,
        connection_generation=generation,
    )

    assert result.code is expected
    assert result.structurally_ready is False
    assert result.request_target is None
    assert result.response_target is None
    assert result.hardware_eligible is False


@pytest.mark.parametrize(
    ("metadata_transform", "expected"),
    [
        (lambda rows: rows[1:], VendorGattPreflightCode.REQUEST_ENDPOINT_MISSING),
        (lambda rows: rows[:1], VendorGattPreflightCode.RESPONSE_ENDPOINT_MISSING),
        (
            lambda rows: rows + (rows[0],),
            VendorGattPreflightCode.REQUEST_ENDPOINT_AMBIGUOUS,
        ),
        (
            lambda rows: rows + (rows[1],),
            VendorGattPreflightCode.RESPONSE_ENDPOINT_AMBIGUOUS,
        ),
        (
            lambda rows: (
                _metadata(
                    OTHER_SERVICE,
                    VENDOR_CHARACTERISTIC_33F3,
                    ("write",),
                    (),
                    "wrong-service-request",
                ),
                rows[1],
            ),
            VendorGattPreflightCode.REQUEST_ENDPOINT_WRONG_SERVICE,
        ),
        (
            lambda rows: (
                rows[0],
                _metadata(
                    OTHER_SERVICE,
                    VENDOR_CHARACTERISTIC_33F4,
                    ("notify",),
                    (CCCD,),
                    "wrong-service-response",
                ),
            ),
            VendorGattPreflightCode.RESPONSE_ENDPOINT_WRONG_SERVICE,
        ),
    ],
)
def test_endpoint_absence_ambiguity_and_wrong_service_fail_closed(
    metadata_transform, expected
):
    metadata = metadata_transform(_route_metadata(VendorGattRoute.MAIN))

    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services={VENDOR_SERVICE_56FF},
        metadata=metadata,
        connection_generation=GENERATION,
    )

    assert result.code is expected
    assert result.structurally_ready is False


@pytest.mark.parametrize(
    ("request_properties", "response_properties", "descriptors", "expected"),
    [
        (
            ("write-without-response",),
            ("notify",),
            (CCCD,),
            VendorGattPreflightCode.RESPONSE_WRITE_UNAVAILABLE,
        ),
        (
            ("write",),
            ("indicate",),
            (CCCD,),
            VendorGattPreflightCode.NOTIFY_UNAVAILABLE,
        ),
        (
            ("write",),
            ("notify",),
            (),
            VendorGattPreflightCode.CCCD_NOT_ADVERTISED,
        ),
        (
            ("write",),
            ("notify",),
            (CCCD, CCCD),
            VendorGattPreflightCode.CCCD_AMBIGUOUS,
        ),
    ],
)
def test_properties_and_cccd_are_checked_without_claiming_acknowledgement(
    request_properties, response_properties, descriptors, expected
):
    metadata = (
        _metadata(
            VENDOR_SERVICE_56FF,
            VENDOR_CHARACTERISTIC_33F3,
            request_properties,
            (),
            "request",
        ),
        _metadata(
            VENDOR_SERVICE_56FF,
            VENDOR_CHARACTERISTIC_33F4,
            response_properties,
            descriptors,
            "response",
        ),
    )

    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services={VENDOR_SERVICE_56FF},
        metadata=metadata,
        connection_generation=GENERATION,
    )

    assert result.code is expected
    assert result.cccd_advertised is False


@pytest.mark.parametrize(
    ("request_changes", "response_changes", "expected"),
    [
        ({"include_target": False}, {}, VendorGattPreflightCode.TARGET_IDENTITY_MISSING),
        ({"generation": GENERATION - 1}, {}, VendorGattPreflightCode.TARGET_GENERATION_MISMATCH),
        (
            {"target_uuid": VENDOR_CHARACTERISTIC_33F4},
            {},
            VendorGattPreflightCode.TARGET_METADATA_MISMATCH,
        ),
        (
            {"target_service_uuid": OTHER_SERVICE},
            {},
            VendorGattPreflightCode.TARGET_METADATA_MISMATCH,
        ),
        (
            {"target_instance_id": "response"},
            {},
            VendorGattPreflightCode.TARGET_IDENTITY_AMBIGUOUS,
        ),
    ],
)
def test_connection_scoped_target_identity_is_required(
    request_changes, response_changes, expected
):
    metadata = (
        _metadata(
            VENDOR_SERVICE_56FF,
            VENDOR_CHARACTERISTIC_33F3,
            ("write",),
            (),
            "request",
            **request_changes,
        ),
        _metadata(
            VENDOR_SERVICE_56FF,
            VENDOR_CHARACTERISTIC_33F4,
            ("notify",),
            (CCCD,),
            "response",
            **response_changes,
        ),
    )

    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services={VENDOR_SERVICE_56FF},
        metadata=metadata,
        connection_generation=GENERATION,
    )

    assert result.code is expected
    assert result.structurally_ready is False
    assert result.request_target is None
    assert result.response_target is None


@pytest.mark.parametrize(
    "bad_metadata",
    [
        (object(),),
        (
            GattCharacteristicMetadata(
                service_uuid="not-a-uuid",
                uuid=VENDOR_CHARACTERISTIC_33F3,
                properties=("write",),
                descriptor_uuids=(),
            ),
        ),
        (
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F3,
                properties=(object(),),
                descriptor_uuids=(),
            ),
        ),
    ],
)
def test_malformed_metadata_returns_one_stable_failure_without_raising(bad_metadata):
    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services={VENDOR_SERVICE_56FF},
        metadata=bad_metadata,
        connection_generation=GENERATION,
    )

    assert result.code is VendorGattPreflightCode.MALFORMED_METADATA
    assert result.structurally_ready is False


def test_only_closed_route_enum_is_accepted():
    with pytest.raises(TypeError, match="exact VendorGattRoute"):
        resolve_vendor_gatt_route(
            "main",  # type: ignore[arg-type]
            services={VENDOR_SERVICE_56FF},
            metadata=_route_metadata(VendorGattRoute.MAIN),
            connection_generation=GENERATION,
        )


@pytest.mark.parametrize(
    "metadata",
    [
        (
            _metadata(
                VENDOR_SERVICE_56FF,
                VENDOR_CHARACTERISTIC_33F3,
                ("write", "WRITE"),
                (),
                "request",
            ),
            _route_metadata(VendorGattRoute.MAIN)[1],
        ),
        (
            _route_metadata(VendorGattRoute.MAIN)[0],
            GattCharacteristicMetadata(
                service_uuid=VENDOR_SERVICE_56FF,
                uuid=VENDOR_CHARACTERISTIC_33F4,
                properties=("notify",),
                descriptor_uuids=(CCCD,),
                instance_id="response",
                descriptor_instance_ids=("one", "extra"),
                target=GattCharacteristicTarget(
                    GENERATION,
                    VENDOR_SERVICE_56FF,
                    VENDOR_CHARACTERISTIC_33F4,
                    "response",
                ),
            ),
        ),
    ],
)
def test_duplicate_properties_and_descriptor_identity_mismatch_are_malformed(metadata):
    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services={VENDOR_SERVICE_56FF},
        metadata=metadata,
        connection_generation=GENERATION,
    )

    assert result.code is VendorGattPreflightCode.MALFORMED_METADATA
    assert result.structurally_ready is False


def test_instance_identity_must_be_unique_across_complete_snapshot():
    request, response = _route_metadata(VendorGattRoute.MAIN)
    unrelated = _metadata(
        OTHER_SERVICE,
        uuid16(0x2A19),
        ("read",),
        (),
        request.instance_id,
    )

    result = resolve_vendor_gatt_route(
        VendorGattRoute.MAIN,
        services={VENDOR_SERVICE_56FF},
        metadata=(request, response, unrelated),
        connection_generation=GENERATION,
    )

    assert result.code is VendorGattPreflightCode.TARGET_IDENTITY_AMBIGUOUS
    assert result.structurally_ready is False
