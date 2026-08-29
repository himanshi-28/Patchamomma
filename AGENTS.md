# SakhiCircle Engineering Instructions

## Source of truth

- Read `PRODUCT.md`, `DESIGN.md`, and `SakhiCircle Technical Requirements.md` before changing product behavior.
- `docs/validation/acceptance.feature` is the locked acceptance contract.

## Test-first gate

- Add or update the relevant test before implementing a feature.
- Run the focused test and confirm it fails for the expected missing behavior.
- Do not delete, skip, weaken, or rewrite an approved assertion to make implementation pass.
- After implementation, run focused tests, then the complete web-client and backend suites.
- Stop after each delivery part and present UI, API, and test evidence for user approval.

## Commands

- Web tests: `pnpm --filter @sakhicircle/web test`
- Web build: `pnpm --filter @sakhicircle/web build`
- Web browser tests: `pnpm --filter @sakhicircle/web test:e2e`
- Backend tests: `.venv/bin/python -m pytest services/api/tests`
- Local website: `pnpm --filter @sakhicircle/web dev --host 0.0.0.0`
- Local API: `.venv/bin/python -m uvicorn app.main:app --app-dir services/api --reload --port 8080`

`apps/web` is the primary product client. `apps/mobile` is frozen historical Android evidence and must not receive new product features or be deleted without explicit approval.

## Safety

- Never commit API keys, service-account credentials, user transcripts, or payment secrets.
- Automated tests must use deterministic fakes instead of paid APIs.
- Raw audio must never be persisted.
- Production-only integrations must fail closed when configuration is missing.
