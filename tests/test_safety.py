import pytest

from jring.diagnostics import Redactor
from jring.discovery import (
    DiscoveryObservation,
    build_selection_candidates,
    discover,
    select_exact,
)


def test_address_redaction_is_stable_but_not_reversible():
    redactor = Redactor(salt=b"test-salt")
    alias = redactor.address("AA:BB:CC:DD:EE:FF")
    assert alias.startswith("device-")
    assert "AA" not in alias
    assert alias == redactor.address("AA:BB:CC:DD:EE:FF")


def test_selection_requires_exact_explicit_address():
    with pytest.raises(ValueError):
        select_exact(None)
    assert select_exact("AA:BB:CC:DD:EE:FF") == "AA:BB:CC:DD:EE:FF"


def test_discovery_bounds_fail_before_loading_hardware_dependency():
    import asyncio
    with pytest.raises(ValueError):
        asyncio.run(discover(timeout=31))


def test_aliases_change_between_process_seeds_and_hide_addresses():
    observations = (
        DiscoveryObservation(
            address="AA:BB:CC:DD:EE:FF",
            name="JRing",
            service_uuids=("1812",),
            rssi=-48,
        ),
    )

    first = build_selection_candidates(observations, salt=b"first-process-seed")[0]
    second = build_selection_candidates(observations, salt=b"second-process-seed")[0]

    assert first.alias != second.alias
    assert "AA:BB" not in first.alias
    assert "AA:BB" not in repr(first)
    assert "AA:BB" not in str(first.public_summary())
    assert first.public_summary()["likely_jring_basis"] == "client_name_heuristic"
    assert first.connection_address() == "AA:BB:CC:DD:EE:FF"
