"""Closed aggregate evidence for recovered request/callback Binder parity."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._vendor_binder_rows import CALLBACK_BINDER_ROWS, REQUEST_BINDER_ROWS
from .vendor_app_use_evidence import recovered_vendor_app_use_evidence
from .vendor_codec_registry import CALLBACK_CODEC_LOCATORS, REQUEST_CODEC_LOCATORS


class BinderDirection(str, Enum):
    REQUEST = "request"
    CALLBACK = "callback"


@dataclass(frozen=True, init=False, repr=False)
class BinderTransactionRow:
    ledger_name: str
    direction: BinderDirection
    transaction_id: int
    semantic_argument_kinds: tuple[str, ...]
    parcel_argument_kinds: tuple[str, ...]
    semantic_result_kind: str
    parcel_result_kind: str
    arity: int
    runtime_dispatch_evidence: str
    wire_relationship_kind: str
    opaque_semantic_group: str | None
    codec_locator_status: str

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("Binder transaction evidence is closed")

    @property
    def call_mode(self) -> str:
        return "synchronous"

    @property
    def interface_proxy_stub_implementation_match(self) -> bool:
        return True

    @property
    def runnable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False


@dataclass(frozen=True, init=False, repr=False)
class BinderInterfaceSurface:
    direction: BinderDirection
    rows: tuple[BinderTransactionRow, ...]
    transaction_ids: tuple[int, ...]
    declaration_count: int
    proxy_method_count: int
    stub_dispatch_count: int
    implementation_count: int
    synchronous_transaction_count: int
    one_way_transaction_count: int
    reply_parcel_count: int
    exception_handshake_count: int
    proxy_stub_id_mismatch_count: int
    prototype_mismatch_count: int
    parcel_order_mismatch_count: int
    overloaded_method_count: int
    distinct_semantic_shape_count: int
    distinct_parcel_shape_count: int
    semantic_result_kind_counts: tuple[tuple[str, int], ...]
    parcel_result_kind_counts: tuple[tuple[str, int], ...]
    arity_counts: tuple[tuple[int, int], ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("Binder interface evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredVendorBinderEvidence:
    request: BinderInterfaceSurface
    callback: BinderInterfaceSurface
    trailing_data_rejection_observed: bool
    exhaustive_semantic_alias_partition_established: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("vendor Binder evidence is closed")

    @property
    def total_transaction_count(self) -> int:
        return self.request.declaration_count + self.callback.declaration_count

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def evidence_scope(self) -> str:
        return "binder_interface_proxy_stub_implementation_parity"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def hardware_eligible(self) -> bool:
        return False

    @property
    def hardware_verified(self) -> bool:
        return False


def _surface(
    direction: BinderDirection,
    raw_rows: tuple[tuple[object, ...], ...],
    *,
    distinct_semantic_shape_count: int,
    distinct_parcel_shape_count: int,
    semantic_result_kind_counts: tuple[tuple[str, int], ...],
    parcel_result_kind_counts: tuple[tuple[str, int], ...],
    arity_counts: tuple[tuple[int, int], ...],
) -> BinderInterfaceSurface:
    rows = []
    app_use = recovered_vendor_app_use_evidence()
    runtime_by_name = {
        row.name: row.state.value
        for row in (
            app_use.requests
            if direction is BinderDirection.REQUEST
            else app_use.callbacks
        )
    }
    locators = (
        REQUEST_CODEC_LOCATORS
        if direction is BinderDirection.REQUEST
        else CALLBACK_CODEC_LOCATORS
    )
    for raw in raw_rows:
        row = object.__new__(BinderTransactionRow)
        names = (
            "ledger_name", "transaction_id", "semantic_argument_kinds",
            "parcel_argument_kinds", "semantic_result_kind", "parcel_result_kind",
            "arity",
        )
        for name, value in zip(names, raw, strict=True):
            object.__setattr__(row, name, value)
        object.__setattr__(row, "direction", direction)
        object.__setattr__(
            row, "runtime_dispatch_evidence", runtime_by_name[row.ledger_name]
        )
        object.__setattr__(
            row, "wire_relationship_kind", "not_exhaustively_classified"
        )
        object.__setattr__(row, "opaque_semantic_group", None)
        locator = locators.get(row.ledger_name)
        object.__setattr__(
            row,
            "codec_locator_status",
            "no_offline_codec_locator" if locator is None else locator.kind.value,
        )
        rows.append(row)
    row_tuple = tuple(rows)
    count = len(row_tuple)
    surface = object.__new__(BinderInterfaceSurface)
    values = {
        "direction": direction,
        "rows": row_tuple,
        "transaction_ids": tuple(range(1, count + 1)),
        "declaration_count": count,
        "proxy_method_count": count,
        "stub_dispatch_count": count,
        "implementation_count": count,
        "synchronous_transaction_count": count,
        "one_way_transaction_count": 0,
        "reply_parcel_count": count,
        "exception_handshake_count": count,
        "proxy_stub_id_mismatch_count": 0,
        "prototype_mismatch_count": 0,
        "parcel_order_mismatch_count": 0,
        "overloaded_method_count": 0,
        "distinct_semantic_shape_count": distinct_semantic_shape_count,
        "distinct_parcel_shape_count": distinct_parcel_shape_count,
        "semantic_result_kind_counts": semantic_result_kind_counts,
        "parcel_result_kind_counts": parcel_result_kind_counts,
        "arity_counts": arity_counts,
    }
    for name, value in values.items():
        object.__setattr__(surface, name, value)
    return surface


_REQUEST = _surface(
    BinderDirection.REQUEST,
    REQUEST_BINDER_ROWS,
    distinct_semantic_shape_count=36,
    distinct_parcel_shape_count=28,
    semantic_result_kind_counts=(
        ("int32", 102), ("void", 6), ("string", 2), ("bool", 2),
    ),
    parcel_result_kind_counts=(("int32", 104), ("void", 6), ("string", 2)),
    arity_counts=(
        (0, 27), (1, 54), (2, 11), (3, 6), (4, 7), (5, 2),
        (6, 1), (7, 2), (8, 1), (16, 1),
    ),
)
_CALLBACK = _surface(
    BinderDirection.CALLBACK,
    CALLBACK_BINDER_ROWS,
    distinct_semantic_shape_count=33,
    distinct_parcel_shape_count=31,
    semantic_result_kind_counts=(("void", 103), ("int32", 2)),
    parcel_result_kind_counts=(("void", 103), ("int32", 2)),
    arity_counts=(
        (0, 6), (1, 57), (2, 18), (3, 5), (4, 9), (5, 5),
        (6, 1), (8, 2), (9, 1), (11, 1),
    ),
)

_EVIDENCE = object.__new__(RecoveredVendorBinderEvidence)
object.__setattr__(_EVIDENCE, "request", _REQUEST)
object.__setattr__(_EVIDENCE, "callback", _CALLBACK)
object.__setattr__(_EVIDENCE, "trailing_data_rejection_observed", False)
object.__setattr__(
    _EVIDENCE, "exhaustive_semantic_alias_partition_established", False
)


def recovered_vendor_binder_evidence() -> RecoveredVendorBinderEvidence:
    """Return immutable sanitized aggregate Binder evidence."""

    return _EVIDENCE


__all__ = [
    "BinderDirection",
    "BinderInterfaceSurface",
    "BinderTransactionRow",
    "RecoveredVendorBinderEvidence",
    "recovered_vendor_binder_evidence",
]
