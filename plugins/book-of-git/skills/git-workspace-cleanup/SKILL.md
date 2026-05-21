---
name: git-workspace-cleanup
description: Explicit-invocation-only Git cleanup workflow that keeps only the main worktree and local main branch, then updates main. Use only when the user explicitly invokes $git-workspace-cleanup, /book-of-git:git-workspace-cleanup, or asks to use the git-workspace-cleanup skill.
disable-model-invocation: true
---

# Git Workspace Cleanup

Return a Git repository to a single clean main worktree: remove every non-main worktree, delete every local branch except `main`, and fast-forward `main` from its remote.

This is destructive. Never run it implicitly.

## Invocation

Use this skill only when the user explicitly invokes it. In Codex, the explicit invocation form is `$git-workspace-cleanup`. In Claude Code-compatible plugin readers, the explicit invocation form is `/book-of-git:git-workspace-cleanup`.

## Required Flow

1. State that the workflow can delete local worktrees and branches.
2. Resolve the bundled script relative to this `SKILL.md`:

   ```text
   scripts/git_workspace_cleanup.py
   ```

3. Run the bundled script in dry-run mode from any path inside the repository:

   ```bash
   python3 <skill-dir>/scripts/git_workspace_cleanup.py --repo . --dry-run
   ```

4. Show the user the main worktree path and the worktrees and branches that would be removed.
5. Ask for explicit approval before mutating the repository.
6. After approval, run:

   ```bash
   python3 <skill-dir>/scripts/git_workspace_cleanup.py --repo . --yes
   ```

7. Continue subsequent repository work from the printed main worktree path.
8. Verify the final state with:

   ```bash
   git worktree list
   git branch --format='%(refname:short)'
   git status --short --branch
   git pull --ff-only
   ```

Use `--repo <path>` when the current shell is not inside the target repository.

## Safety Rules

- Do not remove the worktree checked out on `main`.
- Do not delete the local `main` branch.
- Do not mutate anything unless the user approves the dry-run result.
- Stop if the main worktree is dirty.
- Stop if an extra worktree is dirty. Use `--force-worktrees` only when the user explicitly approves discarding files in those dirty extra worktrees.
- Treat `git pull --ff-only` failure as a blocker. Do not merge, rebase, reset, or force-push as part of this skill.
- If the repository uses a preserved branch other than `main`, rerun the script with `--main-branch <branch>` only after the user confirms that branch name.

## Script Behavior

The bundled script:

- locates the worktree checked out on the preserved branch, defaulting to `main`
- removes every other worktree
- deletes every other local branch with `git branch -D`
- runs `git fetch --prune origin`
- runs `git pull --ff-only origin main`

The script requires either `--dry-run` or `--yes`; it refuses to mutate by default.
