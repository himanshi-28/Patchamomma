import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { JSDOM } from "../../apps/web/node_modules/jsdom/lib/api.js";

const prototype = readFileSync(
  new URL("../../docs/ui-review/sc-300-onboarding-prototype.html", import.meta.url),
  "utf8",
);

const render = async (query = "locale=en&stage=capture") => {
  const dom = new JSDOM(prototype, {
    beforeParse(window) {
      window.scrollTo = () => {};
    },
    pretendToBeVisual: true,
    runScripts: "dangerously",
    url: `https://sc300.test/?${query}`,
  });
  await new Promise((resolve) => dom.window.requestAnimationFrame(resolve));
  return dom;
};

const change = (window, element) => element.dispatchEvent(new window.Event("change", { bubbles: true }));
const input = (window, element) => element.dispatchEvent(new window.Event("input", { bubbles: true }));

test("language switching preserves one shared learner draft and localizes accessibility", async () => {
  const dom = await render();
  const { document } = dom.window;
  const englishTranscript = document.querySelector("#wish-en");
  englishTranscript.value = "My exact learner-entered words";
  input(dom.window, englishTranscript);

  document.querySelector('button[data-locale="hi"]').click();
  await new Promise((resolve) => dom.window.requestAnimationFrame(resolve));

  assert.equal(document.body.dataset.locale, "hi");
  assert.equal(document.querySelector("#wish-hi").value, "My exact learner-entered words");
  assert.equal(document.querySelector("[data-primary-nav]").getAttribute("aria-label"), "मुख्य नेविगेशन");
  assert.equal(document.querySelector("[data-profile]").getAttribute("aria-label"), "मीरा शर्मा प्रोफ़ाइल");
  assert.equal(document.documentElement.lang, "hi");
  assert.equal(document.activeElement.textContent, "आप फिर से क्या शुरू करना चाहती हैं?");
  dom.window.close();
});

test("language switching preserves an unsaved inline edit", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  document.querySelector('[data-edit-field="hobby"]').click();
  const englishEditor = document.querySelector("#hobby-en");
  englishEditor.value = "Hand-built pottery";
  input(dom.window, englishEditor);
  document.querySelector('button[data-locale="hi"]').click();

  assert.equal(document.querySelector("#hobby-hi").value, "Hand-built pottery");
  assert.equal(document.querySelector('[data-field="hobby"] .editor-wrap').hidden, false);
  dom.window.close();
});

test("review requires transcript check and plan consent but not matching consent", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  const confirm = document.querySelector("[data-confirm]");
  assert.equal(confirm.disabled, true);
  assert.equal(document.querySelector('[data-progress-step="review"]').getAttribute("aria-current"), "step");

  document.querySelector("[data-review-transcript]").click();
  assert.equal(document.querySelector("[data-transcript-review]").open, false);
  assert.equal(confirm.disabled, true);

  const planConsent = document.querySelector('[data-consent="plan"]');
  planConsent.checked = true;
  change(dom.window, planConsent);
  assert.equal(confirm.disabled, false);
  assert.equal(document.querySelector('[data-consent="matching"]').checked, false);
  dom.window.close();
});

test("native inline editing updates the shared field without changing transcript", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  const originalTranscript = document.querySelector("#review-transcript-en").value;
  document.querySelector('[data-edit-field="goal"]').click();
  const editor = document.querySelector('#goal-en');
  editor.value = "Paint one card by Friday";
  document.querySelector('[data-save-field="goal"]').click();

  assert.equal(document.querySelector('[data-field-value="goal"]').textContent, "Paint one card by Friday");
  assert.equal(document.querySelector("#review-transcript-en").value, originalTranscript);
  assert.equal(document.querySelector('[data-field="goal"]'), document.activeElement);
  dom.window.close();
});

