import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const repoFile = (path) => new URL(`../../${path}`, import.meta.url);

test("SC-300 defines the complete bilingual edit-before-save onboarding contract", () => {
  const specification = readFileSync(
    repoFile("docs/implementation/SC-300_ONBOARDING_UX.md"),
    "utf8",
  );
  const prototype = readFileSync(
    repoFile("docs/ui-review/sc-300-onboarding-prototype.html"),
    "utf8",
  );
  const combined = `${specification}\n${prototype}`;

  for (const field of [
    "hobby",
    "experience",
    "goal",
    "availability",
    "language",
    "accessibility",
    "format",
    "consent",
    "city",
  ]) {
    assert.match(combined, new RegExp(`data-field=["']${field}["']`));
  }

  assert.match(prototype, /data-locale="en"/);
  assert.match(prototype, /data-locale="hi"/);
  assert.match(prototype, /data-stage="capture"/);
  assert.match(prototype, /data-stage="review"/);
  assert.match(combined, /Nothing has been saved/i);
  assert.match(combined, /अभी कुछ भी सेव नहीं हुआ है/);
  assert.match(combined, /raw audio[^.]*never stored/i);
  assert.match(combined, /कच्ची ऑडियो[^।]*कभी सेव नहीं/i);
  assert.match(combined, /transcript[^.]*discarded/i);
  assert.match(combined, /ट्रांसक्रिप्ट[^।]*हटा दी जाएगी/i);
  assert.match(combined, /Confirm and create my 4-week plan/);
  assert.match(combined, /पुष्टि करें और मेरी 4-सप्ताह की योजना बनाएँ/);

  assert.match(prototype, /const onboardingDraft\s*=/);
  assert.match(prototype, /data-shared-transcript/);
  assert.match(prototype, /data-group="learning"/);
  assert.match(prototype, /data-group="time-comfort"/);
  assert.match(prototype, /data-group="preferences-permission"/);
  assert.match(prototype, /data-consent="plan"/);
  assert.match(prototype, /data-consent="matching"/);
  assert.match(prototype, /data-consent="plan"[^>]*required/);
  assert.match(prototype, /aria-current="step"/);
  assert.match(prototype, /मुख्य नेविगेशन/);
  assert.match(prototype, /मीरा शर्मा प्रोफ़ाइल/);
  assert.match(prototype, /data-field-editor/);
  assert.doesNotMatch(prototype, /contentEditable|contenteditable/);

  for (const scenario of [
    "empty",
    "mic-denied",
    "unsupported",
    "missing",
    "changed",
    "save-error",
    "success",
  ]) {
    assert.match(combined, new RegExp(`data-scenario=["']${scenario}["']`));
  }

  assert.match(combined, /My words look right/);
  assert.match(combined, /मेरे शब्द सही हैं/);
  assert.match(combined, /create my private 4-week plan/i);
  assert.match(combined, /मेरी निजी 4-सप्ताह की योजना/);
  assert.match(combined, /suggest compatible people/i);
  assert.match(combined, /उपयुक्त लोगों के सुझाव/);
  assert.match(combined, /speech provider/i);
  assert.match(combined, /स्पीच सेवा/);
  assert.match(prototype, /@media \(min-width: 900px\)/);
  assert.doesNotMatch(prototype, /body \{ font-size: 17px/);
  assert.match(prototype, /\.help-button \{ min-height: 48px/);
  assert.match(prototype, /\.edit-action, \.save-field \{ min-height: 48px/);
  assert.match(prototype, /\.draft-state \{[^}]*font-size: 0\.94rem/s);
  assert.match(prototype, /\.field-label \{[^}]*font-size: 0\.94rem/s);
  assert.match(prototype, /\.label-help,[^}]*font-size: 0\.94rem/s);
});
