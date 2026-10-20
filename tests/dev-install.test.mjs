import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildPlan,
  parseClaudeMarketplace,
  parseClaudePlugins,
  parseCodexConfigMarketplace,
  parseCodexPlugins,
  plannedIds,
  samePath,
  GITHUB_SOURCE,
} from "../tools/dev.mjs";

const REPO = process.platform === "win32" ? "G:\\grimoire" : "/work/grimoire";
const PLUGINS = ["archmage", "book-of-engineering"];

function state({ claude = {}, codex = {} } = {}) {
  return {
    claude: { marketplace: null, plugins: [], local: false, ...claude },
    codex: { marketplace: null, plugins: [], local: false, ...codex },
  };
}

const githubState = () =>
  state({
    claude: { marketplace: { kind: "github", repo: GITHUB_SOURCE }, plugins: [{ id: "archmage@grimoire", version: "0.1.0" }] },
    codex: { marketplace: { kind: "git", source: `https://github.com/${GITHUB_SOURCE}` }, plugins: [{ id: "archmage@grimoire", version: "0.1.0" }] },
  });

const localState = () =>
  state({
    claude: { marketplace: { kind: "directory", path: REPO }, plugins: [{ id: "archmage@grimoire", version: "0.1.0" }], local: true },
    codex: { marketplace: { kind: "local", source: REPO }, plugins: [{ id: "archmage@grimoire", version: "0.1.0" }], local: true },
  });

test("parsers read the harness CLI output shapes", () => {
  assert.deepEqual(
    parseClaudeMarketplace([{ name: "other" }, { name: "grimoire", source: "directory", path: "G:\\grimoire" }]).kind,
    "directory",
  );
  assert.equal(parseClaudeMarketplace([{ name: "grimoire", source: "github", repo: "hon454/grimoire" }]).repo, "hon454/grimoire");
  assert.equal(parseClaudeMarketplace([]), null);
  assert.deepEqual(parseClaudePlugins([{ id: "archmage@grimoire", version: "0.1.0", scope: "user" }, { id: "eli5@claude-community" }]), [
    { id: "archmage@grimoire", version: "0.1.0", scope: "user" },
  ]);
  const toml = `[marketplaces.openai-bundled]\nsource_type = "local"\nsource = 'x'\n\n[marketplaces.grimoire]\nsource_type = "local"\nsource = '\\\\?\\G:\\grimoire'\n\n[plugins."archmage@grimoire"]\nenabled = true\n`;
  const mp = parseCodexConfigMarketplace(toml);
  assert.equal(mp.kind, "local");
  assert.equal(mp.source, "\\\\?\\G:\\grimoire");
  assert.equal(parseCodexConfigMarketplace("[marketplaces.other]\nsource_type = \"git\"\n"), null);
  assert.deepEqual(parseCodexPlugins({ installed: [{ pluginId: "archmage@grimoire", marketplaceName: "grimoire", version: "0.1.0", installed: true, enabled: true }, { pluginId: "pdf@openai", marketplaceName: "openai" }] }), [
    { id: "archmage@grimoire", version: "0.1.0", enabled: true },
  ]);
});

test("samePath ignores the Windows long-path prefix and slash style", () => {
  if (process.platform === "win32") {
    assert.ok(samePath("\\\\?\\G:\\grimoire", "G:/grimoire"));
    assert.ok(samePath("g:\\grimoire\\", "G:\\grimoire"));
    assert.ok(!samePath("G:\\grimoire", "G:\\other"));
  } else {
    assert.ok(samePath("/work/grimoire/", "/work/grimoire"));
    assert.ok(!samePath("/work/grimoire", "/work/other"));
  }
});

