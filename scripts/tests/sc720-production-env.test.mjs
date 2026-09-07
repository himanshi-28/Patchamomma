import assert from "node:assert/strict";
import { mkdtemp, readFile, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  APP_ID,
  ENV_FIELD_NAMES,
  PROJECT_ID,
  buildProductionEnvironment,
  prepareProductionEnvironment,
} from "../sc720-prepare-web-env.mjs";

const API_KEY = `fake-${"a".repeat(32)}`;
const SITE_KEY = `fake-site-${"b".repeat(32)}`;
const SDK_AUTH_DOMAIN = `${PROJECT_ID}.firebaseapp.com`;
const LEGACY_HOSTING_AUTH_DOMAIN = `${PROJECT_ID}.web.app`;
const HOSTING_AUTH_DOMAIN = "sakhi-circle.web.app";
const API_BASE_URL =
  "https://sakhicircle-api-859217028205.asia-south1.run.app";

function sdkPayload(overrides = {}) {
  return JSON.stringify({
    status: "success",
    result: {
      sdkConfig: {
        apiKey: API_KEY,
        authDomain: SDK_AUTH_DOMAIN,
        projectId: PROJECT_ID,
        appId: APP_ID,
        ...overrides,
      },
    },
  });
}

function appCheckPayload(overrides = {}) {
  return JSON.stringify({
    status: "success",
    result: {
      provider: "recaptcha-enterprise",
      configured: true,
      siteKey: SITE_KEY,
      ...overrides,
    },
  });
}

test("SC-720 builds only the locked production environment", () => {
  const environment = buildProductionEnvironment({
    sdkPayload: sdkPayload(),
    appCheckPayload: appCheckPayload(),
  });

  assert.equal(
    environment,
    [
      "VITE_DEMO_MODE=false",
      "VITE_ADAPTER_MODE=production",
      `VITE_API_BASE_URL=${API_BASE_URL}`,
      `VITE_FIREBASE_API_KEY=${API_KEY}`,
      `VITE_FIREBASE_AUTH_DOMAIN=${HOSTING_AUTH_DOMAIN}`,
      `VITE_FIREBASE_PROJECT_ID=${PROJECT_ID}`,
      `VITE_FIREBASE_APP_ID=${APP_ID}`,
      `VITE_FIREBASE_APP_CHECK_SITE_KEY=${SITE_KEY}`,
      "",
    ].join("\n"),
  );
});

test("SC-720 uses exact read-only CLI calls and reports no configuration values", async () => {
  const directory = await mkdtemp(join(tmpdir(), "sc720-production-env-"));
  const targetPath = join(directory, ".env.production.local");
  const calls = [];
  const execute = async (executable, args, options = {}) => {
    calls.push({
      executable,
      args,
      environment: options.environment ?? {},
    });
    if (args.includes("apps:sdkconfig")) {
      return { stdout: sdkPayload(), stderr: "" };
    }
    return { stdout: appCheckPayload(), stderr: "" };
  };

  const result = await prepareProductionEnvironment({ execute, targetPath });

  assert.deepEqual(calls, [
    {
      executable: "npx",
      args: [
        "--yes",
        "firebase-tools@15.28.1",
        "apps:sdkconfig",
        "WEB",
        APP_ID,
        "--project",
        PROJECT_ID,
        "--json",
      ],
      environment: {},
    },
    {
      executable: "npx",
      args: [
        "--yes",
        "firebase-tools@15.28.1",
        "appcheck:providers:get",
        "recaptcha-enterprise",
        "--app",
        APP_ID,
        "--project",
        PROJECT_ID,
        "--json",
      ],
      environment: {
        FIREBASE_CLI_EXPERIMENTS: "appcheckadmin",
      },
    },
  ]);
  assert.deepEqual(result, {
    status: "created",
    fields: ENV_FIELD_NAMES,
  });
  assert.equal((await stat(targetPath)).mode & 0o777, 0o600);
  assert.match(await readFile(targetPath, "utf8"), /VITE_ADAPTER_MODE=production/);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(`${API_KEY}|${SITE_KEY}`));
});

