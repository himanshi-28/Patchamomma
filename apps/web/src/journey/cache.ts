import type {
  JourneyActivity,
  JourneyActivityKind,
  JourneyDraft,
  JourneyWeek,
  LocalizedInstructions,
  LocalizedText,
} from "./runtime";

export const CONFIRMED_JOURNEY_CACHE_KEY = "sakhicircle-confirmed-journey-cache";
const CACHE_VERSION = "journey-cache-v1";
const ACTIVITY_KINDS = new Set<JourneyActivityKind>(["learn", "practice", "create", "reflect", "rest"]);
const GENERATORS = new Set(["deterministic_fixture", "gemini_adk", "curated_fallback"]);
const FALLBACK_REASONS = new Set([
  "workflow_unavailable",
  "workflow_timeout",
  "validation_failed_twice",
  "review_failed_twice",
  "localization_failed_twice",
]);
const PASSED_CHECKS = ["schema", "schedule", "accessibility", "safety", "localization"] as const;

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function copyLocalizedText(value: unknown): LocalizedText | null {
  const source = asRecord(value);
  const en = nonEmptyString(source?.en);
  const hi = nonEmptyString(source?.hi);
  return en && hi ? { en, hi } : null;
}

function copyInstructions(value: unknown): LocalizedInstructions | null {
  const source = asRecord(value);
  if (!Array.isArray(source?.en) || !Array.isArray(source.hi)) return null;
  const en = source.en.map(nonEmptyString);
  const hi = source.hi.map(nonEmptyString);
  if (en.length === 0 || hi.length === 0 || en.includes(null) || hi.includes(null)) return null;
  return { en: en as string[], hi: hi as string[] };
}

function isIsoDate(value: unknown): value is string {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === value;
}

function copyActivity(value: unknown, expectedDay: number): JourneyActivity | null {
  const source = asRecord(value);
  if (!source) return null;
  const activityId = nonEmptyString(source.activityId);
  const title = copyLocalizedText(source.title);
  const instructions = copyInstructions(source.instructions);
  const accessibleAlternative = copyLocalizedText(source.accessibleAlternative);
  const reflectionPrompt = copyLocalizedText(source.reflectionPrompt);
  const safetyNote = copyLocalizedText(source.safetyNote);
  const kind = typeof source.kind === "string" && ACTIVITY_KINDS.has(source.kind as JourneyActivityKind)
    ? source.kind as JourneyActivityKind
    : null;
  const validDuration = Number.isInteger(source.durationMinutes)
    && (source.durationMinutes as number) >= 0
    && (source.durationMinutes as number) <= 45;

  if (!activityId || source.dayNumber !== expectedDay || !isIsoDate(source.date) || !kind
    || typeof source.required !== "boolean" || !validDuration || !title || !instructions
    || !accessibleAlternative || !reflectionPrompt || !safetyNote) return null;

  return {
    activityId,
    dayNumber: expectedDay,
    date: source.date,
    kind,
    required: source.required,
    durationMinutes: source.durationMinutes as number,
    title,
    instructions,
    accessibleAlternative,
    reflectionPrompt,
    safetyNote,
  };
}

function copyWeek(value: unknown, expectedWeek: number): JourneyWeek | null {
  const source = asRecord(value);
  const theme = copyLocalizedText(source?.theme);
  const outcome = copyLocalizedText(source?.outcome);
  if (!source || source.weekNumber !== expectedWeek || !theme || !outcome
    || !Array.isArray(source.activities) || source.activities.length !== 7) return null;

  const activities: JourneyActivity[] = [];
  for (let index = 0; index < source.activities.length; index += 1) {
    const activity = copyActivity(source.activities[index], (expectedWeek - 1) * 7 + index + 1);
    if (!activity) return null;
    activities.push(activity);
  }
  return { weekNumber: expectedWeek, theme, outcome, activities };
}

function sanitizeConfirmedJourney(value: unknown): JourneyDraft | null {
  const source = asRecord(value);
  if (!source || source.schemaVersion !== "1.0.0" || source.status !== "confirmed"
    || source.timezone !== "Asia/Kolkata" || !isIsoDate(source.startsOn)
    || !Array.isArray(source.languages) || source.languages.length !== 2
    || source.languages[0] !== "en" || source.languages[1] !== "hi"
    || !Array.isArray(source.weeks) || source.weeks.length !== 4) return null;

  const journeyId = nonEmptyString(source.journeyId);
  const title = copyLocalizedText(source.title);
  const summary = copyLocalizedText(source.summary);
  const provenance = asRecord(source.provenance);
  const review = asRecord(source.review);
  if (!journeyId || !title || !summary || !provenance || !review) return null;

  const generator = typeof provenance.generator === "string" && GENERATORS.has(provenance.generator)
    ? provenance.generator as JourneyDraft["provenance"]["generator"]
    : null;
  const fallbackReason = provenance.fallbackReason === null
    ? null
    : typeof provenance.fallbackReason === "string" && FALLBACK_REASONS.has(provenance.fallbackReason)
      ? provenance.fallbackReason as Exclude<JourneyDraft["provenance"]["fallbackReason"], null>
      : undefined;
  const passedChecks = review.passedChecks;
  const passedChecksMatch = Array.isArray(passedChecks)
    && passedChecks.length === PASSED_CHECKS.length
    && PASSED_CHECKS.every((check, index) => passedChecks[index] === check);
  if (!generator || !Number.isInteger(provenance.attempts) || (provenance.attempts as number) < 0
    || typeof provenance.fallbackUsed !== "boolean" || fallbackReason === undefined
    || review.status !== "passed" || review.contractVersion !== "safety-accessibility-v1"
    || !passedChecksMatch) return null;

  const weeks: JourneyWeek[] = [];
  for (let index = 0; index < source.weeks.length; index += 1) {
    const week = copyWeek(source.weeks[index], index + 1);
    if (!week) return null;
    weeks.push(week);
  }

  return {
    schemaVersion: "1.0.0",
    journeyId,
    status: "confirmed",
    startsOn: source.startsOn,
    timezone: "Asia/Kolkata",
    languages: ["en", "hi"],
    title,
    summary,
    provenance: {
      generator,
      attempts: provenance.attempts as number,
      fallbackUsed: provenance.fallbackUsed,
      fallbackReason,
    },
    review: {
      status: "passed",
      contractVersion: "safety-accessibility-v1",
      passedChecks: [...PASSED_CHECKS],
    },
    weeks,
  };
}

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function cacheConfirmedJourney(journey: JourneyDraft): boolean {
  const storage = browserStorage();
  const safeJourney = sanitizeConfirmedJourney(journey);
  if (!storage || !safeJourney) return false;
  try {
    storage.setItem(CONFIRMED_JOURNEY_CACHE_KEY, JSON.stringify({
      version: CACHE_VERSION,
      journey: safeJourney,
    }));
    return true;
  } catch {
    return false;
  }
}

export function readConfirmedJourneyCache(): JourneyDraft | null {
  const storage = browserStorage();
  if (!storage) return null;
  try {
    const stored = storage.getItem(CONFIRMED_JOURNEY_CACHE_KEY);
    if (!stored) return null;
    const envelope = asRecord(JSON.parse(stored));
    if (envelope?.version !== CACHE_VERSION) return null;
    return sanitizeConfirmedJourney(envelope.journey);
  } catch {
    return null;
  }
}
