import { expect, test } from "@playwright/test";

const expectDocumentToFitViewport = async (page: import("@playwright/test").Page) => {
  const overflow = await page.evaluate(() => ({
    horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
  }));

  expect(overflow.horizontal).toBeLessThanOrEqual(1);
  expect(overflow.vertical).toBeLessThanOrEqual(1);
};

const makeJourneyFixture = () => {
  const startsOn = new Date("2026-08-26T00:00:00Z");
  return {
    schemaVersion: "1.0.0",
    journeyId: "journey_browser_fixture",
    status: "draft",
    startsOn: "2026-08-26",
    timezone: "Asia/Kolkata",
    languages: ["en", "hi"],
    title: {
      en: "Four steady weeks for watercolour painting",
      hi: "वॉटरकलर पेंटिंग के लिए चार सहज सप्ताह",
    },
    summary: {
      en: "A steady plan for making one greeting card.",
      hi: "एक शुभकामना कार्ड बनाने की सहज योजना।",
    },
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
      theme: { en: `Week ${weekIndex + 1}`, hi: `सप्ताह ${weekIndex + 1}` },
      outcome: {
        en: "Build confidence steadily.",
        hi: "धीरे-धीरे आत्मविश्वास बढ़ाएँ।",
      },
      activities: Array.from({ length: 7 }, (_, dayIndex) => {
        const dayNumber = weekIndex * 7 + dayIndex + 1;
        const activityDate = new Date(startsOn);
        activityDate.setUTCDate(startsOn.getUTCDate() + dayNumber - 1);
        const required = dayIndex < 4;
        return {
          activityId: `day-${String(dayNumber).padStart(2, "0")}`,
          dayNumber,
          date: activityDate.toISOString().slice(0, 10),
          kind: required ? "practice" : "rest",
          required,
          durationMinutes: required ? 30 : 0,
          title: { en: `Colour practice ${dayNumber}`, hi: `रंग अभ्यास ${dayNumber}` },
          instructions: {
            en: ["Set out paper, water, and three colours."],
            hi: ["कागज़, पानी और तीन रंग तैयार रखें।"],
          },
          accessibleAlternative: {
            en: "Work seated at a table.",
            hi: "मेज़ पर बैठकर काम करें।",
          },
          reflectionPrompt: {
            en: "What felt comfortable today?",
            hi: "आज क्या सहज लगा?",
          },
          safetyNote: {
            en: "Use non-toxic colours and pause if uncomfortable.",
            hi: "गैर-विषैले रंग इस्तेमाल करें और असहजता होने पर रुकें।",
          },
        };
      }),
    })),
  };
};

