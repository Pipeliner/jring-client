#!/usr/bin/env python3
"""Inspect, compare, and checksum prepared JRing release artifacts."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import os
import re
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


_VERSION = re.compile(r'^version\s*=\s*"([^"]+)"$', re.MULTILINE)
_FORBIDDEN = {".env", ".pcap", ".pcapng", ".apk", ".xapk", ".har", "capture"}


class ReleaseError(ValueError):
    pass


def project_version(pyproject: Path) -> str:
    match = _VERSION.search(pyproject.read_text(encoding="utf-8"))
    if not match:
        raise ReleaseError("project version is missing")
    return match.group(1)


def _safe_members(names: list[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        lowered = name.lower()
        if path.is_absolute() or ".." in path.parts:
            raise ReleaseError("artifact contains an unsafe path")
        if any(marker in lowered for marker in _FORBIDDEN):
            raise ReleaseError("artifact contains a forbidden member")


def _metadata_field(content: str, field: str) -> str:
    prefix = f"{field}: "
    for line in content.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise ReleaseError(f"artifact metadata {field.lower()} is missing")


def inspect_artifacts(directory: Path, version: str) -> list[Path]:
    wheel = directory / f"jring_client-{version}-py3-none-any.whl"
    sdist = directory / f"jring_client-{version}.tar.gz"
    if not wheel.is_file() or not sdist.is_file():
        raise ReleaseError("expected one versioned wheel and source archive")
    unexpected = [
        path for path in directory.iterdir()
        if path.is_file() and path not in {wheel, sdist}
    ]
    if unexpected:
        raise ReleaseError("artifact directory contains undeclared files")

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        _safe_members(names)
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ReleaseError("wheel metadata is ambiguous")
        metadata = archive.read(metadata_names[0]).decode("utf-8")
        if _metadata_field(metadata, "Version") != version:
            raise ReleaseError("wheel version does not match project version")
        if _metadata_field(metadata, "License-Expression") != "MIT":
            raise ReleaseError("wheel license does not match project license")
        license_names = [
            name for name in names if name.endswith(".dist-info/licenses/LICENSE")
        ]
        if len(license_names) != 1:
            raise ReleaseError("wheel license file is missing or ambiguous")
        if any(not (name.startswith("jring/") or ".dist-info/" in name) for name in names):
            raise ReleaseError("wheel contains an undeclared top-level member")

    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        _safe_members(names)
        if any(member.issym() or member.islnk() for member in members):
            raise ReleaseError("source archive contains a link")
        pkg_info = [
            member for member in members
            if member.name == f"jring_client-{version}/PKG-INFO"
        ]
        if len(pkg_info) != 1:
            raise ReleaseError("source metadata is ambiguous")
        handle = archive.extractfile(pkg_info[0])
        if handle is None:
            raise ReleaseError("source metadata is unreadable")
        source_metadata = handle.read().decode("utf-8")
        if _metadata_field(source_metadata, "Version") != version:
            raise ReleaseError("source version does not match project version")
        if _metadata_field(source_metadata, "License-Expression") != "MIT":
            raise ReleaseError("source license does not match project license")
        required = {
            f"jring_client-{version}/README.md",
            f"jring_client-{version}/LICENSE",
            f"jring_client-{version}/SECURITY.md",
            f"jring_client-{version}/CONTRIBUTING.md",
            f"jring_client-{version}/scripts/evidence_tool.py",
        }
        if not required.issubset(names):
            raise ReleaseError("source archive is missing declared review files")
        sources_name = f"jring_client-{version}/src/jring_client.egg-info/SOURCES.txt"
        source_members = [member for member in members if member.name == sources_name]
        if len(source_members) != 1:
            raise ReleaseError("source archive declaration is missing")
        source_handle = archive.extractfile(source_members[0])
        if source_handle is None:
            raise ReleaseError("source archive declaration is unreadable")
        declared = set(source_handle.read().decode("utf-8").splitlines())
        prefix = f"jring_client-{version}/"
        actual = {
            member.name.removeprefix(prefix)
            for member in members
            if member.isfile()
        }
        generated = {"PKG-INFO", "setup.cfg"}
        if actual - generated != declared:
            raise ReleaseError("source archive contains undeclared files")
    return [wheel, sdist]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def compare_directories(first: Path, second: Path) -> None:
    first_files = {path.name: digest(path) for path in first.iterdir() if path.is_file()}
    second_files = {path.name: digest(path) for path in second.iterdir() if path.is_file()}
    if first_files != second_files:
        raise ReleaseError("repeated builds are not byte-for-byte reproducible")


def normalize_sdist(path: Path, epoch: int) -> None:
    if epoch <= 0:
        raise ReleaseError("source date epoch must be positive")
    descriptor, temporary = tempfile.mkstemp(prefix=".jring-sdist-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=epoch) as compressed:
                with tarfile.open(path, "r:gz") as source:
                    with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target:
                        for member in sorted(source.getmembers(), key=lambda item: item.name):
                            normalized = copy.copy(member)
                            normalized.mtime = epoch
                            normalized.uid = 0
                            normalized.gid = 0
                            normalized.uname = ""
                            normalized.gname = ""
                            normalized.pax_headers = {}
                            payload = source.extractfile(member) if member.isfile() else None
                            target.addfile(normalized, payload)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_checksums(directory: Path, artifacts: list[Path]) -> Path:
    destination = directory / "SHA256SUMS"
    lines = [f"{digest(path)}  {path.name}\n" for path in sorted(artifacts)]
    destination.write_text("".join(lines), encoding="ascii")
    return destination


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify prepared JRing artifacts")
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    inspect.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    compare = sub.add_parser("compare")
    compare.add_argument("first", type=Path)
    compare.add_argument("second", type=Path)
    normalize = sub.add_parser("normalize-sdist")
    normalize.add_argument("archive", type=Path)
    normalize.add_argument("--epoch", type=int, required=True)
    checksums = sub.add_parser("checksums")
    checksums.add_argument("directory", type=Path)
    checksums.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    version = sub.add_parser("check-version")
    version.add_argument("tag")
    version.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "compare":
            compare_directories(args.first, args.second)
        elif args.command == "normalize-sdist":
            normalize_sdist(args.archive, args.epoch)
        elif args.command == "check-version":
            expected = f"v{project_version(args.pyproject)}"
            if args.tag != expected:
                raise ReleaseError("tag does not match project version")
        else:
            artifacts = inspect_artifacts(args.directory, project_version(args.pyproject))
            if args.command == "checksums":
                write_checksums(args.directory, artifacts)
    except (OSError, UnicodeError, zipfile.BadZipFile, tarfile.TarError, ReleaseError) as error:
        message = str(error) if isinstance(error, ReleaseError) else "artifact could not be inspected"
        print(f"release: error: {message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
