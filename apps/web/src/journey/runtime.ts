import type { Locale } from "../onboarding/runtime";

export interface LocalizedText {
  en: string;
  hi: string;
}

export interface LocalizedInstructions {
  en: string[];
  hi: string[];
}

export type JourneyActivityKind = "learn" | "practice" | "create" | "reflect" | "rest";

export interface JourneyActivity {
  activityId: string;
  dayNumber: number;
  date: string;
  kind: JourneyActivityKind;
  required: boolean;
  durationMinutes: number;
  title: LocalizedText;
  instructions: LocalizedInstructions;
  accessibleAlternative: LocalizedText;
  reflectionPrompt: LocalizedText;
  safetyNote: LocalizedText;
}

export interface JourneyWeek {
  weekNumber: number;
  theme: LocalizedText;
  outcome: LocalizedText;
  activities: JourneyActivity[];
}

export interface JourneyDraft {
  schemaVersion: "1.0.0" | "1.1.0";
  journeyId: string;
  status: "draft" | "confirmed";
  startsOn: string;
  timezone: "Asia/Kolkata";
  languages: ["en", "hi"];
  title: LocalizedText;
  summary: LocalizedText;
  provenance: {
    generator: "deterministic_fixture" | "gemini_adk" | "curated_fallback";
    attempts: number;
    fallbackUsed: boolean;
    fallbackReason: "workflow_unavailable" | "workflow_timeout" | "validation_failed_twice" | "review_failed_twice" | "localization_failed_twice" | null;
  };
  review: {
    status: "passed";
    contractVersion: "safety-accessibility-v1";
    passedChecks: ["schema", "schedule", "accessibility", "safety", "localization"];
  };
  weeks: JourneyWeek[];
}

export interface JourneyGateway {
  create(startsOn: string): Promise<JourneyDraft>;
  confirm(draft: JourneyDraft): Promise<JourneyDraft>;
  loadConfirmed?(): Promise<JourneyDraft | null>;
}

interface JourneyApiGatewayOptions {
  apiBaseUrl: string;
  requestHeaders(): Promise<Record<string, string>>;
  requestTimeoutMs?: number;
  fetcher?: typeof fetch;
}

// Covers two bounded 30-second review attempts plus network and response parsing time.
const DEFAULT_JOURNEY_REQUEST_TIMEOUT_MS = 75_000;

export function nextJourneyStartDate(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? "";
  const indiaDate = new Date(`${value("year")}-${value("month")}-${value("day")}T00:00:00Z`);
  indiaDate.setUTCDate(indiaDate.getUTCDate() + 1);
  return indiaDate.toISOString().slice(0, 10);
}

export function shiftJourneyStartDate(draft: JourneyDraft, startsOn: string): JourneyDraft {
  const nextStart = new Date(`${startsOn}T00:00:00Z`);
  if (Number.isNaN(nextStart.valueOf())) return draft;
  return {
    ...draft,
    startsOn,
    weeks: draft.weeks.map((week) => ({
      ...week,
      activities: week.activities.map((activity) => {
        const activityDate = new Date(nextStart);
        activityDate.setUTCDate(nextStart.getUTCDate() + activity.dayNumber - 1);
        return { ...activity, date: activityDate.toISOString().slice(0, 10) };
      }),
    })),
  };
}

export function createJourneyApiGateway({
  apiBaseUrl,
  requestHeaders,
  requestTimeoutMs = DEFAULT_JOURNEY_REQUEST_TIMEOUT_MS,
  fetcher = fetch,
}: JourneyApiGatewayOptions): JourneyGateway {
  const api = apiBaseUrl.replace(/\/$/, "");
  const headers = async () => ({ ...(await requestHeaders()), "Content-Type": "application/json" });
  const request = async (url: string, init: RequestInit): Promise<JourneyDraft> => {
    const controller = new AbortController();
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const timedOut = new Promise<never>((_resolve, reject) => {
      timeout = setTimeout(() => {
        controller.abort();
        reject(new Error(`Plan request timed out after ${Math.round(requestTimeoutMs / 1_000)} seconds.`));
      }, requestTimeoutMs);
    });
    const response = (async () => {
      const result = await fetcher(url, { ...init, headers: await headers(), signal: controller.signal });
      if (!result.ok) throw new Error(`Journey request failed with status ${result.status}.`);
      return result.json() as Promise<JourneyDraft>;
    })();

    try {
      return await Promise.race([response, timedOut]);
    } finally {
      if (timeout !== undefined) clearTimeout(timeout);
    }
  };
  return {
    async loadConfirmed() {
      const result = await fetcher(`${api}/api/v1/journeys/current`, {
        method: "GET",
        headers: await headers(),
      });
      if (result.status === 404) return null;
      if (!result.ok) throw new Error(`Journey request failed with status ${result.status}.`);
      return result.json() as Promise<JourneyDraft>;
    },
    async create(startsOn) {
      return request(`${api}/api/v1/journeys`, {
        method: "POST",
        body: JSON.stringify({ startsOn }),
      });
    },
    async confirm(draft) {
      return request(`${api}/api/v1/journeys/${encodeURIComponent(draft.journeyId)}`, {
        method: "PUT",
        body: JSON.stringify(draft),
      });
    },
  };
}

export function localized(value: LocalizedText, locale: Locale): string {
  return value[locale];
}
