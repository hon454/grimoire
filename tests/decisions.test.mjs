import { test } from "node:test";
import assert from "node:assert/strict";
import { cpSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { REPO_ROOT, makeSandbox } from "./helpers.mjs";

function withDocs(sb) {
  cpSync(join(REPO_ROOT, "docs"), join(sb.dir, "docs"), { recursive: true });
  return join(sb.dir, "docs", "decisions");
}

test("check accepts the repository's decision records", () => {
  const sb = makeSandbox();
  try {
    withDocs(sb);
    const r = sb.tool(["check"]);
    assert.equal(r.code, 0, r.out);
  } finally {
    sb.cleanup();
  }
});

test("check rejects a gap in ADR numbering, a bad status and a missing date", () => {
  const sb = makeSandbox();
  try {
    const dir = withDocs(sb);
    writeFileSync(join(dir, "0099-skipped-number.md"), "---\nstatus: approved\ndate: today\n---\n# x\n");
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /ADR numbers must be consecutive/);
    assert.match(r.stdout, /ADR status "approved"/);
    assert.match(r.stdout, /ADR date must be YYYY-MM-DD/);
  } finally {
    sb.cleanup();
  }
});

test("check rejects ARCHITECTURE.md links to ADRs that do not exist", () => {
  const sb = makeSandbox();
  try {
    withDocs(sb);
    const arch = join(sb.dir, "docs", "ARCHITECTURE.md");
    writeFileSync(arch, "see [0042](decisions/0042-not-there.md)\n");
    const r = sb.tool(["check"]);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /links to missing ADR "0042-not-there\.md"/);
  } finally {
    sb.cleanup();
  }
});

test("check ignores a repository without docs/decisions", () => {
  const sb = makeSandbox();
  try {
    mkdirSync(join(sb.dir, "docs"), { recursive: true });
    const r = sb.tool(["check"]);
    assert.equal(r.code, 0, r.out);
  } finally {
    sb.cleanup();
  }
});
