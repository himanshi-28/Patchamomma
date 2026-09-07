import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  createAnalyticsAwareFetcher,
  createAnalyticsReceiptGateway,
} from "./analytics/runtime";
import { App } from "./App";
import { createFirebaseAuthGateway } from "./auth/firebase";
import {
  createDeterministicAuthGateway,
  createUnavailableAuthGateway,
  protectedRequestHeaders,
  resolveAuthRuntimeConfig,
  type AuthGateway,
} from "./auth/runtime";
import { resolveApiBaseUrl } from "./deployment/runtime";
import { createJourneyApiGateway } from "./journey/runtime";
import {
  createDeterministicProfileExtractionGateway,
  createProfileApiGateway,
  createProfileExtractionApiGateway,
  createTranscriptAdapterForMode,
} from "./onboarding/runtime";
import { createRecommendationApiGateway } from "./recommendation/runtime";
import "./styles.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("SakhiCircle could not find its application root.");
}

let demoMode = false;
let authGateway: AuthGateway;
let adapterMode: "deterministic" | "firebase_emulator" | "production" = "deterministic";

try {
  const authConfig = resolveAuthRuntimeConfig(import.meta.env);
  demoMode = authConfig.demoMode;
  adapterMode = authConfig.adapterMode;
  authGateway = authConfig.adapterMode === "deterministic"
    ? createDeterministicAuthGateway({ demoMode })
    : createFirebaseAuthGateway(authConfig);
} catch (error) {
  authGateway = createUnavailableAuthGateway(
    error instanceof Error ? error : new Error("Authentication configuration is unavailable."),
  );
}

const apiBaseUrl = resolveApiBaseUrl(import.meta.env, window.location);
const transcriptAdapter = createTranscriptAdapterForMode(adapterMode);
const analyticsReceiptGateway = createAnalyticsReceiptGateway({
  apiBaseUrl,
  requestHeaders: () => protectedRequestHeaders(authGateway, adapterMode),
});
const analyticsAwareFetch = createAnalyticsAwareFetcher({
  resume: (receipt) => analyticsReceiptGateway.resume(receipt),
});
const profileGateway = createProfileApiGateway({
  apiBaseUrl,
  requestHeaders: () => protectedRequestHeaders(authGateway, adapterMode),
  fetcher: analyticsAwareFetch,
});
const profileExtractionGateway = adapterMode === "deterministic"
  ? createDeterministicProfileExtractionGateway()
  : createProfileExtractionApiGateway({
      apiBaseUrl,
      requestHeaders: () => protectedRequestHeaders(authGateway, adapterMode),
      fetcher: analyticsAwareFetch,
    });
const journeyGateway = createJourneyApiGateway({
  apiBaseUrl,
  requestHeaders: () => protectedRequestHeaders(authGateway, adapterMode),
  fetcher: analyticsAwareFetch,
});
const recommendationGateway = createRecommendationApiGateway({
  apiBaseUrl,
  requestHeaders: () => protectedRequestHeaders(authGateway, adapterMode),
  fetcher: analyticsAwareFetch,
});

createRoot(root).render(
  <StrictMode>
    <App
      demoMode={demoMode}
      authGateway={authGateway}
      transcriptAdapter={transcriptAdapter}
      profileGateway={profileGateway}
      profileExtractionGateway={profileExtractionGateway}
      journeyGateway={journeyGateway}
      recommendationGateway={recommendationGateway}
    />
  </StrictMode>,
);
