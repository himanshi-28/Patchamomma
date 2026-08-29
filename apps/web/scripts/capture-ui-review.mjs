import { mkdir } from "node:fs/promises";
import { chromium } from "@playwright/test";

const baseUrl = process.env.UI_BASE_URL ?? "http://127.0.0.1:4174";
const outputDirectory = "docs/ui-review";

await mkdir(outputDirectory, { recursive: true });

const browser = await chromium.launch();

for (const review of [
  { name: "mobile", viewport: { width: 360, height: 800 } },
  { name: "desktop", viewport: { width: 1280, height: 800 } },
]) {
  const page = await browser.newPage({ viewport: review.viewport });
  await page.goto(baseUrl);
  await page.screenshot({ path: `${outputDirectory}/${review.name}-login.png`, fullPage: false });

  await page.getByRole("button", { name: "हिंदी में देखें" }).click();
  await page.screenshot({ path: `${outputDirectory}/${review.name}-login-hi.png`, fullPage: false });
  await page.getByRole("button", { name: "View in English" }).click();

  await page.getByRole("button", { name: "Continue as Meera" }).click();
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
  );
  await page.screenshot({ path: `${outputDirectory}/${review.name}-shell.png`, fullPage: false });
  await page.close();
}

await browser.close();
