#!/usr/bin/env node
// SessionStart hook for the archmage plugin.
//
// Reads the body of skills/required-reading/SKILL.md and hands it to the
// harness as additional context. Works in Claude Code and Codex:
//
//   Claude Code  stdout JSON {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"..."}}
//   Codex        stdout plain text (Codex adds plain SessionStart stdout as developer context)
//
// Harness detection: Codex exports PLUGIN_ROOT for plugin hooks in addition to
// the compatibility variable CLAUDE_PLUGIN_ROOT; Claude Code exports only the
// CLAUDE_* variables. GRIMOIRE_HARNESS=claude|codex overrides detection (used by tests).
//
// Dependency-free, Node >= 20. Never throws: on any failure it exits 0 with no
// output so the session still starts.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pluginRoot = process.env.CLAUDE_PLUGIN_ROOT || process.env.PLUGIN_ROOT || join(here, "..");

export function detectHarness(env = process.env) {
  const forced = (env.GRIMOIRE_HARNESS || "").toLowerCase();
  if (forced === "claude" || forced === "codex") return forced;
  if (env.PLUGIN_ROOT && !env.CLAUDE_PROJECT_DIR) return "codex";
  return "claude";
}

export function stripFrontmatter(markdown) {
  if (!markdown.startsWith("---")) return markdown.trim();
  const end = markdown.indexOf("\n---", 3);
  if (end === -1) return markdown.trim();
  return markdown.slice(end + 4).trim();
}

export function buildContext(skillBody) {
  return [
    "<grimoire_required_reading>",
    "The grimoire is installed. The text below is the archmage's required reading on how to use its books.",
    "",
    skillBody,
    "</grimoire_required_reading>",
  ].join("\n");
}

export function render(harness, context) {
  if (harness === "codex") return context + "\n";
  return JSON.stringify({
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: context,
    },
  }) + "\n";
}

function main() {
  // Drain stdin so the harness never blocks on a full pipe; the payload is not needed.
  try {
    if (!process.stdin.isTTY) readFileSync(0, "utf8");
  } catch {
    // ignore
  }
  let body;
  try {
    body = stripFrontmatter(readFileSync(join(pluginRoot, "skills", "required-reading", "SKILL.md"), "utf8"));
  } catch {
    return;
  }
  process.stdout.write(render(detectHarness(), buildContext(body)));
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main();
}