test("empty and missing scenarios fail closed without losing recovery controls", async () => {
  const empty = await render("locale=en&stage=capture&scenario=empty");
  assert.equal(empty.window.document.querySelector("[data-go-stage='review']").disabled, true);
  assert.equal(empty.window.document.querySelector('.scenario-panel[data-scenario="empty"]').getAttribute("role"), "status");
  const emptyTranscript = empty.window.document.querySelector("#wish-en");
  emptyTranscript.value = "I want to learn pottery";
  input(empty.window, emptyTranscript);
  assert.equal(empty.window.document.body.dataset.scenario, "ready");
  empty.window.document.querySelector("[data-go-stage='review']").click();
  const emptyMissingRows = empty.window.document.querySelectorAll(".field-row.is-missing");
  assert.equal(emptyMissingRows.length, 7);
  empty.window.document.querySelector("[data-update-details]").click();
  assert.equal(empty.window.document.querySelector('[data-field-value="hobby"]').textContent, "Pottery");
  assert.equal(empty.window.document.querySelectorAll(".field-row.is-missing").length, 5);
  const markedKeys = [...empty.window.document.querySelectorAll(".field-row")]
    .filter((row) => row.querySelector("[data-changed-badge]")?.hidden === false)
    .map((row) => row.dataset.field);
  assert.deepEqual(markedKeys, ["hobby", "goal"]);
  for (const key of markedKeys) {
    empty.window.document.querySelector(`[data-edit-field="${key}"]`).click();
    empty.window.document.querySelector(`[data-save-field="${key}"]`).click();
  }
  assert.equal(empty.window.document.body.dataset.scenario, "missing");
  empty.window.close();

  const missing = await render("locale=en&stage=review&scenario=missing");
  const planConsent = missing.window.document.querySelector('[data-consent="plan"]');
  missing.window.document.querySelector("[data-review-transcript]").click();
  planConsent.checked = true;
  change(missing.window, planConsent);
  assert.equal(missing.window.document.querySelector("[data-confirm]").disabled, true);
  assert.equal(missing.window.document.querySelector('[data-field="goal"]').classList.contains("is-missing"), true);
  missing.window.document.querySelector('[data-edit-field="goal"]').click();
  const goalEditor = missing.window.document.querySelector("#goal-en");
  goalEditor.value = "Paint a card";
  input(missing.window, goalEditor);
  missing.window.document.querySelector('[data-save-field="goal"]').click();
  assert.equal(missing.window.document.body.dataset.scenario, "ready");
  missing.window.close();
});

test("microphone-denied and unsupported states focus recovery then clear on typing", async () => {
  for (const scenario of ["mic-denied", "unsupported"]) {
    const dom = await render(`locale=en&stage=capture&scenario=${scenario}`);
    const { document } = dom.window;
    document.querySelector("[data-voice-button]").click();
    assert.equal(document.activeElement, document.querySelector(`.scenario-panel[data-scenario="${scenario}"]`));
    const transcript = document.querySelector("#wish-en");
    transcript.value = "I will continue by typing";
    input(dom.window, transcript);
    assert.equal(document.body.dataset.scenario, "ready");
    assert.equal(document.querySelector("[data-go-stage='review']").disabled, false);
    dom.window.close();
  }
});

test("changed extraction is distinct and clears after the marked row is saved", async () => {
  const dom = await render("locale=en&stage=review&scenario=changed");
  const { document } = dom.window;
  assert.equal(document.querySelector('[data-field-value="goal"]').textContent, "Paint one watercolour card for my granddaughter");
  assert.equal(document.querySelector('[data-field="goal"] [data-changed-badge]').hidden, false);
  document.querySelector('[data-edit-field="goal"]').click();
  document.querySelector('[data-save-field="goal"]').click();
  assert.equal(document.body.dataset.scenario, "ready");
  assert.equal(document.querySelector('[data-field="goal"] [data-changed-badge]').hidden, true);
  dom.window.close();
});

