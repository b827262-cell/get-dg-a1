import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("frontend test command is wired", () => {
  assert.equal("SecMon", "SecMon");
});

test("console uses guarded P4 operational routes and avoids persistent credential/XSS sinks", () => {
  const source = readFileSync(new URL("../src/main.ts", import.meta.url), "utf8");
  assert.match(source, /\/dashboard\/summary/);
  assert.match(source, /\/events/);
  assert.match(source, /\/attackers/);
  assert.match(source, /\/alerts/);
  assert.match(source, /\/operations\/health/);
  assert.match(source, /\/allowlist/);
  assert.match(source, /\/admin\/audit/);
  assert.match(source, /\/admin\/users/);
  assert.match(source, /\/firewall\/blocks/);
  assert.match(source, /Authorization/);
  assert.match(source, /requiredReason/);
  assert.match(source, /guarded/);
  assert.doesNotMatch(source, /localStorage|sessionStorage|innerHTML/);
});