test("SC-720 refuses cross-project, cross-app, wrong-provider, or unsafe values", () => {
  const invalidCases = [
    { sdkPayload: sdkPayload({ projectId: "wrong-project" }), message: /project/ },
    { sdkPayload: sdkPayload({ appId: "1:wrong:web:app" }), message: /app/ },
    { sdkPayload: sdkPayload({ authDomain: "wrong.example" }), message: /auth domain/ },
    {
      appCheckPayload: appCheckPayload({ provider: "recaptcha-v3" }),
      message: /provider/,
    },
    {
      appCheckPayload: appCheckPayload({ configured: false }),
      message: /configured/,
    },
    { sdkPayload: sdkPayload({ apiKey: "unsafe\nvalue" }), message: /unsafe/ },
  ];

  for (const invalid of invalidCases) {
    assert.throws(
      () =>
        buildProductionEnvironment({
          sdkPayload: invalid.sdkPayload ?? sdkPayload(),
          appCheckPayload: invalid.appCheckPayload ?? appCheckPayload(),
        }),
      invalid.message,
    );
  }
});

test("SC-720 is idempotent and will not overwrite different local configuration", async () => {
  const directory = await mkdtemp(join(tmpdir(), "sc720-production-env-"));
  const targetPath = join(directory, ".env.production.local");
  const execute = async (_executable, args) => ({
    stdout: args.includes("apps:sdkconfig") ? sdkPayload() : appCheckPayload(),
    stderr: "",
  });

  assert.equal(
    (await prepareProductionEnvironment({ execute, targetPath })).status,
    "created",
  );
  assert.equal(
    (await prepareProductionEnvironment({ execute, targetPath })).status,
    "unchanged",
  );

  await writeFile(targetPath, "different\n", { mode: 0o600 });
  await assert.rejects(
    prepareProductionEnvironment({ execute, targetPath }),
    /refusing to overwrite/i,
  );
});

test("SC-720 migrates only approved legacy Firebase auth domains", async (context) => {
  for (const legacyAuthDomain of [SDK_AUTH_DOMAIN, LEGACY_HOSTING_AUTH_DOMAIN]) {
    await context.test(legacyAuthDomain, async () => {
      const directory = await mkdtemp(join(tmpdir(), "sc720-production-env-"));
      const targetPath = join(directory, ".env.production.local");
      const execute = async (_executable, args) => ({
        stdout: args.includes("apps:sdkconfig") ? sdkPayload() : appCheckPayload(),
        stderr: "",
      });

      const legacyEnvironment = buildProductionEnvironment({
        sdkPayload: sdkPayload(),
        appCheckPayload: appCheckPayload(),
      }).replace(HOSTING_AUTH_DOMAIN, legacyAuthDomain);
      await writeFile(targetPath, legacyEnvironment, { mode: 0o600 });

      assert.equal(
        (await prepareProductionEnvironment({ execute, targetPath })).status,
        "migrated-auth-domain",
      );
      assert.match(
        await readFile(targetPath, "utf8"),
        new RegExp(`VITE_FIREBASE_AUTH_DOMAIN=${HOSTING_AUTH_DOMAIN}`),
      );
    });
  }
});

test("SC-720 converts CLI failures to fixed non-disclosing errors", async () => {
  const directory = await mkdtemp(join(tmpdir(), "sc720-production-env-"));
  const targetPath = join(directory, ".env.production.local");
  const execute = async () => {
    throw new Error(`provider returned ${SITE_KEY}`);
  };

  await assert.rejects(
    prepareProductionEnvironment({ execute, targetPath }),
    (error) => {
      assert.match(error.message, /configuration read failed/i);
      assert.doesNotMatch(error.message, new RegExp(SITE_KEY));
      return true;
    },
  );
});
