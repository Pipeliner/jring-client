from dataclasses import asdict
import json

import jring.vendor_input_preview as preview_module
import pytest
from jring.input import SensorEvent
from jring.vendor_protocol import parse_vendor_step_counter


def test_synthetic_vendor_step_bridge_uses_decoder_baseline_and_exact_increment(
    monkeypatch,
):
    decoded_frames = []

    def tracking_decoder(frame):
        decoded_frames.append(frame)
        return parse_vendor_step_counter(frame)

    monkeypatch.setattr(preview_module, "parse_vendor_step_counter", tracking_decoder)

    result = preview_module.synthetic_vendor_step_preview()

    assert len(decoded_frames) == 2
    assert all(type(frame) is bytes and len(frame) == 20 for frame in decoded_frames)
    assert [frame[0] for frame in decoded_frames] == [0x51, 0x51]
    assert result.event == SensorEvent("step")
    assert result.source == "synthetic_vendor_cumulative_counter"
    assert result.counter_semantics == "baseline_then_exact_single_increment"
    assert result.baseline_established is True
    assert result.exact_single_increment is True
    assert result.live_available is False
    assert result.hardware_verified is False
    assert result.input_emitted is False


def test_vendor_step_preview_exposes_no_frame_counter_or_runtime_identity():
    result = preview_module.synthetic_vendor_step_preview()
    rendered = json.dumps(asdict(result), sort_keys=True)

    assert set(asdict(result)) == {
        "event",
        "source",
        "counter_semantics",
        "baseline_established",
        "exact_single_increment",
        "live_available",
        "hardware_verified",
        "input_emitted",
    }
    assert all(
        private not in rendered
        for private in (
            "cumulative_steps",
            "frame",
            "payload",
            "observed_at",
            "epoch",
            "address",
            "path",
            "target",
        )
    )
    assert "SyntheticVendorStepPreview" in repr(result)
    assert "hardware_verified=False" in repr(result)
    assert result.event.kind in repr(result)
    assert result.source in repr(result)
    with pytest.raises(TypeError, match="bridge-owned"):
        preview_module.SyntheticVendorStepPreview(
            event=SensorEvent("not-step"),
            live_available=True,
            hardware_verified=True,
            input_emitted=True,
        )


def test_vendor_step_preview_fails_closed_when_baseline_is_not_silent(monkeypatch):
    class UnsafeAdapter:
        def __init__(self, *, minimum_interval):
            assert minimum_interval == 0.5

        def observe(self, **_kwargs):
            return SensorEvent("step")

    monkeypatch.setattr(preview_module, "ExperimentalStepCounterAdapter", UnsafeAdapter)

    try:
        preview_module.synthetic_vendor_step_preview()
    except RuntimeError as exc:
        assert str(exc) == "synthetic vendor step baseline was not silent"
    else:
        raise AssertionError("unsafe baseline must fail closed")
