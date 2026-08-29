# SakhiCircle

SakhiCircle is a voice-first, mobile-first learning and mentorship PWA for Indian women aged 45 and above.

## Build-phase status

- The Patchamomma 2026 idea checkpoint form was submitted on 2026-08-21.
- `apps/web` is again the primary product client using React, TypeScript, Vite, and PWA support.
- `services/api` remains the Python FastAPI boundary for local development and Cloud Run.
- `apps/mobile` is frozen as historical Android evidence; do not add product features or delete it without explicit approval.
- The August 28 target is one deployed vertical slice: sign-in, English/Hindi input, editable four-week journey, explainable match, and one analytics proof.

## Local setup

1. Install dependencies with `pnpm install`.
2. Create `.venv` with Python 3.11+ and install `pip install -e 'services/api[dev]'`.
3. Start the complete local environment with `pnpm dev:local`.
4. Open `http://localhost:5173`; API health is at `http://localhost:8080/health` and explicit readiness is at `http://localhost:8080/ready`.

The command binds the website and API to `0.0.0.0`, enables only the synthetic demo session, selects deterministic adapters, and disables paid API calls. Stop both services together with `Ctrl+C`. Run `pnpm test:local` to verify the command contract without starting either service.

`firebase.json` reserves the Firebase Auth, Firestore, Hosting, and Storage emulator configuration. The deterministic adapter profile is the supported zero-credential default; a later adapter task may explicitly select the emulator profile when those feature boundaries are implemented.

## Deployment direction

- Website: Firebase Hosting.
- API: FastAPI on Cloud Run in `asia-south1`.
- Operational data: Firebase Authentication and Firestore.
- Intelligence: Gemini through a server-controlled adapter, with deterministic fallbacks in tests.
- Analytics: pseudonymous events in BigQuery with a small Looker Studio proof.

Netlify is a fallback only. Local development must remain complete and demonstrable without paid API calls.

## Validation

- Locked behavior: `docs/validation/acceptance.feature`
- Web unit tests: `pnpm --filter @sakhicircle/web test`
- Web browser tests: `pnpm --filter @sakhicircle/web test:e2e`
- Web build: `pnpm --filter @sakhicircle/web build`
- Backend tests: `.venv/bin/python -m pytest services/api/tests`
- Historical Android evidence: `docs/validation/evidence/native/README.md`

No real user data, raw audio, API keys, payment credentials, or confidential work data belongs in this repository.
