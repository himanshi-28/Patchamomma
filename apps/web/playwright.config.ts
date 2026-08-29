import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "mobile-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 360, height: 800 },
      },
    },
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
  webServer: [
    {
      command: "node_modules/.bin/vite --host 127.0.0.1 --port 4173 --strictPort",
      env: {
        VITE_DEMO_MODE: "true",
        VITE_ADAPTER_MODE: "deterministic",
        VITE_API_BASE_URL: "http://127.0.0.1:8080",
      },
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "../../.venv/bin/python -m uvicorn app.main:app --app-dir ../../services/api --host 127.0.0.1 --port 8080",
      env: {
        SAKHI_APP_ENV: "test",
        SAKHI_DEMO_MODE: "true",
        SAKHI_ADAPTER_MODE: "deterministic",
        SAKHI_JOURNEY_ADAPTER_MODE: "deterministic",
        SAKHI_PAID_API_CALLS_ENABLED: "false",
        SAKHI_ALLOWED_ORIGINS: '["http://127.0.0.1:4173"]',
      },
      url: "http://127.0.0.1:8080/ready",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
