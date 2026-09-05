import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const evidenceRoot = new URL(
  "../../docs/validation/evidence/web/sc-725/",
  import.meta.url,
);

const SIGN_IN_CAPTURE = "deployed-mobile-sign-in-en-360x800.jpg";

const readJson = async (name) =>
  JSON.parse(await readFile(new URL(name, evidenceRoot), "utf8"));

const readJpegSize = async (name) => {
  const bytes = await readFile(new URL(name, evidenceRoot));
  assert.deepEqual([...bytes.subarray(0, 2)], [255, 216], `${name} must be a JPEG capture`);

  let offset = 2;
  while (offset + 9 < bytes.length) {
    if (bytes[offset] !== 255) {
      offset += 1;
      continue;
    }
    const marker = bytes[offset + 1];
    offset += 2;
    if (marker === 217 || marker === 218) break;
    const segmentLength = bytes.readUInt16BE(offset);
    if ([192, 193, 194, 195, 197, 198, 199, 201, 202, 203, 205, 206, 207].includes(marker)) {
      return [bytes.readUInt16BE(offset + 5), bytes.readUInt16BE(offset + 3)];
    }
    offset += segmentLength;
  }
  assert.fail(`${name} does not contain JPEG dimensions`);
};

test("SC-725 records the deployed English/Hindi vertical-slice evidence", async () => {
  const manifest = await readJson("manifest.json");

  assert.equal(manifest.task, "SC-725");
  assert.equal(manifest.status, "complete");
  assert.equal(manifest.hostingUrl, "https://patchamomma-2026-505415.web.app");
  assert.equal(
    manifest.apiBaseUrl,
    "https://sakhicircle-api-859217028205.asia-south1.run.app",
  );
  assert.equal(manifest.timezone, "Asia/Kolkata");
  assert.match(manifest.capturedAt, /^2026-09-\d{2}T\d{2}:\d{2}:\d{2}[+]05:30$/);
  assert.deepEqual(manifest.languages, ["en", "hi"]);
  assert.deepEqual(manifest.apiEvidence, {
    healthStatus: 200,
    readyStatus: 200,
    profileSaveStatus: 200,
    journeyCreateStatus: 200,
    journeySaveStatus: 200,
    recommendationStatus: 200,
  });
  assert.equal(manifest.browserEvidence.syntheticRecommendation, true);
  assert.equal(manifest.browserEvidence.recommendationScore, 100);
  assert.equal(manifest.browserEvidence.recommendationReasons, 3);
  assert.equal(manifest.browserEvidence.mobileHorizontalOverflow, 0);
  assert.equal(manifest.userAttestation.result, "works-as-designed");
  assert.deepEqual(manifest.userAttestation.languages, ["en", "hi"]);
  assert.deepEqual(manifest.userAttestation.viewports, ["mobile", "desktop"]);
  assert.equal(manifest.userAttestation.screenshotsRequired, false);
});

test("SC-725 includes the exact deployed mobile sign-in capture", async () => {
  assert.deepEqual(await readJpegSize(SIGN_IN_CAPTURE), [360, 800]);
});

test("SC-725 evidence README states the production and privacy boundaries", async () => {
  const readme = await readFile(new URL("README.md", evidenceRoot), "utf8");

  for (const requiredText of [
    "Firebase Hosting",
    "Cloud Run",
    "English",
    "Hindi",
    "synthetic",
    "No raw audio",
    "No transcript",
    "SC-725",
  ]) {
    assert.match(readme, new RegExp(requiredText, "i"));
  }
});
