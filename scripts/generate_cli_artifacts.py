#!/usr/bin/env python3
"""Generate inert terminal-help artifacts from the authoritative JRing parser."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import os
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
if os.fspath(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, os.fspath(SOURCE_ROOT))

from jring.cli import build_parser  # noqa: E402


ARTIFACTS = (
    Path("src/jring/resources/completions/jring.bash"),
    Path("src/jring/resources/man/jring.1"),
)


@dataclass(frozen=True)
class OptionSurface:
    flags: tuple[str, ...]
    destination: str
    help: str
    metavar: str | None
    choices: tuple[str, ...]
    takes_value: bool
    file_value: bool
    required: bool


@dataclass(frozen=True)
class CommandSurface:
    name: str
    help: str
    options: tuple[OptionSurface, ...]


@dataclass(frozen=True)
class CliSurface:
    program: str
    description: str
    global_options: tuple[OptionSurface, ...]
    commands: tuple[CommandSurface, ...]

    def with_description(self, description: str) -> "CliSurface":
        return replace(self, description=description)


def _plain(value: object) -> str:
    text = str(value)
    for character in text:
        codepoint = ord(character)
        if codepoint < 32 and character not in "\t\n\r":
            raise ValueError("CLI help contains an unsupported control character")
        if codepoint == 127:
            raise ValueError("CLI help contains an unsupported control character")
    return " ".join(text.split())


def _option(action: argparse.Action) -> OptionSurface:
    if not action.option_strings:
        raise ValueError("visible positional arguments are unsupported")
    supported = (
        argparse._HelpAction,
        argparse._VersionAction,
        argparse._StoreAction,
        argparse._StoreTrueAction,
        argparse._StoreFalseAction,
    )
    if not isinstance(action, supported):
        raise ValueError(f"unsupported argparse action: {type(action).__name__}")
    takes_value = not isinstance(
        action,
        (argparse._HelpAction, argparse._VersionAction,
         argparse._StoreTrueAction, argparse._StoreFalseAction),
    )
    if takes_value and action.nargs not in (None, 1):
        raise ValueError("only single-value CLI options are supported")
    choices = tuple(_plain(choice) for choice in (action.choices or ()))
    metavar = None
    if takes_value:
        metavar = _plain(action.metavar or action.dest.upper().replace("_", "-"))
    return OptionSurface(
        flags=tuple(_plain(flag) for flag in action.option_strings),
        destination=_plain(action.dest),
        help=_plain(action.help or ""),
        metavar=metavar,
        choices=choices,
        takes_value=takes_value,
        file_value=action.dest in {"address_file", "output"},
        required=bool(action.required),
    )


def _visible_options(parser: argparse.ArgumentParser) -> tuple[OptionSurface, ...]:
    options = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            raise ValueError("nested subcommands are unsupported")
        if action.help is argparse.SUPPRESS:
            continue
        options.append(_option(action))
    return tuple(options)


def extract_surface(parser: argparse.ArgumentParser) -> CliSurface:
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    if len(subparsers) != 1 or not subparsers[0].required:
        raise ValueError("exactly one required subcommand group is supported")
    subparser = subparsers[0]
    command_help = {
        action.dest: _plain(action.help)
        for action in subparser._choices_actions
    }
    commands = tuple(
        CommandSurface(
            name=_plain(name),
            help=command_help[name],
            options=_visible_options(command_parser),
        )
        for name, command_parser in subparser.choices.items()
    )
    global_options = tuple(
        _option(action)
        for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction)
        and action.help is not argparse.SUPPRESS
    )
    return CliSurface(
        program=_plain(parser.prog),
        description=_plain(parser.description or ""),
        global_options=global_options,
        commands=commands,
    )


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _all_flags(options: tuple[OptionSurface, ...]) -> str:
    return " ".join(flag for option in options for flag in option.flags)


def _bash_patterns(
    options: tuple[OptionSurface, ...], prefix: str = ""
) -> tuple[str, dict[tuple[str, ...], str], str]:
    files = []
    choices: dict[tuple[str, ...], list[str]] = {}
    values = []
    for option in options:
        if not option.takes_value:
            continue
        patterns = [f"{prefix}{flag}" for flag in option.flags]
        if option.file_value:
            files.extend(patterns)
        elif option.choices:
            choices.setdefault(option.choices, []).extend(patterns)
        else:
            values.extend(patterns)
    return (
        "|".join(files),
        {
            choice_values: "|".join(patterns)
            for choice_values, patterns in choices.items()
        },
        "|".join(values),
    )


def _bash_value_dispatch(
    options: tuple[OptionSurface, ...], prefix: str = "", indent: str = "        "
) -> list[str]:
    file_pattern, choice_patterns, value_pattern = _bash_patterns(options, prefix)
    lines = []
    if file_pattern:
        lines.extend([
            f"{indent}{file_pattern})",
            f"{indent}    compopt -o filenames 2>/dev/null || true",
            f'{indent}    mapfile -t COMPREPLY < <(compgen -f -- "$current")',
            f"{indent}    return",
            f"{indent}    ;;",
        ])
    for choices, pattern in choice_patterns.items():
        lines.extend([
            f"{indent}{pattern})",
            f'{indent}    mapfile -t COMPREPLY < <(compgen -W "{" ".join(choices)}" -- "$current")',
            f"{indent}    return",
            f"{indent}    ;;",
        ])
    if value_pattern:
        lines.extend([
            f"{indent}{value_pattern})",
            f"{indent}    COMPREPLY=()",
            f"{indent}    return",
            f"{indent}    ;;",
        ])
    return lines


def _bash_attached_dispatch(
    options: tuple[OptionSurface, ...], prefix: str = "", indent: str = "        "
) -> list[str]:
    files = []
    choices: dict[tuple[str, ...], list[str]] = {}
    values = []
    for option in options:
        if not option.takes_value:
            continue
        patterns = [
            f"{prefix}{flag}=*" for flag in option.flags if flag.startswith("--")
        ]
        if option.file_value:
            files.extend(patterns)
        elif option.choices:
            choices.setdefault(option.choices, []).extend(patterns)
        else:
            values.extend(patterns)
    lines = []
    if files:
        lines.extend([
            f"{indent}{'|'.join(files)})",
            f'{indent}    option_prefix="${{current%%=*}}="',
            f'{indent}    option_value="${{current#*=}}"',
            f"{indent}    compopt -o filenames 2>/dev/null || true",
            f'{indent}    mapfile -t COMPREPLY < <(compgen -f -- "$option_value")',
            f'{indent}    for index in "${{!COMPREPLY[@]}}"; do',
            f'{indent}        COMPREPLY[index]="$option_prefix${{COMPREPLY[index]}}"',
            f"{indent}    done",
            f"{indent}    return",
            f"{indent}    ;;",
        ])
    for choice_values, patterns in choices.items():
        lines.extend([
            f"{indent}{'|'.join(patterns)})",
            f'{indent}    option_prefix="${{current%%=*}}="',
            f'{indent}    option_value="${{current#*=}}"',
            f'{indent}    mapfile -t COMPREPLY < <(compgen -W "{" ".join(choice_values)}" -- "$option_value")',
            f'{indent}    for index in "${{!COMPREPLY[@]}}"; do',
            f'{indent}        COMPREPLY[index]="$option_prefix${{COMPREPLY[index]}}"',
            f"{indent}    done",
            f"{indent}    return",
            f"{indent}    ;;",
        ])
    if values:
        lines.extend([
            f"{indent}{'|'.join(values)})",
            f"{indent}    COMPREPLY=()",
            f"{indent}    return",
            f"{indent}    ;;",
        ])
    return lines


def render_bash(surface: CliSurface) -> str:
    commands = " ".join(command.name for command in surface.commands)
    global_flags = _all_flags(surface.global_options)
    global_value_flags = "|".join(
        option.flags[0] for option in surface.global_options if option.takes_value
    )
    lines = [
        "# Generated by scripts/generate_cli_artifacts.py; do not edit.",
        "_jring_completion()",
        "{",
        "    local current command previous words index word option_prefix option_value",
        '    current="${COMP_WORDS[COMP_CWORD]}"',
        '    previous=""',
        '    if (( COMP_CWORD > 0 )); then previous="${COMP_WORDS[COMP_CWORD-1]}"; fi',
        '    command=""',
        "",
        "    for (( index=1; index < COMP_CWORD; index++ )); do",
        '        word="${COMP_WORDS[index]}"',
        '        case "$word" in',
    ]
    if global_value_flags:
        lines.extend([
            f"            {global_value_flags}) ((index++)) ;;",
        ])
    lines.extend([
        f"            {'|'.join(command.name for command in surface.commands)}) command=\"$word\"; break ;;",
        "        esac",
        "    done",
        "",
        '    if [[ -z "$command" ]]; then',
        '        case "$current" in',
    ])
    lines.extend(_bash_attached_dispatch(surface.global_options, indent="            "))
    lines.extend([
        "        esac",
        '        case "$previous" in',
    ])
    lines.extend(_bash_value_dispatch(surface.global_options, indent="            "))
    lines.extend([
        "        esac",
        f"        words={_shell_quote(global_flags + ' ' + commands)}",
        '        mapfile -t COMPREPLY < <(compgen -W "$words" -- "$current")',
        "        return",
        "    fi",
        "",
        '    case "$command" in',
    ])
    for command in surface.commands:
        lines.append(
            f"        {command.name}) words={_shell_quote(_all_flags(command.options))} ;;"
        )
    lines.extend([
        "        *) return ;;",
        "    esac",
        "",
        '    case "$command:$current" in',
    ])
    for command in surface.commands:
        lines.extend(_bash_attached_dispatch(command.options, prefix=f"{command.name}:"))
    lines.extend([
        "    esac",
        "",
        '    case "$command:$previous" in',
    ])
    for command in surface.commands:
        lines.extend(_bash_value_dispatch(command.options, prefix=f"{command.name}:"))
    lines.extend([
        "    esac",
        '    mapfile -t COMPREPLY < <(compgen -W "$words" -- "$current")',
        "}",
        "complete -F _jring_completion jring",
        "",
    ])
    return "\n".join(lines)


def _roff(value: str) -> str:
    escaped_words = []
    for word in _plain(value).replace("\\", r"\e").replace("-", r"\-").split(" "):
        if word.startswith((".", "'")):
            word = r"\&" + word
        escaped_words.append(word)
    return " ".join(escaped_words)


def _man_option(option: OptionSurface) -> list[str]:
    flags = ", ".join(_roff(flag) for flag in option.flags)
    if option.metavar:
        flags += rf" \fI{_roff(option.metavar)}\fR"
    detail = option.help
    if option.choices:
        detail += f" Choices: {', '.join(option.choices)}."
    if option.required:
        detail += " Required."
    return [".TP", f".B {flags}", _roff(detail)]


def render_man(surface: CliSurface) -> str:
    lines = [
        '.TH "JRING" "1" "" "jring" "User Commands"',
        '.SH "NAME"',
        r"jring \- privacy\-first Linux client for explicitly selected JRing devices",
        '.SH "SYNOPSIS"',
        r".B jring",
        r"[global options] command [command options]",
        '.SH "DESCRIPTION"',
        _roff(
            "JRing is offline by default and does not scan, connect, write, or emit "
            "desktop input unless the matching command and explicit authorization gate "
            "are supplied. Generated help never probes Bluetooth or the host."
        ),
        _roff(surface.description),
        '.SH "COMMANDS"',
    ]
    for command in surface.commands:
        lines.extend([".TP", f".B {_roff(command.name)}", _roff(command.help)])
    lines.extend(['.SH "GLOBAL OPTIONS"'])
    for option in surface.global_options:
        lines.extend(_man_option(option))
    for command in surface.commands:
        lines.append(f'.SS "jring {command.name}"')
        for option in command.options:
            lines.extend(_man_option(option))
    lines.extend([
        '.SH "EXIT STATUS"',
        "Zero indicates success. Nonzero values identify usage, unavailable prerequisite, "
        "permission, timeout, protocol, or internal failures.",
        '.SH "PRIVACY AND FILES"',
        "Completion and manual artifacts are static package resources. Installing JRing "
        "does not configure a shell or copy these files into host completion or manual "
        "directories. Device addresses, captures, environment values, and runtime "
        "observations are never inputs to generation.",
        "",
    ])
    return "\n".join(lines)


def generate_artifacts(parser: argparse.ArgumentParser) -> dict[Path, bytes]:
    surface = extract_surface(parser)
    rendered = (
        render_bash(surface),
        render_man(surface),
    )
    return {
        path: text.encode("utf-8")
        for path, text in zip(ARTIFACTS, rendered, strict=True)
    }


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check tracked artifacts (default)")
    mode.add_argument("--write", action="store_true", help="atomically update tracked artifacts")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    generated = generate_artifacts(build_parser())
    if args.write:
        for relative, content in generated.items():
            _write_atomic(args.root / relative, content)
        return 0
    for relative, expected in generated.items():
        path = args.root / relative
        try:
            actual = path.read_bytes()
        except OSError:
            actual = None
        if actual != expected:
            print(f"generated CLI artifact is stale: {relative}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
