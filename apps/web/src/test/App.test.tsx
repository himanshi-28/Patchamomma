import axe from "axe-core";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import { App } from "../App";
import { createDeterministicAuthGateway } from "../auth/runtime";
import type { AuthGateway } from "../auth/runtime";
import { cacheConfirmedJourney } from "../journey/cache";
import type { JourneyDraft } from "../journey/runtime";
import styles from "../styles.css?raw";
import documentSource from "../../index.html?raw";
import viteConfigSource from "../../vite.config.ts?raw";

const seriousViolations = async (container: HTMLElement) => {
  const result = await axe.run(container);
  return result.violations.filter(
    (violation) => violation.impact === "critical" || violation.impact === "serious",
  );
};

afterEach(() => window.localStorage.clear());

const bilingual = (en: string, hi: string) => ({ en, hi });

function makeCachedJourney(): JourneyDraft {
  return {
    schemaVersion: "1.0.0",
    journeyId: "journey_app_cache",
    status: "confirmed",
    startsOn: "2026-08-26",
    timezone: "Asia/Kolkata",
    languages: ["en", "hi"],
    title: bilingual("My saved painting plan", "मेरी सेव की हुई पेंटिंग योजना"),
    summary: bilingual("A steady four-week plan.", "चार सप्ताह की सहज योजना।"),
    provenance: { generator: "deterministic_fixture", attempts: 0, fallbackUsed: false, fallbackReason: null },
    review: {
      status: "passed",
      contractVersion: "safety-accessibility-v1",
      passedChecks: ["schema", "schedule", "accessibility", "safety", "localization"],
    },
    weeks: Array.from({ length: 4 }, (_, weekIndex) => ({
      weekNumber: weekIndex + 1,
      theme: bilingual(`Week ${weekIndex + 1}`, `सप्ताह ${weekIndex + 1}`),
      outcome: bilingual("Build confidence.", "आत्मविश्वास बढ़ाएँ।"),
      activities: Array.from({ length: 7 }, (_, dayIndex) => {
        const dayNumber = weekIndex * 7 + dayIndex + 1;
        return {
          activityId: `app-day-${dayNumber}`,
          dayNumber,
          date: `2026-09-${String(dayNumber).padStart(2, "0")}`,
          kind: dayIndex < 4 ? "practice" as const : "rest" as const,
          required: dayIndex < 4,
          durationMinutes: dayIndex < 4 ? 30 : 0,
          title: bilingual(`Saved activity ${dayNumber}`, `सेव गतिविधि ${dayNumber}`),
          instructions: { en: ["Prepare the paper."], hi: ["कागज़ तैयार रखें।"] },
          accessibleAlternative: bilingual("Work seated.", "बैठकर काम करें।"),
          reflectionPrompt: bilingual("What felt good?", "क्या अच्छा लगा?"),
          safetyNote: bilingual("Pause if uncomfortable.", "असहज होने पर रुकें।"),
        };
      }),
    })),
  };
}

