#!/usr/bin/env node
// grimoire maintainer tool. Dependency-free, Node >= 20.
//
//   node tools/grimoire.mjs check                      validate plugins and marketplaces
//   node tools/grimoire.mjs stamp [plugin] [--set X]   write VERSION into manifests, regenerate marketplaces
//   node tools/grimoire.mjs new-book <name> [...]      scaffold a new book-of-* plugin
//   node tools/grimoire.mjs marketplaces               regenerate both marketplace files only
//
// Every command accepts --root <dir> (defaults to the repository root).

import {
  existsSync,
  lstatSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TOOL_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT = resolve(TOOL_DIR, "..");
const TEMPLATE_DIR = join(TOOL_DIR, "templates");

const MARKETPLACE = {
  name: "grimoire",
  displayName: "Grimoire",
  description: "A spellbook of plugins for Claude Code and Codex. Each plugin is a book; archmage is the required reading.",
  owner: { name: "hon454", url: "https://github.com/hon454" },
};

const META_PLUGIN = "archmage";
const BOOK_PREFIX = "book-of-";
const DEFAULT_CATEGORY = "Developer Tools";
const KEBAB = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const SEMVER = /^\d+\.\d+\.\d+$/;
const SKILL_FRONTMATTER_KEYS = new Set(["name", "description", "metadata", "license", "allowed-tools"]);
const COMMON_HOOK_EVENTS = new Set([
  "SessionStart",
  "UserPromptSubmit",
  "PreToolUse",
  "PostToolUse",
  "PermissionRequest",
  "Stop",
  "SubagentStart",
  "SubagentStop",
  "PreCompact",
  "SessionEnd",
]);
const FORBIDDEN_ENTRIES = [
  ["plugin.json", "a root plugin.json makes Codex skip .codex-plugin/plugin.json and load no plugin hooks"],
  ["commands", "grimoire ships skills only; commands duplicate skills in the slash menu and have no Codex equivalent"],
  ["bin", "claude.ai and Cowork refuse plugins that contain bin/"],
  ["CLAUDE.md", "Claude Code does not load CLAUDE.md inside a plugin and warns about it; put instructions in a skill"],
];
const TEXT_EXTENSIONS = new Set([".md", ".json", ".mjs", ".js", ".cjs", ".ts", ".yaml", ".yml", ".txt", ".toml"]);
const PERSONAL_PATH = /[A-Za-z]:\\Users\\|\/Users\/|\/home\//;

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const positional = [];
  const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next !== undefined && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(a);
    }
  }
  return { positional, flags };
}

function readText(file) {
  return readFileSync(file, "utf8");
}

function readJson(file) {
  return JSON.parse(readText(file));
}

function writeJson(file, value) {
  writeFileSync(file, JSON.stringify(value, null, 2) + "\n");
}

function writeText(file, text) {
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, text);
}

function posix(p) {
  return p.split(sep).join("/");
}

function isDir(p) {
  return existsSync(p) && statSync(p).isDirectory();
}

function listDirs(p) {
  if (!isDir(p)) return [];
  return readdirSync(p, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort();
}

function walk(dir, visit) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    visit(full, entry);
    if (entry.isDirectory() && !entry.isSymbolicLink()) walk(full, visit);
  }
}

