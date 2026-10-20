import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { makeSandbox } from "./helpers.mjs";

test("new-book scaffolds a plugin that passes check and lands in both marketplaces", () => {
  const sb = makeSandbox();
  try {
    const r = sb.tool([
      "new-book",
      "book-of-engineering",
      "--description",
      "Engineering workflows.",
      "--category",
      "Engineering",
      "--skill",
      "code-review",
    ]);
    assert.equal(r.code, 0, r.out);

    const root = join(sb.dir, "plugins", "book-of-engineering");
    for (const rel of [
      "VERSION",
      "CHANGELOG.md",
      "README.md",
      ".claude-plugin/plugin.json",
      ".codex-plugin/plugin.json",
      "skills/code-review/SKILL.md",
      "skills/code-review/agents/openai.yaml",
    ]) {
      assert.ok(existsSync(join(root, rel)), `missing ${rel}`);
    }
    assert.ok(!existsSync(join(root, "plugin.json")), "must not create a root plugin.json");

    const codex = JSON.parse(readFileSync(join(root, ".codex-plugin", "plugin.json"), "utf8"));
    assert.deepEqual(codex.hooks, {});
    assert.equal(codex.interface.category, "Engineering");
    assert.equal(codex.description, "Engineering workflows.");

    const claudeMp = JSON.parse(readFileSync(join(sb.dir, ".claude-plugin", "marketplace.json"), "utf8"));
    const codexMp = JSON.parse(readFileSync(join(sb.dir, ".agents", "plugins", "marketplace.json"), "utf8"));
    const claudeNames = claudeMp.plugins.map((p) => p.name);
    assert.ok(claudeNames.includes("archmage") && claudeNames.includes("book-of-engineering"), claudeNames.join(","));
    assert.deepEqual([...claudeNames].sort(), claudeNames, "Claude marketplace is sorted by name");
    assert.deepEqual(codexMp.plugins.map((p) => p.name), ["archmage", "book-of-engineering"]);
    const book = codexMp.plugins.find((p) => p.name === "book-of-engineering");
    assert.equal(book.category, "Engineering");
    assert.equal(book.source.path, "./plugins/book-of-engineering");

    const c = sb.tool(["check"]);
    assert.equal(c.code, 0, c.out);
  } finally {
    sb.cleanup();
  }
});

test("new-book rejects names without the book-of- prefix and skill names with articles or too many words", () => {
  const sb = makeSandbox();
  try {
    assert.equal(sb.tool(["new-book", "engineering"]).code, 1);
    assert.equal(sb.tool(["new-book", "book-of-x", "--skill", "writing-an-adr"]).code, 1);
    assert.equal(sb.tool(["new-book", "book-of-x", "--skill", "Review"]).code, 1);
    assert.equal(sb.tool(["new-book", "book-of-x", "--skill", "one-two-three-four-five"]).code, 1);
    assert.equal(sb.tool(["new-book", "archmage"]).code, 1, "existing plugin");
    assert.ok(!existsSync(join(sb.dir, "plugins", "book-of-x")));
  } finally {
    sb.cleanup();
  }
});

test("stamp --set writes VERSION into both manifests and regenerates marketplaces", () => {
  const sb = makeSandbox();
  try {
    const r = sb.tool(["stamp", "archmage", "--set", "0.9.0"]);
    assert.equal(r.code, 0, r.out);
    const root = join(sb.dir, "plugins", "archmage");
    assert.equal(readFileSync(join(root, "VERSION"), "utf8").trim(), "0.9.0");
    for (const rel of [".claude-plugin/plugin.json", ".codex-plugin/plugin.json"]) {
      assert.equal(JSON.parse(readFileSync(join(root, rel), "utf8")).version, "0.9.0");
    }
    const mp = JSON.parse(readFileSync(join(sb.dir, ".claude-plugin", "marketplace.json"), "utf8"));
    assert.equal(mp.plugins[0].version, "0.9.0");
    // The CHANGELOG was not updated, so check must now fail on exactly that.
    const c = sb.tool(["check"]);
    assert.equal(c.code, 1);
    assert.match(c.stdout, /CHANGELOG\.md newest entry is \d+\.\d+\.\d+ but VERSION is 0\.9\.0/);
  } finally {
    sb.cleanup();
  }
});
