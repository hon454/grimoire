#!/usr/bin/env python3
"""Read the translation locale from the Grimoire session config cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    tomllib = None  # type: ignore[assignment]


def git_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        result = None

    if result and result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip()).resolve()

    current = cwd.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def grimoire_home() -> Path:
    configured = os.environ.get("GRIMOIRE_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".grimoire"


def default_cache_path(project_root: Path | None, home: Path) -> Path:
    cache_root = home / "cache" / "sessions"
    if project_root is None:
        return cache_root / "no-project" / "config.toml"
    digest = hashlib.sha256(str(project_root).encode("utf-8")).hexdigest()[:12]
    return cache_root / digest / "config.toml"


def load_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        return load_output_toml_fallback(path)
    with path.open("rb") as handle:
        parsed = tomllib.load(handle)
    if not isinstance(parsed, dict):
        raise RuntimeError("session config cache root must be a TOML table")
    return parsed


def strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(line):
        if in_double and escaped:
            escaped = False
            continue
        if in_double and char == "\\":
            escaped = True
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def parse_string_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        parsed = json.loads(value)
        if isinstance(parsed, str):
            return parsed
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    raise RuntimeError(f"unsupported TOML string value: {value}")


def load_output_toml_fallback(path: Path) -> dict[str, Any]:
    current_section = ""
    output: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = strip_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            continue
        if current_section != "output" or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"locale", "locale_source", "configured_locale"}:
            output[key] = parse_string_value(value)
    return {"output": output}


def resolve_locale(cwd: Path, cache_path: Path | None) -> dict[str, str]:
    project_root = git_root(cwd)
    resolved_cache_path = cache_path or default_cache_path(project_root, grimoire_home())
    if not resolved_cache_path.exists():
        raise RuntimeError(f"session config cache not found: {resolved_cache_path}")

    data = load_toml(resolved_cache_path)
    output = data.get("output")
    if not isinstance(output, dict):
        raise RuntimeError(f"{resolved_cache_path}: missing [output] table")

    locale = output.get("locale")
    if not isinstance(locale, str) or not locale.strip():
        raise RuntimeError(f"{resolved_cache_path}: missing output.locale")

    locale_source = output.get("locale_source", "")
    if not isinstance(locale_source, str):
        locale_source = ""

    configured_locale = output.get("configured_locale", "")
    if not isinstance(configured_locale, str):
        configured_locale = ""

    return {
        "locale": locale.strip(),
        "locale_source": locale_source,
        "configured_locale": configured_locale,
        "cache_path": str(resolved_cache_path),
        "project_root": str(project_root) if project_root else "",
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read output.locale from the Grimoire session config cache."
    )
    parser.add_argument("--cwd", default=".", help="Working directory for project cache lookup.")
    parser.add_argument("--cache-path", help="Explicit session config cache path.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format. text prints only the locale.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        result = resolve_locale(
            Path(args.cwd).expanduser(),
            Path(args.cache_path).expanduser() if args.cache_path else None,
        )
    except Exception as error:  # noqa: BLE001 - CLI should show actionable errors.
        print(f"error: {error}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(result["locale"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
