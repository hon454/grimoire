import { cpSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

export const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const TOOL = join(REPO_ROOT, "tools", "grimoire.mjs");

export function runTool(args, opts = {}) {
  const r = spawnSync(process.execPath, [TOOL, ...args], {
    cwd: opts.cwd || REPO_ROOT,
    encoding: "utf8",
    env: { ...process.env, ...(opts.env || {}) },
  });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr, out: r.stdout + r.stderr };
}

// Copies plugins/, claude-code-mods/ and tools/ into a temporary directory so tests can mutate freely.
export function makeSandbox() {
  const dir = mkdtempSync(join(tmpdir(), "grimoire-test-"));
  for (const sub of ["plugins", "claude-code-mods", "tools"]) {
    if (existsSync(join(REPO_ROOT, sub))) cpSync(join(REPO_ROOT, sub), join(dir, sub), { recursive: true });
  }
  runTool(["marketplaces", "--root", dir]);
  return {
    dir,
    tool: (args) => runTool([...args, "--root", dir]),
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}
