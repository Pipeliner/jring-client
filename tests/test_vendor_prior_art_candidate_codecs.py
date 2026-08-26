from dataclasses import FrozenInstanceError
import pytest
from jring.vendor_prior_art_candidate_codecs import PriorArtCandidateError, SpeculativeCombinedMeasurement, SpeculativeHistoryFragmentKind, classify_speculative_heart_rate_history_fragment, parse_speculative_combined_measurement


def test_external_24_claim_is_a_pure_non_authorizing_candidate_decoder():
    result = parse_speculative_combined_measurement(bytes((0x24, 70, 120, 80, 98, 2, 3, 45, 30)))
    assert (result.heart_rate_bpm, result.systolic, result.diastolic, result.oxygen_percent) == (70, 120, 80, 98)
    assert result.provenance == "external_prior_art_unverified"
    assert result.runtime_authority is False
    with pytest.raises(FrozenInstanceError): result.runtime_authority = True
    with pytest.raises(TypeError, match="codec-owned"): SpeculativeCombinedMeasurement()


@pytest.mark.parametrize("payload", (b"", bytes(9), bytes((0x24,)) * 10))
def test_candidate_decoder_rejects_non_exact_external_claim(payload):
    with pytest.raises(PriorArtCandidateError, match="invalid_speculative"): parse_speculative_combined_measurement(payload)


@pytest.mark.parametrize("marker,kind", ((0xF0, "header"), (0xAA, "index"), (0xA0, "data"), (0xFF, "complete_marker")))
def test_external_16_history_claim_is_marker_classification_only(marker, kind):
    result = classify_speculative_heart_rate_history_fragment(bytes((0x16, marker)))
    assert result.kind.value == kind and result.provenance == "external_prior_art_unverified"
    assert result.runtime_authority is False


def test_unknown_or_malformed_external_history_claim_is_rejected():
    for payload in (b"", b"\x16", b"\x16\x01"):
        with pytest.raises(PriorArtCandidateError): classify_speculative_heart_rate_history_fragment(payload)
