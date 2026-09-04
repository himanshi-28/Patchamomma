interface DeploymentEnvironment {
  VITE_ADAPTER_MODE?: "deterministic" | "firebase_emulator" | "production";
  VITE_API_BASE_URL?: string;
}

interface BrowserLocation {
  protocol: string;
  hostname: string;
}

export const PRODUCTION_API_BASE_URL =
  "https://sakhicircle-api-859217028205.asia-south1.run.app";

export function resolveApiBaseUrl(
  environment: DeploymentEnvironment,
  location: BrowserLocation,
): string {
  const configured = environment.VITE_API_BASE_URL?.replace(/\/+$/, "");

  if (environment.VITE_ADAPTER_MODE === "production") {
    if (!configured) {
      throw new Error("VITE_API_BASE_URL is required in production.");
    }

    let parsed: URL;
    try {
      parsed = new URL(configured);
    } catch {
      throw new Error("The production API URL must be valid HTTPS.");
    }
    if (parsed.protocol !== "https:") {
      throw new Error("The production API URL must use HTTPS.");
    }
    if (
      parsed.origin !== PRODUCTION_API_BASE_URL
      || parsed.pathname !== "/"
      || parsed.search
      || parsed.hash
    ) {
      throw new Error("VITE_API_BASE_URL must use the approved Cloud Run service.");
    }
    return parsed.origin;
  }

  return configured || `${location.protocol}//${location.hostname}:8080`;
}
