from dataclasses import FrozenInstanceError

import pytest

from jring.vendor_prior_art_hypotheses import PriorArtHypothesis, prior_art_hypotheses_payload, recovered_prior_art_hypotheses
from jring.vendor_runtime_scope_eligibility import recovered_runtime_scope_eligibility


def test_external_hypotheses_are_ranked_explicitly_speculative_and_non_authorizing():
    rows = recovered_prior_art_hypotheses()
    assert [row.confidence.value for row in rows] == ["high", "high", "high", "medium", "medium"]
    assert all(row.evidence_url.startswith("https://") and row.runtime_authority is False for row in rows)
    payload = prior_art_hypotheses_payload()
    assert payload["speculative"] is True and payload["runtime_authority"] is False
    assert recovered_runtime_scope_eligibility().rows == ()


def test_hypotheses_are_closed():
    row = recovered_prior_art_hypotheses()[0]
    with pytest.raises(TypeError, match="closed"):
        PriorArtHypothesis()
    with pytest.raises(FrozenInstanceError):
        row.runtime_authority = True
