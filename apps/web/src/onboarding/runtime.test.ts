import { describe, expect, it, vi } from "vitest";
import {
  createProfileExtractionApiGateway,
  createTranscriptAdapterForMode,
  createDeterministicTranscriptAdapter,
  createProfileApiGateway,
  extractLearningWish,
  ProfileSaveError,
} from "./runtime";

describe("SC-310 onboarding runtime", () => {
  it("returns a visible deterministic transcript without exposing raw audio", async () => {
    const adapter = createDeterministicTranscriptAdapter();

    const result = await adapter.capture("en");

    expect(result.transcript).toContain("restart watercolours");
    expect(result.providerName).toBe("SakhiCircle deterministic local voice");
    expect(result).not.toHaveProperty("audio");
    expect(result).not.toHaveProperty("rawAudio");
  });

  it("uses synthetic voice only for deterministic mode", () => {
    expect(createTranscriptAdapterForMode("deterministic").providerName).toBe(
      "SakhiCircle deterministic local voice",
    );
    expect(createTranscriptAdapterForMode("production").providerName).toBe(
      "Browser speech recognition",
    );
    expect(createTranscriptAdapterForMode("firebase_emulator").providerName).toBe(
      "Browser speech recognition",
    );
  });

  it("extracts structured fields but never infers either consent", () => {
    const wish = extractLearningWish(
      "I want to restart watercolours and make a greeting card. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, and a small online group in Pune.",
      "en",
    );

    expect(wish.hobby).toBe("Watercolour painting");
    expect(wish.goal).toBe("Paint a greeting card");
    expect(wish.availability).toBe("30 minutes · 4 days a week");
    expect(wish.planConsent).toBe(false);
    expect(wish.matchingConsent).toBe(false);
  });

  it("recognizes a plain request to learn painting without inventing optional details", () => {
    const wish = extractLearningWish("I want to learn paint", "en");

    expect(wish.hobby).toBe("Painting");
    expect(wish.experience).toBe("");
    expect(wish.goal).toBe("");
  });

  it("extracts any clearly stated learning topic, goal, and supported time choice", () => {
    const kathak = extractLearningWish("I want to learn Kathak.", "en");
    const pottery = extractLearningWish(
      "I want to learn pottery so I can make diyas. I have 15 minutes, three days a week.",
      "en",
    );

    expect(kathak.hobby).toBe("Kathak");
    expect(pottery.hobby).toBe("Pottery");
    expect(pottery.goal).toBe("Make diyas");
    expect(pottery.availability).toBe("15 minutes · 3 days a week");
  });

  it("requests private AI suggestions without storing or adding consent", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      source: "gemini",
      fields: {
        hobby: "Kathak",
        experience: "New to this",
        goal: "Perform a short piece",
        availability: "30 minutes · 4 days a week",
        language: "English and Hindi",
        accessibility: "No support needed right now",
        format: "At home · individual",
        city: "",
      },
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const gateway = createProfileExtractionApiGateway({
      apiBaseUrl: "https://api.example.test",
      requestHeaders: async () => ({ Authorization: "Bearer token" }),
      fetcher,
    });

    const result = await gateway.extract(
      "I want to learn Kathak and perform a short piece.",
      "en",
    );

    expect(result.source).toBe("gemini");
    expect(result.fields.hobby).toBe("Kathak");
    expect(result.fields.planConsent).toBe(false);
    expect(result.fields.matchingConsent).toBe(false);
    expect(fetcher).toHaveBeenCalledWith(
      "https://api.example.test/api/v1/profile/extractions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          transcript: "I want to learn Kathak and perform a short piece.",
          locale: "en",
        }),
      }),
    );
  });

  it("reports a maintenance response distinctly from a connection failure", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: "maintenance_mode", message: "Temporarily paused." },
    }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    }));
    const gateway = createProfileApiGateway({
      apiBaseUrl: "https://api.example.test",
      requestHeaders: async () => ({ Authorization: "Bearer token" }),
      fetcher,
    });

    await expect(gateway.save({
      ...extractLearningWish("I want to learn paint", "en"),
      availability: "30 minutes · 4 days a week",
      language: "English",
      accessibility: "No support needed right now",
      format: "At home · individual",
      planConsent: true,
    })).rejects.toEqual(expect.objectContaining<Partial<ProfileSaveError>>({ reason: "maintenance" }));
  });

  it("sends only reviewed structured fields to the authenticated profile boundary", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "saved" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    const gateway = createProfileApiGateway({
      apiBaseUrl: "http://localhost:8080",
      requestHeaders: async () => ({ Authorization: "Bearer demo-learner-token" }),
      fetcher,
    });
    const profile = {
      ...extractLearningWish("watercolour greeting card 30 minutes Hindi Pune", "en"),
      experience: "Restarting after many years" as const,
      accessibility: "Larger text · seated alternatives" as const,
      format: "At home · small online group" as const,
      planConsent: true,
    };

    await gateway.save(profile);

    const body = JSON.parse(String(fetcher.mock.calls[0][1]?.body));
    expect(body).toEqual(profile);
    expect(body).not.toHaveProperty("transcript");
    expect(body).not.toHaveProperty("audio");
  });
});
