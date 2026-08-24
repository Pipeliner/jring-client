import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPDX = "MIT"
NOTICE = "Copyright (c) 2026 JRing Client contributors"


def test_mit_license_text_and_notice_are_present():
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")

    assert license_text.startswith(f"MIT License\n\n{NOTICE}\n\n")
    assert "Permission is hereby granted, free of charge" in license_text
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in license_text
    assert license_text.endswith("DEALINGS IN THE\nSOFTWARE.\n")


def test_repository_and_package_license_declarations_agree():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    decision = (ROOT / "docs" / "LICENSE_DECISION.md").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    project_block = pyproject.split("[project]", 1)[1].split("[project.", 1)[0]
    assert re.search(r'^license = "MIT"$', project_block, re.MULTILINE)
    assert re.search(r'^license-files = \["LICENSE"\]$', project_block, re.MULTILINE)
    assert "[MIT License](LICENSE)" in readme
    assert "[MIT License](LICENSE)" in contributing
    assert "SPDX identifier: **MIT**" in decision
    assert "Status: **selected and implemented**" in decision
    assert "include LICENSE" in manifest.splitlines()
