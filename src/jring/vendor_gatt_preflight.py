"""Pure, hardware-ineligible preparation for closed vendor GATT routes.

This module accepts an already collected metadata snapshot.  It does not own a
transport and cannot scan, connect, read, subscribe, or write.  A ready result says
only that one connection-scoped main or raw route is structurally targetable; it is
not owner authorization or evidence that the route works on hardware.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from .transport import (
    GattCharacteristicMetadata,
    GattCharacteristicTarget,
    GattDescriptorTarget,
)
from .uuids import (
    VENDOR_CHARACTERISTIC_33F3,
    VENDOR_CHARACTERISTIC_33F4,
    VENDOR_CHARACTERISTIC_33F5,
    VENDOR_CHARACTERISTIC_33F6,
    VENDOR_SERVICE_56FF,
    uuid16,
)


class VendorGattRoute(str, Enum):
    """The two statically closed vendor endpoint pairs."""

    MAIN = "main"
    RAW = "raw"


class VendorGattPreflightCode(str, Enum):
    """Stable, non-sensitive outcome codes for route preparation."""

    STRUCTURALLY_READY = "structurally_ready"
    INVALID_CONNECTION_GENERATION = "invalid_connection_generation"
    MALFORMED_SERVICE_INVENTORY = "malformed_service_inventory"
    MALFORMED_METADATA = "malformed_metadata"
    SERVICE_NOT_ADVERTISED = "service_not_advertised"
    REQUEST_ENDPOINT_MISSING = "request_endpoint_missing"
    RESPONSE_ENDPOINT_MISSING = "response_endpoint_missing"
    REQUEST_ENDPOINT_AMBIGUOUS = "request_endpoint_ambiguous"
    RESPONSE_ENDPOINT_AMBIGUOUS = "response_endpoint_ambiguous"
    REQUEST_ENDPOINT_WRONG_SERVICE = "request_endpoint_wrong_service"
    RESPONSE_ENDPOINT_WRONG_SERVICE = "response_endpoint_wrong_service"
    RESPONSE_WRITE_UNAVAILABLE = "response_write_unavailable"
    NOTIFY_UNAVAILABLE = "notify_unavailable"
    CCCD_NOT_ADVERTISED = "cccd_not_advertised"
    CCCD_AMBIGUOUS = "cccd_ambiguous"
    TARGET_IDENTITY_MISSING = "target_identity_missing"
    TARGET_IDENTITY_AMBIGUOUS = "target_identity_ambiguous"
    TARGET_GENERATION_MISMATCH = "target_generation_mismatch"
    TARGET_METADATA_MISMATCH = "target_metadata_mismatch"


_ROUTE_UUIDS = {
    VendorGattRoute.MAIN: (
        VENDOR_CHARACTERISTIC_33F3,
        VENDOR_CHARACTERISTIC_33F4,
    ),
    VendorGattRoute.RAW: (
        VENDOR_CHARACTERISTIC_33F5,
        VENDOR_CHARACTERISTIC_33F6,
    ),
}
_CCCD = uuid16(0x2902)


class VendorGattPreflightResult:
    __slots__ = (
        "_route",
        "_code",
        "_request_target",
        "_response_target",
        "_cccd_target",
        "_cccd_advertised",
    )

    def __init__(
        self,
        route: VendorGattRoute,
        code: VendorGattPreflightCode,
        request_target: GattCharacteristicTarget | None = None,
        response_target: GattCharacteristicTarget | None = None,
        cccd_target: GattDescriptorTarget | None = None,
        cccd_advertised: bool = False,
    ) -> None:
        object.__setattr__(self, "_route", route)
        object.__setattr__(self, "_code", code)
        object.__setattr__(self, "_request_target", request_target)
        object.__setattr__(self, "_response_target", response_target)
        object.__setattr__(self, "_cccd_target", cccd_target)
        object.__setattr__(self, "_cccd_advertised", cccd_advertised)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("vendor GATT preflight results are immutable")

    @property
    def route(self) -> VendorGattRoute:
        return self._route

    @property
    def code(self) -> VendorGattPreflightCode:
        return self._code

    @property
    def request_target(self) -> GattCharacteristicTarget | None:
        return self._request_target

    @property
    def response_target(self) -> GattCharacteristicTarget | None:
        return self._response_target

    @property
    def cccd_target(self) -> GattDescriptorTarget | None:
        return self._cccd_target

    @property
    def cccd_advertised(self) -> bool:
        return self._cccd_advertised

    @property
    def structurally_ready(self) -> bool:
        """Whether fields align, without claiming transport ownership of targets."""

        return self.code is VendorGattPreflightCode.STRUCTURALLY_READY

    @property
    def runnable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False

    @property
    def owner_authorized(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            "VendorGattPreflightResult("
            f"route={self.route.value!r}, code={self.code.value!r}, "
            f"structurally_ready={self.structurally_ready!r}, has_request_target="
            f"{self.request_target is not None!r}, has_response_target="
            f"{self.response_target is not None!r}, "
            f"has_cccd_target={self.cccd_target is not None!r}, "
            f"cccd_advertised={self.cccd_advertised!r}, runnable=False, "
            "hardware_eligible=False, hardware_verified=False, "
            "owner_authorized=False)"
        )

    def public_payload(self) -> dict[str, object]:
        return {
            "route": self.route.value,
            "code": self.code.value,
            "structurally_ready": self.structurally_ready,
            "has_request_target": self.request_target is not None,
            "has_response_target": self.response_target is not None,
            "has_cccd_target": self.cccd_target is not None,
            "cccd_advertised": self.cccd_advertised,
            "runnable": False,
            "hardware_eligible": False,
            "hardware_verified": False,
            "owner_authorized": False,
        }


def _failure(
    route: VendorGattRoute, code: VendorGattPreflightCode
) -> VendorGattPreflightResult:
    return VendorGattPreflightResult(route=route, code=code)


def _uuid(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


def _valid_string_tuple(value: object) -> bool:
    return isinstance(value, tuple) and all(isinstance(item, str) for item in value)


def _metadata_is_well_formed(record: object) -> bool:
    if type(record) is not GattCharacteristicMetadata:
        return False
    if _uuid(record.service_uuid) is None or _uuid(record.uuid) is None:
        return False
    if not _valid_string_tuple(record.properties):
        return False
    if len({value.casefold() for value in record.properties}) != len(
        record.properties
    ):
        return False
    if not _valid_string_tuple(record.descriptor_uuids):
        return False
    if any(_uuid(value) is None for value in record.descriptor_uuids):
        return False
    if not _valid_string_tuple(record.descriptor_instance_ids):
        return False
    if record.descriptor_instance_ids and len(record.descriptor_instance_ids) != len(
        record.descriptor_uuids
    ):
        return False
    if len(set(record.descriptor_instance_ids)) != len(record.descriptor_instance_ids):
        return False
    if record.instance_id is not None and (
        not isinstance(record.instance_id, str) or not record.instance_id
    ):
        return False
    target = record.target
    if target is None:
        return True
    if type(target) is not GattCharacteristicTarget:
        return False
    return (
        isinstance(target.connection_generation, int)
        and not isinstance(target.connection_generation, bool)
        and target.connection_generation > 0
        and _uuid(target.service_uuid) is not None
        and _uuid(target.uuid) is not None
        and isinstance(target.instance_id, str)
        and bool(target.instance_id)
    )


def _endpoint(
    route: VendorGattRoute,
    records: tuple[GattCharacteristicMetadata, ...],
    endpoint_uuid: str,
    *,
    missing: VendorGattPreflightCode,
    ambiguous: VendorGattPreflightCode,
    wrong_service: VendorGattPreflightCode,
) -> GattCharacteristicMetadata | VendorGattPreflightResult:
    matches = tuple(
        record for record in records if _uuid(record.uuid) == endpoint_uuid
    )
    if not matches:
        return _failure(route, missing)
    if len(matches) != 1:
        return _failure(route, ambiguous)
    if _uuid(matches[0].service_uuid) != VENDOR_SERVICE_56FF:
        return _failure(route, wrong_service)
    return matches[0]


def resolve_vendor_gatt_route(
    route: VendorGattRoute,
    *,
    services: set[str] | frozenset[str],
    metadata: tuple[GattCharacteristicMetadata, ...],
    connection_generation: int,
) -> VendorGattPreflightResult:
    """Resolve one closed route from a connection's metadata without performing I/O."""

    if type(route) is not VendorGattRoute:
        raise TypeError("route must be an exact VendorGattRoute")
    if (
        isinstance(connection_generation, bool)
        or not isinstance(connection_generation, int)
        or connection_generation <= 0
    ):
        return _failure(route, VendorGattPreflightCode.INVALID_CONNECTION_GENERATION)
    if not isinstance(services, (set, frozenset)) or any(
        _uuid(service) is None for service in services
    ):
        return _failure(route, VendorGattPreflightCode.MALFORMED_SERVICE_INVENTORY)
    normalized_services = {_uuid(service) for service in services}
    if VENDOR_SERVICE_56FF not in normalized_services:
        return _failure(route, VendorGattPreflightCode.SERVICE_NOT_ADVERTISED)
    if not isinstance(metadata, tuple) or not all(
        _metadata_is_well_formed(record) for record in metadata
    ):
        return _failure(route, VendorGattPreflightCode.MALFORMED_METADATA)
    request_uuid, response_uuid = _ROUTE_UUIDS[route]
    request = _endpoint(
        route,
        metadata,
        request_uuid,
        missing=VendorGattPreflightCode.REQUEST_ENDPOINT_MISSING,
        ambiguous=VendorGattPreflightCode.REQUEST_ENDPOINT_AMBIGUOUS,
        wrong_service=VendorGattPreflightCode.REQUEST_ENDPOINT_WRONG_SERVICE,
    )
    if isinstance(request, VendorGattPreflightResult):
        return request
    response = _endpoint(
        route,
        metadata,
        response_uuid,
        missing=VendorGattPreflightCode.RESPONSE_ENDPOINT_MISSING,
        ambiguous=VendorGattPreflightCode.RESPONSE_ENDPOINT_AMBIGUOUS,
        wrong_service=VendorGattPreflightCode.RESPONSE_ENDPOINT_WRONG_SERVICE,
    )
    if isinstance(response, VendorGattPreflightResult):
        return response

    instance_ids = tuple(
        record.instance_id for record in metadata if record.instance_id is not None
    )
    if len(set(instance_ids)) != len(instance_ids):
        return _failure(route, VendorGattPreflightCode.TARGET_IDENTITY_AMBIGUOUS)

    request_properties = {value.casefold() for value in request.properties}
    response_properties = {value.casefold() for value in response.properties}
    if "write" not in request_properties:
        return _failure(route, VendorGattPreflightCode.RESPONSE_WRITE_UNAVAILABLE)
    if "notify" not in response_properties:
        return _failure(route, VendorGattPreflightCode.NOTIFY_UNAVAILABLE)
    cccd_count = sum(
        _uuid(descriptor) == _CCCD for descriptor in response.descriptor_uuids
    )
    if cccd_count == 0:
        return _failure(route, VendorGattPreflightCode.CCCD_NOT_ADVERTISED)
    if cccd_count != 1:
        return _failure(route, VendorGattPreflightCode.CCCD_AMBIGUOUS)
    if len(response.descriptor_instance_ids) != len(response.descriptor_uuids):
        return _failure(route, VendorGattPreflightCode.TARGET_IDENTITY_MISSING)
    cccd_index = next(
        index
        for index, descriptor in enumerate(response.descriptor_uuids)
        if _uuid(descriptor) == _CCCD
    )
    cccd_instance_id = response.descriptor_instance_ids[cccd_index]
    if not cccd_instance_id:
        return _failure(route, VendorGattPreflightCode.TARGET_IDENTITY_MISSING)

    request_target = request.target
    response_target = response.target
    if (
        request_target is None
        or response_target is None
        or request.instance_id is None
        or response.instance_id is None
    ):
        return _failure(route, VendorGattPreflightCode.TARGET_IDENTITY_MISSING)
    if request_target.connection_generation != connection_generation or (
        response_target.connection_generation != connection_generation
    ):
        return _failure(route, VendorGattPreflightCode.TARGET_GENERATION_MISMATCH)
    if request_target.instance_id == response_target.instance_id:
        return _failure(route, VendorGattPreflightCode.TARGET_IDENTITY_AMBIGUOUS)
    for record, target in (
        (request, request_target),
        (response, response_target),
    ):
        if (
            _uuid(target.service_uuid) != _uuid(record.service_uuid)
            or _uuid(target.uuid) != _uuid(record.uuid)
            or target.instance_id != record.instance_id
        ):
            return _failure(route, VendorGattPreflightCode.TARGET_METADATA_MISMATCH)

    return VendorGattPreflightResult(
        route=route,
        code=VendorGattPreflightCode.STRUCTURALLY_READY,
        request_target=request_target,
        response_target=response_target,
        cccd_target=GattDescriptorTarget(
            connection_generation=connection_generation,
            service_uuid=VENDOR_SERVICE_56FF,
            characteristic_uuid=response_uuid,
            characteristic_instance_id=response_target.instance_id,
            uuid=_CCCD,
            instance_id=cccd_instance_id,
        ),
        cccd_advertised=True,
    )


__all__ = [
    "VendorGattPreflightCode",
    "VendorGattPreflightResult",
    "VendorGattRoute",
    "resolve_vendor_gatt_route",
]
