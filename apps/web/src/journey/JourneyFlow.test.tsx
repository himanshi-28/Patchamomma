import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { run } from "axe-core";
import { describe, expect, it, vi } from "vitest";
import { JourneyFlow } from "./JourneyFlow";
import { readConfirmedJourneyCache } from "./cache";
import type { JourneyDraft } from "./runtime";

const bilingual = (en: string, hi: string) => ({ en, hi });
const bilingualList = (en: string[], hi: string[]) => ({ en, hi });

function makeDraft(fallbackUsed = false, weekCount = 4): JourneyDraft {
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
    weeks: Array.from({ length: weekCount }, (_, weekIndex) => ({
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

function makeVideoGuidedDraft(): JourneyDraft {
  const draft = makeDraft();
  const videos = [
    {
      videoId: "9Pp3cOAcOyQ",
      title: "Episode 1 · Pranam and Tatkar",
      url: "https://www.youtube.com/watch?v=9Pp3cOAcOyQ&list=PLBAnl0RYZD0f7tY_AlfoD4cllILauhJJX&index=1",
      position: 0,
      durationSeconds: 19 * 60,
      defaultLanguage: "hi",
      captionsAvailable: true,
    },
    {
      videoId: "ZQyoV07o2z8",
      title: "Episode 2 · Tatkar at Thaah and Dugun",
      url: "https://www.youtube.com/watch?v=ZQyoV07o2z8&list=PLBAnl0RYZD0f7tY_AlfoD4cllILauhJJX&index=2",
      position: 1,
      durationSeconds: 29 * 60,
      defaultLanguage: "hi",
      captionsAvailable: true,
    },
  ];
  return {
    ...draft,
    schemaVersion: "1.2.0",
    videoRecommendation: {
      status: "recommended",
      provider: "youtube",
      message: bilingual("A verified course is ready.", "एक सत्यापित पाठ्यक्रम तैयार है।"),
    },
    recommendedPlaylist: {
      provider: "youtube",
      playlistId: "PLBAnl0RYZD0f7tY_AlfoD4cllILauhJJX",
      title: "Learn Kathak with us | Sangeet Pravah World",
      channelTitle: "Sangeet Pravah World",
      url: "https://www.youtube.com/playlist?list=PLBAnl0RYZD0f7tY_AlfoD4cllILauhJJX",
      selectionMethod: "automatic",
      languageMatch: "preferred",
      defaultLanguage: "hi",
      captionsAvailable: true,
      selectedVideoCount: 8,
      totalVideoCount: 25,
      selectionNote: bilingual(
        "Eight sequential beginner lessons selected from this 25-video playlist and divided across your four weeks.",
        "इस 25-वीडियो प्लेलिस्ट से शुरुआती स्तर के आठ क्रमिक पाठ चुनकर आपके चार सप्ताह में बाँटे गए हैं।",
      ),
      sourceNote: bilingual(
        "YouTube controls video availability, captions, ads, and data use. Your written plan still works if a video is unavailable.",
        "वीडियो की उपलब्धता, कैप्शन, विज्ञापन और डेटा उपयोग YouTube नियंत्रित करता है। कोई वीडियो उपलब्ध न हो, तब भी आपकी लिखित योजना काम करेगी।",
      ),
      fetchedAt: "2026-09-09T10:00:00Z",
      expiresAt: "2026-10-08T10:00:00Z",
    },
    weeks: draft.weeks.map((week, index) => ({
      ...week,
      videoGuide: {
        videos: index === 0 ? videos : [{ ...videos[1], videoId: `week-${index + 1}-video`, title: `Week ${index + 1} lesson` }],
        prerequisites: bilingualList(
          ["No prior Kathak experience is needed.", "Keep a clear practice space and a stable support nearby."],
          ["कथक का पहले से अनुभव ज़रूरी नहीं है।", "अभ्यास की जगह खाली रखें और पास में स्थिर सहारा रखें।"],
        ),
        summary: bilingual(
          "Begin with Pranam, Tatkar, and a comfortable introduction to changing pace.",
          "प्रणाम, तत्कार और सहज गति बदलने की शुरुआत करें।",
        ),
        keyPoints: bilingualList(
          ["Watch once before practising.", "Choose clarity and comfort before speed."],
          ["अभ्यास से पहले एक बार देखें।", "गति से पहले स्पष्टता और सुविधा चुनें।"],
        ),
        whatToExpect: bilingual(
          "The coordination may feel unfamiliar. Pause and replay short sections.",
          "तालमेल नया लग सकता है। छोटे हिस्सों को रोककर दोबारा देखें।",
        ),
        expectedResult: bilingual(
          "Repeat the demonstrated beginner sequence slowly at your comfortable pace.",
          "दिखाए गए शुरुआती क्रम को अपनी सहज गति से धीरे-धीरे दोहराएँ।",
        ),
      },
    })),
  } as JourneyDraft;
}

describe("SC-410 journey flow", () => {
  it("shows plan creation before the ready screen and review", async () => {
    const user = userEvent.setup();
    const draft = makeDraft();
    let finishCreation: ((created: JourneyDraft) => void) | undefined;
    const create = vi.fn().mockReturnValue(new Promise<JourneyDraft>((resolve) => {
      finishCreation = resolve;
    }));

    render(<JourneyFlow locale="en" gateway={{ create, confirm: vi.fn() }} />);

    expect(screen.getByText("Creating your reviewed four-week plan and finding a suitable video course…")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Your plan is ready" })).not.toBeInTheDocument();
    finishCreation?.(draft);

    expect(await screen.findByRole("heading", { name: "Your plan is ready" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: draft.title.en })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));
    expect(screen.getByRole("heading", { name: draft.title.en })).toBeVisible();
  });

  it("uses the learner's selected timeline throughout creation and review", async () => {
    const user = userEvent.setup();
    const draft = makeDraft(false, 6);
    const create = vi.fn().mockResolvedValue(draft);

    render(<JourneyFlow locale="en" planWeeks={6} gateway={{ create, confirm: vi.fn() }} />);

    expect(screen.getByText("Creating your reviewed six-week plan and finding a suitable video course…")).toBeVisible();
    expect(await screen.findByText("Your reviewed details were accepted and your six-week plan has been created.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Review my six-week plan" }));
    expect(screen.getByText("Review all six weeks. You can change the date, plan title, time, steps, accessible alternative, and reflection before saving.")).toBeVisible();
  });

  it("generates an unsaved draft and has no serious accessibility violations", async () => {
    const user = userEvent.setup();
    const draft = makeDraft();
    const create = vi.fn().mockResolvedValue(draft);
    const confirm = vi.fn();
    const rendered = render(<JourneyFlow locale="en" gateway={{ create, confirm }} />);

    expect(await screen.findByRole("heading", { name: "Your plan is ready" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));
    expect(screen.getByRole("heading", { name: draft.title.en })).toBeVisible();
    expect(create).toHaveBeenCalledTimes(1);
    expect(confirm).not.toHaveBeenCalled();
    expect(screen.getByText("Not saved yet")).toBeVisible();
    const violations = (await run(rendered.container)).violations
      .filter((violation) => ["serious", "critical"].includes(violation.impact ?? ""));
    expect(violations).toEqual([]);
  });

  it("shows the recommended YouTube playlist and complete weekly video guidance", async () => {
    const user = userEvent.setup();
    const draft = makeVideoGuidedDraft();
    render(<JourneyFlow locale="en" gateway={{ create: vi.fn().mockResolvedValue(draft), confirm: vi.fn() }} />);

    await screen.findByRole("heading", { name: "Your plan is ready" });
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));

    expect(screen.getByRole("heading", { name: "Recommended YouTube playlist" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open complete playlist on YouTube" })).toHaveAttribute(
      "href",
      draft.recommendedPlaylist?.url,
    );
    expect(screen.getByRole("heading", { name: "Video lessons for this week" })).toBeVisible();
    expect(screen.getByRole("link", { name: /Episode 1 · Pranam and Tatkar/ })).toHaveAttribute(
      "href",
      draft.weeks[0].videoGuide?.videos[0].url,
    );
    expect(screen.getByText("Before you watch")).toBeVisible();
    expect(screen.getByText("Learning overview—not a transcript summary")).toBeVisible();
    expect(screen.getByText("Preferred language confirmed")).toBeVisible();
    expect(screen.getByRole("link", { name: "YouTube Terms" })).toHaveAttribute(
      "href",
      "https://www.youtube.com/t/terms",
    );
    expect(screen.getByRole("link", { name: "Google Privacy Policy" })).toHaveAttribute(
      "href",
      "https://policies.google.com/privacy",
    );
    expect(screen.getByText("Key points")).toBeVisible();
    expect(screen.getByText("What to expect")).toBeVisible();
    expect(screen.getByText("Expected result")).toBeVisible();
    expect(screen.getByText("No prior Kathak experience is needed.")).toBeVisible();
    expect(screen.getByText("Repeat the demonstrated beginner sequence slowly at your comfortable pace.")).toBeVisible();
  });

  it("shows video guidance in Hindi without changing the recommended links", async () => {
    const user = userEvent.setup();
    const draft = makeVideoGuidedDraft();
    const create = vi.fn().mockResolvedValue(draft);
    const rendered = render(<JourneyFlow locale="en" gateway={{ create, confirm: vi.fn() }} />);

    await screen.findByRole("heading", { name: "Your plan is ready" });
    rendered.rerender(<JourneyFlow locale="hi" gateway={{ create, confirm: vi.fn() }} />);
    await user.click(screen.getByRole("button", { name: "मेरी चार-सप्ताह की योजना देखें" }));

    expect(screen.getByRole("heading", { name: "सुझाई गई YouTube प्लेलिस्ट" })).toBeVisible();
    expect(screen.getByText("देखने से पहले")).toBeVisible();
    expect(screen.getByText("सीखने का अवलोकन—ट्रांसक्रिप्ट सारांश नहीं")).toBeVisible();
    expect(screen.getByText("मुख्य बातें")).toBeVisible();
    expect(screen.getByText("क्या उम्मीद रखें")).toBeVisible();
    expect(screen.getByText("अपेक्षित परिणाम")).toBeVisible();
    expect(screen.getByRole("link", { name: /Episode 1 · Pranam and Tatkar/ })).toHaveAttribute(
      "href",
      draft.weeks[0].videoGuide?.videos[0].url,
    );
  });

  it("shows the same reviewed draft in Hindi without regenerating", async () => {
    const user = userEvent.setup();
    const draft = makeDraft();
    const create = vi.fn().mockResolvedValue(draft);
    const rendered = render(<JourneyFlow locale="en" gateway={{ create, confirm: vi.fn() }} />);
    await screen.findByRole("heading", { name: "Your plan is ready" });

    rendered.rerender(<JourneyFlow locale="hi" gateway={{ create, confirm: vi.fn() }} />);

    expect(screen.getByRole("heading", { name: "आपकी योजना तैयार है" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "मेरी चार-सप्ताह की योजना देखें" }));
    expect(screen.getByRole("heading", { name: draft.title.hi })).toBeVisible();
    expect(screen.getByText("अभी सेव नहीं हुई")).toBeVisible();
    expect(create).toHaveBeenCalledTimes(1);
  });

  it("sends title, duration, and instruction edits only on explicit confirmation", async () => {
    const user = userEvent.setup();
    const draft = makeDraft();
    const confirm = vi.fn().mockImplementation(async (edited: JourneyDraft) => ({ ...edited, status: "confirmed" as const }));
    render(<JourneyFlow locale="en" gateway={{ create: vi.fn().mockResolvedValue(draft), confirm }} />);
    await screen.findByRole("heading", { name: "Your plan is ready" });
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));

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

  it("reports the confirmed plan to the app shell after saving", async () => {
    const user = userEvent.setup();
    const draft = makeDraft();
    const saved = { ...draft, status: "confirmed" as const };
    const onConfirmed = vi.fn();

    render(
      <JourneyFlow
        locale="en"
        gateway={{
          create: vi.fn().mockResolvedValue(draft),
          confirm: vi.fn().mockResolvedValue(saved),
        }}
        onConfirmed={onConfirmed}
      />,
    );

    await screen.findByRole("heading", { name: "Your plan is ready" });
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));
    await user.click(screen.getByRole("button", { name: "Confirm and save my plan" }));

    expect(onConfirmed).toHaveBeenCalledWith(saved);
  });

  it("rejects by clearing the draft from memory without persisting", async () => {
    const user = userEvent.setup();
    const confirm = vi.fn();
    render(<JourneyFlow locale="en" gateway={{ create: vi.fn().mockResolvedValue(makeDraft()), confirm }} />);
    await screen.findByRole("heading", { name: "Your plan is ready" });
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));
    expect(screen.getByText("Not saved yet")).toBeVisible();

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

    await screen.findByRole("heading", { name: "Your plan is ready" });
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "We couldn't create a personalised plan just now. Here is a reviewed four-week plan you can use or edit.",
    );
    await user.click(screen.getByRole("button", { name: "Try personalised plan again" }));

    expect(await screen.findByRole("heading", { name: "Your plan is ready" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Review my four-week plan" }));
    expect(screen.getByRole("heading", { name: personalised.title.en })).toBeVisible();
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

  it("keeps the written plan and refreshes an unavailable video recommendation", async () => {
    const user = userEvent.setup();
    const unavailable: JourneyDraft = {
      ...makeDraft(),
      schemaVersion: "1.2.0",
      status: "confirmed",
      videoRecommendation: {
        status: "no_match",
        provider: "youtube",
        message: bilingual(
          "No suitable video course was found. Your complete written plan is ready.",
          "उपयुक्त वीडियो पाठ्यक्रम नहीं मिला। आपकी लिखित योजना तैयार है।",
        ),
      },
    };
    const refreshed = { ...makeVideoGuidedDraft(), status: "confirmed" as const };
    const refreshVideos = vi.fn().mockResolvedValue(refreshed);

    render(
      <JourneyFlow
        locale="en"
        gateway={{ create: vi.fn(), confirm: vi.fn(), refreshVideos }}
        initialJourney={unavailable}
      />,
    );

    expect(screen.getByText(unavailable.videoRecommendation!.message.en)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Find videos again" }));
    expect(refreshVideos).toHaveBeenCalledWith(unavailable.journeyId);
    expect(await screen.findByRole("heading", { name: "Recommended YouTube playlist" })).toBeVisible();
  });
});