test("deterministic extraction marks an optional city when it changes", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  document.querySelector('[data-edit-field="city"]').click();
  const city = document.querySelector("#city-en");
  city.value = "Mumbai";
  input(dom.window, city);
  document.querySelector('[data-save-field="city"]').click();
  document.querySelector("[data-update-details]").click();
  assert.equal(document.querySelector('[data-field="city"] [data-changed-badge]').hidden, false);
  dom.window.close();
});

test("save failure keeps the draft and moves focus to retryable recovery", async () => {
  const dom = await render("locale=en&stage=review&scenario=save-error");
  const { document } = dom.window;
  const before = document.querySelector("#review-transcript-en").value;
  assert.equal(document.querySelector("[data-confirm]").disabled, false);
  document.querySelector("[data-confirm]").click();
  await new Promise((resolve) => dom.window.setTimeout(resolve, 500));

  const recovery = document.querySelector('.scenario-panel[data-scenario="save-error"]');
  assert.equal(document.activeElement, recovery);
  assert.equal(document.querySelector("#review-transcript-en").value, before);
  assert.equal(document.body.dataset.scenario, "save-error");
  document.querySelector("[data-retry]").click();
  assert.equal(document.body.dataset.scenario, "ready");
  assert.equal(document.querySelector("#review-transcript-en").value, before);
  assert.equal(document.activeElement, document.querySelector("[data-confirm]"));
  dom.window.close();
});

test("success discards the temporary transcript and moves focus to success", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  document.querySelector("[data-review-transcript]").click();
  const planConsent = document.querySelector('[data-consent="plan"]');
  planConsent.checked = true;
  change(dom.window, planConsent);
  document.querySelector("[data-confirm]").click();
  await new Promise((resolve) => dom.window.setTimeout(resolve, 500));

  assert.equal(document.body.dataset.scenario, "success");
  assert.equal(document.querySelector("#review-transcript-en").value, "");
  assert.equal(document.activeElement, document.querySelector('.success-screen[data-scenario="success"]'));
  dom.window.close();
});

test("review accordions disclose one task group at a time", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  assert.equal(document.querySelector('[data-group="learning"]').open, false);
  document.querySelector('[data-group="learning"] summary').click();
  assert.equal(document.querySelector('[data-group="learning"]').open, false);
  assert.equal(document.querySelector("[data-transcript-review]").open, true);
  document.querySelector("[data-review-transcript]").click();
  assert.equal(document.querySelector('[data-group="learning"]').open, true);
  document.querySelector('[data-group="time-comfort"] summary').click();
  assert.equal(document.querySelector('[data-group="learning"]').open, false);
  assert.equal(document.querySelector('[data-group="time-comfort"]').open, true);
  document.querySelector("[data-transcript-review] summary").click();
  assert.equal(document.querySelector("[data-transcript-review]").open, true);
  assert.equal(document.querySelector('[data-group="time-comfort"]').open, false);
  dom.window.close();
});

test("constrained details reject values outside approved choices", async () => {
  const dom = await render("locale=en&stage=review");
  const { document } = dom.window;
  document.querySelector('[data-edit-field="language"]').click();
  const editor = document.querySelector("#language-en");
  editor.value = "Klingon";
  input(dom.window, editor);
  document.querySelector('[data-save-field="language"]').click();
  assert.equal(editor.getAttribute("aria-invalid"), "true");
  assert.equal(document.querySelector('[data-field="language"] .editor-wrap').hidden, false);
  document.querySelector('button[data-locale="hi"]').click();
  assert.equal(document.querySelector('[data-field="language"] [data-field-error]').textContent, "सूची में दिया कोई विकल्प चुनें।");
  dom.window.close();
});

test("prototype markup has unique element ids", async () => {
  const dom = await render();
  const ids = [...dom.window.document.querySelectorAll("[id]")].map((node) => node.id);
  assert.equal(new Set(ids).size, ids.length);
  dom.window.close();
});
