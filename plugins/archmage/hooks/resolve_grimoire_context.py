#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import locale as python_locale
import os
import platform
import re
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback.
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


SCHEMA_VERSION = 1
FALLBACK_LOCALE = "en-US"
IGNORED_LOCALES = {"", "C", "POSIX", "C.UTF-8"}
ALLOWED_TOP_LEVEL = {"schema_version", "output", "tracker"}
ALLOWED_OUTPUT_KEYS = {"locale"}
ALLOWED_TRACKER_KEYS = {"primary", "linear"}
ALLOWED_LINEAR_KEYS = {"team_identifier"}
TRACKER_PRIMARY_VALUES = {"none", "github", "linear"}


CommandRunner = Callable[[Sequence[str]], Optional[str]]


@dataclass(frozen=True)
class LocaleResult:
    locale: str
    source: str
    raw: str


@dataclass(frozen=True)
class ConfigSource:
    scope: str
    path: Path
    exists: bool


class ConfigError(ValueError):
    pass


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


def command_stdout(command: Sequence[str], cwd: Optional[Path] = None) -> Optional[str]:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
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


def parse_apple_languages(output: str) -> Optional[LocaleResult]:
    pattern = r'"([^"]+)"|([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})*)'
    for match in re.finditer(pattern, output):
        raw = match.group(1) or match.group(2)
        normalized = normalize_locale(raw)
        if normalized:
            return LocaleResult(normalized, "os:macos:AppleLanguages", raw)
    return None


def detect_macos_locale(runner: CommandRunner) -> Optional[LocaleResult]:
    apple_languages = runner(["defaults", "read", "-g", "AppleLanguages"])
    if apple_languages:
        detected = parse_apple_languages(apple_languages)
        if detected:
            return detected

    apple_locale = runner(["defaults", "read", "-g", "AppleLocale"])
    if apple_locale:
        normalized = normalize_locale(apple_locale)
        if normalized:
            return LocaleResult(normalized, "os:macos:AppleLocale", apple_locale)

    return None


def detect_windows_locale(runner: CommandRunner) -> Optional[LocaleResult]:
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
            return LocaleResult(normalized, "os:windows:Get-Culture", raw)
    return None


def detect_env_locale(environ: Mapping[str, str]) -> Optional[LocaleResult]:
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        raw = environ.get(key, "")
        normalized = normalize_locale(raw)
        if normalized:
            return LocaleResult(normalized, "env:" + key, raw)
    return None


def detect_python_locale() -> Optional[LocaleResult]:
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
            return LocaleResult(normalized, "python:locale", raw)
    return None


def detect_os_preferred_locale(
    environ: Optional[Mapping[str, str]] = None,
    system_name: Optional[str] = None,
    runner: Optional[CommandRunner] = None,
) -> LocaleResult:
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

    return LocaleResult(FALLBACK_LOCALE, "fallback", FALLBACK_LOCALE)


def default_user_grimoire_home(environ: Mapping[str, str]) -> Path:
    configured = environ.get("GRIMOIRE_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".grimoire"


def git_root(cwd: Path) -> Optional[Path]:
    output = command_stdout(["git", "rev-parse", "--show-toplevel"], cwd)
    if output:
        return Path(output).resolve()

    current = cwd.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def default_project_config(cwd: Path) -> Optional[Path]:
    root = git_root(cwd)
    if not root:
        return None
    return root / ".grimoire" / "config.toml"


def default_cache_path(project_root: Optional[Path], user_home: Path) -> Path:
    cache_root = user_home / "cache" / "sessions"
    if not project_root:
        return cache_root / "no-project" / "config.toml"
    digest = hashlib.sha256(str(project_root).encode("utf-8")).hexdigest()[:12]
    return cache_root / digest / "config.toml"


def load_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if tomllib is None:
        return parse_simple_toml(text, path)
    try:
        with path.open("rb") as handle:
            parsed = tomllib.load(handle)
    except tomllib.TOMLDecodeError as error:  # type: ignore[union-attr]
        raise ConfigError(str(error)) from error
    if not isinstance(parsed, dict):
        raise ConfigError("config root must be a TOML table")
    return parsed


def strip_toml_comment(line: str) -> str:
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


def split_array_items(raw: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escaped = False

    for char in raw:
        if in_double and escaped:
            current.append(char)
            escaped = False
            continue
        if in_double and char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            current.append(char)
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            current.append(char)
            continue
        if char == "," and not in_single and not in_double:
            item = "".join(current).strip()
            if item:
                items.append(item)
            current = []
            continue
        current.append(char)

    item = "".join(current).strip()
    if item:
        items.append(item)
    return items


def parse_simple_toml_value(raw: str, path: Path, line_number: int) -> Any:
    value = raw.strip()
    if not value:
        raise ConfigError(f"{path}:{line_number}: empty value")
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError as error:
            raise ConfigError(f"{path}:{line_number}: invalid string: {error}") from error
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_simple_toml_value(item, path, line_number) for item in split_array_items(inner)]
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"[+-]?\d+", value):
        return int(value)
    raise ConfigError(f"{path}:{line_number}: unsupported TOML value {value!r}")


