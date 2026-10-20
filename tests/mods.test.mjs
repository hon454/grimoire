import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { makeSandbox } from "./helpers.mjs";

test("new-mod scaffolds a Claude-only mod that passes check and appears only in the Claude marketplace", () => {
  const sb = makeSandbox();
  try {
    const r = sb.tool(["new-mod", "token-weather", "--description", "A band above the prompt."]);
    assert.equal(r.code, 0, r.out);
    const root = join(sb.dir, "claude-code-mods", "token-weather");
    for (const rel of ["VERSION", "CHANGELOG.md", "README.md", ".claude-plugin/plugin.json", "hooks/hooks.json", "hooks/token-weather.mjs", "tests/token-weather.test.ts"]) {
      assert.ok(existsSync(join(root, rel)), `missing ${rel}`);
    }
    assert.ok(!existsSync(join(root, ".codex-plugin")), "mods have no Codex manifest");
    assert.deepEqual(JSON.parse(readFileSync(join(root, "hooks", "hooks.json"), "utf8")), { modules: ["./token-weather.mjs"] });

    const claudeMp = JSON.parse(readFileSync(join(sb.dir, ".claude-plugin", "marketplace.json"), "utf8"));
    const codexMp = JSON.parse(readFileSync(join(sb.dir, ".agents", "plugins", "marketplace.json"), "utf8"));
    const entry = claudeMp.plugins.find((p) => p.name === "token-weather");
    assert.ok(entry, "mod listed in the Claude marketplace");
    assert.equal(entry.source, "./claude-code-mods/token-weather");
    assert.ok(entry.tags.includes("claude-code-mod"));
    assert.ok(!codexMp.plugins.some((p) => p.name === "token-weather"), "mod absent from the Codex marketplace");

    const c = sb.tool(["check"]);
    assert.equal(c.code, 0, c.out);
    assert.match(c.stdout, /1 mod\(s\)/);
  } finally {
    sb.cleanup();
  }
});

test("new-mod rejects dual-harness-looking names and names already used by a plugin", () => {
  const sb = makeSandbox();
  try {
    assert.equal(sb.tool(["new-mod", "book-of-weather"]).code, 1);
    assert.equal(sb.tool(["new-mod", "archmage"]).code, 1);
    assert.equal(sb.tool(["new-mod", "Token_Weather"]).code, 1);
  } finally {
    sb.cleanup();
  }
});

test("check rejects a mod with command hooks, a Codex manifest, or a missing module", () => {
  const sb = makeSandbox();
  try {
    assert.equal(sb.tool(["new-mod", "broken"]).code, 0);
    const root = join(sb.dir, "claude-code-mods", "broken");
    writeFileSync(join(root, "hooks", "hooks.json"), JSON.stringify({ modules: ["./missing.mjs"], hooks: { SessionStart: [] } }));
    mkdirSync(join(root, ".codex-plugin"));
    writeFileSync(join(root, ".codex-plugin", "plugin.json"), "{}");
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /must not have \.codex-plugin/);
    assert.match(r.stdout, /must not also declare command "hooks"/);
    assert.match(r.stdout, /module "\.\/missing\.mjs" named in hooks\/hooks\.json does not exist/);
  } finally {
    sb.cleanup();
  }
});

test("check rejects a mod whose name collides with a plugin", () => {
  const sb = makeSandbox();
  try {
    assert.equal(sb.tool(["new-mod", "shadow"]).code, 0);
    // Forge a plugin with the same name after the fact (new-mod itself refuses this).
    const p = join(sb.dir, "plugins", "shadow");
    mkdirSync(p, { recursive: true });
    writeFileSync(join(p, "VERSION"), "0.1.0\n");
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /name collides with plugins\/shadow/);
  } finally {
    sb.cleanup();
  }
});

test("stamp --set also stamps a mod's Claude manifest", () => {
  const sb = makeSandbox();
  try {
    assert.equal(sb.tool(["new-mod", "stampable"]).code, 0);
    const r = sb.tool(["stamp", "stampable", "--set", "0.2.0"]);
    assert.equal(r.code, 0, r.out);
    const m = JSON.parse(readFileSync(join(sb.dir, "claude-code-mods", "stampable", ".claude-plugin", "plugin.json"), "utf8"));
    assert.equal(m.version, "0.2.0");
  } finally {
    sb.cleanup();
  }
});
