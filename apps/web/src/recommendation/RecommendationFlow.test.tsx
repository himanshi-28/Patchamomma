import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { run } from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { RecommendationFlow } from "./RecommendationFlow";
import type { RecommendationResponse } from "./runtime";


const response: RecommendationResponse = {
  contractVersion: "matching-v1.0.0",
  recommendationType: "mentor",
  source: "deterministic_synthetic",
  synthetic: true,
  status: "matched",
  scoreThreshold: 65,
  resultLimit: 3,
  demoProfiles: [
    { candidateId: "syn_partner_0001", displayName: "Kavita Demo", synthetic: true, hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" } },
    { candidateId: "syn_partner_0004", displayName: "Anita Demo", synthetic: true, hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" } },
    { candidateId: "syn_partner_0005", displayName: "Farah Demo", synthetic: true, hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" } },
    { candidateId: "syn_partner_0006", displayName: "Jyoti Demo", synthetic: true, hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" } },
    { candidateId: "syn_partner_0007", displayName: "Nandini Demo", synthetic: true, hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" } },
    { candidateId: "syn_partner_0008", displayName: "Sunita Demo", synthetic: true, hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" } },
  ],
  results: [{
    candidateId: "syn_mentor_0001",
    candidateType: "mentor",
    displayName: "Leela Mentor Demo",
    synthetic: true,
    score: 100,
    scoreOutOf: 100,
    hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" },
    reasons: [
      { factor: "hobbyGoalFit", reasonCode: "same_hobby_and_goal", points: 30, maxPoints: 30, text: { en: "You share the same hobby and first goal.", hi: "आपका शौक और पहला लक्ष्य समान है।" } },
      { factor: "schedule", reasonCode: "same_practice_rhythm", points: 20, maxPoints: 20, text: { en: "Your practice rhythms match.", hi: "आप दोनों के अभ्यास की गति समान है।" } },
      { factor: "language", reasonCode: "preferred_language_shared", points: 15, maxPoints: 15, text: { en: "You both prefer Hindi for learning.", hi: "आप दोनों सीखने के लिए हिंदी पसंद करती हैं।" } },
    ],
    factorBreakdown: [
      { factor: "hobbyGoalFit", points: 30, maxPoints: 30 },
      { factor: "schedule", points: 20, maxPoints: 20 },
      { factor: "language", points: 15, maxPoints: 15 },
      { factor: "skillLevel", points: 15, maxPoints: 15 },
      { factor: "pace", points: 10, maxPoints: 10 },
      { factor: "format", points: 10, maxPoints: 10 },
      { factor: "price", points: 0, maxPoints: 0 },
    ],
  }],
};


describe("SC-510 recommendation flow", () => {
  it("waits for the explicit action, then focuses one accessible explainable result", async () => {
    const user = userEvent.setup();
    const find = vi.fn().mockResolvedValue(response);
    const rendered = render(
      <RecommendationFlow locale="en" matchingConsent gateway={{ find }} />,
    );

    expect(find).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Find my mentor" }));

    const heading = await screen.findByRole("heading", { name: "Your demo mentor" });
    expect(document.activeElement).toBe(heading);
    expect(find).toHaveBeenCalledTimes(1);
    expect(find).toHaveBeenCalledWith("mentor");
    expect(screen.getByText("Demo match — synthetic profile")).toBeVisible();
    expect(screen.getByText("Match score: 100 out of 100")).toBeVisible();
    expect(within(screen.getByRole("heading", { name: "Why this match fits" }).parentElement!).getAllByRole("listitem")).toHaveLength(3);
    const violations = (await run(rendered.container)).violations
      .filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""));
    expect(violations).toEqual([]);
  });

  it("shows six clearly synthetic same-interest demo profiles without changing ranked results", async () => {
    const user = userEvent.setup();
    const find = vi.fn().mockResolvedValue(response);
    render(<RecommendationFlow locale="en" matchingConsent gateway={{ find }} />);

    await user.click(screen.getByRole("button", { name: /^Find my/ }));

    expect(await screen.findByRole("heading", { name: "6 demo profiles share your interest" })).toBeVisible();
    expect(screen.getByRole("list", { name: "Demo profiles interested in Watercolour painting" }).children).toHaveLength(6);
    expect(screen.getByText("Kavita Demo")).toBeVisible();
    expect(screen.getByText("Sunita Demo")).toBeVisible();
    expect(screen.getByText("These profiles are fictional and are shown only to demonstrate matching.")).toBeVisible();
    expect(response.results).toHaveLength(1);
  });

  it("switches to reviewed Hindi copy without refetching or reranking", async () => {
    const user = userEvent.setup();
    const find = vi.fn().mockResolvedValue(response);
    const rendered = render(<RecommendationFlow locale="en" matchingConsent gateway={{ find }} />);
    await user.click(screen.getByRole("button", { name: "Find my mentor" }));
    await screen.findByText("Leela Mentor Demo");

    rendered.rerender(<RecommendationFlow locale="hi" matchingConsent gateway={{ find }} />);

    expect(screen.getByRole("heading", { name: "आपकी डेमो मेंटर" })).toBeVisible();
    expect(screen.getByText("मैच स्कोर: 100 में से 100")).toBeVisible();
    expect(screen.getByText("आप दोनों सीखने के लिए हिंदी पसंद करती हैं।")).toBeVisible();
    expect(find).toHaveBeenCalledTimes(1);
  });

  it("does not request without consent and clears an in-memory result when consent is revoked", async () => {
    const user = userEvent.setup();
    const find = vi.fn().mockResolvedValue(response);
    const rendered = render(<RecommendationFlow locale="en" matchingConsent={false} gateway={{ find }} />);

    expect(screen.getByRole("button", { name: "Review matching permission" })).toBeVisible();
    expect(find).not.toHaveBeenCalled();
    rendered.rerender(<RecommendationFlow locale="en" matchingConsent gateway={{ find }} />);
    await user.click(screen.getByRole("button", { name: "Find my mentor" }));
    await screen.findByText("Leela Mentor Demo");
    rendered.rerender(<RecommendationFlow locale="en" matchingConsent={false} gateway={{ find }} />);

    expect(screen.queryByText("Leela Mentor Demo")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review matching permission" })).toBeVisible();
    expect(find).toHaveBeenCalledTimes(1);
  });

  it("keeps the confirmed journey context through private empty and retryable error states", async () => {
    const user = userEvent.setup();
    const find = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ...response, status: "no_matches", results: [], emptyReason: "no_eligible_candidate" });
    render(<RecommendationFlow locale="en" matchingConsent gateway={{ find }} />);

    await user.click(screen.getByRole("button", { name: "Find my mentor" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your saved plan is still ready");
    await user.click(screen.getByRole("button", { name: "Try matching again" }));

    expect(await screen.findByText("We couldn't find a compatible demo match yet. Your learning plan is still ready, and you can try again later.")).toBeVisible();
    expect(find).toHaveBeenCalledTimes(2);
  });
});
