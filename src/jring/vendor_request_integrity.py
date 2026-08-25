"""Identity-bound seals for closed offline vendor request objects.

The seal is process-local and contains no publication or hardware authority.  It keeps
the exact private frame bytes outside dataclass fields and representations so a request
cannot be altered after its typed encoder validates it and then promoted into a fake
executable operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from weakref import WeakKeyDictionary


class _RequestIntegrityToken:
    def __copy__(self) -> "_RequestIntegrityToken":
        return self

    def __deepcopy__(self, _memo: dict[int, object]) -> "_RequestIntegrityToken":
        return self


@dataclass(frozen=True)
class _RequestIntegrityRecord:
    request_type: type
    operation: object = field(repr=False)
    frames: tuple[bytes, ...] = field(repr=False)


_REQUEST_INTEGRITY_RECORDS: WeakKeyDictionary[
    _RequestIntegrityToken, _RequestIntegrityRecord
] = WeakKeyDictionary()


def seal_vendor_request(
    request: object, *, operation: object, frames: tuple[bytes, ...]
) -> None:
    """Bind a newly validated typed request to its exact synthetic frame sequence."""

    if not frames or any(
        type(frame) is not bytes or len(frame) != 20 for frame in frames
    ):
        raise ValueError("request integrity requires exact 20-byte frames")
    token = _RequestIntegrityToken()
    object.__setattr__(request, "_request_integrity_token", token)
    _REQUEST_INTEGRITY_RECORDS[token] = _RequestIntegrityRecord(
        request_type=type(request),
        operation=operation,
        frames=tuple(frames),
    )


def validate_vendor_request(
    request: object, *, operation: object, frames: tuple[bytes, ...]
) -> None:
    """Fail closed when a sealed request's execution-relevant shape changed."""

    token = getattr(request, "_request_integrity_token", None)
    if type(token) is not _RequestIntegrityToken:
        raise ValueError("vendor request integrity identity was mutated")
    expected = _REQUEST_INTEGRITY_RECORDS.get(token)
    if expected is None:
        raise ValueError("vendor request integrity identity is unavailable")
    if (
        type(request) is not expected.request_type
        or operation is not expected.operation
        or type(frames) is not tuple
        or any(type(frame) is not bytes for frame in frames)
        or frames != expected.frames
    ):
        raise ValueError("vendor request integrity shape was mutated")


__all__ = ["seal_vendor_request", "validate_vendor_request"]
