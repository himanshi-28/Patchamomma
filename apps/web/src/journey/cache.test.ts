import { afterEach, describe, expect, it } from "vitest";
import {
  CONFIRMED_JOURNEY_CACHE_KEY,
  cacheConfirmedJourney,
  readConfirmedJourneyCache,
} from "./cache";
import type { JourneyDraft } from "./runtime";

const bilingual = (en: string, hi: string) => ({ en, hi });

function makeConfirmedJourney(): JourneyDraft {
  return {
    schemaVersion: "1.0.0",
    journeyId: "journey_cache_fixture",
    status: "confirmed",
    startsOn: "2026-08-26",
    timezone: "Asia/Kolkata",
    languages: ["en", "hi"],
    title: bilingual("My watercolour month", "मेरा वॉटरकलर महीना"),
    summary: bilingual("A steady four-week plan.", "चार सप्ताह की सहज योजना।"),
    provenance: {
      generator: "deterministic_fixture",
      attempts: 0,
      fallbackUsed: false,
      fallbackReason: null,
    },
    review: {
      status: "passed",
      contractVersion: "safety-accessibility-v1",
      passedChecks: ["schema", "schedule", "accessibility", "safety", "localization"],
    },
    weeks: Array.from({ length: 4 }, (_, weekIndex) => ({
      weekNumber: weekIndex + 1,
      theme: bilingual(`Week ${weekIndex + 1}`, `सप्ताह ${weekIndex + 1}`),
      outcome: bilingual("Build confidence steadily.", "धीरे-धीरे आत्मविश्वास बढ़ाएँ।"),
      activities: Array.from({ length: 7 }, (_, dayIndex) => {
        const dayNumber = weekIndex * 7 + dayIndex + 1;
        return {
          activityId: `day-${dayNumber}`,
          dayNumber,
          date: `2026-09-${String(dayNumber).padStart(2, "0")}`,
          kind: dayIndex < 4 ? "practice" as const : "rest" as const,
          required: dayIndex < 4,
          durationMinutes: dayIndex < 4 ? 30 : 0,
          title: bilingual(`Colour practice ${dayNumber}`, `रंग अभ्यास ${dayNumber}`),
          instructions: { en: ["Prepare the paper."], hi: ["कागज़ तैयार रखें।"] },
          accessibleAlternative: bilingual("Work seated.", "बैठकर काम करें।"),
          reflectionPrompt: bilingual("What felt good?", "क्या अच्छा लगा?"),
          safetyNote: bilingual("Pause if uncomfortable.", "असहज होने पर रुकें।"),
        };
      }),
    })),
  };
}

afterEach(() => window.localStorage.clear());

describe("confirmed journey offline cache", () => {
  it("stores and restores only the confirmed reviewed journey", () => {
    const journey = makeConfirmedJourney();

    expect(cacheConfirmedJourney(journey)).toBe(true);
    expect(readConfirmedJourneyCache()).toEqual(journey);
  });

  it("stores variable-length journeys only under the extended schema", () => {
    const fourWeekJourney = makeConfirmedJourney();
    const sixWeekJourney = {
      ...fourWeekJourney,
      schemaVersion: "1.1.0" as const,
      weeks: [
        ...fourWeekJourney.weeks,
        ...fourWeekJourney.weeks.slice(0, 2).map((week, index) => ({
          ...week,
          weekNumber: index + 5,
          activities: week.activities.map((activity, dayIndex) => ({
            ...activity,
            activityId: `day-${index * 7 + dayIndex + 29}`,
            dayNumber: index * 7 + dayIndex + 29,
          })),
        })),
      ],
    } satisfies JourneyDraft;

    expect(cacheConfirmedJourney(sixWeekJourney)).toBe(true);
    expect(readConfirmedJourneyCache()?.schemaVersion).toBe("1.1.0");
    expect(cacheConfirmedJourney({ ...sixWeekJourney, schemaVersion: "1.0.0" })).toBe(false);
  });

  it("rejects drafts and strips fields outside the journey contract", () => {
    const draft = { ...makeConfirmedJourney(), status: "draft" as const };
    expect(cacheConfirmedJourney(draft)).toBe(false);

    const journeyWithPrivateInput = {
      ...makeConfirmedJourney(),
      transcript: "I want to learn painting",
      rawAudio: "must-never-be-stored",
    } as JourneyDraft;
    expect(cacheConfirmedJourney(journeyWithPrivateInput)).toBe(true);

    const stored = window.localStorage.getItem(CONFIRMED_JOURNEY_CACHE_KEY) ?? "";
    expect(stored).not.toContain("transcript");
    expect(stored).not.toContain("rawAudio");
  });

  it("fails closed when cached data is corrupted or incomplete", () => {
    window.localStorage.setItem(CONFIRMED_JOURNEY_CACHE_KEY, "not-json");
    expect(readConfirmedJourneyCache()).toBeNull();

    window.localStorage.setItem(CONFIRMED_JOURNEY_CACHE_KEY, JSON.stringify({
      version: "journey-cache-v1",
      journey: { status: "confirmed", weeks: [] },
    }));
    expect(readConfirmedJourneyCache()).toBeNull();
  });
});