def parse_simple_toml(text: str, path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    current = root

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_toml_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if not section_name:
                raise ConfigError(f"{path}:{line_number}: empty section name")
            current = root
            for part in section_name.split("."):
                if not re.fullmatch(r"[A-Za-z0-9_-]+", part):
                    raise ConfigError(f"{path}:{line_number}: invalid section name {section_name!r}")
                current = current.setdefault(part, {})
                if not isinstance(current, dict):
                    raise ConfigError(f"{path}:{line_number}: section conflicts with scalar value")
            continue

        key, separator, raw_value = line.partition("=")
        if separator != "=":
            raise ConfigError(f"{path}:{line_number}: expected key = value")
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]+", key):
            raise ConfigError(f"{path}:{line_number}: invalid key {key!r}")
        if key in current:
            raise ConfigError(f"{path}:{line_number}: duplicate key {key!r}")
        current[key] = parse_simple_toml_value(raw_value, path, line_number)

    return root


def require_table(value: Any, name: str, errors: list[str]) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.append(f"{name} must be a TOML table")
        return None
    return value


def validate_locale(value: Any, name: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{name} must be a string")
        return
    if value != "auto" and normalize_locale(value) is None:
        errors.append(f"{name} must be 'auto' or a valid locale tag")


def validate_config(data: dict[str, Any], source: ConfigSource) -> list[str]:
    errors: list[str] = []
    prefix = str(source.path)

    for key in data:
        if key not in ALLOWED_TOP_LEVEL:
            errors.append(f"{prefix}: unknown top-level key '{key}'")

    schema_version = data.get("schema_version", SCHEMA_VERSION)
    if schema_version != SCHEMA_VERSION:
        errors.append(f"{prefix}: schema_version must be {SCHEMA_VERSION}")

    output = require_table(data.get("output"), f"{prefix}: output", errors)
    if output is not None:
        for key in output:
            if key not in ALLOWED_OUTPUT_KEYS:
                errors.append(f"{prefix}: output.{key} is not supported")
        if "locale" in output:
            validate_locale(output["locale"], f"{prefix}: output.locale", errors)

    tracker = require_table(data.get("tracker"), f"{prefix}: tracker", errors)
    if tracker is not None:
        for key in tracker:
            if key not in ALLOWED_TRACKER_KEYS:
                errors.append(f"{prefix}: tracker.{key} is not supported")
        primary = tracker.get("primary")
        if primary is not None and primary not in TRACKER_PRIMARY_VALUES:
            errors.append(
                f"{prefix}: tracker.primary must be one of "
                + ", ".join(sorted(TRACKER_PRIMARY_VALUES))
            )
        linear = require_table(tracker.get("linear"), f"{prefix}: tracker.linear", errors)
        if linear is not None:
            for key in linear:
                if key not in ALLOWED_LINEAR_KEYS:
                    errors.append(f"{prefix}: tracker.linear.{key} is not supported")
            team_identifier = linear.get("team_identifier")
            if team_identifier is not None:
                if not isinstance(team_identifier, str):
                    errors.append(f"{prefix}: tracker.linear.team_identifier must be a string")
                elif not re.fullmatch(r"[A-Z][A-Z0-9]{1,9}", team_identifier):
                    errors.append(
                        f"{prefix}: invalid Linear team identifier {team_identifier!r}"
                    )

    return errors


def merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if key == "schema_version":
            merged[key] = value
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def empty_config() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "output": {"locale": "auto"},
        "tracker": {"primary": "none"},
    }


def read_sources(sources: Sequence[ConfigSource]) -> tuple[dict[str, Any], list[dict[str, str]], list[str]]:
    config = empty_config()
    loaded: list[dict[str, str]] = []
    errors: list[str] = []

    for source in sources:
        if not source.exists:
            continue
        try:
            data = load_toml_file(source.path)
        except ConfigError as error:
            errors.append(f"{source.path}: {error}")
            continue
        source_errors = validate_config(data, source)
        if source_errors:
            errors.extend(source_errors)
            continue
        config = merge_dict(config, data)
        loaded.append({"scope": source.scope, "path": str(source.path)})

    return config, loaded, errors


def locale_from_config(config: dict[str, Any], loaded_sources: Sequence[dict[str, str]]) -> Optional[LocaleResult]:
    configured = config.get("output", {}).get("locale", "auto")
    if configured == "auto":
        return None

    normalized = normalize_locale(configured)
    if not normalized:
        return None

    source = "config"
    for loaded in reversed(loaded_sources):
        try:
            data = load_toml_file(Path(loaded["path"]))
        except ConfigError:
            continue
        output = data.get("output", {})
        if isinstance(output, dict) and "locale" in output:
            source = "config:" + loaded["scope"]
            break

    return LocaleResult(normalized, source, configured)


