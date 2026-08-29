---
target: SC-300 onboarding prototype
total_score: 20
p0_count: 0
p1_count: 4
timestamp: 2026-08-24T14-16-41Z
slug: docs-ui-review-sc-300-onboarding-prototype-html
---
# SC-300 onboarding prototype critique

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 2/4 | Progress, draft, listening, and privacy states exist; extraction, validation, saving, and failure feedback do not. |
| 2 | Match System / Real World | 3/4 | Respectful plain language; “compatible people” and provisional symbols remain vague. |
| 3 | User Control and Freedom | 2/4 | Back and editing exist, but language switching forks the draft and apparent controls are inert. |
| 4 | Consistency and Standards | 2/4 | Visual parity is strong; assistive labels and form state are not bilingual equivalents. |
| 5 | Error Prevention | 2/4 | Consent gates confirmation, but missing required fields do not and structured fields use unconstrained contenteditable text. |
| 6 | Recognition Rather Than Recall | 2/4 | Desktop co-locates transcript and summary; mobile separates them by several screens of scrolling. |
| 7 | Flexibility and Efficiency | 2/4 | Speak/type and inline editing are offered; keyboard semantics and interruption recovery are weak. |
| 8 | Aesthetic and Minimalist Design | 2/4 | Calm and legible, but the long ledger and uniform beige surfaces create administrative density. |
| 9 | Error Recovery | 1/4 | Permission denial, unsupported speech, missing details, extraction failure, and save failure are absent. |
| 10 | Help and Documentation | 2/4 | Inline instructions help, but no contextual “Need help?” entry exists at difficult decisions. |
| **Total** | | **20/40** | **Acceptable — significant improvements needed before approval** |

## Anti-Patterns Verdict

The interface does not look obviously AI-generated. It avoids gradient text, glass, oversized radii, ghost-card shadows, repetitive icon cards, and decorative animation. The deterministic scan returned zero findings.

The remaining AI residue is subtle: placeholder-like `▣`, `●●`, and `◇` navigation symbols; repeated heading/helper/rounded-surface composition; an empty beige desktop transcript column; and little SakhiCircle personality beyond palette and Hindi copy. Browser overlay injection was blocked by the browser URL security policy, so screenshots and DOM inspection were used instead.

## Overall Impression

The opening earns trust: voice and text share one visible field, the transcript stays editable, consent is unchecked, and the storage boundary is repeated at the right moments. The review then turns a personal aspiration into a long compliance audit. The single biggest opportunity is to preserve one bilingual draft while turning review into a short, grouped checklist with explicit recovery states.

## What’s Working

1. Trust and agency are explicit: nothing is saved, the transcript remains editable, consent is unchecked, and transcript disposal is stated clearly.
2. English/Hindi visual parity covers capture, review, fields, consent, privacy, and navigation.
3. The physical baseline is thoughtful: 18px body text, 48px actions, visible focus, flat surfaces, and reduced-motion handling.

## Cognitive Load

Six of eight checks fail: chunking, visual hierarchy, one thing at a time, minimal choices, working memory, and progressive disclosure. Mobile review is 360×2608px in English and 360×2504px in Hindi. It exposes Update, eight Edit actions, consent, Back, and Confirm in one uninterrupted task.

## Emotional Journey

The opening question is dignified and the raw-audio reassurance arrives at the vulnerable moment. The emotional valley is the repetitive eight-row audit. The ending is a disabled low-emphasis button plus a storage footnote, so the strongest moment is the opening and the weakest is the end.

## Priority Issues

### [P1] Language switching forks onboarding state

English and Hindi own separate capture textareas, review textareas, summaries, and consent checkboxes. Switching changes only the displayed locale. An edit or consent choice in one language disappears in the other.

- **Fix:** Use one locale-independent draft object for transcript, nine fields, consent, and stage. Translate labels only; preserve the learner’s words unless she explicitly requests translation. Preserve focus and announce the language change.
- **Suggested command:** `$impeccable harden`

### [P1] Assistive semantics fail at stage, language, and Edit interactions

Stage/locale changes hide the focused button without moving focus. Progress lacks `aria-current="step"`. Repeated Edit buttons do not name their field. Generic `<p contenteditable>` controls do not provide field semantics. Hindi mode retains English accessible names for home, profile, navigation, and progress.

- **Fix:** Use field-specific native controls, field-specific accessible names, localized landmarks, `aria-current="step"`, and focus the new screen heading after stage/language changes.
- **Suggested command:** `$impeccable audit`

### [P1] Mobile review is a three-viewport compliance ledger

The transcript, eight fields, consent, and confirmation form one long mobile page. Users must remember the transcript while checking fields much farther down.

- **Fix:** Let the learner mark the transcript reviewed and collapse it to a reopenable summary. Group fields into Learning, Time & comfort, and Preferences & permission, with at most four visible fields per group. Keep the next action reachable above bottom navigation; make the desktop transcript sticky.
- **Suggested command:** `$impeccable distill`

### [P1] Required contract states are missing or inert

The contract names empty, denied/unsupported microphone, missing-detail, changed-field, save-failure, retry, and success states. The prototype demonstrates only the populated happy path. “Update details from my words” has no handler; confirmation checks only consent.

- **Fix:** Add reviewable states for empty input, denied/unsupported speech, missing required fields, changed extraction, saving, failure with retry, and success. Use constrained controls for experience, availability, language, accessibility, and format.
- **Suggested command:** `$impeccable harden`

### [P2] Consent and the absolute audio promise need sharper boundaries

Plan creation and people recommendations share one required checkbox. “Compatible people” does not explain visibility or use. “Raw audio is never stored” cannot be proven by a prototype whose voice button only changes visual state.

- **Fix:** Decide whether plan creation and matching require separate consent. Explain which details power each purpose. Lock a speech architecture that can support the storage claim, or disclose browser/provider processing precisely.
- **Suggested command:** `$impeccable clarify`

## Persona Red Flags

### Jordan — first-timer

- The capture screen looks pre-filled without identifying the narrative as sample data.
- Capture asks for hobby, goal, and time, but review unexpectedly requires eight non-consent details.
- “Update details,” profile, and two navigation links appear functional without useful outcomes.
- No contextual help entry exists at speech, editing, or consent decisions.

### Sam — keyboard/screen-reader user

- Focus remains on hidden controls after stage and language changes.
- Repeated Edit actions do not identify their field.
- Current progress is visual only.
- Hindi mode exposes English landmark and profile labels.
- Navigation and helper text drop below the project’s 18px-equivalent reading baseline.

### Casey — distracted mobile user

- Capture exceeds one viewport and review exceeds three; primary actions are not in the initial thumb zone.
- Bottom navigation competes with unfinished onboarding.
- The memory-only draft is lost on refresh, eviction, or restart.
- Denied or unsupported speech fallback is described but not demonstrated.

## Minor Observations

1. “SakhiCircle home” points to main content rather than home.
2. `#circle` and `#mentors` targets do not exist.
3. The approved hobby label and prototype review label differ.
4. Disabled confirmation text is faint for the high-legibility audience.
5. Generic symbols and sparkle mark feel provisional.

## Questions to Consider

1. Should private plan creation and matching consent remain inseparable?
2. Should language switching preserve the learner’s words verbatim or offer a separate confirmed translation?
3. Does app navigation need to remain actionable during unfinished onboarding?
4. Which speech architecture can prove the raw-audio promise across both SakhiCircle and the browser/provider?
