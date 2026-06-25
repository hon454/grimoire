#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import locale as python_locale
import os
import platform
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Optional, Sequence


FALLBACK_LOCALE = "en-US"
IGNORED_LOCALES = {"", "C", "POSIX", "C.UTF-8"}


@dataclass(frozen=True)
class OutputLocale:
    locale: str
    source: str
    raw: str


CommandRunner = Callable[[Sequence[str]], Optional[str]]


def normalize_locale(value: str) -> Optional[str]:
    raw = value.strip().strip("\"'")
    if not raw:
        return None

    raw = raw.split(":", 1)[0]
    raw = raw.split(".", 1)[0]
    raw = raw.split("@", 1)[0]
    raw = raw.replace("_", "-")

    if raw.upper() in IGNORED_LOCALES:
        return None

    parts = [part for part in raw.split("-") if part]
    if not parts or not re.fullmatch(r"[A-Za-z]{2,3}", parts[0]):
        return None

    normalized = [parts[0].lower()]
    for part in parts[1:]:
        if re.fullmatch(r"[A-Za-z]{4}", part):
            normalized.append(part.title())
        elif re.fullmatch(r"[A-Za-z]{2}|[0-9]{3}", part):
            normalized.append(part.upper())
        elif re.fullmatch(r"[A-Za-z0-9]{5,8}|[0-9][A-Za-z0-9]{3}", part):
            normalized.append(part.lower())
        else:
            return None

    return "-".join(normalized)


def command_stdout(command: Sequence[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            list(command),
            check=False,
            text=True,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip()


def parse_apple_languages(output: str) -> Optional[OutputLocale]:
    pattern = r'"([^"]+)"|([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*)'
    for match in re.finditer(pattern, output):
        raw = match.group(1) or match.group(2)
        normalized = normalize_locale(raw)
        if normalized:
            return OutputLocale(normalized, "macos:AppleLanguages", raw)
    return None


def detect_macos_locale(runner: CommandRunner) -> Optional[OutputLocale]:
    apple_languages = runner(["defaults", "read", "-g", "AppleLanguages"])
    if apple_languages:
        detected = parse_apple_languages(apple_languages)
        if detected:
            return detected

    apple_locale = runner(["defaults", "read", "-g", "AppleLocale"])
    if apple_locale:
        normalized = normalize_locale(apple_locale)
        if normalized:
            return OutputLocale(normalized, "macos:AppleLocale", apple_locale)

    return None


def detect_windows_locale(runner: CommandRunner) -> Optional[OutputLocale]:
    commands = [
        ["powershell", "-NoProfile", "-Command", "(Get-Culture).Name"],
        ["powershell.exe", "-NoProfile", "-Command", "(Get-Culture).Name"],
        ["pwsh", "-NoProfile", "-Command", "(Get-Culture).Name"],
    ]
    for command in commands:
        raw = runner(command)
        if not raw:
            continue
        normalized = normalize_locale(raw)
        if normalized:
            return OutputLocale(normalized, "windows:Get-Culture", raw)
    return None


def detect_env_locale(environ: Mapping[str, str]) -> Optional[OutputLocale]:
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        raw = environ.get(key, "")
        normalized = normalize_locale(raw)
        if normalized:
            return OutputLocale(normalized, "env:" + key, raw)
    return None


def detect_python_locale() -> Optional[OutputLocale]:
    candidates = []
    try:
        candidates.append(python_locale.getlocale()[0])
    except ValueError:
        pass
    try:
        candidates.append(python_locale.getdefaultlocale()[0])
    except ValueError:
        pass

    for raw in candidates:
        if not raw:
            continue
        normalized = normalize_locale(raw)
        if normalized:
            return OutputLocale(normalized, "python:locale", raw)
    return None


def detect_os_preferred_locale(
    explicit_locale: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    system_name: Optional[str] = None,
    runner: Optional[CommandRunner] = None,
) -> OutputLocale:
    if explicit_locale:
        normalized = normalize_locale(explicit_locale)
        if not normalized:
            raise ValueError("invalid explicit locale: " + explicit_locale)
        return OutputLocale(normalized, "explicit", explicit_locale)

    active_environ = os.environ if environ is None else environ
    active_system = system_name or platform.system()
    active_runner = runner or command_stdout

    if active_system == "Darwin":
        detected = detect_macos_locale(active_runner)
        if detected:
            return detected
    elif active_system == "Windows":
        detected = detect_windows_locale(active_runner)
        if detected:
            return detected

    detected = detect_env_locale(active_environ)
    if detected:
        return detected

    detected = detect_python_locale()
    if detected:
        return detected

    return OutputLocale(FALLBACK_LOCALE, "fallback", FALLBACK_LOCALE)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect the host OS preferred locale with an optional explicit override."
    )
    parser.add_argument(
        "--explicit-locale",
        help="Explicit final-output locale tag supplied by the user.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    try:
        result = detect_os_preferred_locale(explicit_locale=args.explicit_locale)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    else:
        print("Locale: " + result.locale)
        print("Source: " + result.source)
        print("Raw: " + result.raw)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
