#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitResult:
    returncode: int
    stdout: str
    stderr: str


def run_git(args: list[str], repo: Path, *, check: bool = True) -> GitResult:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    git_result = GitResult(result.returncode, result.stdout, result.stderr)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise GitError(f"git {' '.join(args)}: {message}")
    return git_result


def run_git_bytes(args: list[str], repo: Path, *, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
    )
    if check and result.returncode != 0:
        message = (
            result.stderr.decode(errors="replace").strip()
            or result.stdout.decode(errors="replace").strip()
            or "git command failed"
        )
        raise GitError(f"git {' '.join(args)}: {message}")
    return result.stdout


def require_repo(repo: Path) -> Path:
    result = run_git(["rev-parse", "--show-toplevel"], repo)
    return Path(result.stdout.strip()).resolve()


def git_dir(repo: Path) -> Path:
    result = run_git(["rev-parse", "--absolute-git-dir"], repo)
    return Path(result.stdout.strip()).resolve()


def current_branch(repo: Path) -> str | None:
    branch = run_git(["branch", "--show-current"], repo).stdout.strip()
    return branch or None


def current_head(repo: Path) -> str:
    return run_git(["rev-parse", "--verify", "HEAD"], repo).stdout.strip()


def upstream_ref(repo: Path) -> str | None:
    result = run_git(
        ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def base_ref_info(repo: Path, base_ref: str | None) -> dict[str, Any] | None:
    if not base_ref:
        return None
    result = run_git(["rev-parse", "--verify", f"{base_ref}^{{commit}}"], repo, check=False)
    if result.returncode != 0:
        return {"ref": base_ref, "exists": False, "sha": None}
    return {"ref": base_ref, "exists": True, "sha": result.stdout.strip()}


def operation_state(repo: Path) -> dict[str, Any]:
    directory = git_dir(repo)
    operations: list[str] = []

    if (directory / "rebase-merge").exists():
        operations.append("rebase-merge")
    if (directory / "rebase-apply").exists():
        operations.append("rebase-apply")
    if (directory / "MERGE_HEAD").exists():
        operations.append("merge")
    if (directory / "CHERRY_PICK_HEAD").exists():
        operations.append("cherry-pick")
    if (directory / "REVERT_HEAD").exists():
        operations.append("revert")

    return {"in_progress": bool(operations), "operations": operations}


def split_nul(output: bytes) -> list[str]:
    return [part.decode(errors="surrogateescape") for part in output.split(b"\0") if part]


def unmerged_paths(repo: Path) -> list[str]:
    output = run_git_bytes(["diff", "--name-only", "--diff-filter=U", "-z"], repo)
    return sorted(split_nul(output))


def ls_files_unmerged(repo: Path) -> dict[str, list[dict[str, str]]]:
    output = run_git(["ls-files", "-u"], repo).stdout
    entries: dict[str, list[dict[str, str]]] = {}
    for line in output.splitlines():
        metadata, _, path = line.partition("\t")
        mode, sha, stage = metadata.split()
        entries.setdefault(path, []).append({"mode": mode, "sha": sha, "stage": stage})
    return entries


def status_short(repo: Path) -> list[str]:
    output = run_git(["status", "--short", "--branch"], repo).stdout
    return output.splitlines()


def porcelain_paths(repo: Path) -> list[dict[str, Any]]:
    output = run_git_bytes(["status", "--porcelain=v1", "-z"], repo)
    parts = split_nul(output)
    items: list[dict[str, Any]] = []
    index = 0
    while index < len(parts):
        record = parts[index]
        index += 1
        if len(record) < 3:
            continue
        code = record[:2]
        path = record[3:]
        item: dict[str, Any] = {"code": code, "path": path}
        if code[0] in {"R", "C"}:
            if index < len(parts):
                item["from_path"] = parts[index]
                index += 1
        items.append(item)
    return items


def marker_counts(path: Path) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as error:
        return {"readable": False, "error": str(error)}

    if b"\0" in data[:8192]:
        return {"readable": True, "binary": True, "markers": None}

    text = data.decode("utf-8", errors="replace")
    return {
        "readable": True,
        "binary": False,
        "markers": {
            "start": text.count("<<<<<<<"),
            "separator": text.count("======="),
            "end": text.count(">>>>>>>"),
        },
    }


def conflict_details(repo: Path) -> list[dict[str, Any]]:
    staged = ls_files_unmerged(repo)
    details: list[dict[str, Any]] = []
    for path in unmerged_paths(repo):
        full_path = repo / path
        working_file: dict[str, Any] = {"exists": full_path.exists()}
        if full_path.exists():
            working_file.update(marker_counts(full_path))
        details.append(
            {
                "path": path,
                "stages": staged.get(path, []),
                "working_file": working_file,
            }
        )
    return details


def collect(repo_arg: str, base_ref: str | None) -> dict[str, Any]:
    repo = require_repo(Path(repo_arg).resolve())
    return {
        "repo_root": str(repo),
        "branch": current_branch(repo),
        "head": current_head(repo),
        "upstream": upstream_ref(repo),
        "base": base_ref_info(repo, base_ref),
        "operation": operation_state(repo),
        "status": {
            "short": status_short(repo),
            "porcelain": porcelain_paths(repo),
        },
        "conflicts": conflict_details(repo),
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"Repository: {report['repo_root']}")
    print(f"Branch: {report['branch'] or '(detached)'}")
    print(f"HEAD: {report['head']}")
    print(f"Upstream: {report['upstream'] or '(none)'}")

    base = report["base"]
    if base:
        status = base["sha"] if base["exists"] else "missing"
        print(f"Base: {base['ref']} ({status})")

    operation = report["operation"]
    if operation["in_progress"]:
        print(f"Operation in progress: {', '.join(operation['operations'])}")
    else:
        print("Operation in progress: none")

    print("Status:")
    for line in report["status"]["short"]:
        print(f"  {line}")

    conflicts = report["conflicts"]
    print(f"Unmerged paths: {len(conflicts)}")
    for conflict in conflicts:
        print(f"  {conflict['path']}")
        stages = ", ".join(entry["stage"] for entry in conflict["stages"])
        print(f"    stages: {stages or '(none)'}")
        working_file = conflict["working_file"]
        if working_file.get("binary"):
            print("    markers: binary file")
        elif working_file.get("markers") is not None:
            markers = working_file["markers"]
            print(
                "    markers: "
                f"start={markers['start']} separator={markers['separator']} end={markers['end']}"
            )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only Git conflict preflight for deterministic state collection."
    )
    parser.add_argument("--repo", default=".", help="Any path inside the repository.")
    parser.add_argument("--base-ref", help="Optional fetched base ref to verify, e.g. origin/main.")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        report = collect(args.repo, args.base_ref)
    except GitError as error:
        print(str(error), file=sys.stderr)
        return 1

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
