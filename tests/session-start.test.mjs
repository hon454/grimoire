import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { REPO_ROOT } from "./helpers.mjs";
import { detectHarness, stripFrontmatter, render } from "../plugins/archmage/scripts/session-start.mjs";

const PLUGIN = join(REPO_ROOT, "plugins", "archmage");
const SCRIPT = join(PLUGIN, "scripts", "session-start.mjs");

function runHook(env) {
  const base = { PATH: process.env.PATH, SystemRoot: process.env.SystemRoot, TEMP: process.env.TEMP, TMP: process.env.TMP, HOME: process.env.HOME, USERPROFILE: process.env.USERPROFILE };
  return spawnSync(process.execPath, [SCRIPT], {
    input: JSON.stringify({ session_id: "t", hook_event_name: "SessionStart", source: "startup" }),
    encoding: "utf8",
    env: { ...base, ...env },
  });
}

test("detectHarness: Claude sets only CLAUDE_* variables, Codex also sets PLUGIN_ROOT", () => {
  assert.equal(detectHarness({ CLAUDE_PLUGIN_ROOT: "/p", CLAUDE_PROJECT_DIR: "/w" }), "claude");
  assert.equal(detectHarness({ CLAUDE_PLUGIN_ROOT: "/p", PLUGIN_ROOT: "/p" }), "codex");
  assert.equal(detectHarness({ GRIMOIRE_HARNESS: "codex", CLAUDE_PROJECT_DIR: "/w" }), "codex");
  assert.equal(detectHarness({}), "claude");
});

test("stripFrontmatter removes the YAML block and keeps the body", () => {
  assert.equal(stripFrontmatter("---\nname: x\n---\n\n# Title\nbody\n"), "# Title\nbody");
  assert.equal(stripFrontmatter("no frontmatter\n"), "no frontmatter");
});

test("render: Claude gets hookSpecificOutput JSON, Codex gets plain text", () => {
  const claude = JSON.parse(render("claude", "ctx"));
  assert.equal(claude.hookSpecificOutput.hookEventName, "SessionStart");
  assert.equal(claude.hookSpecificOutput.additionalContext, "ctx");
  assert.equal(render("codex", "ctx"), "ctx\n");
});

test("hook process emits the required reading for Claude Code", () => {
  const r = runHook({ CLAUDE_PLUGIN_ROOT: PLUGIN, CLAUDE_PROJECT_DIR: REPO_ROOT });
  assert.equal(r.status, 0, r.stderr);
  const out = JSON.parse(r.stdout);
  assert.match(out.hookSpecificOutput.additionalContext, /<grimoire_required_reading>/);
  assert.match(out.hookSpecificOutput.additionalContext, /# Reading the grimoire/);
  assert.doesNotMatch(out.hookSpecificOutput.additionalContext, /^---/m, "frontmatter must be stripped");
});

test("hook process emits plain text for Codex", () => {
  const r = runHook({ CLAUDE_PLUGIN_ROOT: PLUGIN, PLUGIN_ROOT: PLUGIN });
  assert.equal(r.status, 0, r.stderr);
  assert.ok(r.stdout.startsWith("<grimoire_required_reading>"));
  assert.throws(() => JSON.parse(r.stdout));
});

test("hook process stays silent and exits 0 when the skill file is missing", () => {
  const r = runHook({ CLAUDE_PLUGIN_ROOT: join(REPO_ROOT, "does-not-exist"), CLAUDE_PROJECT_DIR: REPO_ROOT });
  assert.equal(r.status, 0);
  assert.equal(r.stdout, "");
});