const makeRecommendationFixture = () => ({
  contractVersion: "matching-v1.0.0",
  recommendationType: "partner",
  source: "deterministic_synthetic",
  synthetic: true,
  status: "matched",
  scoreThreshold: 65,
  resultLimit: 3,
  results: [{
    candidateId: "syn_partner_0001",
    candidateType: "partner",
    displayName: "Kavita Demo",
    synthetic: true,
    score: 100,
    scoreOutOf: 100,
    hobby: { en: "Watercolour painting", hi: "वॉटरकलर पेंटिंग" },
    reasons: [
      { factor: "hobbyGoalFit", reasonCode: "same_hobby_and_goal", points: 30, maxPoints: 30, text: { en: "You share the same hobby and first goal.", hi: "आपका शौक और पहला लक्ष्य समान है।" } },
      { factor: "schedule", reasonCode: "same_practice_rhythm", points: 20, maxPoints: 20, text: { en: "Your practice rhythms match.", hi: "आप दोनों के अभ्यास की गति समान है।" } },
      { factor: "language", reasonCode: "preferred_language_shared", points: 15, maxPoints: 15, text: { en: "You share a preferred learning language.", hi: "आप दोनों की पसंदीदा सीखने की भाषा समान है।" } },
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
});

test("login stays focused and the shell fits without overflow", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();
  await expect(page.getByText("A friendly place to learn, teach, and belong.")).toBeVisible();
  await expect(page.getByText("Sign in securely. No password needed.")).toBeVisible();
  await expect(page.getByRole("img", { name: "Sakhi, your SakhiCircle guide" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Hi, let me help you" })).toBeVisible();
  await expect(page.getByText("She made space for everyone else. This space is hers.")).toHaveCount(0);

  const loginFit = await page.evaluate(() => ({
    horizontal: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    vertical: document.documentElement.scrollHeight - document.documentElement.clientHeight,
  }));
  expect(loginFit.horizontal).toBeLessThanOrEqual(1);
  expect(loginFit.vertical).toBeLessThanOrEqual(1);

  const viewport = page.viewportSize();
  const signInBox = await page.locator(".sign-in-panel").boundingBox();
  expect(viewport).not.toBeNull();
  expect(signInBox).not.toBeNull();
  if (viewport && signInBox && viewport.width > 780) {
    const signInCenter = signInBox.x + signInBox.width / 2;
    expect(Math.abs(signInCenter - viewport.width / 2)).toBeLessThanOrEqual(2);
  }

  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();

  const shellOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(shellOverflow).toBeLessThanOrEqual(1);
});

test("explicit sign-out clears local user state and returns to sign-in", async ({ page }) => {
  await page.goto("/");
  await page.evaluate(() => {
    localStorage.setItem("sakhicircle-onboarding-draft", "private draft");
    sessionStorage.setItem("sakhicircle-user-query-state", "private query");
  });
  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("button", { name: "Meera Sharma profile" }).click();
  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(page.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toHaveCount(0);
  expect(await page.evaluate(() => ({
    draft: localStorage.getItem("sakhicircle-onboarding-draft"),
    query: sessionStorage.getItem("sakhicircle-user-query-state"),
  }))).toEqual({ draft: null, query: null });
});

test("every required sign-in action is visible without scrolling at 360 by 800", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");

  const requiredActions = [
    page.getByRole("button", { name: "हिंदी में देखें" }),
    page.getByLabel("Email address"),
    page.getByRole("button", { name: "Send sign-in link" }),
    page.getByRole("button", { name: "Continue with Google" }),
    page.getByRole("button", { name: "Continue as Meera" }),
  ];

  for (const action of requiredActions) {
    await expect(action).toBeVisible();
    await expect(action).toBeInViewport({ ratio: 1 });
  }

  await expectDocumentToFitViewport(page);
});

test("login language switching translates every required action without overflow", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");

  await page.getByRole("button", { name: "हिंदी में देखें" }).click();
  await expect(page.getByRole("heading", { name: "SakhiCircle में आपका स्वागत है" })).toBeVisible();
  await expect(page.getByLabel("ईमेल पता")).toBeVisible();
  await expect(page.getByRole("button", { name: "साइन-इन लिंक भेजें" })).toBeInViewport({ ratio: 1 });
  await expect(page.getByRole("button", { name: "Google से जारी रखें" })).toBeInViewport({ ratio: 1 });
  await expect(page.getByRole("button", { name: "मीरा के रूप में जारी रखें" })).toBeInViewport({ ratio: 1 });
  await expectDocumentToFitViewport(page);

  await page.getByRole("button", { name: "View in English" }).click();
  await expect(page.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue as Meera" })).toBeVisible();
});

test("the default mobile shell avoids scrolling until optional guidance is expanded", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();

  await expectDocumentToFitViewport(page);
  const stepsToggle = page.getByRole("button", { name: /How SakhiCircle works/ });
  await expect(stepsToggle).toBeVisible();
  await expect(stepsToggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".how-it-works ol")).not.toBeVisible();

  await stepsToggle.click();
  await expect(stepsToggle).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".how-it-works ol")).toBeVisible();

  await page.setViewportSize({ width: 1024, height: 800 });
  await page.setViewportSize({ width: 360, height: 800 });
  await expect(stepsToggle).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".how-it-works ol")).not.toBeVisible();
  await expectDocumentToFitViewport(page);
});

test("the default mobile shell still fits with slightly enlarged system text", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await page.evaluate(() => {
    document.documentElement.style.fontSize = "17px";
  });
  await page.getByRole("button", { name: "Continue as Meera" }).click();

  await expectDocumentToFitViewport(page);
  await expect(page.getByRole("button", { name: /How SakhiCircle works/ })).toBeInViewport({ ratio: 1 });
});

