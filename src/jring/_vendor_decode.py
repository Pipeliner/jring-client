"""Shared primitives for callback-faithful offline vendor decoding."""

from .protocol import ProtocolError


def apk_hex_u32(field: bytes) -> int:
    """Mirror Java Integer.parseInt(hex, 16) for a four-byte LE field."""

    if len(field) != 4:
        raise ProtocolError("vendor integer field must be exactly four bytes")
    value = int.from_bytes(field, "little")
    if value > 0x7FFFFFFF:
        raise ProtocolError("vendor integer value exceeds APK signed range")
    return value
