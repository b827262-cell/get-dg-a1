import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("frontend test command is wired", () => {
  assert.equal("SecMon", "SecMon");
});

test("console uses the P2 API and avoids persistent credential/XSS sinks", () => {
  const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(source, /\/dashboard\/summary/);
  assert.match(source, /\/admin\/users/);
  assert.match(source, /\/firewall\/block/);
  assert.match(source, /Authorization/);
  assert.doesNotMatch(source, /localStorage|sessionStorage|innerHTML/);
});
