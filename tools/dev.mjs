// Development install for grimoire: the "swap model" of ADR 0009.
//
// The marketplace name stays `grimoire` in both harnesses. dev-install swaps the
// registered source (normally GitHub) for this local checkout, dev-refresh
// re-copies the plugins after edits, and dev-uninstall swaps GitHub back.
// Plugin ids such as `archmage@grimoire` never change across a swap, so the
// harnesses' enabled-plugin settings are left alone.
//
// Everything that touches the user's machine goes through `runner`, so the plan
// builder below is pure and unit-testable.

import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { createInterface } from "node:readline/promises";

export const MARKETPLACE_NAME = "grimoire";
export const GITHUB_SOURCE = "hon454/grimoire";

// ---------------------------------------------------------------------------
// Running harness CLIs
// ---------------------------------------------------------------------------

function quoteArg(a) {
  return /[\s"]/.test(a) ? `"${a.replace(/"/g, '\\"')}"` : a;
}

export function createRunner({ verbose = false } = {}) {
  return {
    run(argv) {
      if (verbose) console.log(`$ ${argv.map(quoteArg).join(" ")}`);
      const win = process.platform === "win32";
      // claude and codex are .cmd shims on Windows, which spawnSync can only start through a shell.
      const r = win
        ? spawnSync(argv.map(quoteArg).join(" "), { shell: true, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] })
        : spawnSync(argv[0], argv.slice(1), { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
      return { code: r.status ?? 1, stdout: r.stdout || "", stderr: r.stderr || "" };
    },
    json(argv) {
      const r = this.run(argv);
      if (r.code !== 0) throw new Error(`${argv.join(" ")} failed (${r.code}): ${(r.stderr || r.stdout).trim()}`);
      // Some commands print a human line before the JSON; take the first { or [.
      const text = r.stdout;
      const start = Math.min(...["{", "["].map((c) => text.indexOf(c)).filter((i) => i >= 0));
      return JSON.parse(text.slice(start));
    },
  };
}

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

export function normalizePath(p) {
  if (!p) return "";
  let s = String(p).replace(/^\\\\\?\\/, "");
  s = resolve(s).replace(/\\/g, "/").replace(/\/+$/, "");
  return process.platform === "win32" ? s.toLowerCase() : s;
}

export function samePath(a, b) {
  return normalizePath(a) === normalizePath(b);
}

export function codexHome() {
  return process.env.CODEX_HOME || join(homedir(), ".codex");
}

// ---------------------------------------------------------------------------
// Reading state
// ---------------------------------------------------------------------------

// Claude: `claude plugin marketplace list --json` entries look like
//   { name, source: "directory", path }  or  { name, source: "github", repo }
export function parseClaudeMarketplace(list) {
  const entries = Array.isArray(list) ? list : Object.values(list || {});
  const m = entries.find((e) => e && e.name === MARKETPLACE_NAME);
  if (!m) return null;
  const source = typeof m.source === "string" ? m.source : m.source?.source;
  return { kind: source || "unknown", path: m.path ?? m.source?.path, repo: m.repo ?? m.source?.repo, raw: m };
}

export function parseClaudePlugins(list) {
  return (Array.isArray(list) ? list : [])
    .filter((p) => typeof p.id === "string" && p.id.endsWith(`@${MARKETPLACE_NAME}`))
    .map((p) => ({ id: p.id, version: p.version, scope: p.scope }));
}

// Codex: `[marketplaces.grimoire]` in config.toml carries source_type and source.
export function parseCodexConfigMarketplace(toml) {
  const m = new RegExp(`^\\[marketplaces\\.${MARKETPLACE_NAME}\\]\\s*$([\\s\\S]*?)(?=^\\[|(?![\\s\\S]))`, "m").exec(toml);
  if (!m) return null;
  const block = m[1];
  const get = (key) => {
    const r = new RegExp(`^${key}\\s*=\\s*(?:'([^']*)'|"([^"]*)")`, "m").exec(block);
    return r ? (r[1] ?? r[2]) : undefined;
  };
  return { kind: get("source_type") || "unknown", source: get("source"), raw: block.trim() };
}

export function parseCodexPlugins(list) {
  return (list?.installed || [])
    .filter((p) => p.marketplaceName === MARKETPLACE_NAME && p.installed !== false)
    .map((p) => ({ id: p.pluginId || `${p.name}@${MARKETPLACE_NAME}`, version: p.version, enabled: p.enabled }));
}

export function readState(runner, repoRoot) {
  const state = { claude: null, codex: null };
  try {
    state.claude = {
      marketplace: parseClaudeMarketplace(runner.json(["claude", "plugin", "marketplace", "list", "--json"])),
      plugins: parseClaudePlugins(runner.json(["claude", "plugin", "list", "--json"])),
    };
  } catch (e) {
    state.claude = { error: e.message, marketplace: null, plugins: [] };
  }
  try {
    const cfg = join(codexHome(), "config.toml");
    const marketplace = existsSync(cfg) ? parseCodexConfigMarketplace(readFileSync(cfg, "utf8")) : null;
    state.codex = {
      marketplace,
      plugins: parseCodexPlugins(runner.json(["codex", "plugin", "list", "--json"])),
    };
  } catch (e) {
    state.codex = { error: e.message, marketplace: null, plugins: [] };
  }
  state.claude.local = Boolean(state.claude.marketplace && state.claude.marketplace.kind === "directory" && samePath(state.claude.marketplace.path, repoRoot));
  state.codex.local = Boolean(state.codex.marketplace && state.codex.marketplace.kind === "local" && samePath(state.codex.marketplace.source, repoRoot));
  return state;
}

export function describeState(state) {
  const lines = [];
  for (const h of ["claude", "codex"]) {
    const s = state[h];
    const mp = s.marketplace;
    let where = "not registered";
    if (mp) where = h === "claude" ? `${mp.kind} ${mp.path || mp.repo || ""}`.trim() : `${mp.kind} ${mp.source || ""}`.trim();
    lines.push(`${h.padEnd(7)} marketplace ${MARKETPLACE_NAME}: ${where}${s.local ? "  (this checkout)" : ""}`);
    if (s.error) lines.push(`        could not read state: ${s.error}`);
    for (const p of s.plugins) lines.push(`        installed ${p.id} ${p.version || ""}`.trimEnd());
    if (!s.plugins.length) lines.push("        no grimoire plugins installed");
  }
  return lines.join("\n");
}

// ---------------------------------------------------------------------------
// Planning (pure)
// ---------------------------------------------------------------------------

const CLAUDE_DATA_WARNING = (ids) =>
  `Claude Code deletes the saved data, options and secrets of every plugin installed from marketplace "${MARKETPLACE_NAME}" when the marketplace is removed (${ids.length ? ids.join(", ") : "none installed"}).`;

function pluginIds(state, repoPlugins) {
  const ids = state.plugins.map((p) => p.id);
  return ids.length ? ids : repoPlugins.map((n) => `${n}@${MARKETPLACE_NAME}`);
}

function unionIds(state, repoPlugins) {
  return [...new Set([...state.plugins.map((p) => p.id), ...repoPlugins.map((n) => `${n}@${MARKETPLACE_NAME}`)])].sort();
}

export function buildPlan(state, mode, { repoRoot, repoPlugins }) {
  const steps = [];
  const notes = [];
  const step = (harness, title, argv, destructive) => steps.push({ harness, title, argv, destructive });

  const claudeInstalled = new Set(state.claude.plugins.map((p) => p.id));
  const codexInstalled = new Set(state.codex.plugins.map((p) => p.id));

  if (mode === "install") {
    // Claude: removing the marketplace also uninstalls its plugins, so swap first, then install.
    const claudeIds = pluginIds(state.claude, repoPlugins);
    if (state.claude.local) {
      notes.push("claude: marketplace already points at this checkout; plugins are refreshed in place.");
      for (const id of unionIds(state.claude, repoPlugins)) {
        if (claudeInstalled.has(id)) step("claude", `refresh ${id} (uninstall --keep-data, install)`, ["claude", "plugin", "uninstall", id, "--keep-data"]);
        step("claude", `install ${id}`, ["claude", "plugin", "install", id]);
      }
    } else {
      if (state.claude.marketplace) {
        step("claude", `remove marketplace ${MARKETPLACE_NAME} (${state.claude.marketplace.kind})`, ["claude", "plugin", "marketplace", "remove", MARKETPLACE_NAME], CLAUDE_DATA_WARNING([...claudeInstalled]));
      }
      step("claude", `add marketplace ${MARKETPLACE_NAME} from ${repoRoot}`, ["claude", "plugin", "marketplace", "add", repoRoot]);
      for (const id of claudeIds) step("claude", `install ${id}`, ["claude", "plugin", "install", id]);
    }

    // Codex: remove plugins while their marketplace is still registered, swap, then add them back.
    const codexIds = pluginIds(state.codex, repoPlugins);
    if (state.codex.local) {
      notes.push("codex: marketplace already points at this checkout; plugins are re-copied.");
      for (const id of unionIds(state.codex, repoPlugins)) {
        if (codexInstalled.has(id)) step("codex", `remove ${id} (refresh)`, ["codex", "plugin", "remove", id]);
        step("codex", `add ${id}`, ["codex", "plugin", "add", id]);
      }
    } else {
      for (const id of codexIds) if (codexInstalled.has(id)) step("codex", `remove ${id} before the swap`, ["codex", "plugin", "remove", id]);
      if (state.codex.marketplace) step("codex", `remove marketplace ${MARKETPLACE_NAME} (${state.codex.marketplace.kind})`, ["codex", "plugin", "marketplace", "remove", MARKETPLACE_NAME]);
      step("codex", `add marketplace ${MARKETPLACE_NAME} from ${repoRoot}`, ["codex", "plugin", "marketplace", "add", repoRoot]);
      for (const id of codexIds) step("codex", `add ${id}`, ["codex", "plugin", "add", id]);
    }
    notes.push("codex: plugin hooks keep their /hooks trust across remove/add as long as hooks.json is unchanged; an edited hooks.json needs re-trust.");
  } else if (mode === "refresh") {
    if (!state.claude.local && !state.codex.local) {
      throw new Error(`neither harness has marketplace "${MARKETPLACE_NAME}" pointing at ${repoRoot}; run dev-install first`);
    }
    if (state.claude.local) {
      for (const id of unionIds(state.claude, repoPlugins)) {
        if (claudeInstalled.has(id)) step("claude", `refresh ${id} (uninstall --keep-data, install)`, ["claude", "plugin", "uninstall", id, "--keep-data"]);
        step("claude", `install ${id}`, ["claude", "plugin", "install", id]);
      }
    } else {
      notes.push("claude: marketplace is not this checkout; skipped (run dev-install to swap).");
    }
    if (state.codex.local) {
      for (const id of unionIds(state.codex, repoPlugins)) {
        if (codexInstalled.has(id)) step("codex", `remove ${id} (refresh)`, ["codex", "plugin", "remove", id]);
        step("codex", `add ${id}`, ["codex", "plugin", "add", id]);
      }
    } else {
      notes.push("codex: marketplace is not this checkout; skipped (run dev-install to swap).");
    }
  } else if (mode === "uninstall") {
    if (state.claude.local) {
      const ids = [...claudeInstalled];
      step("claude", `remove local marketplace ${MARKETPLACE_NAME}`, ["claude", "plugin", "marketplace", "remove", MARKETPLACE_NAME], CLAUDE_DATA_WARNING(ids));
      step("claude", `add marketplace ${MARKETPLACE_NAME} from GitHub ${GITHUB_SOURCE}`, ["claude", "plugin", "marketplace", "add", GITHUB_SOURCE]);
      for (const id of ids) step("claude", `install ${id}`, ["claude", "plugin", "install", id]);
    } else {
      notes.push("claude: marketplace is not this checkout; nothing to restore.");
    }
    if (state.codex.local) {
      const ids = [...codexInstalled];
      for (const id of ids) step("codex", `remove ${id} before the swap`, ["codex", "plugin", "remove", id]);
      step("codex", `remove local marketplace ${MARKETPLACE_NAME}`, ["codex", "plugin", "marketplace", "remove", MARKETPLACE_NAME]);
      step("codex", `add marketplace ${MARKETPLACE_NAME} from GitHub ${GITHUB_SOURCE}`, ["codex", "plugin", "marketplace", "add", GITHUB_SOURCE]);
      for (const id of ids) step("codex", `add ${id}`, ["codex", "plugin", "add", id]);
    } else {
      notes.push("codex: marketplace is not this checkout; nothing to restore.");
    }
  } else {
    throw new Error(`unknown dev mode "${mode}"`);
  }
  return { steps, notes };
}

export function describePlan(plan) {
  const lines = [];
  plan.steps.forEach((s, i) => {
    lines.push(`${String(i + 1).padStart(2)}. [${s.harness}] ${s.title}`);
    lines.push(`      ${s.argv.map(quoteArg).join(" ")}`);
    if (s.destructive) lines.push(`      WARNING: ${s.destructive}`);
  });
  for (const n of plan.notes) lines.push(`note: ${n}`);
  return lines.join("\n");
}

// Plugin ids that a plan installs or adds. Used by tests and the post-run check.
export function plannedIds(plan) {
  const ids = new Set();
  for (const s of plan.steps) {
    if ((s.argv[0] === "claude" && s.argv[2] === "install") || (s.argv[0] === "codex" && s.argv[2] === "add" && s.argv[1] === "plugin")) {
      ids.add(s.argv[3]);
    }
  }
  return [...ids].sort();
}

// ---------------------------------------------------------------------------
// Executing
// ---------------------------------------------------------------------------

async function confirm(question) {
  if (!process.stdin.isTTY) return false;
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = (await rl.question(`${question} [y/N] `)).trim().toLowerCase();
    return answer === "y" || answer === "yes";
  } finally {
    rl.close();
  }
}

export async function runDev(mode, { repoRoot, repoPlugins, yes = false, dryRun = false, runner = createRunner({ verbose: true }), log = console.log }) {
  const before = readState(runner, repoRoot);
  log("current state");
  log(describeState(before));
  log("");

  if (mode === "status") return 0;

  const plan = buildPlan(before, mode, { repoRoot, repoPlugins });
  if (!plan.steps.length) {
    log("nothing to do");
    return 0;
  }
  log(`plan (dev-${mode})`);
  log(describePlan(plan));
  log("");
  if (dryRun) return 0;

  const destructive = plan.steps.some((s) => s.destructive);
  if (!yes) {
    const ok = await confirm(destructive ? "This plan deletes Claude plugin data as warned above. Proceed?" : "Proceed?");
    if (!ok) {
      log("aborted; re-run with --yes to skip the prompt (non-interactive shells need it)");
      return 1;
    }
  }

  for (const s of plan.steps) {
    const r = runner.run(s.argv);
    const tail = (r.stdout + r.stderr).trim().split(/\r?\n/).filter(Boolean).slice(-1)[0] || "";
    if (r.code !== 0) {
      log(`FAILED [${s.harness}] ${s.title}: ${tail}`);
      log("stopping; the state above tells you what was already changed");
      return 1;
    }
    log(`ok [${s.harness}] ${s.title}${tail ? `: ${tail}` : ""}`);
  }

  const after = readState(runner, repoRoot);
  log("");
  log("resulting state");
  log(describeState(after));
  const expected = new Set(plannedIds(plan));
  for (const h of ["claude", "codex"]) {
    const have = new Set(after[h].plugins.map((p) => p.id));
    const missing = [...expected].filter((id) => plan.steps.some((s) => s.harness === h && s.argv[3] === id) && !have.has(id));
    if (missing.length) {
      log(`WARNING ${h}: planned plugins are not installed after the run: ${missing.join(", ")}`);
      return 1;
    }
  }
  return 0;
}
