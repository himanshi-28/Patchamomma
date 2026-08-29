import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const repositoryRoot = new URL("../..", import.meta.url);
const packageJson = JSON.parse(
  readFileSync(new URL("../../package.json", import.meta.url), "utf8"),
);
const workflowUrl = new URL("../../.github/workflows/quality.yml", import.meta.url);

test("the root test command is the complete deterministic quality gate", () => {
  assert.equal(packageJson.scripts.test, "pnpm test:quality");
  for (const command of [
    "pnpm test:web",
    "pnpm test:mobile",
    "pnpm test:api",
    "pnpm test:contracts",
    "pnpm lint:api",
    "pnpm build:web",
    "pnpm test:e2e",
  ]) {
    assert.match(packageJson.scripts["test:quality"], new RegExp(command.replaceAll(":", "\\:")));
  }
});

test("continuous integration runs the same root quality gate", () => {
  assert.equal(existsSync(workflowUrl), true);
  const workflow = readFileSync(workflowUrl, "utf8");
  assert.match(workflow, /run: pnpm test\s*$/m);
  assert.doesNotMatch(workflow, /continue-on-error:\s*true/);
  assert.equal(repositoryRoot.pathname.endsWith("/Patchamomma/"), true);
});
