import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const repositoryRoot = new URL("../../", import.meta.url);

const readJson = async (name) =>
  JSON.parse(await readFile(new URL(name, repositoryRoot), "utf8"));

test("production Hosting deploys to the SakhiCircle site", async () => {
  const [firebaseConfig, firebaseProjects] = await Promise.all([
    readJson("firebase.json"),
    readJson(".firebaserc"),
  ]);

  assert.equal(firebaseConfig.hosting.target, "production");
  assert.equal(
    firebaseProjects.projects.default,
    "patchamomma-2026-505415",
  );
  assert.deepEqual(
    firebaseProjects.targets["patchamomma-2026-505415"].hosting.production,
    ["sakhi-circle"],
  );
});
