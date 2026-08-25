"""Offline-only clean-room codecs derived from static APK evidence.

Nothing in this module transmits to a ring. Static evidence establishes candidate
request bytes, not firmware support, response semantics, side effects, legitimate
session state, or hardware eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .uuids import VENDOR_CHARACTERISTIC_33F3


class StaticQuery(str, Enum):
    CURRENT_SPORT = "current_sport"
    BATTERY = "battery"
    DEVICE_INFO = "device_info"
    BAND_FUNCTIONS = "band_functions"
    MULTI_SPORT_DAY = "multi_sport_day"
    OXYGEN_DAY = "oxygen_day"
    ADVANCED_SENSOR_DAY = "advanced_sensor_day"


_ZERO_ARGUMENT_OPCODES = {
    StaticQuery.CURRENT_SPORT: 0x03,
    StaticQuery.BATTERY: 0x0B,
    StaticQuery.DEVICE_INFO: 0x0C,
    StaticQuery.BAND_FUNCTIONS: 0x20,
}
_DAY_OPCODES = {
    StaticQuery.MULTI_SPORT_DAY: 0x25,
    StaticQuery.OXYGEN_DAY: 0x40,
    StaticQuery.ADVANCED_SENSOR_DAY: 0x55,
}


@dataclass(frozen=True)
class StaticVendorRequest:
    operation: StaticQuery
    _encoded: bytes = field(default=b"", repr=False)

    @property
    def endpoint_uuid(self) -> str:
        return VENDOR_CHARACTERISTIC_33F3

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def hardware_eligible(self) -> bool:
        return False

    def synthetic_bytes_for_test(self) -> bytes:
        """Return the public synthetic vector for offline verification only."""

        return bytes(self._encoded)


def _request(operation: StaticQuery, *fields: int) -> StaticVendorRequest:
    encoded = bytes((operation_opcode(operation), *fields)) + bytes(19 - len(fields))
    return StaticVendorRequest(operation=operation, _encoded=encoded)


def operation_opcode(operation: StaticQuery) -> int:
    try:
        return (_ZERO_ARGUMENT_OPCODES | _DAY_OPCODES)[operation]
    except (KeyError, TypeError) as exc:
        raise ValueError("unsupported static query") from exc


def encode_static_query(operation: StaticQuery) -> StaticVendorRequest:
    if operation not in _ZERO_ARGUMENT_OPCODES:
        raise ValueError("query requires typed arguments or is unsupported")
    return _request(operation)


def encode_day_query(
    operation: StaticQuery, *, day_offset: int
) -> StaticVendorRequest:
    if operation not in _DAY_OPCODES:
        raise ValueError("query does not accept a day offset or is unsupported")
    if type(day_offset) is not int:
        raise TypeError("day offset must be an integer")
    if not 0 <= day_offset <= 0xFF:
        raise ValueError("day offset must fit one unsigned byte")
    return _request(operation, day_offset)