test("the Sakhi guide opens accessible help without leaving sign-in", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Hi, let me help you" }).click();

  await expect(page.getByRole("region", { name: "Sakhi help" })).toBeVisible();
  await expect(page.getByText("What would you like help with?")).toBeVisible();
  await expect(page.getByRole("button", { name: "Signing in" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Finding a hobby" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Using voice" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Welcome to SakhiCircle" })).toBeVisible();

  await page.getByRole("button", { name: "Using voice" }).click();
  await expect(page.getByRole("status")).toContainText("Every voice step also has a text option.");
});

test("Sakhi's full desktop portrait is visible and her speech bubble stays near her head", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");

  const guideBox = await page.locator(".welcome-guide").boundingBox();
  const portraitBox = await page.getByRole("img", { name: "Sakhi, your SakhiCircle guide" }).boundingBox();
  const bubbleBox = await page.locator(".guide-bubble").boundingBox();

  expect(guideBox).not.toBeNull();
  expect(portraitBox).not.toBeNull();
  expect(bubbleBox).not.toBeNull();
  if (!guideBox || !portraitBox || !bubbleBox) return;

  expect(portraitBox.y + portraitBox.height).toBeLessThanOrEqual(guideBox.y + guideBox.height + 1);
  expect(Math.abs(portraitBox.y - (bubbleBox.y + bubbleBox.height))).toBeLessThanOrEqual(32);

  await page.setViewportSize({ width: 360, height: 800 });
  const mobileBubbleFontSize = await page.locator(".guide-bubble").evaluate(
    (element) => Number.parseFloat(window.getComputedStyle(element).fontSize),
  );
  expect(mobileBubbleFontSize).toBeGreaterThanOrEqual(14);
  expect(mobileBubbleFontSize).toBeLessThanOrEqual(15);
});

test("polished hierarchy keeps the primary action distinct and the journey visually open", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");

  const primaryBackground = await page.getByRole("button", { name: "Send sign-in link" }).evaluate(
    (element) => window.getComputedStyle(element).backgroundColor,
  );
  const demoBackground = await page.getByRole("button", { name: "Continue as Meera" }).evaluate(
    (element) => window.getComputedStyle(element).backgroundColor,
  );
  expect(demoBackground).not.toBe(primaryBackground);

  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await expect(page.getByText("Three simple steps")).toBeVisible();
  await expect(page.getByRole("button", { name: "How this works" })).toHaveCount(0);
  await page.getByRole("button", { name: "Need help?" }).click();
  await expect(page.getByText(/Helpful explanations appear beneath unfamiliar sections/)).toBeVisible();
  const journeyBackground = await page.locator(".how-it-works ol").evaluate(
    (element) => window.getComputedStyle(element).backgroundColor,
  );
  expect(journeyBackground).toBe("rgba(0, 0, 0, 0)");

  const activeNavigationBackground = await page.getByRole("link", { name: "Today" }).evaluate(
    (element) => window.getComputedStyle(element).backgroundColor,
  );
  const railBackground = await page.getByRole("navigation", { name: "Primary navigation" }).evaluate(
    (element) => window.getComputedStyle(element).backgroundColor,
  );
  expect(activeNavigationBackground).not.toBe(railBackground);
});

test("visible controls meet the 48px target baseline", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();

  const undersized = await page.locator("button, input, nav a, [role='button']").evaluateAll(
    (elements) =>
      elements
        .filter((element) => {
          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0;
        })
        .map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            label: element.getAttribute("aria-label") ?? element.textContent?.trim() ?? element.tagName,
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          };
        })
        .filter(({ width, height }) => width < 48 || height < 48),
  );

  expect(undersized).toEqual([]);
});

test("keyboard users can reach the main content and primary navigation", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();

  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("link", { name: "Today" }).focus();
  await expect(page.getByRole("link", { name: "Today" })).toBeFocused();
});

test("sign-in transition resets scroll and moves focus into the app", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();

  await expect(page.locator("#main-content")).toBeFocused();
  expect(await page.evaluate(() => window.scrollY)).toBeLessThanOrEqual(1);
});

