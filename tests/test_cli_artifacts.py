from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from jring.cli import build_parser
from scripts.generate_cli_artifacts import (
    ARTIFACTS,
    CliSurface,
    extract_surface,
    generate_artifacts,
    render_bash,
    render_man,
)


ROOT = Path(__file__).parents[1]
SYNTHETIC_ADDRESS = ":".join(("AA", "BB", "CC", "DD", "EE", "FF"))
SYNTHETIC_BLUEZ_PATH = "/org/" + "bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
EXPECTED_COMMANDS = (
    "doctor",
    "input-actions",
    "protocol-coverage",
    "non-health-capabilities",
    "input",
    "discover",
    "status",
    "capabilities",
    "heart-rate",
    "time-sync",
    "history",
    "verify-device-info",
    "review-owner-evidence",
    "derive-owner-evidence",
)
EXPECTED_OPTIONS = {
    None: (
        ("-h", "--help"),
        ("--version",),
        ("--address",),
        ("--address-file",),
        ("--simulate",),
        ("--simulate-profile",),
        ("--timeout",),
        ("--json",),
    ),
    "doctor": (("-h", "--help"), ("--json",), ("--require-hardware",), ("--require-input",)),
    "input-actions": (("-h", "--help"), ("--json",)),
    "protocol-coverage": (("-h", "--help"), ("--json",)),
    "non-health-capabilities": (("-h", "--help"), ("--json",)),
    "input": (
        ("-h", "--help"),
        ("--simulate",),
        ("--simulate-profile",),
        ("--json",),
        ("--map",),
        ("--allow-input",),
    ),
    "discover": (("-h", "--help"), ("--simulate",), ("--timeout",), ("--json",), ("--active-scan",)),
    "status": (
        ("-h", "--help"),
        ("--address",),
        ("--address-file",),
        ("--simulate",),
        ("--simulate-profile",),
        ("--timeout",),
        ("--json",),
        ("--select",),
        ("--active-scan",),
    ),
    "capabilities": (
        ("-h", "--help"),
        ("--address",),
        ("--address-file",),
        ("--simulate",),
        ("--simulate-profile",),
        ("--timeout",),
        ("--json",),
        ("--select",),
        ("--active-scan",),
        ("--issue-draft-url",),
    ),
    "heart-rate": (
        ("-h", "--help"),
        ("--address",),
        ("--address-file",),
        ("--simulate",),
        ("--simulate-profile",),
        ("--timeout",),
        ("--json",),
        ("--select",),
        ("--active-scan",),
        ("--allow-notifications",),
    ),
    "time-sync": (
        ("-h", "--help"),
        ("--address",),
        ("--address-file",),
        ("--simulate",),
        ("--timeout",),
        ("--json",),
        ("--allow-write", "--yes"),
    ),
    "history": (("-h", "--help"), ("--simulate",), ("--json",), ("--output",), ("--force",)),
    "verify-device-info": (
        ("-h", "--help"),
        ("--address-file",),
        ("--private-output",),
        ("--model-family",),
        ("--firmware-major",),
        ("--timeout",),
        ("--json",),
        ("--allow-connect",),
        ("--allow-notifications",),
        ("--allow-write",),
        ("--negative-control",),
        ("--select",),
        ("--active-scan",),
    ),
    "review-owner-evidence": (
        ("-h", "--help"),
        ("--private-input",),
        ("--decision",),
        ("--evidence-reference",),
        ("--review-output",),
        ("--allow-review-decision",),
        ("--json",),
    ),
    "derive-owner-evidence": (
        ("-h", "--help"),
        ("--private-input",),
        ("--public-output",),
        ("--review-receipt",),
        ("--allow-public-evidence",),
        ("--json",),
    ),
}


def _option_flags(surface: CliSurface) -> dict[str | None, tuple[tuple[str, ...], ...]]:
    return {
        None: tuple(option.flags for option in surface.global_options),
        **{
            command.name: tuple(option.flags for option in command.options)
            for command in surface.commands
        },
    }


def test_surface_exactly_tracks_visible_parser_contexts_aliases_and_choices():
    surface = extract_surface(build_parser())

    assert tuple(command.name for command in surface.commands) == EXPECTED_COMMANDS
    assert _option_flags(surface) == EXPECTED_OPTIONS
    choices = {
        (command.name if command else None, option.flags): option.choices
        for command in (None, *surface.commands)
        for option in (surface.global_options if command is None else command.options)
        if option.choices
    }
    assert choices == {
        (None, ("--simulate-profile",)): ("basic", "hid"),
        ("input", ("--simulate-profile",)): ("basic", "hid"),
        ("status", ("--simulate-profile",)): ("basic", "hid"),
        ("capabilities", ("--simulate-profile",)): ("basic", "hid"),
        ("heart-rate", ("--simulate-profile",)): ("basic", "hid"),
        ("review-owner-evidence", ("--decision",)): ("promote", "reject"),
    }
    assert not any(
        option.flags[0] in {"--address", "--address-file", "--timeout"}
        for option in next(command for command in surface.commands if command.name == "input").options
    )
    assert all(
        option.help != "None"
        for command in (None, *surface.commands)
        for option in (surface.global_options if command is None else command.options)
    )


def test_checked_in_artifacts_are_exact_parser_derived_bytes():
    generated = generate_artifacts(build_parser())
    assert tuple(generated) == tuple(ARTIFACTS)
    for relative, content in generated.items():
        path = ROOT / relative
        assert path.read_bytes() == content
        assert content.endswith(b"\n")
        assert b"\r" not in content


