import type {
  JourneyActivity,
  JourneyActivityKind,
  JourneyDraft,
  JourneyWeek,
  LocalizedInstructions,
  LocalizedText,
  RecommendedPlaylist,
  RecommendedVideo,
  VideoRecommendation,
  WeeklyVideoGuide,
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
const SUPPORTED_TIMELINES = new Set([2, 4, 6, 8]);

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

function isIsoTimestamp(value: unknown): value is string {
  return typeof value === "string" && !Number.isNaN(new Date(value).valueOf());
}

function exactYouTubeUrl(value: string, kind: "video" | "playlist", id: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === "https:"
      && parsed.hostname === "www.youtube.com"
      && parsed.pathname === (kind === "video" ? "/watch" : "/playlist")
      && parsed.searchParams.get(kind === "video" ? "v" : "list") === id;
  } catch {
    return false;
  }
}

function copyRecommendedVideo(value: unknown): RecommendedVideo | null {
  const source = asRecord(value);
  const videoId = nonEmptyString(source?.videoId);
  const title = nonEmptyString(source?.title);
  const url = nonEmptyString(source?.url);
  const defaultLanguage = source?.defaultLanguage === null
    ? null
    : nonEmptyString(source?.defaultLanguage);
  if (!videoId || !/^[A-Za-z0-9_-]{11}$/.test(videoId) || !title || !url
    || !exactYouTubeUrl(url, "video", videoId)
    || !Number.isInteger(source?.position) || (source?.position as number) < 0
    || !Number.isInteger(source?.durationSeconds)
    || (source?.durationSeconds as number) < 1
    || (source?.durationSeconds as number) > 10800
    || (source?.defaultLanguage !== null && !defaultLanguage)
    || typeof source?.captionsAvailable !== "boolean") return null;
  return {
    videoId,
    title,
    url,
    position: source.position as number,
    durationSeconds: source.durationSeconds as number,
    defaultLanguage,
    captionsAvailable: source.captionsAvailable,
  };
}

function copyWeeklyVideoGuide(value: unknown): WeeklyVideoGuide | null {
  const source = asRecord(value);
  if (!source || !Array.isArray(source.videos) || source.videos.length === 0 || source.videos.length > 8) return null;
  const videos = source.videos.map(copyRecommendedVideo);
  const prerequisites = copyInstructions(source.prerequisites);
  const summary = copyLocalizedText(source.summary);
  const keyPoints = copyInstructions(source.keyPoints);
  const whatToExpect = copyLocalizedText(source.whatToExpect);
  const expectedResult = copyLocalizedText(source.expectedResult);
  if (videos.includes(null) || !prerequisites || !summary || !keyPoints || !whatToExpect || !expectedResult) return null;
  return {
    videos: videos as RecommendedVideo[],
    prerequisites,
    summary,
    keyPoints,
    whatToExpect,
    expectedResult,
  };
}

function copyRecommendedPlaylist(value: unknown): RecommendedPlaylist | null {
  const source = asRecord(value);
  const playlistId = nonEmptyString(source?.playlistId);
  const title = nonEmptyString(source?.title);
  const channelTitle = nonEmptyString(source?.channelTitle);
  const url = nonEmptyString(source?.url);
  const selectionNote = copyLocalizedText(source?.selectionNote);
  const sourceNote = copyLocalizedText(source?.sourceNote);
  const defaultLanguage = source?.defaultLanguage === null
    ? null
    : nonEmptyString(source?.defaultLanguage);
  if (!source || source.provider !== "youtube" || !playlistId || !/^[A-Za-z0-9_-]{12,80}$/.test(playlistId)
    || !title || !channelTitle || !url || !exactYouTubeUrl(url, "playlist", playlistId)
    || source.selectionMethod !== "automatic"
    || !["preferred", "fallback", "unknown"].includes(String(source.languageMatch))
    || (source.defaultLanguage !== null && !defaultLanguage)
    || (source.captionsAvailable !== null && typeof source.captionsAvailable !== "boolean")
    || !Number.isInteger(source.selectedVideoCount) || (source.selectedVideoCount as number) < 1
    || !Number.isInteger(source.totalVideoCount) || (source.totalVideoCount as number) < (source.selectedVideoCount as number)
    || !selectionNote || !sourceNote || !isIsoTimestamp(source.fetchedAt)
    || !isIsoTimestamp(source.expiresAt)
    || new Date(source.expiresAt as string) <= new Date(source.fetchedAt as string)) return null;
  return {
    provider: "youtube",
    playlistId,
    title,
    channelTitle,
    url,
    selectionMethod: "automatic",
    languageMatch: source.languageMatch as RecommendedPlaylist["languageMatch"],
    defaultLanguage,
    captionsAvailable: source.captionsAvailable as boolean | null,
    selectedVideoCount: source.selectedVideoCount as number,
    totalVideoCount: source.totalVideoCount as number,
    selectionNote,
    sourceNote,
    fetchedAt: source.fetchedAt as string,
    expiresAt: source.expiresAt as string,
  };
}

