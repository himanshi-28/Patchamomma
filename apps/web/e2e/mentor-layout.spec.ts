import { expect, test } from "@playwright/test";

test("mentor heading and registration action share the desktop row without collapsing", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");

  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.getByRole("link", { name: "Mentors" }).click();

  const headingCopy = page.locator(".activity-center-heading > div");
  const registerButton = page.getByRole("button", { name: "Register as a mentor" });
  const [headingBox, buttonBox] = await Promise.all([
    headingCopy.boundingBox(),
    registerButton.boundingBox(),
  ]);

  expect(headingBox).not.toBeNull();
  expect(buttonBox).not.toBeNull();
  expect(headingBox!.width).toBeGreaterThanOrEqual(480);
  expect(buttonBox!.width).toBeLessThanOrEqual(320);
  expect(buttonBox!.width).toBeLessThan(headingBox!.width);
  expect(headingBox!.x + headingBox!.width).toBeLessThan(buttonBox!.x);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
});
