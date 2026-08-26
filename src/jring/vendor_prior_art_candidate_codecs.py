"""Speculative external-protocol candidate codecs; never runtime or hardware authority."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PriorArtCandidateError(ValueError):
    pass


class SpeculativeHistoryFragmentKind(str, Enum):
    HEADER = "header"
    INDEX = "index"
    DATA = "data"
    COMPLETE_MARKER = "complete_marker"


@dataclass(frozen=True, init=False, repr=False)
class SpeculativeHistoryFragment:
    kind: SpeculativeHistoryFragmentKind
    provenance: str
    runtime_authority: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("speculative history fragments are codec-owned")


@dataclass(frozen=True, init=False, repr=False)
class SpeculativeCombinedMeasurement:
    heart_rate_bpm: int
    systolic: int
    diastolic: int
    oxygen_percent: int
    fatigue: int
    stress: int
    blood_sugar_tenths_mmol_l: int
    hrv_ms: int
    provenance: str
    runtime_authority: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("speculative candidate measurements are codec-owned")


def parse_speculative_combined_measurement(payload: bytes) -> SpeculativeCombinedMeasurement:
    """Parse the public prior-art 0x24/9-byte claim without retaining raw input."""
    if type(payload) is not bytes or len(payload) != 9 or payload[0] != 0x24:
        raise PriorArtCandidateError("invalid_speculative_combined_measurement")
    value = object.__new__(SpeculativeCombinedMeasurement)
    for name, item in {
        "heart_rate_bpm": payload[1], "systolic": payload[2], "diastolic": payload[3],
        "oxygen_percent": payload[4], "fatigue": payload[5], "stress": payload[6],
        "blood_sugar_tenths_mmol_l": payload[7], "hrv_ms": payload[8],
        "provenance": "external_prior_art_unverified", "runtime_authority": False,
    }.items(): object.__setattr__(value, name, item)
    return value


def classify_speculative_heart_rate_history_fragment(payload: bytes) -> SpeculativeHistoryFragment:
    """Classify only public 0x16 marker claims; do not decode or reassemble data."""
    if type(payload) is not bytes or len(payload) < 2 or payload[0] != 0x16:
        raise PriorArtCandidateError("invalid_speculative_history_fragment")
    kinds = {0xF0: SpeculativeHistoryFragmentKind.HEADER, 0xAA: SpeculativeHistoryFragmentKind.INDEX, 0xA0: SpeculativeHistoryFragmentKind.DATA, 0xFF: SpeculativeHistoryFragmentKind.COMPLETE_MARKER}
    try: kind = kinds[payload[1]]
    except KeyError as exc: raise PriorArtCandidateError("unknown_speculative_history_marker") from exc
    result = object.__new__(SpeculativeHistoryFragment)
    object.__setattr__(result, "kind", kind)
    object.__setattr__(result, "provenance", "external_prior_art_unverified")
    object.__setattr__(result, "runtime_authority", False)
    return result
