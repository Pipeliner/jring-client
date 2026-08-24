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


def make_artifacts(directory, version="0.5.0", extra_member=None):
    wheel = directory / f"jring_client-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("jring/__init__.py", "")
        archive.writestr(
            f"jring_client-{version}.dist-info/METADATA",
            f"Name: jring-client\nVersion: {version}\n",
        )
        if extra_member:
            archive.writestr(extra_member, "unsafe")
    source_root = directory / f"jring_client-{version}"
    (source_root / "scripts").mkdir(parents=True)
    for name in ("README.md", "SECURITY.md", "CONTRIBUTING.md"):
        (source_root / name).write_text(name)
    (source_root / "scripts" / "evidence_tool.py").write_text("")
    egg_info = source_root / "src" / "jring_client.egg-info"
    egg_info.mkdir(parents=True)
    declared = {
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "scripts/evidence_tool.py",
        "src/jring_client.egg-info/SOURCES.txt",
    }
    (egg_info / "SOURCES.txt").write_text("\n".join(sorted(declared)) + "\n")
    (source_root / "PKG-INFO").write_text(f"Name: jring-client\nVersion: {version}\n")
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
