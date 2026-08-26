"""Closed, non-runnable registry for all recovered vendor callback declarations."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .vendor_callback_surfaces import recovered_callback_behavior_surfaces
from .vendor_coverage import static_vendor_callback_coverage
from .vendor_request_callback_correlation import recovered_request_callback_correlations


class CallbackEventPrivacy(str, Enum):
    NONE = "none"
    DEVICE_OR_HEALTH_DATA = "device_or_health_data"
    IDENTIFIER_OR_PRIVATE_DATA = "identifier_or_private_data"
    UNKNOWN = "unknown"


class CallbackSemanticConfidence(str, Enum):
    STATIC_DECODER = "static_decoder"
    STATIC_BEHAVIOR = "static_behavior"
    DECLARATION_ONLY = "declaration_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True, init=False, repr=False)
class CallbackEventRegistryRow:
    callback_id: str
    origin: str
    privacy: CallbackEventPrivacy
    confidence: CallbackSemanticConfidence
    related_operations: tuple[str, ...]
    ordering_policy: str
    input_eligible: bool
    live_eligible: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("callback event registry rows are closed")


def recovered_callback_event_registry() -> tuple[CallbackEventRegistryRow, ...]:
    surfaces = {row.name: row for row in recovered_callback_behavior_surfaces()}
    relations: dict[str, list[str]] = {}
    for row in recovered_request_callback_correlations().rows:
        for callback in row.callbacks:
            relations.setdefault(callback, []).append(row.request)
    rows = []
    for callback in static_vendor_callback_coverage():
        surface = surfaces.get(callback.name)
        privacy = (CallbackEventPrivacy.IDENTIFIER_OR_PRIVATE_DATA if surface and surface.privacy_classes else CallbackEventPrivacy.DEVICE_OR_HEALTH_DATA if callback.python_state.value.startswith("offline_response") else CallbackEventPrivacy.UNKNOWN)
        confidence = (CallbackSemanticConfidence.STATIC_DECODER if callback.python_state.value == "offline_response_codec" else CallbackSemanticConfidence.STATIC_BEHAVIOR if surface else CallbackSemanticConfidence.DECLARATION_ONLY if callback.source == "declared_without_invocation" else CallbackSemanticConfidence.UNKNOWN)
        value = object.__new__(CallbackEventRegistryRow)
        for name, item in {"callback_id": callback.name, "origin": callback.source, "privacy": privacy, "confidence": confidence, "related_operations": tuple(sorted(relations.get(callback.name, ()))), "ordering_policy": "counter_or_marker_required_else_unsequenced", "input_eligible": False, "live_eligible": False}.items():
            object.__setattr__(value, name, item)
        rows.append(value)
    if len(rows) != 105 or len({row.callback_id for row in rows}) != len(rows):
        raise RuntimeError("callback_event_registry_not_closed")
    return tuple(rows)


def callback_event_registry_payload() -> dict[str, object]:
    rows = recovered_callback_event_registry()
    return {"schema_version": 1, "callback_count": len(rows), "live_eligible_count": 0, "input_eligible_count": 0, "rows": [{"callback_id": row.callback_id, "origin": row.origin, "privacy": row.privacy.value, "confidence": row.confidence.value, "related_operations": list(row.related_operations), "ordering_policy": row.ordering_policy, "input_eligible": False, "live_eligible": False} for row in rows]}
