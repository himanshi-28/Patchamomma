---
target: SC-300 onboarding prototype
total_score: 36
p0_count: 0
p1_count: 0
timestamp: 2026-08-24T15-09-28Z
slug: docs-ui-review-sc-300-onboarding-prototype-html
---
# SC-300 onboarding prototype — post-fix critique

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of System Status | 4/4 | Capture, validation, saving, failure, retry, changed rows, and success are explicit. |
| 2 | Match System / Real World | 4/4 | Plain bilingual language and purpose-specific consent match the learner's task. |
| 3 | User Control and Freedom | 4/4 | Back, editing, language switching, optional matching, Retry, and recovery preserve the draft and focus. |
| 4 | Consistency and Standards | 4/4 | One shared draft, localized accessible names/errors, native controls, and consistent 18px/48px baselines. |
| 5 | Error Prevention | 3/4 | Required and constrained values fail closed; extraction remains a deterministic preview rather than product implementation. |
| 6 | Recognition Rather Than Recall | 4/4 | Transcript-first review and mutually exclusive groups keep one bounded task visible. |
| 7 | Flexibility and Efficiency | 3/4 | Voice/type and bilingual editing are represented, but actual voice input belongs to SC-310. |
| 8 | Aesthetic and Minimalist Design | 3/4 | The structure is calm and concise; current post-fix visual captures could not be regenerated for final visual scoring. |
| 9 | Error Recovery | 4/4 | All seven recovery scenarios are represented and behavior-tested, including focus and draft preservation. |
| 10 | Help and Documentation | 3/4 | Contextual Help and provider-boundary copy are present; the implemented provider link belongs to SC-310. |
| **Total** | | **36/40** | **Excellent design contract; ready for approval after visual evidence refresh** |

## Anti-Patterns Verdict

The revised interface does not read as AI-generated. It uses the established Olive Cream system, consistent inline icons, restrained surfaces, one-task disclosure, and field-specific language. The deterministic Impeccable scan returned `[]`; no false positives or waived findings remain.

No reliable browser overlay is available. The in-app browser blocked the local `file://` prototype under its URL policy, and no workaround was attempted.

## Overall Impression

The flow now preserves the emotional strength of “begin again” without turning review into a compliance ledger. One shared bilingual draft, transcript-first disclosure, exact changed-row marking, separate consent, and complete recovery states make the design contract coherent and implementable.

## What's Working

1. Trust boundaries are precise: SakhiCircle storage is distinguished from browser speech-provider processing, plan and matching permissions are separate, and success actually clears the transcript.
2. The mobile review is bounded: only transcript or one three-to-four-item section can be open, with 18px body text and 48px minimum targets.
3. Recovery is first-class: empty, denied, unsupported, missing, changed, save-error, retry, and success behavior preserve context and move focus deliberately.

## Priority Issues

No P0, P1, or P2 design issues remain in the independent post-fix assessment.

### [P3] Refresh visual approval evidence

The existing SC-300 PNG files predate the hardened revision. The capture script is prepared to produce eight core and seven state captures, serious/critical axe checks, 48px-target checks, and 320px/200% reflow checks, but it was not run because local browser access was blocked by the active browser safety policy.

## Persona Red Flags

- **Jordan — first-timer:** no blocking red flags remain; Help, plain-language recovery, and transcript-first review explain the unfamiliar flow.
- **Sam — keyboard/screen-reader user:** no blocking red flags remain in source/behavior checks; localized landmarks, field-specific actions, live status, current-step semantics, and recovery focus are covered.
- **Casey — distracted mobile user:** no blocking red flags remain; one open group, preserved draft, explicit Retry, and separate optional matching reduce abandonment risk.

## Minor Observations

1. Voice capture, provider selection/linking, and persistence remain simulations by design and must be implemented test-first in SC-310 only after approval.
2. The unchanged app unit baseline still has two legacy Today/Watercolour failures unrelated to SC-300; build, API, and E2E remain green.

## Questions to Consider

No new design decision is required. The user already selected full P1 remediation, three grouped sections, and separate plan/matching consent.
