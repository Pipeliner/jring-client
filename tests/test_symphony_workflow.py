from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = (ROOT / "WORKFLOW.md").read_text(encoding="utf-8")
TEXT = " ".join(WORKFLOW.split())
ROADMAP = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
JTBD = (ROOT / "docs" / "JTBD.md").read_text(encoding="utf-8")
ROADMAP_TEXT = " ".join(ROADMAP.split())
JTBD_TEXT = " ".join(JTBD.split())


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


def test_complete_implementation_tracker_is_milestoned_and_decision_complete():
    for milestone in range(7):
        assert f"M{milestone} —" in ROADMAP
    for issue in range(32, 49):
        assert f"issues/{issue}" in ROADMAP
    for status in (
        "hardware_verified",
        "proven_unavailable",
        "blocked_vendor_authorization",
        "unsafe",
        "excluded_non_ring",
    ):
        assert f"`{status}`" in ROADMAP
    assert "Fish completion remains out of scope" in ROADMAP_TEXT
    assert "JSON Lines, MPRIS, and allowlisted `uinput`" in JTBD_TEXT
    assert "Vendor accounts, advertising/social integrations, and Android-only plumbing" in JTBD_TEXT
