// Run with: claude plugin test claude-code-mods/{{NAME}}
import { test, expect } from "claude-code/testing";
import { register } from "../hooks/{{NAME}}.mjs";

test("exports register(on, options)", async () => {
  expect(typeof register).toBe("function");
});
