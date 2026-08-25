from dataclasses import FrozenInstanceError, asdict, fields
import inspect
import json

import pytest

import jring.vendor_dispatcher_evidence as dispatcher_module
from jring.vendor_coverage import static_vendor_callback_coverage
from jring.vendor_dispatcher_evidence import recovered_dispatcher_evidence


def test_dispatcher_structure_distinguishes_targets_invokes_and_opcodes():
    evidence = recovered_dispatcher_evidence()

    assert evidence.token_comparison_count == 106
    assert evidence.routing_branch_comparison_count == 105
    assert evidence.distinct_casefolded_opcode_count == 104
    assert evidence.recognized_no_direct_callback_opcodes == (
        0x1C, 0x83, 0x8B, 0x8C, 0x9C,
    )
    assert evidence.callback_bearing_distinct_opcode_count == 99
    assert evidence.syntactic_callback_invoke_count == 125
    assert evidence.reachable_callback_invoke_count == 124
    assert evidence.shadowed_callback_invoke_count == 1
    assert evidence.unique_callback_target_count == 85
    assert evidence.unique_target_without_reachable_invoke_count == 0
    assert evidence.switch_instruction_count == 0
    assert evidence.switch_payload_count == 0
    assert evidence.minimum_token_count == 20


def test_callback_opcode_crosswalk_accounts_for_all_reachable_routes():
    evidence = recovered_dispatcher_evidence()
    rows = {row.callback: row for row in evidence.callback_routes}
    reachable = {
        opcode for row in rows.values() for opcode in row.reachable_opcodes
    }
    shadowed = {
        opcode for row in rows.values() for opcode in row.shadowed_opcodes
    }

    assert len(rows) == 85
    assert len(reachable) == 99
    assert not reachable.intersection(evidence.recognized_no_direct_callback_opcodes)
    assert reachable | set(evidence.recognized_no_direct_callback_opcodes) == set(
        evidence.recognized_opcodes
    )
    assert shadowed == {0x9A}
    assert rows["onSetGoalStep"].reachable_opcodes == (0x1A, 0x9A)
    assert rows["onSetEcgMode"].reachable_opcodes == (0x2A,)
    assert rows["onSetEcgMode"].shadowed_opcodes == (0x9A,)
    assert all(row.reachable_opcodes for row in rows.values())
    assert set(rows) <= {row.name for row in static_vendor_callback_coverage()}


def test_dispatcher_evidence_is_closed_sanitized_and_non_runnable():
    evidence = recovered_dispatcher_evidence()

    assert evidence is recovered_dispatcher_evidence()
    with pytest.raises(TypeError):
        type(evidence)()
    with pytest.raises(TypeError):
        type(evidence.callback_routes[0])()
    with pytest.raises(FrozenInstanceError):
        evidence.callback_routes = ()
    assert evidence.maturity == "static_apk_only"
    assert evidence.runnable is False
    assert evidence.python_callable is False
    assert evidence.hardware_eligible is False
    assert evidence.hardware_verified is False
    assert evidence.semantic_meanings_established is False

    forbidden = {
        "source", "path", "descriptor", "prototype", "fingerprint",
        "instruction_offset", "dex_digest", "payload", "frame",
    }
    for model in (type(evidence), type(evidence.callback_routes[0])):
        assert forbidden.isdisjoint(field.name for field in fields(model))
    serialized = json.dumps(asdict(evidence), sort_keys=True).lower()
    assert "sha256" not in serialized
    assert ".smali" not in serialized
    source = inspect.getsource(dispatcher_module).lower()
    assert "import pathlib" not in source
    assert "import subprocess" not in source
    assert "open(" not in source
