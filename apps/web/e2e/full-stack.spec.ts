import { expect, test } from "@playwright/test";

test("the real browser completes the judged journey against FastAPI without route mocks", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "One full-stack browser profile is sufficient.");

  await page.goto("/");
  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("button", { name: "Choose my first hobby" }).click();
  await page.getByRole("textbox", { name: "Your learning wish" }).fill(
    "I want to restart watercolours and paint a greeting card. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, seated alternatives, and a small online group in Pune.",
  );
  await page.getByRole("button", { name: "Review my details" }).click();
  await page.getByRole("button", { name: "My words look right" }).click();

  const permissionToggle = page.getByRole("button", { name: "Preferences & permission" });
  if (await permissionToggle.isVisible()) await permissionToggle.click();
  await page.getByRole("checkbox", { name: /I agree SakhiCircle may use/ }).check();
  await page.getByRole("checkbox", { name: /Also use hobby, language/ }).check();

  const profileResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/profile") && response.request().method() === "PUT",
    { timeout: 5_000 },
  );
  const createResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/journeys") && response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Confirm and create my 4-week plan" }).click();
  expect((await profileResponse).status()).toBe(200);
  expect((await createResponse).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Your plan is ready" })).toBeFocused();
  await page.getByRole("button", { name: "Review my four-week plan" }).click();
  await expect(page.getByRole("heading", { name: "Four steady weeks for Watercolour painting" })).toBeFocused();

  const confirmResponse = page.waitForResponse(
    (response) => response.url().includes("/api/v1/journeys/") && response.request().method() === "PUT",
  );
  await page.getByRole("button", { name: "Confirm and save my plan" }).click();
  expect((await confirmResponse).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Your four-week plan is saved" })).toBeFocused();

  const recommendationResponse = page.waitForResponse(
    (response) => response.url().endsWith("/api/v1/recommendations?type=mentor"),
  );
  await page.getByRole("button", { name: "Find my mentor" }).click();
  expect((await recommendationResponse).status()).toBe(200);
  await expect(page.getByRole("heading", { name: "Your demo mentor" })).toBeFocused();
  await expect(page.getByText("Leela Mentor Demo")).toBeVisible();
});