def make_session_config(
    config: dict[str, Any],
    loaded_sources: Sequence[dict[str, str]],
    errors: Sequence[str],
    cache_path: Path,
    project_root: Optional[Path],
    locale_result: LocaleResult,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    session = {
        "schema_version": SCHEMA_VERSION,
        "session": {
            "generated_at": generated,
            "cache_path": str(cache_path),
            "project_root": str(project_root) if project_root else "",
            "sources": [loaded["scope"] + ":" + loaded["path"] for loaded in loaded_sources],
            "warnings": list(errors),
        },
        "output": {
            "locale": locale_result.locale,
            "locale_source": locale_result.source,
            "configured_locale": config.get("output", {}).get("locale", "auto"),
        },
        "tracker": deepcopy(config.get("tracker", {"primary": "none"})),
    }
    return session


def resolve_context(
    cwd: Path,
    user_config: Optional[Path] = None,
    project_config: Optional[Path] = None,
    cache_path: Optional[Path] = None,
    explicit_locale: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
    system_name: Optional[str] = None,
    runner: Optional[CommandRunner] = None,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    active_environ = os.environ if environ is None else environ
    user_home = default_user_grimoire_home(active_environ)
    project_root = git_root(cwd)
    user_path = user_config or user_home / "config.toml"
    project_path = project_config
    if project_path is None:
        project_path = default_project_config(cwd)

    sources = [ConfigSource("user", user_path, user_path.exists())]
    if project_path is not None:
        sources.append(ConfigSource("project", project_path, project_path.exists()))

    config, loaded_sources, errors = read_sources(sources)

    if explicit_locale:
        normalized = normalize_locale(explicit_locale)
        if not normalized:
            errors.append("explicit locale must be a valid locale tag")
            locale_result = LocaleResult(FALLBACK_LOCALE, "fallback", FALLBACK_LOCALE)
        else:
            locale_result = LocaleResult(normalized, "explicit", explicit_locale)
    else:
        locale_result = locale_from_config(config, loaded_sources) or detect_os_preferred_locale(
            environ=active_environ,
            system_name=system_name,
            runner=runner,
        )

    resolved_cache_path = cache_path or default_cache_path(project_root, user_home)
    return make_session_config(
        config,
        loaded_sources,
        errors,
        resolved_cache_path,
        project_root,
        locale_result,
        generated_at,
    )


def toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value: {value!r}")


def write_toml_section(lines: list[str], heading: str, values: Mapping[str, Any]) -> None:
    lines.append("")
    lines.append(f"[{heading}]")
    for key in sorted(values):
        value = values[key]
        if isinstance(value, dict):
            continue
        lines.append(f"{key} = {toml_value(value)}")


def to_toml(data: Mapping[str, Any]) -> str:
    lines = [f"schema_version = {toml_value(data['schema_version'])}"]
    for section in ("session", "output", "tracker"):
        values = data.get(section, {})
        if isinstance(values, dict):
            write_toml_section(lines, section, values)
            for key in sorted(values):
                nested = values[key]
                if isinstance(nested, dict):
                    write_toml_section(lines, f"{section}.{key}", nested)
    return "\n".join(lines).strip() + "\n"


def cache_session_config(data: Mapping[str, Any], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(to_toml(data), encoding="utf-8")


def print_text(data: Mapping[str, Any]) -> None:
    output = data["output"]
    tracker = data["tracker"]
    session = data["session"]
    print(
        "Grimoire context: "
        f"locale={output['locale']} "
        f"source={output['locale_source']} "
        f"tracker={tracker.get('primary', 'none')} "
        f"cache={session['cache_path']}"
    )
    warnings = session.get("warnings", [])
    for warning in warnings:
        print("Grimoire context warning: " + warning, file=sys.stderr)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resolve user and project .grimoire config into a session config cache."
    )
    parser.add_argument("--cwd", default=".", help="Working directory for project config lookup.")
    parser.add_argument("--user-config", help="Override the user .grimoire/config.toml path.")
    parser.add_argument("--project-config", help="Override the project .grimoire/config.toml path.")
    parser.add_argument("--cache-path", help="Override the session config cache path.")
    parser.add_argument("--explicit-locale", help="Explicit final-output locale tag.")
    parser.add_argument("--cache", action="store_true", help="Write the resolved session config.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when config is invalid.")
    parser.add_argument(
        "--format",
        choices=("text", "json", "toml"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    data = resolve_context(
        cwd=Path(args.cwd).resolve(),
        user_config=Path(args.user_config).expanduser() if args.user_config else None,
        project_config=Path(args.project_config).expanduser() if args.project_config else None,
        cache_path=Path(args.cache_path).expanduser() if args.cache_path else None,
        explicit_locale=args.explicit_locale,
    )

    warnings = data["session"].get("warnings", [])
    if args.cache and not warnings:
        cache_session_config(data, Path(data["session"]["cache_path"]))

    if args.format == "json":
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    elif args.format == "toml":
        print(to_toml(data), end="")
    else:
        print_text(data)

    if args.strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
