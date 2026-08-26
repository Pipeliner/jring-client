"""Ranked external JRing hypotheses; deliberately excluded from runtime authority."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PriorArtConfidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, init=False, repr=False)
class PriorArtHypothesis:
    identifier: str
    claim: str
    confidence: PriorArtConfidence
    evidence_url: str
    clean_room_state: str
    runtime_authority: bool

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("prior-art hypotheses are closed")


_ROWS = (
    ("frame-shape-20-byte-command-first", "Generic JRing traffic uses 20-byte command-first frames.", "high", "https://jw-tech.fr/en/blog/smart-ring-reverse-engineering", "corroborates existing static 20-byte builders; field meanings unverified"),
    ("family-56ff-jring", "A generic JRing family exposes a 56ff BLE service.", "high", "https://github.com/saksham2001/PulseLoopiOS", "corroborates APK UUID evidence; exact device/build unknown"),
    ("sr08-jring-alias", "SR08 is marketed for the JRing app and Smart_Ring pairing name.", "high", "https://manuals.plus/m/15d858d0c40176cef74f1a9cb4efb58d5ac8c1dc50c0dfd91032c0226bc88474", "retail alias only; no firmware equivalence"),
    ("combined-measurement-24", "A 0x24 measurement layout is claimed for one 56ff/JRing family.", "medium", "https://github.com/foureight84/PulseLoopAndroid", "external decoder claim; requires independent static and owner evidence"),
    ("history-16-and-10", "0x16 heart-rate and 0x10 activity history layouts are claimed for one 56ff/JRing family.", "medium", "https://github.com/foureight84/PulseLoopAndroid", "external decoder claim; terminal/order behavior unverified"),
)


def recovered_prior_art_hypotheses() -> tuple[PriorArtHypothesis, ...]:
    rows = []
    for identifier, claim, confidence, url, state in _ROWS:
        row = object.__new__(PriorArtHypothesis)
        for name, value in {"identifier": identifier, "claim": claim, "confidence": PriorArtConfidence(confidence), "evidence_url": url, "clean_room_state": state, "runtime_authority": False}.items():
            object.__setattr__(row, name, value)
        rows.append(row)
    return tuple(rows)


def prior_art_hypotheses_payload() -> dict[str, object]:
    rows = recovered_prior_art_hypotheses()
    return {"schema_version": 1, "speculative": True, "runtime_authority": False, "rows": [{"id": row.identifier, "claim": row.claim, "confidence": row.confidence.value, "evidence_url": row.evidence_url, "clean_room_state": row.clean_room_state, "runtime_authority": False} for row in rows]}