function titleCase(name) {
  return name
    .split("-")
    .map((w) => (w === "of" || w === "a" || w === "the" ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ")
    .replace(/^./, (c) => c.toUpperCase());
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

// Minimal YAML frontmatter reader: returns top-level keys and scalar values.
export function parseFrontmatter(markdown) {
  if (!markdown.startsWith("---")) return null;
  const end = markdown.indexOf("\n---", 3);
  if (end === -1) return null;
  const block = markdown.slice(3, end).replace(/^\r?\n/, "");
  const data = {};
  for (const line of block.split(/\r?\n/)) {
    const m = /^([A-Za-z][A-Za-z0-9_-]*):(.*)$/.exec(line);
    if (!m) continue;
    let value = m[2].trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    data[m[1]] = value;
  }
  return data;
}

// ---------------------------------------------------------------------------
// Plugin model
// ---------------------------------------------------------------------------

function pluginsDir(root) {
  return join(root, "plugins");
}

function loadPlugin(root, dir) {
  const path = join(pluginsDir(root), dir);
  const read = (rel) => (existsSync(join(path, rel)) ? readJson(join(path, rel)) : null);
  return {
    dir,
    path,
    version: existsSync(join(path, "VERSION")) ? readText(join(path, "VERSION")).trim() : null,
    claude: read(".claude-plugin/plugin.json"),
    codex: read(".codex-plugin/plugin.json"),
  };
}

function loadPlugins(root) {
  return listDirs(pluginsDir(root)).map((d) => loadPlugin(root, d));
}

// ---------------------------------------------------------------------------
// Marketplaces (generated)
// ---------------------------------------------------------------------------

export function buildMarketplaces(plugins) {
  const entries = plugins
    .filter((p) => p.claude && p.codex)
    .sort((a, b) => a.dir.localeCompare(b.dir));
  const claude = {
    name: MARKETPLACE.name,
    owner: MARKETPLACE.owner,
    description: MARKETPLACE.description,
    plugins: entries.map((p) => ({
      name: p.claude.name,
      source: `./plugins/${p.dir}`,
      description: p.claude.description,
      version: p.version,
      category: p.codex.interface?.category || DEFAULT_CATEGORY,
      tags: p.claude.keywords || [],
    })),
  };
  const codex = {
    name: MARKETPLACE.name,
    interface: { displayName: MARKETPLACE.displayName },
    plugins: entries.map((p) => ({
      name: p.codex.name,
      source: { source: "local", path: `./plugins/${p.dir}` },
      policy: { installation: "AVAILABLE", authentication: "ON_INSTALL" },
      category: p.codex.interface?.category || DEFAULT_CATEGORY,
    })),
  };
  return { claude, codex };
}

function marketplaceFiles(root) {
  return {
    claude: join(root, ".claude-plugin", "marketplace.json"),
    codex: join(root, ".agents", "plugins", "marketplace.json"),
  };
}

function writeMarketplaces(root) {
  const built = buildMarketplaces(loadPlugins(root));
  const files = marketplaceFiles(root);
  mkdirSync(dirname(files.claude), { recursive: true });
  mkdirSync(dirname(files.codex), { recursive: true });
  writeJson(files.claude, built.claude);
  writeJson(files.codex, built.codex);
  return files;
}

// ---------------------------------------------------------------------------
// check
// ---------------------------------------------------------------------------

class Report {
  constructor() {
    this.errors = [];
    this.warnings = [];
  }
  error(where, msg) {
    this.errors.push(`${where}: ${msg}`);
  }
  warn(where, msg) {
    this.warnings.push(`${where}: ${msg}`);
  }
}

function changelogLatestVersion(text) {
  for (const line of text.split(/\r?\n/)) {
    const m = /^##\s+\[?(\d+\.\d+\.\d+)\]?/.exec(line);
    if (m) return m[1];
  }
  return null;
}

function checkPlugin(p, report, seenSkills) {
  const id = `plugins/${p.dir}`;

  if (!KEBAB.test(p.dir)) report.error(id, "plugin directory name must be kebab-case");
  if (p.dir !== META_PLUGIN && !p.dir.startsWith(BOOK_PREFIX)) {
    report.error(id, `plugin name must start with "${BOOK_PREFIX}" (only "${META_PLUGIN}" is exempt)`);
  }

  // VERSION and CHANGELOG
  if (!p.version) report.error(id, "missing VERSION file");
  else if (!SEMVER.test(p.version)) report.error(id, `VERSION "${p.version}" is not MAJOR.MINOR.PATCH`);
  const changelog = join(p.path, "CHANGELOG.md");
  if (!existsSync(changelog)) {
    report.error(id, "missing CHANGELOG.md");
  } else {
    const latest = changelogLatestVersion(readText(changelog));
    if (!latest) report.error(id, "CHANGELOG.md has no versioned heading like \"## [0.1.0] - 2026-01-01\"");
    else if (p.version && latest !== p.version) {
      report.error(id, `CHANGELOG.md newest entry is ${latest} but VERSION is ${p.version}`);
    }
  }

  // Manifests
  if (!p.claude) report.error(id, "missing .claude-plugin/plugin.json");
  if (!p.codex) report.error(id, "missing .codex-plugin/plugin.json");
  for (const [label, m] of [["claude", p.claude], ["codex", p.codex]]) {
    if (!m) continue;
    if (m.name !== p.dir) report.error(id, `${label} manifest name "${m.name}" does not equal directory name`);
    if (p.version && m.version !== p.version) report.error(id, `${label} manifest version "${m.version}" does not equal VERSION ${p.version}`);
    if (!m.description) report.error(id, `${label} manifest has no description`);
    if (!m.author?.name) report.error(id, `${label} manifest has no author.name`);
  }
  if (p.claude && p.codex && p.claude.description !== p.codex.description) {
    report.error(id, "claude and codex manifests have different descriptions");
  }

  // Forbidden entries at the plugin root
  for (const [entry, why] of FORBIDDEN_ENTRIES) {
    if (existsSync(join(p.path, entry))) report.error(id, `"${entry}" is not allowed: ${why}`);
  }

  // Symlinks and personal paths anywhere in the plugin
  walk(p.path, (full, entry) => {
    const rel = posix(relative(p.path, full));
    if (lstatSync(full).isSymbolicLink()) {
      report.error(id, `symlink "${rel}" is not allowed: Codex drops symlinks when copying plugins`);
      return;
    }
    if (entry.isFile()) {
      const ext = full.slice(full.lastIndexOf("."));
      if (TEXT_EXTENSIONS.has(ext) && PERSONAL_PATH.test(readText(full))) {
        report.error(id, `"${rel}" contains a personal absolute path`);
      }
    }
  });

  // Hooks
  const hooksFile = join(p.path, "hooks", "hooks.json");
  const hasHooks = existsSync(hooksFile);
  if (p.codex) {
    if (hasHooks) {
      if (p.codex.hooks !== "./hooks/hooks.json") {
        report.error(id, 'codex manifest must set "hooks": "./hooks/hooks.json" because hooks/hooks.json exists');
      }
    } else if (!(p.codex.hooks && typeof p.codex.hooks === "object" && !Array.isArray(p.codex.hooks) && Object.keys(p.codex.hooks).length === 0)) {
      report.error(id, 'codex manifest must set "hooks": {} when the plugin ships no hooks (omitting it enables auto-discovery)');
    }
    if (p.codex.skills !== "./skills/") report.warn(id, 'codex manifest should set "skills": "./skills/"');
  }
  if (hasHooks) checkHooks(p, hooksFile, report, id);

  // Skills
  const skillsDir = join(p.path, "skills");
  const skills = listDirs(skillsDir);
  if (skills.length === 0) report.warn(id, "plugin has no skills");
  for (const skill of skills) checkSkill(p, skill, report, `${id}/skills/${skill}`, seenSkills);
}

function checkHooks(p, hooksFile, report, id) {
  let data;
  try {
    data = readJson(hooksFile);
  } catch (e) {
    report.error(id, `hooks/hooks.json is not valid JSON: ${e.message}`);
    return;
  }
  if (!data.hooks || typeof data.hooks !== "object") {
    report.error(id, 'hooks/hooks.json must wrap the event map in a top-level "hooks" key');
    return;
  }
  for (const [event, groups] of Object.entries(data.hooks)) {
    if (!COMMON_HOOK_EVENTS.has(event)) {
      report.error(id, `hook event "${event}" is not supported by both harnesses`);
    }
    if (!Array.isArray(groups)) {
      report.error(id, `hook event "${event}" must map to an array of matcher groups`);
      continue;
    }
    for (const group of groups) {
      for (const handler of group.hooks || []) {
        if (handler.type !== "command") {
          report.error(id, `hook handler type "${handler.type}" is not portable; use "command"`);
          continue;
        }
        const cmd = handler.command || "";
        if (/\.sh\b/.test(cmd)) report.warn(id, `hook command "${cmd}" runs a .sh file; prefer node .mjs for Windows`);
        for (const m of cmd.matchAll(/\$\{CLAUDE_PLUGIN_ROOT\}\/([^"'\s]+)/g)) {
          if (!existsSync(join(p.path, m[1]))) report.error(id, `hook command references missing file "${m[1]}"`);
        }
        if (!cmd.includes("${CLAUDE_PLUGIN_ROOT}")) {
          report.warn(id, `hook command "${cmd}" does not use \${CLAUDE_PLUGIN_ROOT}; relative paths are not portable`);
        }
      }
    }
  }
}

function checkSkill(p, skill, report, id, seenSkills) {
  const dir = join(p.path, "skills", skill);
  if (!KEBAB.test(skill)) report.error(id, "skill directory name must be kebab-case");
  if (!/^[a-z0-9]+ing(-|$)/.test(skill)) {
    report.error(id, 'skill name must be a gerund phrase such as "reading-the-grimoire"');
  }
  if (seenSkills.has(skill)) report.error(id, `skill name already used by ${seenSkills.get(skill)}`);
  else seenSkills.set(skill, `plugins/${p.dir}`);

  const skillFile = join(dir, "SKILL.md");
  if (!existsSync(skillFile)) {
    report.error(id, "missing SKILL.md");
  } else {
    const fm = parseFrontmatter(readText(skillFile));
    if (!fm) {
      report.error(id, "SKILL.md has no YAML frontmatter");
    } else {
      for (const key of Object.keys(fm)) {
        if (!SKILL_FRONTMATTER_KEYS.has(key)) {
          report.error(id, `frontmatter key "${key}" is not accepted by both harnesses; move it under metadata`);
        }
      }
      if (fm.name !== skill) report.error(id, `frontmatter name "${fm.name}" does not equal directory name`);
      if (!fm.description) report.error(id, "frontmatter description is missing or empty");
    }
  }

  const sidecar = join(dir, "agents", "openai.yaml");
  if (!existsSync(sidecar)) {
    report.error(id, "missing agents/openai.yaml (Codex UI metadata)");
  } else {
    const text = readText(sidecar);
    for (const key of ["display_name", "short_description", "allow_implicit_invocation"]) {
      if (!text.includes(`${key}:`)) report.error(id, `agents/openai.yaml lacks "${key}"`);
    }
  }
}

function checkMarketplaces(root, plugins, report) {
  const built = buildMarketplaces(plugins);
  const files = marketplaceFiles(root);
  for (const [label, file] of Object.entries(files)) {
    const rel = posix(relative(root, file));
    if (!existsSync(file)) {
      report.error(rel, `missing; run "node tools/grimoire.mjs stamp"`);
      continue;
    }
    let actual;
    try {
      actual = readJson(file);
    } catch (e) {
      report.error(rel, `invalid JSON: ${e.message}`);
      continue;
    }
    if (JSON.stringify(actual) !== JSON.stringify(built[label])) {
      report.error(rel, `stale: does not match the plugins on disk; run "node tools/grimoire.mjs stamp"`);
    }
  }
}

const ADR_STATUSES = new Set(["proposed", "accepted", "deprecated", "superseded"]);

function checkDecisions(root, report) {
  const dir = join(root, "docs", "decisions");
  if (!isDir(dir)) return;
  const files = readdirSync(dir).filter((f) => f.endsWith(".md") && f !== "README.md" && f !== "template.md").sort();
  const numbers = [];
  for (const file of files) {
    const id = `docs/decisions/${file}`;
    const m = /^(\d{4})-[a-z0-9]+(-[a-z0-9]+)*\.md$/.exec(file);
    if (!m) {
      report.error(id, "ADR file name must be NNNN-kebab-title.md");
      continue;
    }
    numbers.push(Number(m[1]));
    const fm = parseFrontmatter(readText(join(dir, file)));
    if (!fm) {
      report.error(id, "ADR has no YAML frontmatter");
      continue;
    }
    if (!ADR_STATUSES.has(fm.status)) report.error(id, `ADR status "${fm.status}" must be one of ${[...ADR_STATUSES].join(", ")}`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(fm.date || "")) report.error(id, "ADR date must be YYYY-MM-DD");
  }
  numbers.sort((a, b) => a - b);
  numbers.forEach((n, i) => {
    if (n !== i + 1) report.error("docs/decisions", `ADR numbers must be consecutive from 0001; found ${String(n).padStart(4, "0")} at position ${i + 1}`);
  });
  const arch = join(root, "docs", "ARCHITECTURE.md");
  if (existsSync(arch)) {
    for (const m of readText(arch).matchAll(/\(decisions\/([^)\s]+\.md)\)/g)) {
      if (!existsSync(join(dir, m[1]))) report.error("docs/ARCHITECTURE.md", `links to missing ADR "${m[1]}"`);
    }
  }
}

export function check(root) {
  const report = new Report();
  const plugins = loadPlugins(root);
  if (plugins.length === 0) report.error("plugins", "no plugins found");
  const seenSkills = new Map();
  for (const p of plugins) checkPlugin(p, report, seenSkills);
  checkMarketplaces(root, plugins, report);
  checkDecisions(root, report);
  return report;
}

// ---------------------------------------------------------------------------
// stamp
// ---------------------------------------------------------------------------

export function stamp(root, pluginName, setVersion) {
  const plugins = loadPlugins(root).filter((p) => !pluginName || p.dir === pluginName);
  if (pluginName && plugins.length === 0) throw new Error(`plugin "${pluginName}" not found under plugins/`);
  for (const p of plugins) {
    let version = p.version;
    if (setVersion) {
      if (!SEMVER.test(setVersion)) throw new Error(`"${setVersion}" is not MAJOR.MINOR.PATCH`);
      version = setVersion;
      writeFileSync(join(p.path, "VERSION"), version + "\n");
    }
    if (!version) throw new Error(`plugins/${p.dir} has no VERSION file`);
    for (const rel of [".claude-plugin/plugin.json", ".codex-plugin/plugin.json"]) {
      const file = join(p.path, rel);
      if (!existsSync(file)) continue;
      const manifest = readJson(file);
      manifest.version = version;
      writeJson(file, manifest);
    }
    console.log(`stamped plugins/${p.dir} at ${version}`);
  }
  const files = writeMarketplaces(root);
  console.log(`regenerated ${posix(relative(root, files.claude))} and ${posix(relative(root, files.codex))}`);
}

// ---------------------------------------------------------------------------
// new-book
// ---------------------------------------------------------------------------

function renderTemplate(name, vars) {
  let text = readText(join(TEMPLATE_DIR, name));
  for (const [key, value] of Object.entries(vars)) {
    text = text.replaceAll(`{{${key}}}`, value);
  }
  const leftover = text.match(/\{\{[A-Z_]+\}\}/);
  if (leftover) throw new Error(`template ${name} has an unfilled placeholder ${leftover[0]}`);
  return text;
}

export function newBook(root, name, opts = {}) {
  if (!name) throw new Error("usage: new-book <book-of-name> [--description ...] [--category ...] [--skill ...]");
  if (!KEBAB.test(name)) throw new Error(`"${name}" is not kebab-case`);
  if (!name.startsWith(BOOK_PREFIX)) throw new Error(`"${name}" must start with "${BOOK_PREFIX}" (only "${META_PLUGIN}" is exempt)`);
  const path = join(pluginsDir(root), name);
  if (existsSync(path)) throw new Error(`plugins/${name} already exists`);
  if (opts.skill) {
    if (!KEBAB.test(opts.skill)) throw new Error(`skill "${opts.skill}" is not kebab-case`);
    if (!/^[a-z0-9]+ing(-|$)/.test(opts.skill)) throw new Error(`skill "${opts.skill}" must be a gerund phrase such as "reviewing-code"`);
  }

  const domain = name.slice(BOOK_PREFIX.length);
  const vars = {
    NAME: name,
    TITLE: titleCase(name),
    DOMAIN: domain,
    DESCRIPTION: opts.description || `Grimoire book of ${domain.replaceAll("-", " ")}.`,
    CATEGORY: opts.category || DEFAULT_CATEGORY,
    DATE: today(),
    VERSION: "0.1.0",
  };

  writeText(join(path, "VERSION"), vars.VERSION + "\n");
  writeText(join(path, "CHANGELOG.md"), renderTemplate("CHANGELOG.md", vars));
  writeText(join(path, "README.md"), renderTemplate("README.md", vars));
  writeText(join(path, ".claude-plugin", "plugin.json"), renderTemplate("claude-plugin.json", vars));
  writeText(join(path, ".codex-plugin", "plugin.json"), renderTemplate("codex-plugin.json", vars));
  mkdirSync(join(path, "skills"), { recursive: true });

  if (opts.skill) {
    const skillVars = { ...vars, SKILL: opts.skill, SKILL_TITLE: titleCase(opts.skill) };
    writeText(join(path, "skills", opts.skill, "SKILL.md"), renderTemplate("SKILL.md", skillVars));
    writeText(join(path, "skills", opts.skill, "agents", "openai.yaml"), renderTemplate("openai.yaml", skillVars));
  }

  writeMarketplaces(root);
  console.log(`created plugins/${name}`);
  console.log("next: write skills under skills/<gerund-name>/SKILL.md, then run: node tools/grimoire.mjs check");
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function usage() {
  console.log(`grimoire maintainer tool

  node tools/grimoire.mjs check
  node tools/grimoire.mjs stamp [plugin] [--set X.Y.Z]
  node tools/grimoire.mjs new-book <book-of-name> [--description "..."] [--category "..."] [--skill <gerund-name>]
  node tools/grimoire.mjs marketplaces

  --root <dir>   operate on another checkout (default: this repository)`);
}

function main(argv) {
  const { positional, flags } = parseArgs(argv);
  const root = resolve(flags.root || DEFAULT_ROOT);
  const [command, ...rest] = positional;
  switch (command) {
    case "check": {
      const report = check(root);
      for (const w of report.warnings) console.log(`warning  ${w}`);
      for (const e of report.errors) console.log(`error    ${e}`);
      const plugins = loadPlugins(root).length;
      if (report.errors.length) {
        console.log(`\ncheck failed: ${report.errors.length} error(s), ${report.warnings.length} warning(s) across ${plugins} plugin(s)`);
        return 1;
      }
      console.log(`check passed: ${plugins} plugin(s), ${report.warnings.length} warning(s)`);
      return 0;
    }
    case "stamp":
      stamp(root, rest[0], flags.set === true ? undefined : flags.set);
      return 0;
    case "new-book":
      newBook(root, rest[0], {
        description: typeof flags.description === "string" ? flags.description : undefined,
        category: typeof flags.category === "string" ? flags.category : undefined,
        skill: typeof flags.skill === "string" ? flags.skill : undefined,
      });
      return 0;
    case "marketplaces":
      writeMarketplaces(root);
      console.log("regenerated marketplaces");
      return 0;
    default:
      usage();
      return command ? 1 : 0;
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = main(process.argv.slice(2));
  } catch (e) {
    console.error(`error: ${e.message}`);
    process.exitCode = 1;
  }
}
