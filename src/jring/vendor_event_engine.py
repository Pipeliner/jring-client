"""Generation-bound neutral event projection with no payload or input authority."""
from __future__ import annotations

from .event_contracts import (ContractConfidence, ContractProvenance, DeadlineState, DeviceTimeState, EventRelationship, NeutralEventKind, ObservationWallTimeState, RingEvent, create_ring_event)
from .vendor_session_arbiter import ArbiterRoute, ArbiterToken, VendorSessionArbiter


class VendorEventEngine:
    def __init__(self, arbiter: VendorSessionArbiter) -> None:
        if type(arbiter) is not VendorSessionArbiter:
            raise TypeError("event engine requires exact session arbiter")
        self._arbiter = arbiter
        self._sequence = 0

    def observe(self, token: ArbiterToken, *, callback_id: str) -> RingEvent | None:
        route = self._arbiter.route_callback(token, callback_id=callback_id)
        if route is not ArbiterRoute.NEUTRAL_EVENT:
            return None
        self._sequence += 1
        return create_ring_event(
            semantic_kind=NeutralEventKind.UNKNOWN,
            relationship=EventRelationship.UNKNOWN,
            source_operation=None,
            sequence=self._sequence,
            connection_generation=token.generation,
            provenance=ContractProvenance.SYNTHETIC,
            confidence=ContractConfidence.STATIC_CANDIDATE,
            wall_time_state=ObservationWallTimeState.NOT_RECORDED,
            device_time_state=DeviceTimeState.NOT_PRESENT,
            deadline_state=DeadlineState.NOT_APPLICABLE,
        )