def test_bash_completion_preserves_per_command_option_scope():
    surface = extract_surface(build_parser())
    bash = render_bash(surface)

    for command in surface.commands:
        flags = " ".join(flag for option in command.options for flag in option.flags)
        assert f"        {command.name}) words='{flags}' ;;" in bash

    input_bash = next(
        line for line in bash.splitlines() if line.startswith("        input) words=")
    )
    for suppressed in ("--address", "--address-file", "--timeout"):
        assert suppressed not in input_bash
        assert f"input:{suppressed})" not in bash
    assert "input:--simulate-profile)" in bash
    assert "input:--map)" in bash
    for command in ("status", "capabilities", "heart-rate", "time-sync"):
        assert f"{command}:--address-file)" in bash
    assert bash.count("compopt -o filenames 2>/dev/null || true") == 18


def test_generation_is_reproducible_private_and_host_independent(monkeypatch):
    secrets = (
        SYNTHETIC_ADDRESS,
        SYNTHETIC_BLUEZ_PATH,
        "deadbeefdeadbeef",
        "owner-capture.pcapng",
    )
    for index, secret in enumerate(secrets):
        monkeypatch.setenv(f"JRING_HOSTILE_{index}", secret)
    monkeypatch.setenv("HOME", "/private/owner-home")
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "999999999")

    first = generate_artifacts(build_parser())
    monkeypatch.chdir(ROOT / "docs")
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    second = generate_artifacts(build_parser())

    assert first == second
    joined = b"\n".join(first.values()).decode("utf-8")
    for secret in (*secrets, "/private/owner-home", "999999999", str(ROOT)):
        assert secret not in joined
    assert "\x1b" not in joined
    assert not re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", joined)
    assert "jring --help" not in joined
    assert "eval " not in joined


def test_manual_leads_with_safety_and_covers_every_parser_item_once():
    surface = extract_surface(build_parser())
    manual = render_man(surface)
    plain = re.sub(r"^\.[A-Z]+.*$", "", manual, flags=re.MULTILINE)
    safety = plain.index("offline")
    commands = manual.index('.SH "COMMANDS"')
    assert safety < commands
    assert "does not scan, connect, write, or emit desktop input" in plain
    for heading in (
        "NAME", "SYNOPSIS", "DESCRIPTION", "COMMANDS", "GLOBAL OPTIONS",
        "EXIT STATUS", "PRIVACY AND FILES",
    ):
        assert manual.count(f'.SH "{heading}"') == 1
    for command in surface.commands:
        assert manual.count(f'.SS "jring {command.name}"') == 1
    assert r"\-\-allow\-write, \-\-yes" in manual
    assert "basic, hid" in manual


def test_roff_renderer_neutralizes_macro_and_control_injection():
    surface = extract_surface(build_parser())
    hostile = surface.with_description(".SH OWNED\\path\n'break\ttext")
    manual = render_man(hostile)
    assert '.SH "OWNED"' not in manual
    assert r"\&.SH OWNED\epath \&'break text" in manual


@pytest.mark.skipif(shutil.which("groff") is None, reason="groff is unavailable")
def test_generated_manual_is_accepted_by_a_man_renderer():
    artifact = ROOT / "src" / "jring" / "resources" / "man" / "jring.1"
    completed = subprocess.run(
        ["groff", "-man", "-Tutf8", os.fspath(artifact)],
        check=True,
        capture_output=True,
    )
    plain = re.sub(rb".\x08", b"", completed.stdout)
    plain = re.sub(rb"\x1b\[[0-9;]*m", b"", plain)
    plain = re.sub(rb"\s+", b" ", plain)
    assert b"JRing is offline by default" in plain


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is unavailable")
def test_bash_completion_sources_and_preserves_command_scope():
    artifact = ROOT / "src" / "jring" / "resources" / "completions" / "jring.bash"
    script = f'''source "{artifact}"
COMP_WORDS=(jring status --sim)
COMP_CWORD=2
_jring_completion
printf '%s\\n' "${{COMPREPLY[@]}}"
'''
    completed = subprocess.run(
        ["bash", "--noprofile", "--norc"],
        input=script,
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert completed.stdout.splitlines() == ["--simulate", "--simulate-profile"]


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash is unavailable")
def test_bash_completion_handles_attached_choices_and_file_values(tmp_path):
    artifact = ROOT / "src" / "jring" / "resources" / "completions" / "jring.bash"
    target = tmp_path / "history export.jsonl"
    target.write_text("fixture", encoding="utf-8")
    file_prefix = os.fspath(target)[:-5]
    script = f'''source "{artifact}"
COMP_WORDS=(jring status --simulate-profile=h)
COMP_CWORD=2
_jring_completion
printf 'choice=%s\\n' "${{COMPREPLY[@]}}"
COMP_WORDS=(jring history "--output={file_prefix}")
COMP_CWORD=2
_jring_completion
printf 'file=%s\\n' "${{COMPREPLY[@]}}"
'''
    completed = subprocess.run(
        ["bash", "--noprofile", "--norc"],
        input=script,
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", "")},
    )
    assert completed.stdout.splitlines() == [
        "choice=--simulate-profile=hid",
        f"file=--output={target}",
    ]


def test_generator_check_is_read_only_and_detects_stale_output(tmp_path):
    generated = generate_artifacts(build_parser())
    for relative, content in generated.items():
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    command = [
        os.fspath(Path(os.sys.executable)),
        os.fspath(ROOT / "scripts" / "generate_cli_artifacts.py"),
        "--check",
        "--root",
        os.fspath(tmp_path),
    ]
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert subprocess.run(command, cwd=ROOT, capture_output=True, text=True).returncode == 0
    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    stale = tmp_path / next(iter(ARTIFACTS))
    stale.write_text("stale\n", encoding="utf-8")
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 1
    assert result.stderr == f"generated CLI artifact is stale: {stale.relative_to(tmp_path)}\n"
    assert stale.read_text(encoding="utf-8") == "stale\n"