describe("SakhiCircle app shell", () => {
  it("offers a welcoming guide with plain-language passwordless and Google sign-in", async () => {
    const user = userEvent.setup();
    render(<App demoMode={false} />);

    expect(screen.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();
    expect(screen.getByText("A friendly place to learn, teach, and belong.")).toBeVisible();
    expect(screen.getByText("Sign in securely. No password needed.")).toBeVisible();
    expect(screen.getByRole("img", { name: "Sakhi, your SakhiCircle guide" })).toBeVisible();
    const guide = screen.getByRole("button", { name: "Hi, how may I help you?" });
    expect(guide).toBeVisible();
    expect(screen.queryByText("She made space for everyone else. This space is hers.")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Email address")).toBeVisible();
    expect(screen.getByRole("button", { name: "Send sign-in link" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeVisible();
    expect(screen.getByText(/No popup permission is required/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Continue as Meera" })).not.toBeInTheDocument();

    await user.click(guide);
    expect(screen.getByRole("region", { name: "Sakhi help" })).toBeVisible();
    expect(screen.getByText("What would you like help with?")).toBeVisible();
    expect(screen.getByRole("button", { name: "Signing in" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Finding a hobby" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Using voice" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Reviewing my details" }));
    expect(screen.getByRole("status")).toHaveTextContent("Nothing is saved until you confirm it.");
  });

  it("shows synthetic access only in demo mode", () => {
    render(<App demoMode />);
    expect(screen.getByRole("button", { name: "Continue as Meera" })).toBeVisible();
  });

  it("reports email-link acceptance without claiming inbox delivery", async () => {
    const user = userEvent.setup();
    const authGateway: AuthGateway = {
      observeSession(listener) {
        listener(null);
        return () => undefined;
      },
      sendEmailLink: vi.fn().mockResolvedValue(undefined),
      signInWithGoogle: vi.fn(),
      signInDemo: vi.fn(),
      signOut: vi.fn(),
      getIdToken: vi.fn(),
      getAppCheckToken: vi.fn(),
    };
    render(<App authGateway={authGateway} />);

    await user.type(screen.getByLabelText("Email address"), "rangnanihimanshi@gmail.com");
    await user.click(screen.getByRole("button", { name: "Send sign-in link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Firebase accepted the request for rangnanihimanshi@gmail.com",
    );
    expect(screen.getByRole("status")).toHaveTextContent("Spam or Promotions");
    expect(screen.getByRole("status")).toHaveTextContent("5 minutes");
  });

  it("signs out of the deterministic session and returns to sign-in", async () => {
    const user = userEvent.setup();
    const authGateway = createDeterministicAuthGateway({ demoMode: true });
    render(<App demoMode authGateway={authGateway} />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));
    await user.click(screen.getByRole("button", { name: "Meera Sharma profile" }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    expect(screen.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();
    expect(screen.queryByRole("navigation", { name: "Primary navigation" })).not.toBeInTheDocument();
  });

  it("switches the complete login experience between Hindi and English", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "हिंदी में देखें" }));

    expect(screen.getByRole("heading", { name: "SakhiCircle में आपका स्वागत है" })).toBeVisible();
    expect(screen.getByText("सीखने, सिखाने और अपनापन पाने की एक दोस्ताना जगह।")).toBeVisible();
    expect(screen.getByLabelText("ईमेल पता")).toBeVisible();
    expect(screen.getByRole("button", { name: "साइन-इन लिंक भेजें" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Google से जारी रखें" })).toBeVisible();
    expect(screen.getByRole("button", { name: "मीरा के रूप में जारी रखें" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "View in English" }));

    expect(screen.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();
    expect(screen.getByLabelText("Email address")).toBeVisible();
    expect(screen.getByRole("button", { name: "Continue as Meera" })).toBeVisible();
  });

  it("renders exactly three labelled primary destinations after demo sign-in", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));
    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    const links = Array.from(navigation.querySelectorAll("a"));

    expect(links).toHaveLength(3);
    expect(screen.getByRole("link", { name: "Today" })).toBeVisible();
    expect(screen.getByRole("link", { name: "My Circle" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Mentors" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Need help?" })).toBeVisible();
    expect(screen.getByText("Hi, Meera")).toBeVisible();
    expect(screen.queryByText("Namaste, Meera")).not.toBeInTheDocument();
  });

  it("uses the signed-in account name throughout the authenticated shell", () => {
    const authGateway: AuthGateway = {
      observeSession(listener) {
        listener({ uid: "himanshi", displayName: "Himanshi Rangnani", synthetic: false });
        return () => undefined;
      },
      sendEmailLink: vi.fn(),
      signInWithGoogle: vi.fn(),
      signInDemo: vi.fn(),
      signOut: vi.fn(),
      getIdToken: vi.fn().mockResolvedValue("token"),
      getAppCheckToken: vi.fn().mockResolvedValue("app-check"),
    };

    render(<App authGateway={authGateway} />);

    expect(screen.getByText("Hi, Himanshi")).toBeVisible();
    expect(screen.queryByText("Hi, Meera")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Himanshi Rangnani profile" })).toBeVisible();
  });

  it("uses reviewed Hindi labels for the same three destinations", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));
    await user.click(screen.getByRole("button", { name: "हिंदी में देखें" }));

    const navigation = screen.getByRole("navigation", { name: "मुख्य नेविगेशन" });
    expect(navigation.querySelectorAll("a")).toHaveLength(3);
    expect(screen.getByRole("link", { name: "आज" })).toBeVisible();
    expect(screen.getByRole("link", { name: "मेरा सर्कल" })).toBeVisible();
    expect(screen.getByRole("link", { name: "मेंटर्स" })).toBeVisible();
    expect(screen.getByRole("tablist", { name: "आज के दृश्य" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "आज" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "मेरी योजना" })).toBeVisible();
  });

  it("announces a language change and focuses the translated active screen without losing learner words", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));
    await user.click(screen.getByRole("button", { name: "Choose my first hobby" }));
    await user.type(screen.getByLabelText("Your learning wish"), "My own painting words");
    await user.click(screen.getByRole("button", { name: "हिंदी में देखें" }));

    const heading = screen.getByRole("heading", { name: "अपनी सीखने की इच्छा बताएँ" });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(screen.getByLabelText("आपकी सीखने की इच्छा")).toHaveValue("My own painting words");
    const announcement = screen.getByText("भाषा हिंदी हुई। आपका ड्राफ़्ट नहीं बदला।");
    expect(announcement).toHaveAttribute("aria-live", "polite");
  });

  it("has no serious axe violations on login or the authenticated shell", async () => {
    const user = userEvent.setup();
    const rendered = render(<App demoMode />);

    expect(await seriousViolations(rendered.container)).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));
    expect(await seriousViolations(rendered.container)).toEqual([]);
  });

  it("opens the locally cached confirmed journey after sign-in without regenerating", async () => {
    const user = userEvent.setup();
    const create = vi.fn();
    expect(cacheConfirmedJourney(makeCachedJourney())).toBe(true);

    render(
      <App
        demoMode
        journeyGateway={{ create, confirm: vi.fn() }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));

    const todayViews = screen.getByRole("tablist", { name: "Today views" });
    expect(todayViews).toBeVisible();
    expect(screen.getByRole("tab", { name: "Today" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "My Plan" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Your plan is ready for today" })).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "My Plan" }));

    expect(await screen.findByRole("heading", { name: "Your four-week plan is saved" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "My Plan" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("link", { name: "My Circle" }));
    await user.click(screen.getByRole("link", { name: "Today" }));
    expect(screen.getByRole("heading", { name: "Your four-week plan is saved" })).toBeVisible();
    expect(create).not.toHaveBeenCalled();
  });
});

describe("requested Olive Cream UI contract", () => {
  it("uses the requested accessible semantic colour tokens", () => {
    const expectedTokens = {
      "--color-bg": "#f8efda",
      "--color-surface": "#efe2c4",
      "--color-surface-strong": "#e5d5ad",
      "--color-ink": "#10140b",
      "--color-muted": "#4d5338",
      "--color-border": "#7a8450",
      "--color-primary": "#7a8450",
      "--color-primary-hover": "#697343",
      "--color-primary-mid": "#7a8450",
      "--color-focus": "#10140b",
      "--color-error": "oklch(0.48 0.18 25)",
    };

    for (const [token, value] of Object.entries(expectedTokens)) {
      expect(styles).toContain(`${token}: ${value};`);
    }

    expect(styles).toMatch(/\.welcome-guide\s*\{[^}]*background: var\(--color-bg\);[^}]*\}/s);

    expect(styles).not.toContain("--color-teal");
    expect(styles).not.toContain("oklch(0.52 0.17 355)");
    expect(styles).not.toContain("oklch(0.45 0.16 355)");
    expect(styles).not.toContain("oklch(0.93 0.04 355)");
  });

  it("uses cream and olive for the browser and installed PWA colours", () => {
    expect(documentSource).toContain('<meta name="theme-color" content="#7a8450" />');
    expect(viteConfigSource).toContain('theme_color: "#7a8450"');
    expect(viteConfigSource).toContain('background_color: "#f8efda"');
    expect(documentSource).not.toContain("#a12c58");
    expect(viteConfigSource).not.toContain("#a12c58");
  });

  it("renders the approved onboarding-first Today hierarchy after sign-in", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));

    expect(screen.getByText("Your next step")).toBeVisible();
    expect(screen.getByRole("heading", { level: 1, name: "Your next chapter starts here" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Choose my first hobby" }));
    expect(screen.getByRole("heading", { level: 1, name: "Share your learning wish" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Start speaking" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Your learning wish")).toBeVisible();
  });

  it("keeps Circle and Mentors honest before onboarding is confirmed", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));

    await user.click(screen.getByRole("link", { name: "My Circle" }));
    expect(screen.getByRole("heading", { level: 1, name: "Your circle is ready when you are" })).toBeVisible();
    expect(screen.getByRole("button", { name: "How matching works" })).toBeVisible();

    await user.click(screen.getByRole("link", { name: "Mentors" }));
    expect(screen.getByRole("heading", { level: 1, name: "Learn from lived experience" })).toBeVisible();
    expect(screen.getByRole("button", { name: "What makes a verified mentor?" })).toBeVisible();
    expect(screen.queryByText("Anjali Sharma")).not.toBeInTheDocument();
  });

  it("opens the synthetic activity centre from the existing Mentors destination in demo mode", async () => {
    const user = userEvent.setup();
    render(<App demoMode />);

    await user.click(screen.getByRole("button", { name: "Continue as Meera" }));
    await user.click(screen.getByRole("button", { name: "Choose my first hobby" }));
    await user.click(screen.getByRole("link", { name: "Mentors" }));

    expect(screen.getByRole("heading", { level: 1, name: "Activities near you" })).toBeVisible();
    expect(screen.getAllByRole("article")).toHaveLength(6);
    expect(screen.getByRole("button", { name: "Join Kathak: Begin with rhythm" })).toBeVisible();
  });
});
