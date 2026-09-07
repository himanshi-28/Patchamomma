import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { run } from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { JourneyFlow } from "./JourneyFlow";
import { readConfirmedJourneyCache } from "./cache";
import type { JourneyDraft } from "./runtime";

const bilingual = (en: string, hi: string) => ({ en, hi });

function makeDraft(fallbackUsed = false): JourneyDraft {
  const startsOn = new Date("2026-08-26T00:00:00Z");
  return {
    schemaVersion: "1.0.0",
    journeyId: "journey_test_fixture",
    status: "draft",
    startsOn: "2026-08-26",
    timezone: "Asia/Kolkata",
    languages: ["en", "hi"],
    title: bilingual("Four weeks to restart watercolour painting", "वॉटरकलर पेंटिंग फिर शुरू करने के चार सप्ताह"),
    summary: bilingual("A steady plan for making one greeting card.", "एक शुभकामना कार्ड बनाने की सहज योजना।"),
    provenance: {
      generator: fallbackUsed ? "curated_fallback" : "deterministic_fixture",
      attempts: 0,
      fallbackUsed,
      fallbackReason: fallbackUsed ? "workflow_unavailable" : null,
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
        const activityDate = new Date(startsOn);
        activityDate.setUTCDate(startsOn.getUTCDate() + dayNumber - 1);
        const required = dayIndex < 4;
        return {
          activityId: `day-${String(dayNumber).padStart(2, "0")}`,
          dayNumber,
          date: activityDate.toISOString().slice(0, 10),
          kind: required ? "practice" as const : "rest" as const,
          required,
          durationMinutes: required ? 30 : 0,
          title: bilingual(`Colour practice ${dayNumber}`, `रंग अभ्यास ${dayNumber}`),
          instructions: {
            en: ["Set out paper, water, and three colours."],
            hi: ["कागज़, पानी और तीन रंग तैयार रखें।"],
          },
          accessibleAlternative: bilingual("Work seated at a table.", "मेज़ पर बैठकर काम करें।"),
          reflectionPrompt: bilingual("What felt comfortable today?", "आज क्या सहज लगा?"),
          safetyNote: bilingual("Use non-toxic colours and pause if uncomfortable.", "गैर-विषैले रंग इस्तेमाल करें और असहजता होने पर रुकें।"),
        };
      }),
    })),
  };
}

describe("SC-410 journey flow", () => {
  it("generates an unsaved draft and has no serious accessibility violations", async () => {
    const draft = makeDraft();
    const create = vi.fn().mockResolvedValue(draft);
    const confirm = vi.fn();
    const rendered = render(<JourneyFlow locale="en" gateway={{ create, confirm }} />);

    expect(await screen.findByRole("heading", { name: draft.title.en })).toBeVisible();
    expect(create).toHaveBeenCalledTimes(1);
    expect(confirm).not.toHaveBeenCalled();
    expect(screen.getByText("Not saved yet")).toBeVisible();
    const violations = (await run(rendered.container)).violations
      .filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""));
    expect(violations).toEqual([]);
  });

  it("shows the same reviewed draft in Hindi without regenerating", async () => {
    const draft = makeDraft();
    const create = vi.fn().mockResolvedValue(draft);
    const rendered = render(<JourneyFlow locale="en" gateway={{ create, confirm: vi.fn() }} />);
    await screen.findByRole("heading", { name: draft.title.en });

    rendered.rerender(<JourneyFlow locale="hi" gateway={{ create, confirm: vi.fn() }} />);

    expect(screen.getByRole("heading", { name: draft.title.hi })).toBeVisible();
    expect(screen.getByText("अभी सेव नहीं हुई")).toBeVisible();
    expect(create).toHaveBeenCalledTimes(1);
  });

  it("sends title, duration, and instruction edits only on explicit confirmation", async () => {
    const user = userEvent.setup();
    const draft = makeDraft();
    const confirm = vi.fn().mockImplementation(async (edited: JourneyDraft) => ({ ...edited, status: "confirmed" as const }));
    render(<JourneyFlow locale="en" gateway={{ create: vi.fn().mockResolvedValue(draft), confirm }} />);
    await screen.findByRole("heading", { name: draft.title.en });

    await user.click(screen.getByRole("button", { name: "Edit plan title" }));
    await user.clear(screen.getByLabelText("Plan title"));
    await user.type(screen.getByLabelText("Plan title"), "My watercolour month");
    await user.click(screen.getByRole("button", { name: "Save plan title" }));
    await user.click(screen.getByRole("button", { name: "Edit day 1" }));
    await user.clear(screen.getByLabelText("Day 1 duration in minutes"));
    await user.type(screen.getByLabelText("Day 1 duration in minutes"), "20");
    await user.clear(screen.getByLabelText("Day 1 instruction 1"));
    await user.type(screen.getByLabelText("Day 1 instruction 1"), "Paint one calm colour wash.");
    await user.click(screen.getByRole("button", { name: "Save day 1" }));

    expect(confirm).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Confirm and save my plan" }));

    expect(confirm).toHaveBeenCalledTimes(1);
    expect(confirm.mock.calls[0][0].title.en).toBe("My watercolour month");
    expect(confirm.mock.calls[0][0].weeks[0].activities[0].durationMinutes).toBe(20);
    expect(confirm.mock.calls[0][0].weeks[0].activities[0].instructions.en[0]).toBe("Paint one calm colour wash.");
    expect(await screen.findByRole("heading", { name: "Your four-week plan is saved" })).toBeVisible();
    expect(readConfirmedJourneyCache()?.title.en).toBe("My watercolour month");
  });

  it("rejects by clearing the draft from memory without persisting", async () => {
    const user = userEvent.setup();
    const confirm = vi.fn();
    render(<JourneyFlow locale="en" gateway={{ create: vi.fn().mockResolvedValue(makeDraft()), confirm }} />);
    await screen.findByText("Not saved yet");

    await user.click(screen.getByRole("button", { name: "Reject this draft" }));

    expect(confirm).not.toHaveBeenCalled();
    expect(screen.queryByText("Colour practice 1")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create another plan" })).toBeVisible();
  });

  it("offers an in-place retry from a validated curated fallback", async () => {
    const user = userEvent.setup();
    const personalised = {
      ...makeDraft(),
      title: bilingual("Your personalised pottery plan", "आपकी व्यक्तिगत पॉटरी योजना"),
    };
    const create = vi.fn()
      .mockResolvedValueOnce(makeDraft(true))
      .mockResolvedValueOnce(personalised);
    render(<JourneyFlow locale="en" gateway={{ create, confirm: vi.fn() }} />);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "We couldn't create a personalised plan just now. Here is a reviewed four-week plan you can use or edit.",
    );
    await user.click(screen.getByRole("button", { name: "Try personalised plan again" }));

    expect(await screen.findByRole("heading", { name: personalised.title.en })).toBeVisible();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(create).toHaveBeenCalledTimes(2);
  });

  it("restores a confirmed journey read-only without regenerating it", async () => {
    const user = userEvent.setup();
    const confirmed = { ...makeDraft(), status: "confirmed" as const };
    const create = vi.fn();

    render(
      <JourneyFlow
        locale="en"
        gateway={{ create, confirm: vi.fn() }}
        initialJourney={confirmed}
      />,
    );

    expect(screen.getByRole("heading", { name: "Your four-week plan is saved" })).toBeVisible();
    expect(screen.getByText("Available offline on this device")).toBeVisible();
    expect(create).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "View saved plan" }));
    expect(screen.getByRole("heading", { name: "Colour practice 1" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Edit day 1" })).not.toBeInTheDocument();
  });
});
