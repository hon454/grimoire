#!/usr/bin/env python3
"""Persist and prune magical-review-response checkpoints."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple


SCHEMA_VERSION = 1
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
TERMINAL_DECISIONS = {"decided", "deferred", "not_applicable"}
TERMINAL_WORKFLOW = {"completed", "not_applicable", "skipped", "blocked"}
WORKFLOW_KEYS = {
    "implementation",
    "verification",
    "reply",
    "resolve",
    "remote_write",
}


class StateError(ValueError):
    pass


def default_state_root() -> Path:
    configured = os.environ.get("GRIMOIRE_HOME")
    home = Path(configured).expanduser() if configured else Path.home() / ".grimoire"
    return home / "state" / "review-response" / "github"


def _exact_keys(value: Dict[str, Any], expected: set, label: str) -> None:
    if set(value) != expected:
        raise StateError(f"{label} must contain exactly {sorted(expected)}")


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise StateError(f"{label} must be a positive integer")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{label} must be a non-empty string")
    return value


def _safe_segment(value: Any, label: str) -> str:
    segment = _nonempty_string(value, label)
    if segment in {".", ".."} or not SAFE_SEGMENT.fullmatch(segment):
        raise StateError(f"{label} contains unsafe characters")
    return segment


def validate_checkpoint(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise StateError("checkpoint must be a JSON object")

    expected = {
        "schema_version",
        "revision",
        "platform",
        "host",
        "repository",
        "pull_request",
        "phase",
        "source_items",
        "decisions",
        "workflow_status",
        "updated_at",
    }
    _exact_keys(value, expected, "checkpoint")

    if value["schema_version"] != SCHEMA_VERSION:
        raise StateError("unsupported schema_version")
    if isinstance(value["revision"], bool) or not isinstance(value["revision"], int):
        raise StateError("revision must be an integer")
    if value["revision"] < 0:
        raise StateError("revision must be non-negative")
    if value["platform"] != "github":
        raise StateError("platform must be github")

    _safe_segment(value["host"], "host")

    repository = value["repository"]
    if not isinstance(repository, dict):
        raise StateError("repository must be an object")
    _exact_keys(repository, {"id", "owner", "name", "url"}, "repository")
    _positive_int(repository["id"], "repository.id")
    _safe_segment(repository["owner"], "repository.owner")
    _safe_segment(repository["name"], "repository.name")
    _nonempty_string(repository["url"], "repository.url")

    pull_request = value["pull_request"]
    if not isinstance(pull_request, dict):
        raise StateError("pull_request must be an object")
    _exact_keys(
        pull_request,
        {"id", "number", "url", "head_sha", "state"},
        "pull_request",
    )
    _positive_int(pull_request["id"], "pull_request.id")
    _positive_int(pull_request["number"], "pull_request.number")
    _nonempty_string(pull_request["url"], "pull_request.url")
    _nonempty_string(pull_request["head_sha"], "pull_request.head_sha")
    _nonempty_string(pull_request["state"], "pull_request.state")

    _nonempty_string(value["phase"], "phase")
    _nonempty_string(value["updated_at"], "updated_at")

    source_items = value["source_items"]
    if not isinstance(source_items, list):
        raise StateError("source_items must be an array")
    source_ids = set()
    for index, item in enumerate(source_items):
        if not isinstance(item, dict):
            raise StateError(f"source_items[{index}] must be an object")
        _exact_keys(
            item,
            {"id", "kind", "fingerprint", "state", "decision_required", "decision_id"},
            f"source_items[{index}]",
        )
        item_id = _nonempty_string(item["id"], f"source_items[{index}].id")
        if item_id in source_ids:
            raise StateError("source item IDs must be unique")
        source_ids.add(item_id)
        _nonempty_string(item["kind"], f"source_items[{index}].kind")
        _nonempty_string(item["fingerprint"], f"source_items[{index}].fingerprint")
        _nonempty_string(item["state"], f"source_items[{index}].state")
        if not isinstance(item["decision_required"], bool):
            raise StateError(f"source_items[{index}].decision_required must be boolean")
        if item["decision_id"] is not None:
            _nonempty_string(item["decision_id"], f"source_items[{index}].decision_id")

    decisions = value["decisions"]
    if not isinstance(decisions, list):
        raise StateError("decisions must be an array")
    decision_ids = set()
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise StateError(f"decisions[{index}] must be an object")
        _exact_keys(
            decision,
            {
                "id",
                "source_ids",
                "type",
                "status",
                "choice",
                "implementation_status",
                "verification_status",
                "reply_status",
                "resolve_action",
            },
            f"decisions[{index}]",
        )
        decision_id = _nonempty_string(decision["id"], f"decisions[{index}].id")
        if decision_id in decision_ids:
            raise StateError("decision IDs must be unique")
        decision_ids.add(decision_id)
        if not isinstance(decision["source_ids"], list) or not decision["source_ids"]:
            raise StateError(f"decisions[{index}].source_ids must be a non-empty array")
        for source_id in decision["source_ids"]:
            if source_id not in source_ids:
                raise StateError(f"decisions[{index}] references an unknown source item")
        for key in (
            "type",
            "status",
            "choice",
            "implementation_status",
            "verification_status",
            "reply_status",
            "resolve_action",
        ):
            _nonempty_string(decision[key], f"decisions[{index}].{key}")

    for index, item in enumerate(source_items):
        decision_id = item["decision_id"]
        if decision_id is not None and decision_id not in decision_ids:
            raise StateError(f"source_items[{index}] references an unknown decision")

    workflow = value["workflow_status"]
    if not isinstance(workflow, dict):
        raise StateError("workflow_status must be an object")
    _exact_keys(workflow, WORKFLOW_KEYS, "workflow_status")
    for key, status_value in workflow.items():
        _nonempty_string(status_value, f"workflow_status.{key}")

    return value


def checkpoint_path(root: Path, value: Dict[str, Any]) -> Path:
    validated = validate_checkpoint(value)
    return (
        root
        / validated["host"]
        / str(validated["repository"]["id"])
        / f'{validated["pull_request"]["number"]}.json'
    )


def _regular_file(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _load_file(path: Path) -> Dict[str, Any]:
    if not _regular_file(path):
        raise StateError("checkpoint path is not a regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"checkpoint is unreadable: {exc}") from exc
    return validate_checkpoint(value)


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(lock_path), flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise StateError("checkpoint lock is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _atomic_write(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp:
            temp_name = temp.name
            os.chmod(temp_name, 0o600)
            json.dump(value, temp, indent=2, sort_keys=True, ensure_ascii=False)
            temp.write("\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
        temp_name = None
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp_name is not None:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def write_checkpoint(root: Path, value: Dict[str, Any]) -> Tuple[Path, Dict[str, Any]]:
    value = json.loads(json.dumps(value))
    value.setdefault("revision", 0)
    value.setdefault("updated_at", "pending")
    validate_checkpoint(value)
    path = checkpoint_path(root, value)
    with _file_lock(path):
        revision = 0
        if path.exists() or path.is_symlink():
            current = _load_file(path)
            if checkpoint_path(root, current) != path:
                raise StateError("existing checkpoint identity does not match its path")
            revision = current["revision"]
        value["revision"] = revision + 1
        value["updated_at"] = datetime.now(timezone.utc).isoformat()
        validate_checkpoint(value)
        _atomic_write(path, value)
    return path, value


def read_checkpoint(root: Path, host: str, repository_id: int, pr_number: int) -> Dict[str, Any]:
    _safe_segment(host, "host")
    path = root / host / str(_positive_int(repository_id, "repository_id")) / f"{_positive_int(pr_number, 'pr_number')}.json"
    value = _load_file(path)
    if checkpoint_path(root, value) != path:
        raise StateError("checkpoint identity does not match its path")
    return value


def _completed(value: Dict[str, Any]) -> bool:
    if value["phase"] != "completed":
        return False
    decisions = {decision["id"]: decision for decision in value["decisions"]}
    for item in value["source_items"]:
        if item["decision_required"]:
            decision = decisions.get(item["decision_id"])
            if decision is None or decision["status"] not in TERMINAL_DECISIONS:
                return False
    if any(decision["status"] not in TERMINAL_DECISIONS for decision in value["decisions"]):
        return False
    return all(status_value in TERMINAL_WORKFLOW for status_value in value["workflow_status"].values())


def _state_files(root: Path) -> Iterator[Path]:
    if not root.exists():
        return
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = [name for name in names if not (Path(directory) / name).is_symlink()]
        for name in files:
            if name.endswith(".json"):
                yield Path(directory) / name


def _gh_api(host: str, endpoint: str, paginate: bool) -> Any:
    command = ["gh", "api", "--hostname", host]
    if paginate:
        command.extend(["--paginate", "--slurp"])
    command.append(endpoint)
    environment = dict(os.environ)
    environment.update({"GH_PAGER": "cat", "NO_COLOR": "1"})
    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=30,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StateError(f"GitHub query failed: {exc}") from exc
    if completed.returncode != 0 or completed.stderr.strip():
        raise StateError("GitHub query returned an error or warning")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise StateError("GitHub query returned invalid or truncated JSON") from exc


def _repo_id_from_pr(value: Any) -> Optional[int]:
    try:
        repository_id = value["base"]["repo"]["id"]
    except (KeyError, TypeError):
        return None
    if isinstance(repository_id, bool) or not isinstance(repository_id, int):
        return None
    return repository_id


def cleanup_checkpoints(
    root: Path,
    api: Optional[Callable[[str, str, bool], Any]] = None,
) -> Dict[str, Any]:
    query = api or _gh_api
    result: Dict[str, Any] = {
        "deleted": [],
        "preserved": [],
        "skipped_repositories": [],
    }
    groups: Dict[Tuple[str, int, str, str], List[Tuple[Path, Dict[str, Any]]]] = {}

    for path in _state_files(root):
        try:
            value = _load_file(path)
            if checkpoint_path(root, value) != path or not _completed(value):
                result["preserved"].append(str(path))
                continue
            repository = value["repository"]
            key = (value["host"], repository["id"], repository["owner"], repository["name"])
            groups.setdefault(key, []).append((path, value))
        except StateError:
            result["preserved"].append(str(path))

    for (host, repository_id, owner, name), candidates in groups.items():
        repository_endpoint = f"repos/{owner}/{name}"
        open_endpoint = f"repos/{owner}/{name}/pulls?state=open&per_page=100"
        try:
            repository = query(host, repository_endpoint, False)
            if not isinstance(repository, dict) or repository.get("id") != repository_id:
                raise StateError("canonical repository identity mismatch")
            pages = query(host, open_endpoint, True)
            if not isinstance(pages, list) or not pages or any(not isinstance(page, list) for page in pages):
                raise StateError("OPEN PR pagination was incomplete")
            open_numbers = set()
            for page in pages:
                for pull in page:
                    if (
                        not isinstance(pull, dict)
                        or isinstance(pull.get("number"), bool)
                        or not isinstance(pull.get("number"), int)
                        or _repo_id_from_pr(pull) != repository_id
                    ):
                        raise StateError("OPEN PR list contained incomplete identity data")
                    open_numbers.add(pull["number"])
        except StateError:
            result["skipped_repositories"].append(f"{host}/{owner}/{name}")
            result["preserved"].extend(str(path) for path, _ in candidates)
            continue

        for path, snapshot in candidates:
            number = snapshot["pull_request"]["number"]
            if number in open_numbers:
                result["preserved"].append(str(path))
                continue
            try:
                pull = query(host, f"repos/{owner}/{name}/pulls/{number}", False)
                if (
                    not isinstance(pull, dict)
                    or pull.get("number") != number
                    or _repo_id_from_pr(pull) != repository_id
                    or pull.get("state") != "closed"
                ):
                    raise StateError("candidate PR was not explicitly CLOSED or MERGED")

                with _file_lock(path):
                    current = _load_file(path)
                    if (
                        current["revision"] != snapshot["revision"]
                        or checkpoint_path(root, current) != path
                        or not _completed(current)
                    ):
                        raise StateError("checkpoint changed before deletion")
                    path.unlink()
                result["deleted"].append(str(path))
            except (OSError, StateError):
                result["preserved"].append(str(path))

    for key in result:
        result[key] = sorted(set(result[key]))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_state_root())
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("write", help="read a checkpoint from stdin and write it atomically")

    read = subparsers.add_parser("read", help="print one validated checkpoint")
    read.add_argument("--host", required=True)
    read.add_argument("--repository-id", required=True, type=int)
    read.add_argument("--pr-number", required=True, type=int)

    subparsers.add_parser("cleanup", help="delete safely completed CLOSED or MERGED checkpoints")
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.command == "write":
            value = json.load(sys.stdin)
            path, stored = write_checkpoint(arguments.root, value)
            output = {"path": str(path), "checkpoint": stored}
        elif arguments.command == "read":
            output = read_checkpoint(
                arguments.root,
                arguments.host,
                arguments.repository_id,
                arguments.pr_number,
            )
        else:
            output = cleanup_checkpoints(arguments.root)
        json.dump(output, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0
    except (OSError, StateError, json.JSONDecodeError) as exc:
        json.dump({"error": str(exc)}, sys.stderr, ensure_ascii=False)
        sys.stderr.write("\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
