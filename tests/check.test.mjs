import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, rmSync, writeFileSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { makeSandbox, runTool } from "./helpers.mjs";

test("check passes on the repository itself", () => {
  const r = runTool(["check"]);
  assert.equal(r.code, 0, r.out);
  assert.match(r.stdout, /check passed/);
});

test("check rejects a root plugin.json, commands/ and bin/", () => {
  const sb = makeSandbox();
  try {
    const arch = join(sb.dir, "plugins", "archmage");
    writeFileSync(join(arch, "plugin.json"), "{}\n");
    mkdirSync(join(arch, "commands"));
    mkdirSync(join(arch, "bin"));
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /"plugin\.json" is not allowed/);
    assert.match(r.stdout, /"commands" is not allowed/);
    assert.match(r.stdout, /"bin" is not allowed/);
  } finally {
    sb.cleanup();
  }
});

test("check requires the codex manifest to pin hooks explicitly", () => {
  const sb = makeSandbox();
  try {
    const file = join(sb.dir, "plugins", "archmage", ".codex-plugin", "plugin.json");
    const m = JSON.parse(readFileSync(file, "utf8"));
    delete m.hooks;
    writeFileSync(file, JSON.stringify(m, null, 2));
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /codex manifest must set "hooks": "\.\/hooks\/hooks\.json"/);
  } finally {
    sb.cleanup();
  }
});

test("check flags VERSION, manifest and CHANGELOG drift", () => {
  const sb = makeSandbox();
  try {
    writeFileSync(join(sb.dir, "plugins", "archmage", "VERSION"), "9.9.9\n");
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /CHANGELOG\.md newest entry is \d+\.\d+\.\d+ but VERSION is 9\.9\.9/);
    assert.match(r.stdout, /claude manifest version "\d+\.\d+\.\d+" does not equal VERSION 9\.9\.9/);
    assert.match(r.stdout, /marketplace\.json: stale/);
  } finally {
    sb.cleanup();
  }
});

test("check enforces skill naming, frontmatter keys and the openai.yaml sidecar", () => {
  const sb = makeSandbox();
  try {
    const skills = join(sb.dir, "plugins", "archmage", "skills");
    mkdirSync(join(skills, "reviewing-a-pull-request"));
    writeFileSync(
      join(skills, "reviewing-a-pull-request", "SKILL.md"),
      "---\nname: reviewing-a-pull-request\ndescription: x\nversion: 1\n---\nbody\n",
    );
    mkdirSync(join(skills, "writing-tests-before-production-code"));
    writeFileSync(
      join(skills, "writing-tests-before-production-code", "SKILL.md"),
      "---\nname: writing-tests-before-production-code\ndescription: x\n---\nbody\n",
    );
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /skill name must not contain the article "a"/);
    assert.match(r.stdout, /skill name must be at most 4 words/);
    assert.match(r.stdout, /frontmatter key "version" is not accepted/);
    assert.match(r.stdout, /missing agents\/openai\.yaml/);
  } finally {
    sb.cleanup();
  }
});

test("check rejects duplicate skill names across plugins and non-portable hook events", () => {
  const sb = makeSandbox();
  try {
    const r1 = sb.tool(["new-book", "book-of-dupes", "--skill", "required-reading"]);
    assert.equal(r1.code, 0, r1.out);
    const hooks = join(sb.dir, "plugins", "archmage", "hooks", "hooks.json");
    const h = JSON.parse(readFileSync(hooks, "utf8"));
    h.hooks.Notification = [{ hooks: [{ type: "command", command: "node \"${CLAUDE_PLUGIN_ROOT}/scripts/missing.mjs\"" }] }];
    writeFileSync(hooks, JSON.stringify(h, null, 2));
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /skill name already used by plugins\/archmage/);
    assert.match(r.stdout, /hook event "Notification" is not supported by both harnesses/);
    assert.match(r.stdout, /references missing file "scripts\/missing\.mjs"/);
    rmSync(join(sb.dir, "plugins", "book-of-dupes"), { recursive: true });
  } finally {
    sb.cleanup();
  }
});
