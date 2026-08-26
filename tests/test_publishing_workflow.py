import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-pypi.yml"
DOCUMENTATION = ROOT / "docs" / "PUBLISHING.md"
README = ROOT / "README.md"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def publish_job(text: str) -> str:
    return text.split("  publish-pypi:", 1)[1]


def validation_job(text: str) -> str:
    return text.split("  build-and-validate:", 1)[1].split("  publish-pypi:", 1)[0]


def test_manual_validation_and_protected_version_tags_trigger_publishing():
    workflow = workflow_text()

    assert "workflow_dispatch:" in workflow
    assert "push:" in workflow
    assert 'tags: ["v*"]' in workflow
    assert re.search(
        r"publish:\s*\n\s+description:.*\n\s+required: true\s*\n"
        r"\s+type: boolean\s*\n\s+default: false",
        workflow,
    )


def test_validation_builds_once_without_oidc_and_exercises_safe_paths():
    validation = validation_job(workflow_text())

    assert "contents: read" in validation
    assert "id-token: write" not in validation
    assert "python -m build" in validation
    assert "normalize-sdist" in validation
    assert "compare dist-a dist-b" in validation
    assert "inspect dist-a" in validation
    assert "check-version" in validation
    assert "python scripts/evidence_tool.py scan ." in validation
    assert "--no-index --no-deps" in validation
    assert "jring doctor --json" in validation
    assert "jring status --simulate --json" in validation
    assert "jring capabilities --simulate --json" in validation


def test_publish_job_is_tag_environment_and_protected_ref_gated():
    publish = publish_job(workflow_text())

    for gate in (
        "inputs.publish == true",
        "github.event_name == 'push'",
        "github.ref_type == 'tag'",
        "github.ref_protected == true",
        "startsWith(github.ref_name, 'v')",
    ):
        assert gate in publish
    assert "environment:" in publish
    assert "name: pypi" in publish
    assert "id-token: write" in publish
    assert "contents: write" not in publish


def test_automatic_tag_path_keeps_protection_and_manual_fallback():
    workflow = workflow_text()
    validation = validation_job(workflow)
    publish = publish_job(workflow)
    assert "github.event_name == 'push' && github.ref_type == 'tag'" in validation
    assert "PUBLISH_REQUESTED" in validation
    assert "github.event_name == 'push'" in publish
    assert "inputs.publish == true" in publish
    assert "GITHUB_REF_PROTECTED" in validation


def test_publish_job_downloads_the_exact_validated_artifact_and_only_publishes_it():
    workflow = workflow_text()
    validation = validation_job(workflow)
    publish = publish_job(workflow)

    assert "artifact-id: ${{ steps.upload.outputs.artifact-id }}" in validation
    assert "id: upload" in validation
    assert "dist/*.whl" in validation
    assert "dist/*.tar.gz" in validation
    assert "dist/SHA256SUMS" not in validation
    assert "artifact-ids: ${{ needs.build-and-validate.outputs.artifact-id }}" in publish
    assert "actions/download-artifact@" in publish
    assert "pypa/gh-action-pypi-publish@" in publish
    assert "actions/checkout@" not in publish
    assert "actions/setup-python@" not in publish
    assert "run:" not in publish
    assert "skip-existing" not in publish


def test_every_external_action_uses_an_immutable_sha_and_no_upload_secret_exists():
    workflow = workflow_text()
    action_refs = re.findall(r"uses:\s*([^\s#]+)", workflow)

    assert action_refs
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref) for ref in action_refs)
    assert "permissions: {}" in workflow
    publish = publish_job(workflow)
    assert re.findall(r"uses:\s*([^\s#]+)", publish) == [
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33",
    ]
    lowered = workflow.lower()
    assert "secrets." not in lowered
    assert "pypi_token" not in lowered
    assert "password:" not in lowered
    assert "contents: write" not in lowered


def test_owner_runbook_names_every_external_gate_and_the_nonpublishing_path():
    documentation = DOCUMENTATION.read_text(encoding="utf-8")

    for term in (
        "validation-only",
        "publish-pypi.yml",
        "Trusted Publisher",
        "Pipeliner/jring-client",
        "pypi",
        "required reviewer",
        "prevent self-review",
        "protected tag",
        "v*",
        "API token",
        "OIDC",
        "publish: false",
        "publish: true",
        "Jobs to be done",
        "Acceptance contract",
        "Publication is automatic",
        "The GitHub controls are configured",
        "Only the PyPI owner",
    ):
        assert term in documentation


def test_uvx_quickstart_and_tui_entrypoint_are_documented():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    install = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    assert 'jring-tui = "jring.cli:tui_main"' in metadata
    for text in (readme, install):
        assert "uvx --from jring-client jring tui" in text
        assert "status --simulate" in text


def test_runtime_dependencies_are_in_base_project_metadata():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"bleak>=0.22,<2"' in metadata
    assert '"evdev>=1.7,<2"' in metadata
    assert "dependencies = []" not in metadata
    assert "[project.optional-dependencies]" in metadata