test("dev-install from a GitHub registration swaps both harnesses and keeps plugin ids", () => {
  const plan = buildPlan(githubState(), "install", { repoRoot: REPO, repoPlugins: PLUGINS });
  const argv = plan.steps.map((s) => s.argv.join(" "));
  // Claude: marketplace remove (destructive, warned) -> add local -> install the same ids.
  const cRemove = argv.indexOf("claude plugin marketplace remove grimoire");
  const cAdd = argv.indexOf(`claude plugin marketplace add ${REPO}`);
  const cInstall = argv.indexOf("claude plugin install archmage@grimoire");
  assert.ok(cRemove >= 0 && cAdd > cRemove && cInstall > cAdd, argv.join("\n"));
  assert.match(plan.steps[cRemove].destructive, /deletes the saved data/);
  // Codex: plugin remove happens before the marketplace swap, add after it.
  const xRemove = argv.indexOf("codex plugin remove archmage@grimoire");
  const xMpRemove = argv.indexOf("codex plugin marketplace remove grimoire");
  const xMpAdd = argv.indexOf(`codex plugin marketplace add ${REPO}`);
  const xAdd = argv.indexOf("codex plugin add archmage@grimoire");
  assert.ok(xRemove >= 0 && xMpRemove > xRemove && xMpAdd > xMpRemove && xAdd > xMpAdd, argv.join("\n"));
  // Invariant: only ids that were installed before are installed again; nothing new, nothing renamed.
  assert.deepEqual(plannedIds(plan), ["archmage@grimoire"]);
});

test("dev-install installs Claude-only mods in Claude Code only", () => {
  const plan = buildPlan(state(), "install", { repoRoot: REPO, repoPlugins: { claude: [...PLUGINS, "token-weather"], codex: PLUGINS } });
  const argv = plan.steps.map((s) => s.argv.join(" "));
  assert.ok(argv.includes("claude plugin install token-weather@grimoire"));
  assert.ok(!argv.some((a) => a.startsWith("codex") && a.includes("token-weather")), "Codex never sees a mod");
  assert.ok(argv.includes("codex plugin add archmage@grimoire"));
});

test("dev-install with nothing installed yet installs every plugin in the repo", () => {
  const plan = buildPlan(state(), "install", { repoRoot: REPO, repoPlugins: PLUGINS });
  assert.deepEqual(plannedIds(plan), ["archmage@grimoire", "book-of-engineering@grimoire"]);
  assert.ok(!plan.steps.some((s) => s.argv.includes("remove")), "no removals when nothing is registered");
});

test("dev-install when already local refreshes instead of swapping", () => {
  const plan = buildPlan(localState(), "install", { repoRoot: REPO, repoPlugins: PLUGINS });
  const argv = plan.steps.map((s) => s.argv.join(" "));
  assert.ok(!argv.some((a) => a.includes("marketplace")), "no marketplace changes");
  assert.ok(argv.includes("claude plugin uninstall archmage@grimoire --keep-data"));
  assert.ok(argv.includes("claude plugin install book-of-engineering@grimoire"), "missing repo plugins get installed");
  assert.ok(argv.includes("codex plugin remove archmage@grimoire"));
  assert.ok(!plan.steps.some((s) => s.destructive), "refresh keeps plugin data");
});

test("dev-refresh refuses when neither harness points at this checkout", () => {
  assert.throws(() => buildPlan(githubState(), "refresh", { repoRoot: REPO, repoPlugins: PLUGINS }), /run dev-install first/);
});

test("dev-refresh only touches the harness that is local", () => {
  const s = localState();
  s.codex = { marketplace: { kind: "git", source: "x" }, plugins: [{ id: "archmage@grimoire" }], local: false };
  const plan = buildPlan(s, "refresh", { repoRoot: REPO, repoPlugins: PLUGINS });
  assert.ok(plan.steps.every((st) => st.harness === "claude"));
  assert.match(plan.notes.join("\n"), /codex: marketplace is not this checkout/);
});

test("dev-uninstall restores GitHub and reinstalls exactly what was installed", () => {
  const plan = buildPlan(localState(), "uninstall", { repoRoot: REPO, repoPlugins: PLUGINS });
  const argv = plan.steps.map((s) => s.argv.join(" "));
  assert.ok(argv.includes(`claude plugin marketplace add ${GITHUB_SOURCE}`));
  assert.ok(argv.includes(`codex plugin marketplace add ${GITHUB_SOURCE}`));
  assert.deepEqual(plannedIds(plan), ["archmage@grimoire"], "book-of-engineering was not installed, so it is not installed now");
  assert.ok(plan.steps.find((s) => s.argv.join(" ") === "claude plugin marketplace remove grimoire").destructive);
});

test("dev-uninstall is a no-op when GitHub is already registered", () => {
  const plan = buildPlan(githubState(), "uninstall", { repoRoot: REPO, repoPlugins: PLUGINS });
  assert.equal(plan.steps.length, 0);
  assert.equal(plan.notes.length, 2);
});
