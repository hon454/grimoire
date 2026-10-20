#!/usr/bin/env node
// Runs the repository's own test suites: tests/*.test.mjs under node --test.
// Explicit file list because `node --test` with a directory is refused on
// newer Node, and its default discovery would also pick up the *.test.ts files
// that mods keep for `claude plugin test`, which import "claude-code".
import { readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dir = join(root, "tests");
const files = readdirSync(dir).filter((f) => f.endsWith(".test.mjs")).sort().map((f) => join(dir, f));
const r = spawnSync(process.execPath, ["--test", ...files, ...process.argv.slice(2)], { stdio: "inherit", cwd: root });
process.exitCode = r.status ?? 1;
