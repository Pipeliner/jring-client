import pytest

from jring.diagnostics import Redactor
from jring.discovery import discover, select_exact


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