function copyVideoRecommendation(value: unknown): VideoRecommendation | null {
  const source = asRecord(value);
  const message = copyLocalizedText(source?.message);
  if (!source || source.provider !== "youtube" || !message
    || !["recommended", "no_match", "unavailable", "not_applicable"].includes(String(source.status))) return null;
  return {
    provider: "youtube",
    status: source.status as VideoRecommendation["status"],
    message,
  };
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
  const videoGuide = source.videoGuide === undefined ? undefined : copyWeeklyVideoGuide(source.videoGuide);
  if (source.videoGuide !== undefined && !videoGuide) return null;
  return {
    weekNumber: expectedWeek,
    theme,
    outcome,
    activities,
    ...(videoGuide ? { videoGuide } : {}),
  };
}

function sanitizeConfirmedJourney(value: unknown): JourneyDraft | null {
  const source = asRecord(value);
  if (!source || !["1.0.0", "1.1.0", "1.2.0"].includes(String(source.schemaVersion)) || source.status !== "confirmed"
    || source.timezone !== "Asia/Kolkata" || !isIsoDate(source.startsOn)
    || !Array.isArray(source.languages) || source.languages.length !== 2
    || source.languages[0] !== "en" || source.languages[1] !== "hi"
    || !Array.isArray(source.weeks) || !SUPPORTED_TIMELINES.has(source.weeks.length)) return null;

  const journeyId = nonEmptyString(source.journeyId);
  const title = copyLocalizedText(source.title);
  const summary = copyLocalizedText(source.summary);
  const provenance = asRecord(source.provenance);
  const review = asRecord(source.review);
  const recommendedPlaylist = source.recommendedPlaylist === undefined
    ? undefined
    : copyRecommendedPlaylist(source.recommendedPlaylist);
  const videoRecommendation = source.videoRecommendation === undefined
    ? undefined
    : copyVideoRecommendation(source.videoRecommendation);
  if (!journeyId || !title || !summary || !provenance || !review) return null;
  if (source.recommendedPlaylist !== undefined && !recommendedPlaylist) return null;
  if (source.videoRecommendation !== undefined && !videoRecommendation) return null;

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
  const recommended = videoRecommendation?.status === "recommended";
  const expectedSchema = videoRecommendation ? "1.2.0" : weeks.length === 4 ? "1.0.0" : "1.1.0";
  if (source.schemaVersion !== expectedSchema
    || recommended !== Boolean(recommendedPlaylist)
    || recommended !== weeks.every((week) => Boolean(week.videoGuide))) return null;
  if (recommendedPlaylist) {
    const videoIds = weeks.flatMap((week) => week.videoGuide?.videos.map((video) => video.videoId) ?? []);
    if (videoIds.length !== recommendedPlaylist.selectedVideoCount
      || new Set(videoIds).size !== videoIds.length) return null;
  }

  return {
    schemaVersion: source.schemaVersion as JourneyDraft["schemaVersion"],
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
    ...(videoRecommendation ? { videoRecommendation } : {}),
    ...(recommendedPlaylist ? { recommendedPlaylist } : {}),
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
    const rawJourney = asRecord(envelope.journey);
    const rawPlaylist = asRecord(rawJourney?.recommendedPlaylist);
    if (rawJourney && isIsoTimestamp(rawPlaylist?.expiresAt)
      && new Date(rawPlaylist.expiresAt as string) <= new Date()) {
      const writtenOnly: Record<string, unknown> = {
        ...rawJourney,
        schemaVersion: Array.isArray(rawJourney.weeks) && rawJourney.weeks.length === 4 ? "1.0.0" : "1.1.0",
        weeks: Array.isArray(rawJourney.weeks)
          ? rawJourney.weeks.map((week) => {
            const copy = { ...(asRecord(week) ?? {}) };
            delete copy.videoGuide;
            return copy;
          })
          : rawJourney.weeks,
      };
      delete writtenOnly.videoRecommendation;
      delete writtenOnly.recommendedPlaylist;
      const safeWrittenPlan = sanitizeConfirmedJourney(writtenOnly);
      if (safeWrittenPlan) cacheConfirmedJourney(safeWrittenPlan);
      return safeWrittenPlan;
    }
    return sanitizeConfirmedJourney(rawJourney);
  } catch {
    return null;
  }
}
