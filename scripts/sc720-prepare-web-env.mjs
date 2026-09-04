import { execFile } from "node:child_process";
import { chmod, readFile, writeFile } from "node:fs/promises";
import { promisify } from "node:util";
import { fileURLToPath, pathToFileURL } from "node:url";

export const PROJECT_ID = "patchamomma-2026-505415";
export const APP_ID = "1:859217028205:web:eaf322c7cc7555721e0b64";
export const API_BASE_URL =
  "https://sakhicircle-api-859217028205.asia-south1.run.app";
export const ENV_FIELD_NAMES = Object.freeze([
  "VITE_DEMO_MODE",
  "VITE_ADAPTER_MODE",
  "VITE_API_BASE_URL",
  "VITE_FIREBASE_API_KEY",
  "VITE_FIREBASE_AUTH_DOMAIN",
  "VITE_FIREBASE_PROJECT_ID",
  "VITE_FIREBASE_APP_ID",
  "VITE_FIREBASE_APP_CHECK_SITE_KEY",
]);

const SDK_AUTH_DOMAIN = `${PROJECT_ID}.firebaseapp.com`;
const HOSTING_AUTH_DOMAIN = `${PROJECT_ID}.web.app`;
const FIREBASE_TOOLS_VERSION = "15.28.1";
const DEFAULT_TARGET_PATH = fileURLToPath(
  new URL("../apps/web/.env.production.local", import.meta.url),
);
const SAFE_ENV_VALUE = /^[A-Za-z0-9._:-]+$/;
const execFileAsync = promisify(execFile);

function parseCliPayload(payload, label) {
  if (typeof payload !== "string") {
    throw new Error(`${label} response is invalid.`);
  }
  try {
    const parsed = JSON.parse(payload);
    if (parsed?.status !== "success" || typeof parsed.result !== "object") {
      throw new Error();
    }
    return parsed.result;
  } catch {
    throw new Error(`${label} response is invalid.`);
  }
}

function requireSafeValue(value, label) {
  if (typeof value !== "string" || !SAFE_ENV_VALUE.test(value)) {
    throw new Error(`${label} contains an unsafe environment value.`);
  }
  return value;
}

export function buildProductionEnvironment({ sdkPayload, appCheckPayload }) {
  const sdkResult = parseCliPayload(sdkPayload, "Firebase SDK configuration");
  const sdkConfig = sdkResult.sdkConfig;
  if (!sdkConfig || typeof sdkConfig !== "object") {
    throw new Error("Firebase SDK configuration response is invalid.");
  }
  if (sdkConfig.projectId !== PROJECT_ID) {
    throw new Error("Firebase project does not match the approved project.");
  }
  if (sdkConfig.appId !== APP_ID) {
    throw new Error("Firebase app does not match the approved app.");
  }
  if (sdkConfig.authDomain !== SDK_AUTH_DOMAIN) {
    throw new Error("Firebase auth domain does not match the approved auth domain.");
  }

  const appCheckResult = parseCliPayload(
    appCheckPayload,
    "Firebase App Check configuration",
  );
  if (appCheckResult.provider !== "recaptcha-enterprise") {
    throw new Error("Firebase App Check provider is not the approved provider.");
  }
  if (appCheckResult.configured !== true) {
    throw new Error("Firebase App Check provider is not configured.");
  }

  const apiKey = requireSafeValue(sdkConfig.apiKey, "Firebase API key");
  const siteKey = requireSafeValue(
    appCheckResult.siteKey,
    "Firebase App Check site key",
  );

  return [
    "VITE_DEMO_MODE=false",
    "VITE_ADAPTER_MODE=production",
    `VITE_API_BASE_URL=${API_BASE_URL}`,
    `VITE_FIREBASE_API_KEY=${apiKey}`,
    `VITE_FIREBASE_AUTH_DOMAIN=${HOSTING_AUTH_DOMAIN}`,
    `VITE_FIREBASE_PROJECT_ID=${PROJECT_ID}`,
    `VITE_FIREBASE_APP_ID=${APP_ID}`,
    `VITE_FIREBASE_APP_CHECK_SITE_KEY=${siteKey}`,
    "",
  ].join("\n");
}

async function executeCli(executable, args, { environment = {} } = {}) {
  const { stdout, stderr } = await execFileAsync(executable, args, {
    encoding: "utf8",
    env: { ...process.env, ...environment },
    maxBuffer: 1024 * 1024,
  });
  return { stdout, stderr };
}

async function writeEnvironmentFile(targetPath, environment) {
  try {
    await writeFile(targetPath, environment, {
      encoding: "utf8",
      flag: "wx",
      mode: 0o600,
    });
    await chmod(targetPath, 0o600);
    return "created";
  } catch (error) {
    if (error?.code !== "EEXIST") {
      throw new Error("Production environment file could not be written.");
    }
  }

  let existing;
  try {
    existing = await readFile(targetPath, "utf8");
  } catch {
    throw new Error("Production environment file could not be read.");
  }
  if (existing !== environment) {
    const legacyAuthLine = `VITE_FIREBASE_AUTH_DOMAIN=${SDK_AUTH_DOMAIN}`;
    const hostingAuthLine = `VITE_FIREBASE_AUTH_DOMAIN=${HOSTING_AUTH_DOMAIN}`;
    const migratedEnvironment = existing.replace(legacyAuthLine, hostingAuthLine);
    const legacyLineCount = existing.split(legacyAuthLine).length - 1;
    if (legacyLineCount !== 1 || migratedEnvironment !== environment) {
      throw new Error("Refusing to overwrite different production configuration.");
    }
    try {
      await writeFile(targetPath, migratedEnvironment, {
        encoding: "utf8",
        mode: 0o600,
      });
      await chmod(targetPath, 0o600);
    } catch {
      throw new Error("Production environment file could not be written.");
    }
    return "migrated-auth-domain";
  }
  try {
    await chmod(targetPath, 0o600);
  } catch {
    throw new Error("Production environment file permissions could not be secured.");
  }
  return "unchanged";
}

export async function prepareProductionEnvironment({
  execute = executeCli,
  targetPath = DEFAULT_TARGET_PATH,
} = {}) {
  let sdkResponse;
  let appCheckResponse;
  try {
    sdkResponse = await execute("npx", [
      "--yes",
      `firebase-tools@${FIREBASE_TOOLS_VERSION}`,
      "apps:sdkconfig",
      "WEB",
      APP_ID,
      "--project",
      PROJECT_ID,
      "--json",
    ]);
    appCheckResponse = await execute("npx", [
      "--yes",
      `firebase-tools@${FIREBASE_TOOLS_VERSION}`,
      "appcheck:providers:get",
      "recaptcha-enterprise",
      "--app",
      APP_ID,
      "--project",
      PROJECT_ID,
      "--json",
    ], {
      environment: {
        FIREBASE_CLI_EXPERIMENTS: "appcheckadmin",
      },
    });
  } catch {
    throw new Error("Firebase production configuration read failed.");
  }

  const environment = buildProductionEnvironment({
    sdkPayload: sdkResponse.stdout,
    appCheckPayload: appCheckResponse.stdout,
  });
  const status = await writeEnvironmentFile(targetPath, environment);
  return { status, fields: ENV_FIELD_NAMES };
}

const isMain =
  process.argv[1] !== undefined &&
  pathToFileURL(process.argv[1]).href === import.meta.url;

if (isMain) {
  try {
    const result = await prepareProductionEnvironment();
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } catch {
    process.stderr.write("Production environment preparation failed.\n");
    process.exitCode = 1;
  }
}
