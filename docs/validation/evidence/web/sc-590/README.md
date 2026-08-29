# SC-590 August 28 Vertical-Slice Evidence

Captured on 2026-08-26 in `Asia/Kolkata`.

## Status

- Local evidence: complete.
- Local user verification: approved on 2026-08-26 after completing the full English/Hindi journey and recommendation flow.
- Deployed evidence: moved to `SC-725`, after the approved cloud, analytics, persistent-adapter and deployment prerequisites.
- Product code changed: none.

## Local browser evidence

The in-app browser completed the real deterministic local flow against `http://localhost:5173` and `http://localhost:8080`:

1. Entered through the explicit synthetic Meera demo action.
2. Used the deterministic voice transcript, reviewed the extracted fields, and confirmed plan and matching consent.
3. Generated the 28-day bilingual journey, changed its English title to `My watercolour greeting-card month`, and explicitly saved it.
4. Requested the synthetic partner only after saving and received Kavita Demo at 100/100 with exactly three visible reasons.
5. Switched the saved result to reviewed Hindi copy without requesting another match.

| Capture | Evidence |
|---|---|
| `local-mobile-sign-in-360x800.jpg` | All sign-in actions fit; document and viewport are both 360×800; horizontal and vertical overflow are 0; visible controls are at least 48 CSS pixels high. |
| `local-mobile-journey-review-360x800.jpg` | Generated journey is explicitly labelled `Not saved yet`, exposes title editing, a start date, four weeks, and the fixed three-item mobile navigation. |
| `local-mobile-match-360x800.jpg` | Saved journey plus labelled synthetic Kavita Demo result and 100/100 score. |
| `local-mobile-match-full-360.jpg` | Full narrow-screen recommendation including all three explanation reasons. |
| `local-mobile-match-hindi-360x800.jpg` | The same saved journey and result in reviewed Hindi UI copy. |
| `local-desktop-match-1280x800.jpg` | Desktop result with the navigation rail at x=0, centered main content, all three reasons visible, and zero horizontal overflow. |

The first manual attempt reached a retry state because an August 25 API process was still serving `/api/v1/profile` but returned `404` for `/api/v1/journeys`. The exact stale SakhiCircle web/API processes were verified, stopped, and replaced with `pnpm dev:local`; the current-source flow then completed end to end.

## API and automated evidence

- Local startup contract: 1/1 passed.
- Current local readiness: `status=ready`, `adapterMode=deterministic`, `paidApiCallsEnabled=false`.
- Focused onboarding/journey/recommendation web tests: 14/14 passed.
- Focused profile/journey/matching/recommendation API tests: 33/33 passed.
- Focused mobile/desktop journey and recommendation browser tests: 4/4 passed.
- Complete FastAPI suite: 44/44 passed.
- Complete Playwright suite: 34/34 passed across 360×800 mobile and 1280×800 desktop.
- Production TypeScript/Vite PWA build: passed; service worker and precache generated.
- Complete web unit suite: 31/33 passed. The two unchanged failures are the previously documented legacy Today/Watercolour preview expectations at `apps/web/src/test/App.test.tsx:165` and `apps/web/src/test/App.test.tsx:179`; no assertion was deleted, skipped, weakened, or rewritten.

Red-test evidence is not applicable because SC-590 captures existing behavior and changes no product code.

## Deployed evidence sequence

The user approved the corrected sequence on 2026-08-26: `SC-600` → `SC-700`/G7 → `SC-705` → `SC-710` → `SC-715` → `SC-720` → `SC-725`. `SC-725` now owns Firebase Hosting, Cloud Run `/health`, and deployed browser evidence, so the approved local evidence can close `SC-590` without misrepresenting local output as a cloud deployment.
