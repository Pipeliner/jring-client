from dataclasses import FrozenInstanceError
import pytest
from jring.vendor_prior_art_candidate_codecs import PriorArtCandidateError, SpeculativeCombinedMeasurement, parse_speculative_combined_measurement


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
