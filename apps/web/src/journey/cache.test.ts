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

  it("stores reviewed video guidance offline and rejects non-YouTube links", () => {
    const journey = makeConfirmedJourney();
    const videos = journey.weeks.map((_, index) => ({
      videoId: `${String(index + 1).padStart(11, "0")}`,
      title: `Kathak lesson ${index + 1}`,
      url: `https://www.youtube.com/watch?v=${String(index + 1).padStart(11, "0")}`,
      position: index,
      durationSeconds: 20 * 60,
      defaultLanguage: "hi",
      captionsAvailable: true,
    }));
    const videoJourney: JourneyDraft = {
      ...journey,
      schemaVersion: "1.2.0",
      videoRecommendation: {
        status: "recommended",
        provider: "youtube",
        message: bilingual("A verified course is ready.", "एक सत्यापित पाठ्यक्रम तैयार है।"),
      },
      recommendedPlaylist: {
        provider: "youtube",
        playlistId: "PLBAnl0RYZD0f7tY_AlfoD4cllILauhJJX",
        title: "Learn Kathak with us",
        channelTitle: "Sangeet Pravah World",
        url: "https://www.youtube.com/playlist?list=PLBAnl0RYZD0f7tY_AlfoD4cllILauhJJX",
        selectionMethod: "automatic",
        languageMatch: "preferred",
        defaultLanguage: "hi",
        captionsAvailable: true,
        selectedVideoCount: 4,
        totalVideoCount: 25,
        selectionNote: bilingual("Four selected lessons.", "चार चुने हुए पाठ।"),
        sourceNote: bilingual("YouTube controls availability.", "उपलब्धता YouTube नियंत्रित करता है।"),
        fetchedAt: "2099-09-09T10:00:00Z",
        expiresAt: "2099-10-08T10:00:00Z",
      },
      weeks: journey.weeks.map((week, index) => ({
        ...week,
        videoGuide: {
          videos: [videos[index]],
          prerequisites: { en: ["Clear some space."], hi: ["कुछ जगह खाली रखें।"] },
          summary: bilingual("Practise one lesson.", "एक पाठ का अभ्यास करें।"),
          keyPoints: { en: ["Move comfortably."], hi: ["सहजता से करें।"] },
          whatToExpect: bilingual("Coordination may feel new.", "तालमेल नया लग सकता है।"),
          expectedResult: bilingual("Repeat one short sequence.", "एक छोटा क्रम दोहराएँ।"),
        },
      })),
    };

    expect(cacheConfirmedJourney(videoJourney)).toBe(true);
    expect(readConfirmedJourneyCache()).toEqual(videoJourney);
    expect(cacheConfirmedJourney({
      ...videoJourney,
      recommendedPlaylist: { ...videoJourney.recommendedPlaylist!, url: "https://example.com/playlist" },
    })).toBe(false);
  });

  it("expires YouTube metadata on access while retaining the written offline plan", () => {
    const journey = makeConfirmedJourney();
    const videoId = "00000000001";
    const expired: JourneyDraft = {
      ...journey,
      schemaVersion: "1.2.0",
      videoRecommendation: {
        status: "recommended",
        provider: "youtube",
        message: bilingual("A verified course is ready.", "एक सत्यापित पाठ्यक्रम तैयार है।"),
      },
      recommendedPlaylist: {
        provider: "youtube",
        playlistId: "PLexpiredCourse123",
        title: "Expired course",
        channelTitle: "Teacher",
        url: "https://www.youtube.com/playlist?list=PLexpiredCourse123",
        selectionMethod: "automatic",
        languageMatch: "preferred",
        defaultLanguage: "en",
        captionsAvailable: true,
        selectedVideoCount: 4,
        totalVideoCount: 4,
        selectionNote: bilingual("Four lessons.", "चार पाठ।"),
        sourceNote: bilingual("YouTube metadata.", "YouTube मेटाडेटा।"),
        fetchedAt: "2020-01-01T00:00:00Z",
        expiresAt: "2020-01-30T00:00:00Z",
      },
      weeks: journey.weeks.map((week, position) => ({
        ...week,
        videoGuide: {
          videos: [{
            videoId: `${videoId.slice(0, -1)}${position + 1}`,
            title: `Lesson ${position + 1}`,
            url: `https://www.youtube.com/watch?v=${videoId.slice(0, -1)}${position + 1}`,
            position,
            durationSeconds: 600,
            defaultLanguage: "en",
            captionsAvailable: true,
          }],
          prerequisites: { en: ["Prepare."], hi: ["तैयार रहें।"] },
          summary: bilingual("Learn.", "सीखें।"),
          keyPoints: { en: ["Notice."], hi: ["ध्यान दें।"] },
          whatToExpect: bilingual("A first step.", "पहला कदम।"),
          expectedResult: bilingual("Show it.", "करके दिखाएँ।"),
        },
      })),
    };

    expect(cacheConfirmedJourney(expired)).toBe(true);
    const restored = readConfirmedJourneyCache();
    expect(restored?.schemaVersion).toBe("1.0.0");
    expect(restored?.videoRecommendation).toBeUndefined();
    expect(restored?.recommendedPlaylist).toBeUndefined();
    expect(restored?.weeks).toHaveLength(4);
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
