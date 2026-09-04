import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { resolveApiBaseUrl } from "./runtime";

const CLOUD_RUN_URL =
  "https://sakhicircle-api-859217028205.asia-south1.run.app";

describe("SC-720 web deployment runtime", () => {
  it("keeps the deterministic local API fallback", () => {
    expect(
      resolveApiBaseUrl(
        { VITE_ADAPTER_MODE: "deterministic" },
        { protocol: "http:", hostname: "127.0.0.1" },
      ),
    ).toBe("http://127.0.0.1:8080");
  });

  it("requires the exact HTTPS Mumbai Cloud Run service in production", () => {
    const location = { protocol: "https:", hostname: "example.web.app" };

    expect(() =>
      resolveApiBaseUrl({ VITE_ADAPTER_MODE: "production" }, location),
    ).toThrow(/VITE_API_BASE_URL/);
    expect(() =>
      resolveApiBaseUrl(
        {
          VITE_ADAPTER_MODE: "production",
          VITE_API_BASE_URL: "http://sakhicircle-api.example.invalid",
        },
        location,
      ),
    ).toThrow(/HTTPS/);
    expect(() =>
      resolveApiBaseUrl(
        {
          VITE_ADAPTER_MODE: "production",
          VITE_API_BASE_URL: "https://other-service.example.com",
        },
        location,
      ),
    ).toThrow(/approved Cloud Run service/);
    expect(
      resolveApiBaseUrl(
        {
          VITE_ADAPTER_MODE: "production",
          VITE_API_BASE_URL: `${CLOUD_RUN_URL}/`,
        },
        location,
      ),
    ).toBe(CLOUD_RUN_URL);
  });

  it("uses the registered reCAPTCHA Enterprise App Check provider", () => {
    const firebaseSource = readFileSync(
      resolve(process.cwd(), "src/auth/firebase.ts"),
      "utf8",
    );

    expect(firebaseSource).toContain("ReCaptchaEnterpriseProvider");
    expect(firebaseSource).not.toContain("new ReCaptchaV3Provider");
  });
});
