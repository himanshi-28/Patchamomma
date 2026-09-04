import { describe, expect, it, vi } from "vitest";
import {
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