test("navigation remains a full-width bottom bar below 900 pixels", async ({ page }) => {
  await page.setViewportSize({ width: 899, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();

  const viewport = page.viewportSize();
  const navigationBox = await page.getByRole("navigation", { name: "Primary navigation" }).boundingBox();

  expect(viewport).not.toBeNull();
  expect(navigationBox).not.toBeNull();
  if (!viewport || !navigationBox) return;

  expect(navigationBox.x).toBeLessThanOrEqual(1);
  expect(navigationBox.width).toBeGreaterThanOrEqual(viewport.width - 2);
  expect(navigationBox.y + navigationBox.height).toBeGreaterThanOrEqual(viewport.height - 2);
});

test("desktop rail touches the left edge and content centers in the remaining canvas", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();

  const viewport = page.viewportSize();
  const navigationBox = await page.getByRole("navigation", { name: "Primary navigation" }).boundingBox();
  const mainBox = await page.locator("#main-content").boundingBox();

  expect(viewport).not.toBeNull();
  expect(navigationBox).not.toBeNull();
  expect(mainBox).not.toBeNull();
  if (!viewport || !navigationBox || !mainBox) return;

  expect.soft(navigationBox.x, "desktop rail left edge").toBeLessThanOrEqual(1);
  expect.soft(navigationBox.width, "desktop rail width").toBeLessThan(280);
  expect.soft(navigationBox.height, "desktop rail height").toBeGreaterThan(400);

  const remainingCanvasLeft = navigationBox.x + navigationBox.width;
  const remainingCanvasCenter = remainingCanvasLeft + (viewport.width - remainingCanvasLeft) / 2;
  const mainCenter = mainBox.x + mainBox.width / 2;
  expect.soft(Math.abs(mainCenter - remainingCanvasCenter), "remaining-canvas centering delta").toBeLessThanOrEqual(2);
});

test("reviewed onboarding details cross the profile boundary only after confirmation", async ({ page }) => {
  const profileRequests: Record<string, unknown>[] = [];
  await page.route("**/api/v1/profile", async (route) => {
    profileRequests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "saved" }),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("button", { name: "Choose my first hobby" }).click();

  const transcript = "I want to restart watercolours and paint a greeting card. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, seated alternatives, and a small online group in Pune.";
  await page.getByRole("textbox", { name: "Your learning wish" }).fill(transcript);
  expect(profileRequests).toHaveLength(0);
  expect(await page.evaluate(() => ({
    local: localStorage.getItem("sakhicircle-onboarding-draft"),
    session: sessionStorage.getItem("sakhicircle-onboarding-draft"),
  }))).toEqual({ local: null, session: null });

  await page.getByRole("button", { name: "Review my details" }).click();
  await expect(page.getByText("Nothing has been saved")).toBeVisible();
  expect(profileRequests).toHaveLength(0);
  await page.getByRole("button", { name: "My words look right" }).click();
  const permissionToggle = page.getByRole("button", { name: "Preferences & permission" });
  if (await permissionToggle.isVisible()) await permissionToggle.click();
  await page.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }).check();
  await page.getByRole("button", { name: "Confirm and create my 4-week plan" }).click();

  await expect(page.getByRole("heading", { name: "Your plan is ready to build" })).toBeFocused();
  expect(profileRequests).toHaveLength(1);
  expect(profileRequests[0]).not.toHaveProperty("transcript");
  expect(profileRequests[0]).not.toHaveProperty("rawAudio");
  expect(profileRequests[0]).toMatchObject({
    hobby: "Watercolour painting",
    planConsent: true,
    matchingConsent: false,
  });
});

test("language switching preserves learner words and deterministic voice remains editable", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("button", { name: "Choose my first hobby" }).click();

  await page.getByRole("button", { name: "Start speaking" }).click();
  const wish = page.getByRole("textbox", { name: "Your learning wish" });
  const transcript = await wish.inputValue();
  expect(transcript).toContain("restart watercolours");
  await expect(page.getByText("SakhiCircle deterministic local voice")).toBeVisible();

  await page.getByRole("button", { name: "हिंदी में देखें" }).click();
  await expect(page.getByRole("heading", { name: "अपनी सीखने की इच्छा बताएँ" })).toBeFocused();
  await expect(page.getByRole("textbox", { name: "आपकी सीखने की इच्छा" })).toHaveValue(transcript);
  await expect(page.getByRole("button", { name: "बोलना शुरू करें" })).toBeVisible();
  await expect(page.getByText("भाषा हिंदी हुई। आपका ड्राफ़्ट नहीं बदला।"))
    .toHaveAttribute("aria-live", "polite");
});

