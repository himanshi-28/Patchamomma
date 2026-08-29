import { mkdir } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "@playwright/test";

const prototypeUrl = pathToFileURL(
  fileURLToPath(new URL("../../../docs/ui-review/sc-300-onboarding-prototype.html", import.meta.url)),
);
const outputDirectory = fileURLToPath(new URL("../../../docs/ui-review/", import.meta.url));
const axePath = fileURLToPath(new URL("../node_modules/axe-core/axe.min.js", import.meta.url));

await mkdir(outputDirectory, { recursive: true });
const browser = await chromium.launch();

const waitForPaint = (page) => page.evaluate(
  () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))),
);

const auditPage = async (page, label, { runAxe = true } = {}) => {
  const layout = await page.evaluate(() => ({
    horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    undersizedTargets: [...document.querySelectorAll("button, nav a, label.consent-label")]
      .filter((element) => {
        const style = window.getComputedStyle(element);
        const bounds = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && bounds.width > 0;
      })
      .map((element) => {
        const bounds = element.getBoundingClientRect();
        return {
          label: element.getAttribute("aria-label") ?? element.textContent?.trim() ?? element.tagName,
          width: Math.round(bounds.width),
          height: Math.round(bounds.height),
        };
      })
      .filter(({ width, height }) => width < 48 || height < 48),
  }));
  if (layout.horizontalOverflow > 1 || layout.undersizedTargets.length > 0) {
    throw new Error(`${label} layout failed: ${JSON.stringify(layout)}`);
  }

  if (!runAxe) return;
  await page.addScriptTag({ path: axePath });
  const violations = await page.evaluate(async () => {
    const result = await axe.run(document, {
      resultTypes: ["violations"],
      rules: { region: { enabled: false } },
    });
    return result.violations
      .filter(({ impact }) => impact === "critical" || impact === "serious")
      .map(({ id, impact, help, nodes }) => ({ id, impact, help, targets: nodes.map((node) => node.target) }));
  });
  if (violations.length > 0) throw new Error(`${label} accessibility failed: ${JSON.stringify(violations)}`);
};

const openPrototype = async ({ viewport, locale, stage, scenario = "ready" }) => {
  const pageErrors = [];
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  const url = new URL(prototypeUrl);
  url.searchParams.set("locale", locale);
  url.searchParams.set("stage", stage);
  url.searchParams.set("scenario", scenario);
  await page.goto(url.href);
  await waitForPaint(page);
  if (pageErrors.length > 0) throw new Error(`${stage}/${locale}/${scenario} script failed: ${pageErrors.join(" | ")}`);
  return page;
};

for (const review of [
  { name: "mobile", viewport: { width: 360, height: 800 } },
  { name: "desktop", viewport: { width: 1280, height: 800 } },
]) {
  for (const locale of ["en", "hi"]) {
    for (const stage of ["capture", "review"]) {
      const page = await openPrototype({ viewport: review.viewport, locale, stage });
      if (stage === "review") {
        await page.locator(`.copy-${locale} [data-review-transcript]`).click();
        await waitForPaint(page);
      }
      if (review.name === "mobile") {
        await page.addStyleTag({ content: "body { position: relative; } .primary-navigation { position: absolute; top: auto; bottom: 0; }" });
      }
      await auditPage(page, `${review.name}/${stage}/${locale}`);
      await page.screenshot({
        path: `${outputDirectory}/sc-300-${review.name}-${stage}-${locale}.png`,
        fullPage: true,
      });
      await page.close();
    }
  }
}

for (const state of [
  { scenario: "empty", locale: "en", stage: "capture" },
  { scenario: "mic-denied", locale: "en", stage: "capture" },
  { scenario: "unsupported", locale: "hi", stage: "capture" },
  { scenario: "missing", locale: "en", stage: "review" },
  { scenario: "changed", locale: "hi", stage: "review" },
  { scenario: "save-error", locale: "en", stage: "review" },
  { scenario: "success", locale: "hi", stage: "review" },
]) {
  const page = await openPrototype({ viewport: { width: 360, height: 800 }, ...state });
  await page.addStyleTag({ content: "body { position: relative; } .primary-navigation { position: absolute; top: auto; bottom: 0; }" });
  await auditPage(page, `mobile/${state.stage}/${state.locale}/${state.scenario}`);
  await page.screenshot({
    path: `${outputDirectory}/sc-300-mobile-state-${state.scenario}-${state.locale}.png`,
    fullPage: true,
  });
  await page.close();
}

for (const locale of ["en", "hi"]) {
  const page = await openPrototype({ viewport: { width: 320, height: 800 }, locale, stage: "review" });
  await page.addStyleTag({ content: ":root { font-size: 200%; }" });
  await waitForPaint(page);
  await auditPage(page, `reflow-320-200-percent/${locale}`, { runAxe: false });
  await page.close();
}

await browser.close();
console.log("SC-300 evidence: 8 core captures, 7 state captures, accessibility clean, 320px/200% reflow clean");
