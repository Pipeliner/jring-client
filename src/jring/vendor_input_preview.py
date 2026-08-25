"""Closed offline bridge from synthetic vendor counters to a neutral input event.

The bridge accepts no caller data and owns no transport or input sink. It exercises
the recovered cumulative-counter decoder, establishes a synthetic baseline, and
accepts exactly one isolated increment for preview. Nothing here is live or hardware
verified.
"""

from __future__ import annotations

from dataclasses import dataclass

from .input import ExperimentalStepCounterAdapter, SensorEvent
from .vendor_protocol import parse_vendor_step_counter


@dataclass(frozen=True, init=False, repr=False)
class SyntheticVendorStepPreview:
    event: SensorEvent
    source: str
    counter_semantics: str
    baseline_established: bool
    exact_single_increment: bool
    live_available: bool
    hardware_verified: bool
    input_emitted: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("synthetic vendor step previews are bridge-owned")

    @classmethod
    def _create(cls, event: SensorEvent) -> "SyntheticVendorStepPreview":
        if type(event) is not SensorEvent or event.kind != "step":
            raise TypeError("synthetic vendor step preview requires an exact step event")
        preview = object.__new__(cls)
        object.__setattr__(preview, "event", event)
        object.__setattr__(preview, "source", "synthetic_vendor_cumulative_counter")
        object.__setattr__(
            preview,
            "counter_semantics",
            "baseline_then_exact_single_increment",
        )
        object.__setattr__(preview, "baseline_established", True)
        object.__setattr__(preview, "exact_single_increment", True)
        object.__setattr__(preview, "live_available", False)
        object.__setattr__(preview, "hardware_verified", False)
        object.__setattr__(preview, "input_emitted", False)
        return preview

    def __repr__(self) -> str:
        return (
            "SyntheticVendorStepPreview(event='step', "
            "source='synthetic_vendor_cumulative_counter', "
            "counter_semantics='baseline_then_exact_single_increment', "
            "live_available=False, hardware_verified=False, input_emitted=False)"
        )


def _frame(cumulative_steps: int) -> bytes:
    return bytes((0x51,)) + cumulative_steps.to_bytes(4, "little") + bytes(15)


def synthetic_vendor_step_preview() -> SyntheticVendorStepPreview:
    """Exercise one closed baseline/+1 fixture through decoder and safe adapter."""

    adapter = ExperimentalStepCounterAdapter(minimum_interval=0.5)
    baseline = parse_vendor_step_counter(_frame(100))
    first = adapter.observe(
        connection_epoch=1,
        cumulative_steps=baseline.cumulative_steps,
        observed_at=1.0,
    )
    if first is not None:
        raise RuntimeError("synthetic vendor step baseline was not silent")

    increment = parse_vendor_step_counter(_frame(101))
    candidate = adapter.observe(
        connection_epoch=1,
        cumulative_steps=increment.cumulative_steps,
        observed_at=2.0,
    )
    if candidate is None or candidate.preview_event_kind != "step":
        raise RuntimeError("synthetic vendor step increment produced no safe preview")
    return SyntheticVendorStepPreview._create(
        SensorEvent(candidate.preview_event_kind)
    )


__all__ = ["SyntheticVendorStepPreview", "synthetic_vendor_step_preview"]