test("bilingual journey stays unsaved through review and persists only the confirmed edits", async ({ page }) => {
  const profileRequests: Record<string, unknown>[] = [];
  const journeyCreates: Record<string, unknown>[] = [];
  const journeyConfirms: Record<string, unknown>[] = [];
  await page.route("**/api/v1/profile", async (route) => {
    profileRequests.push(route.request().postDataJSON());
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "saved" }) });
  });
  await page.route(/\/api\/v1\/journeys(?:\/.*)?$/, async (route) => {
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Firebase-AppCheck",
      "Access-Control-Allow-Methods": "POST, PUT, OPTIONS",
    };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    const payload = route.request().postDataJSON();
    if (route.request().method() === "POST") {
      journeyCreates.push(payload);
      await route.fulfill({ status: 200, contentType: "application/json", headers: corsHeaders, body: JSON.stringify(makeJourneyFixture()) });
      return;
    }
    journeyConfirms.push(payload);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: corsHeaders,
      body: JSON.stringify({ ...payload, status: "confirmed" }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("button", { name: "Choose my first hobby" }).click();
  await page.getByRole("button", { name: "Start speaking" }).click();
  await page.getByRole("button", { name: "Review my details" }).click();
  await page.getByRole("button", { name: "My words look right" }).click();
  const permissionToggle = page.getByRole("button", { name: "Preferences & permission" });
  if (await permissionToggle.isVisible()) await permissionToggle.click();
  await page.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }).check();
  await page.getByRole("button", { name: "Confirm and create my 4-week plan" }).click();

  await expect(page.getByRole("heading", { name: "Your plan is ready to build" })).toBeFocused();
  expect(profileRequests).toHaveLength(1);
  expect(journeyCreates).toHaveLength(0);
  expect(journeyConfirms).toHaveLength(0);

  await page.getByRole("button", { name: "Review my four-week plan" }).click();
  await expect(page.getByRole("heading", { name: "Four steady weeks for watercolour painting" })).toBeFocused();
  expect(journeyCreates).toHaveLength(1);
  expect(journeyConfirms).toHaveLength(0);

  await page.getByRole("button", { name: "हिंदी में देखें" }).click();
  await expect(page.getByRole("heading", { name: "वॉटरकलर पेंटिंग के लिए चार सहज सप्ताह" })).toBeVisible();
  expect(journeyCreates).toHaveLength(1);
  await page.getByRole("button", { name: "View in English" }).click();

  await page.getByRole("button", { name: "Reject this draft" }).click();
  await expect(page.getByRole("heading", { name: "This draft was discarded" })).toBeVisible();
  expect(journeyConfirms).toHaveLength(0);
  await page.getByRole("button", { name: "Create another plan" }).click();
  await expect(page.getByRole("heading", { name: "Four steady weeks for watercolour painting" })).toBeVisible();

  await page.getByRole("button", { name: "Edit plan title" }).click();
  await page.getByLabel("Plan title").fill("My edited watercolour month");
  await page.getByRole("button", { name: "Save plan title" }).click();
  await page.getByRole("button", { name: "Edit day 1" }).click();
  await page.getByLabel("Day 1 duration in minutes").fill("20");
  await page.getByLabel("Day 1 instruction 1").fill("Paint one calm colour wash.");
  expect(journeyConfirms).toHaveLength(0);
  await page.getByRole("button", { name: "Save day 1" }).click();
  const confirmationRequest = page.waitForRequest((request) => (
    request.method() === "PUT" && request.url().includes("/api/v1/journeys/")
  ));
  const confirmationResponse = page.waitForResponse((response) => (
    response.request().method() === "PUT" && response.url().includes("/api/v1/journeys/")
  ));
  await page.getByRole("button", { name: "Confirm and save my plan" }).click();
  await confirmationRequest;
  const confirmedResponse = await confirmationResponse;
  expect(confirmedResponse.ok()).toBe(true);
  expect(await confirmedResponse.json()).toMatchObject({ status: "confirmed" });

  await expect(page.getByRole("heading", { name: "Your four-week plan is saved" })).toBeFocused();
  expect(journeyConfirms).toHaveLength(1);
  expect(journeyConfirms[0]).not.toHaveProperty("transcript");
  expect(journeyConfirms[0]).not.toHaveProperty("rawAudio");
  expect(journeyConfirms[0]).not.toHaveProperty("city");
  expect(journeyConfirms[0]).not.toHaveProperty("uid");
  const confirmedJourney = journeyConfirms[0] as ReturnType<typeof makeJourneyFixture>;
  expect(confirmedJourney.title.en).toBe("My edited watercolour month");
  expect(confirmedJourney.weeks[0].activities[0].durationMinutes).toBe(20);
  expect(confirmedJourney.weeks[0].activities[0].instructions.en).toEqual(["Paint one calm colour wash."]);
});

