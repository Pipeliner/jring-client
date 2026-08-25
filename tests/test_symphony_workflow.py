from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = (ROOT / "WORKFLOW.md").read_text(encoding="utf-8")
TEXT = " ".join(WORKFLOW.split())


def test_symphony_workflow_closes_issue_and_verification_contracts():
    assert all(label in TEXT for label in ("`symphony`", "`jtbd`", "`sdd`", "`tdd`"))
    for evidence in (
        "RED-first test",
        "both full test environments",
        "scripts/evidence_tool.py scan",
        "git diff --check",
        "adversarial UX review",
        "single issue workpad",
        "Create a new fully specified issue",
    ):
        assert evidence in TEXT


def test_symphony_workflow_requires_commits_pushes_and_external_write_boundaries():
    assert "Commit the verified slice" in TEXT
    assert "Run every `gh` command outside the sandbox" in TEXT
    assert "Push completed work unless the operator explicitly says otherwise" in TEXT
    assert "public publication" in TEXT
    assert "explicit authorization for that publication scope" in TEXT


def test_symphony_workflow_cannot_authorize_hardware_or_package_publication():
    for blocked in (
        "radio activation",
        "BLE subscription",
        "GATT/vendor write",
        "RFCOMM connection",
        "`/dev/uinput` emission",
        "PyPI Trusted Publisher identity",
    ):
        assert blocked in TEXT
    assert "A passing local suite does not imply CI success" in TEXT
