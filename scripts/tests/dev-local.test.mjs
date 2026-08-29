import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import test from "node:test";

const packageJson = JSON.parse(
  readFileSync(new URL("../../package.json", import.meta.url), "utf8"),
);

test("the repository exposes one deterministic local startup command", () => {
  assert.equal(packageJson.scripts["dev:local"], "node scripts/dev-local.mjs");

  const result = spawnSync(process.execPath, ["scripts/dev-local.mjs", "--check"], {
    cwd: new URL("../..", import.meta.url),
    encoding: "utf8",
  });

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    services: {
      web: "http://localhost:5173",
      apiHealth: "http://localhost:8080/health",
      apiReadiness: "http://localhost:8080/ready",
    },
    adapterMode: "deterministic",
    demoMode: true,
    paidApiCallsEnabled: false,
  });
});
