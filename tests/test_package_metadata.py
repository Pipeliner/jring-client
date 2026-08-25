from __future__ import annotations

import email.policy
from importlib.metadata import PackageNotFoundError, version
import shutil
import subprocess
import sys
import tarfile
import zipfile
from email.message import Message
from email.parser import Parser
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 support
    import tomli as tomllib


PROJECT_ROOT = Path(__file__).parents[1]
EXPECTED_KEYWORDS = (
    "accessibility",
    "assistive-technology",
    "automation",
    "ble",
    "bluetooth",
    "bluetooth-low-energy",
    "bluez",
    "command-line",
    "input-device",
    "jring",
    "linux",
    "linux-input",
    "privacy",
    "smart-ring",
    "uinput",
    "wearable",
)
EXPECTED_URLS = {
    "Documentation": "https://github.com/Pipeliner/jring-client/tree/main/docs",
    "Issues": "https://github.com/Pipeliner/jring-client/issues",
    "Repository": "https://github.com/Pipeliner/jring-client",
}
EXPECTED_CLASSIFIERS = (
    "Environment :: Console",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: Implementation :: CPython",
)
EXPECTED_BUILD_SYSTEM = ("setuptools==84.0.0",)
EXPECTED_RELEASE_REQUIREMENTS = (
    "build==1.5.0",
    "packaging==26.3",
    "pyproject-hooks==1.2.0",
    "setuptools==84.0.0",
    "tomli==2.4.1",
)
FORBIDDEN_KEYWORD_CLAIMS = {
    "activity",
    "blood-pressure",
    "ecg",
    "fitness",
    "gesture",
    "health",
    "heart-rate",
    "hid",
    "medical",
    "motion",
    "oxygen",
    "sensor",
    "sleep",
    "step",
    "temperature",
}


def _parse_metadata(content: bytes) -> Message:
    return Parser(policy=email.policy.default).parsestr(content.decode("utf-8"))


def _keywords(metadata: Message) -> tuple[str, ...]:
    values = metadata.get_all("Keywords", [])
    assert len(values) == 1
    return tuple(keyword.strip() for keyword in values[0].split(",") if keyword.strip())


def _project_urls(metadata: Message) -> dict[str, str]:
    result = {}
    for value in metadata.get_all("Project-URL", []):
        label, separator, url = value.partition(",")
        assert separator, f"malformed Project-URL metadata: {value!r}"
        label = label.strip()
        assert label not in result, f"duplicate Project-URL label: {label!r}"
        result[label] = url.strip()
    return result


def _require_pinned_local_setuptools(pyproject: dict) -> None:
    requirements = pyproject["build-system"]["requires"]
    pins = [
        value.removeprefix("setuptools==")
        for value in requirements
        if value.startswith("setuptools==")
    ]
    assert len(pins) == 1, "build-system must have one exact setuptools pin"
    required = pins[0]
    try:
        installed = version("setuptools")
    except PackageNotFoundError:
        installed = "not installed"
    if installed != required:
        pytest.skip(
            "fresh artifact metadata requires the pinned local build backend: "
            f"setuptools=={required} (installed: {installed})"
        )


def _build_distributions(tmp_path: Path) -> tuple[Message, Message]:
    source = tmp_path / "source"
    output = tmp_path / "dist"
    shutil.copytree(
        PROJECT_ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            ".pytest_cache",
            ".venv",
            "*.egg-info",
            "__pycache__",
            "build",
            "dist",
        ),
    )
    output.mkdir()
    build_script = (
        "from setuptools import build_meta; import sys; "
        "getattr(build_meta, sys.argv[1])(sys.argv[2])"
    )
    for operation in ("build_wheel", "build_sdist"):
        subprocess.run(
            [sys.executable, "-c", build_script, operation, str(output)],
            cwd=source,
            check=True,
            capture_output=True,
            text=True,
        )

    wheels = list(output.glob("*.whl"))
    sdists = list(output.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1

    with zipfile.ZipFile(wheels[0]) as archive:
        members = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        assert len(members) == 1
        wheel_metadata = _parse_metadata(archive.read(members[0]))

    with tarfile.open(sdists[0], "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")
        ]
        assert len(members) == 1
        handle = archive.extractfile(members[0])
        assert handle is not None
        sdist_metadata = _parse_metadata(handle.read())

    return wheel_metadata, sdist_metadata


def test_source_has_safe_discovery_metadata():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = tomllib.loads(pyproject)["project"]

    source_keywords = tuple(project["keywords"])
    source_urls = project["urls"]
    assert source_keywords == EXPECTED_KEYWORDS
    assert source_urls == EXPECTED_URLS
    assert tuple(project["classifiers"]) == EXPECTED_CLASSIFIERS

    for keyword in source_keywords:
        normalized = keyword.casefold()
        assert not any(claim in normalized for claim in FORBIDDEN_KEYWORD_CLAIMS)


def test_fresh_public_distributions_have_safe_discovery_metadata(tmp_path):
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = tomllib.loads(pyproject_text)
    _require_pinned_local_setuptools(pyproject)
    project = pyproject["project"]
    wheel_metadata, sdist_metadata = _build_distributions(tmp_path)

    source_keywords = tuple(project["keywords"])
    source_urls = project["urls"]

    for metadata in (wheel_metadata, sdist_metadata):
        assert _keywords(metadata) == EXPECTED_KEYWORDS
        assert _project_urls(metadata) == EXPECTED_URLS
        assert tuple(metadata.get_all("Classifier", [])) == EXPECTED_CLASSIFIERS

    assert _keywords(wheel_metadata) == _keywords(sdist_metadata) == source_keywords
    assert _project_urls(wheel_metadata) == _project_urls(sdist_metadata) == source_urls

    wheel = next((tmp_path / "dist").glob("*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        members = {member.filename: member for member in archive.infolist()}
        for relative in (
            "jring/resources/completions/jring.bash",
            "jring/resources/man/jring.1",
        ):
            assert relative in members
            assert (members[relative].external_attr >> 16) & 0o111 == 0
        assert not any("share/" in name for name in members)

    sdist = next((tmp_path / "dist").glob("*.tar.gz"))
    with tarfile.open(sdist, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        prefix = f"jring_client-{pyproject['project']['version']}/"
        for relative in (
            "scripts/generate_cli_artifacts.py",
            "src/jring/resources/completions/jring.bash",
            "src/jring/resources/man/jring.1",
        ):
            assert prefix + relative in members
            assert members[prefix + relative].mode & 0o111 == 0


def test_build_inputs_are_complete_and_exactly_pinned():
    pyproject = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements = tuple(
        line.strip()
        for line in (PROJECT_ROOT / "requirements" / "release.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )

    assert tuple(pyproject["build-system"]["requires"]) == EXPECTED_BUILD_SYSTEM
    assert requirements == EXPECTED_RELEASE_REQUIREMENTS
