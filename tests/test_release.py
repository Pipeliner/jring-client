import tarfile
import zipfile
from pathlib import Path

import pytest

from jring import __version__
from scripts.release_artifacts import (
    ReleaseError,
    compare_directories,
    inspect_artifacts,
    normalize_sdist,
    project_version,
    write_checksums,
)


ROOT = Path(__file__).parents[1]


def make_artifacts(
    directory,
    version="0.5.0",
    extra_member=None,
    extra_member_content="unsafe",
    readme_content="README.md",
    license_expression="MIT",
    include_license=True,
):
    wheel = directory / f"jring_client-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("jring/__init__.py", "")
        archive.writestr("jring/resources/completions/jring.bash", "generated")
        archive.writestr("jring/resources/man/jring.1", "generated")
        archive.writestr(
            f"jring_client-{version}.dist-info/METADATA",
            (
                f"Name: jring-client\nVersion: {version}\n"
                f"License-Expression: {license_expression}\n"
            ),
        )
        if include_license:
            archive.writestr(
                f"jring_client-{version}.dist-info/licenses/LICENSE", "MIT License"
            )
        if extra_member:
            archive.writestr(extra_member, extra_member_content)
    source_root = directory / f"jring_client-{version}"
    (source_root / "scripts").mkdir(parents=True)
    (source_root / "README.md").write_text(readme_content)
    for name in ("SECURITY.md", "CONTRIBUTING.md"):
        (source_root / name).write_text(name)
    if include_license:
        (source_root / "LICENSE").write_text("MIT License")
    (source_root / "scripts" / "evidence_tool.py").write_text("")
    (source_root / "scripts" / "generate_cli_artifacts.py").write_text("")
    resources = source_root / "src" / "jring" / "resources"
    (resources / "completions").mkdir(parents=True)
    (resources / "man").mkdir()
    (resources / "completions" / "jring.bash").write_text("generated")
    (resources / "man" / "jring.1").write_text("generated")
    egg_info = source_root / "src" / "jring_client.egg-info"
    egg_info.mkdir(parents=True)
    declared = {
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "scripts/evidence_tool.py",
        "scripts/generate_cli_artifacts.py",
        "src/jring/resources/completions/jring.bash",
        "src/jring/resources/man/jring.1",
        "src/jring_client.egg-info/SOURCES.txt",
    }
    if include_license:
        declared.add("LICENSE")
    (egg_info / "SOURCES.txt").write_text("\n".join(sorted(declared)) + "\n")
    (source_root / "PKG-INFO").write_text(
        f"Name: jring-client\nVersion: {version}\n"
        f"License-Expression: {license_expression}\n"
    )
    sdist = directory / f"jring_client-{version}.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        archive.add(source_root, arcname=source_root.name)
    return wheel, sdist


def test_project_version_agrees_with_runtime():
    assert project_version(ROOT / "pyproject.toml") == __version__


def test_artifact_inspection_and_checksums_are_deterministic(tmp_path):
    artifacts = make_artifacts(tmp_path)
    assert inspect_artifacts(tmp_path, __version__) == list(artifacts)
    first = write_checksums(tmp_path, list(artifacts)).read_text()
    second = write_checksums(tmp_path, list(reversed(artifacts))).read_text()
    assert first == second
    assert first.splitlines()[0].endswith("jring_client-0.5.0-py3-none-any.whl")


def test_artifact_inspection_rejects_secret_or_undeclared_members(tmp_path):
    make_artifacts(tmp_path, extra_member="jring/.env")
    with pytest.raises(ReleaseError, match="forbidden"):
        inspect_artifacts(tmp_path, __version__)


def test_artifact_inspection_rejects_disguised_decompiler_content_in_wheel(tmp_path):
    marker = "/* " + "JADX INFO:"
    make_artifacts(
        tmp_path,
        extra_member="jring/recovery_notes.py",
        extra_member_content=marker,
    )

    with pytest.raises(ReleaseError) as raised:
        inspect_artifacts(tmp_path, __version__)

    assert str(raised.value) == "artifact contains forbidden content"
    assert "recovery_notes" not in str(raised.value)
    assert marker not in str(raised.value)