test("one explainable match is fetched only by the explicit action and survives locale and zoom changes", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  let recommendationRequests = 0;
  await page.route("**/api/v1/profile", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "saved" }) });
  });
  await page.route(/\/api\/v1\/journeys(?:\/.*)?$/, async (route) => {
    const headers = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Firebase-AppCheck",
      "Access-Control-Allow-Methods": "POST, PUT, OPTIONS",
    };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    const draft = route.request().method() === "POST"
      ? makeJourneyFixture()
      : { ...route.request().postDataJSON(), status: "confirmed" };
    await route.fulfill({ status: 200, contentType: "application/json", headers, body: JSON.stringify(draft) });
  });
  await page.route("**/api/v1/recommendations?type=partner", async (route) => {
    const headers = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "Authorization, X-Firebase-AppCheck",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
    };
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers });
      return;
    }
    recommendationRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers,
      body: JSON.stringify(makeRecommendationFixture()),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("button", { name: "Choose my first hobby" }).click();
  await page.getByRole("button", { name: "Start speaking" }).click();
  await page.getByRole("button", { name: "Review my details" }).click();
  await page.getByRole("button", { name: "My words look right" }).click();
  const permissionToggle = page.getByRole("button", { name: "Preferences & permission" });
  if (await permissionToggle.isVisible()) await permissionToggle.click();
  await page.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }).check();
  await page.getByRole("checkbox", { name: /Also use hobby, language/ }).check();
  await page.getByRole("button", { name: "Confirm and create my 4-week plan" }).click();
  await page.getByRole("button", { name: "Review my four-week plan" }).click();
  await expect(page.getByRole("heading", { name: "Four steady weeks for watercolour painting" })).toBeVisible();
  await page.getByRole("button", { name: "Confirm and save my plan" }).click();

  await expect(page.getByRole("heading", { name: "Your four-week plan is saved" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Find my learning partner" })).toBeVisible();
  expect(recommendationRequests).toBe(0);
  await page.getByRole("button", { name: "Find my learning partner" }).click();

  await expect(page.getByRole("heading", { name: "Your demo learning partner" })).toBeFocused();
  await expect(page.getByText("Demo match — synthetic profile")).toBeVisible();
  await expect(page.getByText("Match score: 100 out of 100")).toBeVisible();
  await expect(page.locator(".recommendation-reasons li")).toHaveCount(3);
  expect(recommendationRequests).toBe(1);

  await page.getByRole("button", { name: "हिंदी में देखें" }).click();
  await expect(page.getByRole("heading", { name: "आपकी डेमो सीखने की साथी" })).toBeVisible();
  await expect(page.getByText("मैच स्कोर: 100 में से 100")).toBeVisible();
  expect(recommendationRequests).toBe(1);

  const undersized = await page.locator(".recommendation-flow button, .matching-disclosure summary").evaluateAll(
    (elements) => elements.map((element) => {
      const rect = element.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }).filter(({ width, height }) => width < 48 || height < 48),
  );
  expect(undersized).toEqual([]);
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  const zoomOverflow = await page.evaluate(() => ({
    amount: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    elements: Array.from(document.querySelectorAll("body *")).map((element) => {
      const rect = element.getBoundingClientRect();
      return {
        selector: `${element.tagName.toLowerCase()}.${element.className}`,
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      };
    }).filter(({ left, right, scrollWidth, clientWidth }) => (
      left < -1 || right > document.documentElement.clientWidth + 1 || scrollWidth > clientWidth + 1
    )).slice(-10),
  }));
  expect(zoomOverflow.amount, JSON.stringify(zoomOverflow.elements)).toBeLessThanOrEqual(1);
  await page.setViewportSize({ width: 320, height: 800 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
