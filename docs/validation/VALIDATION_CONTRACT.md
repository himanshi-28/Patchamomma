# SakhiCircle Locked Validation Contract

Approved on 16 August 2026.

## Enforcement

1. Acceptance behavior is specified in `acceptance.feature` before feature code.
2. Each delivery part adds executable tests for its scenarios before implementation.
3. The focused test run must fail because the behavior is absent, not because the test is malformed.
4. Approved assertions cannot be deleted, skipped, weakened, or inverted without explicit user approval.
5. A part is complete only after focused tests, complete suites, build checks, and user evidence review pass.

## Evidence required after every part

- Changed-file list and architecture decisions.
- Before/after test result showing red then green.
- Browser screenshots at 360×800 and representative desktop width, including overflow and alignment evidence.
- Keyboard, screen-reader, accessible-name, 200% zoom/text-scaling, reduced-motion, and automated axe results.
- Local `localhost` evidence, phone-on-LAN evidence, and the equivalent Firebase Hosting/Cloud Run health evidence once deployed.
- Known limitations and the next part’s proposed tests.

## Human usability gate

Before the final checkpoint, at least three women aged 45 or above must attempt sign-in, learning-wish confirmation, journey review, and recommendation review. Record completion, assistance prompts, time, errors, and qualitative confusion points without recording private speech or personal data.
