from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "book-of-git"
    / "skills"
    / "git-workspace-cleanup"
    / "scripts"
    / "git_workspace_cleanup.py"
)


def run(command: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=check, text=True, capture_output=True)


class GitWorkspaceCleanupScriptTests(unittest.TestCase):
    def make_repo(self, tmp: Path) -> tuple[Path, Path]:
        remote = tmp / "remote.git"
        main = tmp / "main"
        feature = tmp / "feature-worktree"

        run(["git", "init", "--bare", str(remote)], tmp)
        run(["git", "clone", str(remote), str(main)], tmp)
        run(["git", "config", "user.email", "agent@example.com"], main)
        run(["git", "config", "user.name", "Agent"], main)
        run(["git", "checkout", "-b", "main"], main)
        (main / "README.md").write_text("one\n")
        run(["git", "add", "README.md"], main)
        run(["git", "commit", "-m", "initial"], main)
        run(["git", "push", "-u", "origin", "main"], main)
        run(["git", "checkout", "-b", "topic"], main)
        run(["git", "checkout", "main"], main)
        run(["git", "worktree", "add", "-b", "worktree-topic", str(feature)], main)
        run(["git", "config", "user.email", "agent@example.com"], feature)
        run(["git", "config", "user.name", "Agent"], feature)
        return main, remote

    def advance_remote_main(self, tmp: Path, remote: Path) -> None:
        clone = tmp / "remote-advance"
        run(["git", "clone", str(remote), str(clone)], tmp)
        run(["git", "config", "user.email", "agent@example.com"], clone)
        run(["git", "config", "user.name", "Agent"], clone)
        run(["git", "checkout", "main"], clone)
        (clone / "README.md").write_text("two\n")
        run(["git", "commit", "-am", "advance main"], clone)
        run(["git", "push", "origin", "main"], clone)

    def test_dry_run_reports_changes_without_mutating_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            main, remote = self.make_repo(tmp)
            self.advance_remote_main(tmp, remote)

            result = run(
                [sys.executable, str(SCRIPT), "--repo", str(main), "--dry-run"],
                main,
            )

            self.assertIn("Would remove worktree", result.stdout)
            self.assertIn("Would delete local branch: topic", result.stdout)
            self.assertIn("Would update main with --ff-only", result.stdout)
            self.assertTrue((tmp / "feature-worktree").exists())
            branches = run(["git", "branch", "--format=%(refname:short)"], main).stdout
            self.assertIn("topic", branches)
            self.assertEqual((main / "README.md").read_text(), "one\n")

    def test_yes_removes_extra_worktrees_deletes_branches_and_updates_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            main, remote = self.make_repo(tmp)
            self.advance_remote_main(tmp, remote)

            result = run(
                [sys.executable, str(SCRIPT), "--repo", str(main), "--yes"],
                main,
            )

            self.assertIn("Removed worktree", result.stdout)
            self.assertIn("Deleted local branch: topic", result.stdout)
            self.assertIn("Updated main with --ff-only", result.stdout)
            self.assertFalse((tmp / "feature-worktree").exists())
            branches = run(["git", "branch", "--format=%(refname:short)"], main).stdout
            self.assertEqual(["main"], branches.splitlines())
            self.assertEqual((main / "README.md").read_text(), "two\n")

    def test_refuses_to_remove_dirty_worktree_without_force_worktrees(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            main, _remote = self.make_repo(tmp)
            (tmp / "feature-worktree" / "dirty.txt").write_text("dirty\n")

            result = run(
                [sys.executable, str(SCRIPT), "--repo", str(main), "--yes"],
                main,
                check=False,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("dirty worktree", result.stderr)
            self.assertTrue((tmp / "feature-worktree").exists())


if __name__ == "__main__":
    unittest.main()