def test_artifact_inspection_rejects_disguised_decompiler_content_in_sdist(tmp_path):
    marker = "." + "class public L"
    make_artifacts(tmp_path, readme_content=marker)

    with pytest.raises(ReleaseError) as raised:
        inspect_artifacts(tmp_path, __version__)

    assert str(raised.value) == "artifact contains forbidden content"
    assert "README" not in str(raised.value)
    assert marker not in str(raised.value)


def test_artifact_inspection_rejects_inconsistent_license(tmp_path):
    make_artifacts(tmp_path, license_expression="Apache-2.0")
    with pytest.raises(ReleaseError, match="license"):
        inspect_artifacts(tmp_path, __version__)


def test_artifact_inspection_rejects_missing_license_file(tmp_path):
    make_artifacts(tmp_path, include_license=False)
    with pytest.raises(ReleaseError, match="license file"):
        inspect_artifacts(tmp_path, __version__)


def test_repeated_build_comparison_is_byte_exact(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "artifact.whl").write_bytes(b"same")
    (second / "artifact.whl").write_bytes(b"same")
    compare_directories(first, second)
    (second / "artifact.whl").write_bytes(b"different")
    with pytest.raises(ReleaseError, match="not byte-for-byte"):
        compare_directories(first, second)


def test_sdist_normalization_removes_build_time_variance(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = make_artifacts(first_dir)[1]
    second = make_artifacts(second_dir)[1]

    normalize_sdist(first, 1_700_000_000)
    normalize_sdist(second, 1_700_000_000)

    assert first.read_bytes() == second.read_bytes()


def test_release_workflow_is_pinned_and_has_no_publish_step():
    workflow = (ROOT / ".github" / "workflows" / "release-artifacts.yml").read_text()
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "attest-build-provenance@4d101475d8b20a2381f78447822ac1eab6504dd8" in workflow
    assert "download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in workflow
    assert 'python-version: ["3.10", "3.13"]' in workflow
    assert "pypi" not in workflow.lower()
    assert "gh release" not in workflow.lower()
    assert "contents: write" not in workflow.lower()
    assert "python scripts/evidence_tool.py scan ." in workflow


def test_uv_tool_smoke_workflow_installs_exact_wheel_and_runs_safe_commands():
    workflow = (ROOT / ".github" / "workflows" / "uv-tool-smoke.yml").read_text()
    assert "astral-sh/setup-uv@d08d816a1ea176d61a318eff45abd3dffef415b1" in workflow
    assert "python -m build --wheel" in workflow
    assert "uv tool install dist/*.whl" in workflow
    assert "jring --version" in workflow
    assert "jring status --simulate --json" in workflow
    assert "jring-tui" in workflow
    assert "--active-scan" not in workflow
    assert "--allow-input" not in workflow
    assert "id-token: write" not in workflow


def test_install_documentation_covers_lifecycle_and_verification():
    documentation = (ROOT / "docs" / "INSTALL.md").read_text()
    for term in (
        "sha256sum --check",
        "pipx install",
        "uv tool install",
        "upgrade",
        "uninstall",
    ):
        assert term in documentation


def test_packager_guidance_is_version_neutral_pinned_and_non_mutating():
    documentation = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")
    normalized = " ".join(documentation.split())

    assert "jring_client-VERSION-py3-none-any.whl" in documentation
    assert "jring_client-0.5.0-py3-none-any.whl" not in documentation
    for term in (
        "requirements/release.txt",
        "--no-index",
        "--find-links",
        "PIP_NO_INDEX=1",
        "python -m build",
        "isolated virtual environment",
        "does not configure a shell",
        "does not install a man page",
    ):
        assert term in normalized
    assert "do not use pip's `--break-system-packages`" in normalized.lower()


def test_release_workflow_proves_an_isolated_no_index_build_from_pinned_inputs():
    workflow = (ROOT / ".github" / "workflows" / "release-artifacts.yml").read_text()

    for term in (
        "pip download",
        "requirements/release.txt",
        "python -m venv /tmp/jring-offline-build",
        "--no-index --find-links",
        "PIP_NO_INDEX=1",
        "PIP_FIND_LINKS=",
        "python -m build",
    ):
        assert term in workflow
