#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: Optional[str]


class GitError(RuntimeError):
    pass


def run_git(args: List[str], repo: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise GitError(f"git {' '.join(args)}: {message}")
    return result


def require_git_repo(repo: Path) -> Path:
    result = run_git(["rev-parse", "--show-toplevel"], repo)
    return Path(result.stdout.strip()).resolve()


def list_worktrees(repo: Path) -> list[Worktree]:
    output = run_git(["worktree", "list", "--porcelain"], repo).stdout
    entries: List[Worktree] = []
    current_path: Optional[Path] = None
    current_branch: Optional[str] = None

    for line in [*output.splitlines(), ""]:
        if not line:
            if current_path is not None:
                entries.append(Worktree(current_path, current_branch))
            current_path = None
            current_branch = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current_path = Path(value).resolve()
        elif key == "branch":
            prefix = "refs/heads/"
            current_branch = value.removeprefix(prefix)

    return entries


def find_main_worktree(worktrees: List[Worktree], main_branch: str) -> Worktree:
    matches = [worktree for worktree in worktrees if worktree.branch == main_branch]
    if not matches:
        raise GitError(f"no worktree is checked out on {main_branch}")
    if len(matches) > 1:
        paths = ", ".join(str(worktree.path) for worktree in matches)
        raise GitError(f"multiple {main_branch} worktrees found: {paths}")
    return matches[0]


def is_dirty(repo: Path) -> bool:
    return bool(run_git(["status", "--porcelain"], repo).stdout.strip())


def local_branches(repo: Path) -> List[str]:
    output = run_git(["branch", "--format=%(refname:short)"], repo).stdout
    return [line.strip() for line in output.splitlines() if line.strip()]


def require_remote(repo: Path, remote: str) -> None:
    run_git(["remote", "get-url", remote], repo)


def preflight_fast_forward(repo: Path, remote: str, main_branch: str) -> None:
    run_git(["fetch", "--prune", remote], repo)
    upstream = f"{remote}/{main_branch}"
    result = run_git(["merge-base", "--is-ancestor", "HEAD", upstream], repo, check=False)
    if result.returncode != 0:
        raise GitError(
            f"{main_branch} cannot fast-forward to {upstream}; "
            "refusing before removing worktrees or branches"
        )


def plan(args: argparse.Namespace) -> Tuple[Worktree, List[Worktree], List[str]]:
    starting_repo = require_git_repo(Path(args.repo).resolve())
    worktrees = list_worktrees(starting_repo)
    main_worktree = find_main_worktree(worktrees, args.main_branch)
    remove_worktrees = [worktree for worktree in worktrees if worktree.path != main_worktree.path]

    if is_dirty(main_worktree.path):
        raise GitError(f"main worktree is dirty: {main_worktree.path}")

    dirty_worktrees = [worktree.path for worktree in remove_worktrees if is_dirty(worktree.path)]
    if dirty_worktrees and not args.force_worktrees:
        paths = ", ".join(str(path) for path in dirty_worktrees)
        raise GitError(f"dirty worktree cannot be removed without --force-worktrees: {paths}")

    require_remote(main_worktree.path, args.remote)
    delete_branches = [
        branch for branch in local_branches(main_worktree.path) if branch != args.main_branch
    ]

    preflight_fast_forward(main_worktree.path, args.remote, args.main_branch)

    return main_worktree, remove_worktrees, delete_branches


def print_plan(
    main_worktree: Worktree,
    remove_worktrees: List[Worktree],
    delete_branches: List[str],
    args: argparse.Namespace,
) -> None:
    print(f"Main worktree: {main_worktree.path}")
    for worktree in remove_worktrees:
        print(f"Would remove worktree: {worktree.path} ({worktree.branch or 'detached'})")
    for branch in delete_branches:
        print(f"Would delete local branch: {branch}")
    print(f"Fetched --prune {args.remote}")
    print(f"Verified {args.main_branch} can fast-forward to {args.remote}/{args.main_branch}")
    print(f"Would update {args.main_branch} with --ff-only from {args.remote}/{args.main_branch}")


def apply_plan(
    main_worktree: Worktree,
    remove_worktrees: List[Worktree],
    delete_branches: List[str],
    args: argparse.Namespace,
) -> None:
    for worktree in remove_worktrees:
        command = ["worktree", "remove"]
        if args.force_worktrees:
            command.append("--force")
        command.append(str(worktree.path))
        run_git(command, main_worktree.path)
        print(f"Removed worktree: {worktree.path}")

    run_git(["checkout", args.main_branch], main_worktree.path)

    for branch in delete_branches:
        run_git(["branch", "-D", branch], main_worktree.path)
        print(f"Deleted local branch: {branch}")

    run_git(["fetch", "--prune", args.remote], main_worktree.path)
    run_git(["pull", "--ff-only", args.remote, args.main_branch], main_worktree.path)
    print(f"Updated {args.main_branch} with --ff-only from {args.remote}/{args.main_branch}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Keep only the main worktree and local main branch, then update main."
    )
    parser.add_argument("--repo", default=".", help="Any path inside the repository.")
    parser.add_argument("--main-branch", default="main", help="Branch to preserve.")
    parser.add_argument("--remote", default="origin", help="Remote to fetch and pull from.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes only.")
    parser.add_argument("--yes", action="store_true", help="Apply the planned changes.")
    parser.add_argument(
        "--force-worktrees",
        action="store_true",
        help="Allow removal of dirty extra worktrees. This can discard files.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if args.dry_run and args.yes:
        print("--dry-run and --yes cannot be used together", file=sys.stderr)
        return 2
    if not args.dry_run and not args.yes:
        print("refusing to mutate without --yes; use --dry-run to inspect first", file=sys.stderr)
        return 2

    try:
        main_worktree, remove_worktrees, delete_branches = plan(args)
        if args.dry_run:
            print_plan(main_worktree, remove_worktrees, delete_branches, args)
        else:
            apply_plan(main_worktree, remove_worktrees, delete_branches, args)
        return 0
    except GitError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
