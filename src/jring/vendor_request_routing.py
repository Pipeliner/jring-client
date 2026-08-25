"""Closed offline evidence for request packet and queue routing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vendor_coverage import static_vendor_operation_coverage


class RequestPacketShape(str, Enum):
    DETERMINISTIC_MAIN = "deterministic_main"
    DETERMINISTIC_RAW = "deterministic_raw"
    STATEFUL_SHARED_PREFLIGHT = "stateful_shared_preflight"
    CALLER_DIRECTED_DYNAMIC = "caller_directed_dynamic"
    DESCRIPTOR_CONTROL = "descriptor_control"
    INTERNAL_DFU = "internal_dfu"
    NO_FIXED_PACKET = "no_fixed_packet"


class RequestRouteRole(str, Enum):
    MAIN_TX_RX = "main_tx_rx"
    RAW_TX_RX = "raw_tx_rx"
    CALLER_SELECTED = "caller_selected"
    RAW_DESCRIPTOR = "raw_descriptor"
    DFU_INTERNAL = "dfu_internal"
    NONE = "none"


@dataclass(frozen=True, init=False, repr=False)
class RequestRoutingRow:
    name: str
    packet_shape: RequestPacketShape
    route_role: RequestRouteRole
    queue_type: int | None
    packet_layout_statically_identifiable: bool
    standalone_deterministic_offline_codec: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request routing evidence is closed")


@dataclass(frozen=True, init=False, repr=False)
class RecoveredRequestRoutingEvidence:
    requests: tuple[RequestRoutingRow, ...]
    session_constraints: tuple[str, ...]
    python_safety_rules: tuple[str, ...]

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("request routing evidence is closed")

    @property
    def standalone_deterministic_offline_count(self) -> int:
        return sum(row.standalone_deterministic_offline_codec for row in self.requests)

    @property
    def statically_identifiable_layout_count(self) -> int:
        return sum(row.packet_layout_statically_identifiable for row in self.requests)

    def _shape_count(self, shape: RequestPacketShape) -> int:
        return sum(row.packet_shape is shape for row in self.requests)

    @property
    def main_layout_count(self) -> int:
        return self._shape_count(RequestPacketShape.DETERMINISTIC_MAIN)

    @property
    def raw_layout_count(self) -> int:
        return self._shape_count(RequestPacketShape.DETERMINISTIC_RAW)

    @property
    def stateful_shared_layout_count(self) -> int:
        return self._shape_count(RequestPacketShape.STATEFUL_SHARED_PREFLIGHT)

    @property
    def dynamic_payload_count(self) -> int:
        return self._shape_count(RequestPacketShape.CALLER_DIRECTED_DYNAMIC)

    @property
    def descriptor_control_count(self) -> int:
        return self._shape_count(RequestPacketShape.DESCRIPTOR_CONTROL)

    @property
    def internal_dfu_count(self) -> int:
        return self._shape_count(RequestPacketShape.INTERNAL_DFU)

    @property
    def no_fixed_packet_count(self) -> int:
        return self._shape_count(RequestPacketShape.NO_FIXED_PACKET)

    @property
    def maturity(self) -> str:
        return "static_apk_only"

    @property
    def evidence_scope(self) -> str:
        return "request_queue_and_endpoint_roles"

    @property
    def runnable(self) -> bool:
        return False

    @property
    def python_callable(self) -> bool:
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


def _row(
    name: str,
    shape: RequestPacketShape,
    role: RequestRouteRole,
    queue_type: int | None,
    *,
    identifiable: bool,
    standalone: bool,
) -> RequestRoutingRow:
    row = object.__new__(RequestRoutingRow)
    object.__setattr__(row, "name", name)
    object.__setattr__(row, "packet_shape", shape)
    object.__setattr__(row, "route_role", role)
    object.__setattr__(row, "queue_type", queue_type)
    object.__setattr__(row, "packet_layout_statically_identifiable", identifiable)
    object.__setattr__(row, "standalone_deterministic_offline_codec", standalone)
    return row


def _classify(name: str, route: str) -> RequestRoutingRow:
    if route == "main_command":
        return _row(
            name, RequestPacketShape.DETERMINISTIC_MAIN,
            RequestRouteRole.MAIN_TX_RX, 0, identifiable=True, standalone=True,
        )
    if route == "raw_command":
        return _row(
            name, RequestPacketShape.DETERMINISTIC_RAW,
            RequestRouteRole.RAW_TX_RX, 1, identifiable=True, standalone=True,
        )
    if name == "getOtaInfo":
        return _row(
            name, RequestPacketShape.STATEFUL_SHARED_PREFLIGHT,
            RequestRouteRole.MAIN_TX_RX, 0, identifiable=True, standalone=False,
        )
    if name == "writeCharacteristic":
        return _row(
            name, RequestPacketShape.CALLER_DIRECTED_DYNAMIC,
            RequestRouteRole.CALLER_SELECTED, None,
            identifiable=False, standalone=False,
        )
    if name == "openRawDataNotification":
        return _row(
            name, RequestPacketShape.DESCRIPTOR_CONTROL,
            RequestRouteRole.RAW_DESCRIPTOR, None,
            identifiable=False, standalone=False,
        )
    if name == "startFileOta":
        return _row(
            name, RequestPacketShape.INTERNAL_DFU,
            RequestRouteRole.DFU_INTERNAL, None,
            identifiable=False, standalone=False,
        )
    return _row(
        name, RequestPacketShape.NO_FIXED_PACKET,
        RequestRouteRole.NONE, None, identifiable=False, standalone=False,
    )


_ROWS = tuple(
    _classify(operation.name, operation.route)
    for operation in static_vendor_operation_coverage()
)

_EVIDENCE = object.__new__(RecoveredRequestRoutingEvidence)
object.__setattr__(_EVIDENCE, "requests", _ROWS)
object.__setattr__(
    _EVIDENCE,
    "session_constraints",
    (
        "mutable_sdk_and_device_policy_status_guard",
        "shared_connection_state_predicate",
        "history_silence_dedup_and_priority_filters",
        "global_queue_send_gate_and_pending_payload",
        "write_callback_status_is_ignored",
        "accepted_dispatch_can_end_with_unknown_outcome",
        "response_wait_state_is_not_operation_bound",
    ),
)
object.__setattr__(
    _EVIDENCE,
    "python_safety_rules",
    (
        "owner_selection_is_separate_from_source_policy_status",
        "operation_and_connection_generation_must_bind_every_result",
        "automatic_retry_is_not_safe",
        "callback_arrival_is_not_peer_acknowledgement",
        "dynamic_writes_descriptor_control_and_dfu_remain_disabled",
    ),
)


def recovered_request_routing_evidence() -> RecoveredRequestRoutingEvidence:
    """Return immutable sanitized request-routing evidence."""

    return _EVIDENCE


__all__ = [
    "RecoveredRequestRoutingEvidence",
    "RequestPacketShape",
    "RequestRouteRole",
    "RequestRoutingRow",
    "recovered_request_routing_evidence",
]
