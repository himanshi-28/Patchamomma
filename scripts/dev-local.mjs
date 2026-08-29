import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const argumentsSet = new Set(process.argv.slice(2));
const webPort = 5173;
const apiPort = 8080;

const localContract = {
  services: {
    web: `http://localhost:${webPort}`,
    apiHealth: `http://localhost:${apiPort}/health`,
    apiReadiness: `http://localhost:${apiPort}/ready`,
  },
  adapterMode: "deterministic",
  demoMode: true,
  paidApiCallsEnabled: false,
};

if (argumentsSet.has("--check")) {
  process.stdout.write(`${JSON.stringify(localContract)}\n`);
  process.exit(0);
}

const python = resolve(repositoryRoot, ".venv", "bin", "python");
if (!existsSync(python)) {
  process.stderr.write(
    "Local startup needs .venv/bin/python. Follow README Local setup step 2, then rerun pnpm dev:local.\n",
  );
  process.exit(1);
}

const baseEnvironment = {
  ...process.env,
  NO_COLOR: process.env.NO_COLOR ?? "1",
};

const childDefinitions = [
  {
    name: "web",
    command: process.platform === "win32" ? "pnpm.cmd" : "pnpm",
    args: [
      "--filter",
      "@sakhicircle/web",
      "dev",
      "--host",
      "0.0.0.0",
      "--port",
      String(webPort),
      "--strictPort",
    ],
    environment: {
      ...baseEnvironment,
      VITE_DEMO_MODE: "true",
      VITE_ADAPTER_MODE: "deterministic",
      VITE_API_BASE_URL: `http://localhost:${apiPort}`,
    },
  },
  {
    name: "api",
    command: python,
    args: [
      "-m",
      "uvicorn",
      "app.main:app",
      "--app-dir",
      "services/api",
      "--host",
      "0.0.0.0",
      "--port",
      String(apiPort),
    ],
    environment: {
      ...baseEnvironment,
      SAKHI_APP_ENV: "development",
      SAKHI_DEMO_MODE: "true",
      SAKHI_ADAPTER_MODE: "deterministic",
      SAKHI_PAID_API_CALLS_ENABLED: "false",
      SAKHI_ALLOWED_ORIGINS: JSON.stringify([
        `http://localhost:${webPort}`,
        `http://127.0.0.1:${webPort}`,
      ]),
    },
  },
];

const children = [];
let stopping = false;

function stopChild(child) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return;
  }

  if (process.platform === "win32") {
    child.kill("SIGTERM");
  } else {
    try {
      process.kill(-child.pid, "SIGTERM");
    } catch {
      child.kill("SIGTERM");
    }
  }
}

function stopAll(exitCode = 0) {
  if (stopping) {
    return;
  }
  stopping = true;
  for (const child of children) {
    stopChild(child);
  }
  setTimeout(() => process.exit(exitCode), 250).unref();
}

for (const definition of childDefinitions) {
  const child = spawn(definition.command, definition.args, {
    cwd: repositoryRoot,
    env: definition.environment,
    stdio: "inherit",
    detached: process.platform !== "win32",
  });
  children.push(child);
  child.once("error", (error) => {
    process.stderr.write(`${definition.name} failed to start: ${error.message}\n`);
    stopAll(1);
  });
  child.once("exit", (code, signal) => {
    if (!stopping) {
      process.stderr.write(
        `${definition.name} stopped before shutdown (${signal ?? `exit ${code}`}).\n`,
      );
      stopAll(code || 1);
    }
  });
}

process.once("SIGINT", () => stopAll(0));
process.once("SIGTERM", () => stopAll(0));

async function waitFor(url, validate = () => true) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok && (await validate(response))) {
        return;
      }
    } catch {
      // The service is still starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

try {
  await Promise.all([
    waitFor(localContract.services.web),
    waitFor(localContract.services.apiReadiness, async (response) => {
      const readiness = await response.json();
      return (
        readiness.status === "ready" &&
        readiness.adapterMode === localContract.adapterMode &&
        readiness.paidApiCallsEnabled === false
      );
    }),
  ]);
  process.stdout.write(
    `SakhiCircle local environment is ready.\n` +
      `Web: ${localContract.services.web}\n` +
      `API health: ${localContract.services.apiHealth}\n` +
      `API readiness: ${localContract.services.apiReadiness}\n` +
      `Adapters: deterministic; paid API calls: disabled.\n`,
  );
  if (argumentsSet.has("--smoke")) {
    stopAll(0);
  }
} catch (error) {
  process.stderr.write(`${error.message}\n`);
  stopAll(1);
}
