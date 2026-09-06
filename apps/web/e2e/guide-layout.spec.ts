import { expect, test } from "@playwright/test";

test("desktop help opens beside Sakhi while sign-in stays on the right", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await page.getByRole("button", { name: "Hi, how may I help you?" }).click();

  const help = page.getByRole("region", { name: "Sakhi help" });
  const portrait = page.getByRole("img", { name: "Sakhi, your SakhiCircle guide" });
  const signIn = page.locator(".sign-in-panel");

  await expect(help).toBeVisible();
  await expect(portrait).toBeVisible();
  await expect(signIn).toBeVisible();

  const [helpBox, portraitBox, signInBox] = await Promise.all([
    help.boundingBox(),
    portrait.boundingBox(),
    signIn.boundingBox(),
  ]);

  expect(helpBox).not.toBeNull();
  expect(portraitBox).not.toBeNull();
  expect(signInBox).not.toBeNull();
  if (!helpBox || !portraitBox || !signInBox) return;

  expect(helpBox.x + helpBox.width).toBeLessThanOrEqual(portraitBox.x + 1);
  expect(portraitBox.x + portraitBox.width).toBeLessThanOrEqual(signInBox.x + 1);
  expect(1280 - (signInBox.x + signInBox.width)).toBeLessThanOrEqual(64);
});
