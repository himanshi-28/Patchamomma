# SakhiCircle

SakhiCircle is a bilingual, mobile-first learning and mentorship PWA for Indian women aged 45 and above. It is designed for voice-first use, while the current submitted experience is deliberately text-first until the microphone interaction completes its product and accessibility review.

## Final submission status

- The user-confirmed deployment is [https://sakhi-circle.web.app/](https://sakhi-circle.web.app/).
- The verified FastAPI origin is [https://sakhicircle-api-859217028205.asia-south1.run.app](https://sakhicircle-api-859217028205.asia-south1.run.app).
- `apps/web` is the primary React, TypeScript, Vite and installable PWA client. `apps/mobile` is frozen historical Android evidence.

The user confirmed the current submission URL on September 10. The September 6 evidence records a successful production sign-in, confirmed profile save, journey creation and save, explainable synthetic recommendation, English/Hindi use, and responsive mobile/desktop behavior. That evidence used production data adapters with paid API calls disabled. Later Gemini and YouTube implementation is described below as implemented and configuration-gated, not as independently verified in that deployment snapshot.

## What the product does

1. A learner signs in using a Firebase email link or Google account, then types and reviews the hobby or skill she wants to begin or restart.
2. She confirms structured details before anything is stored and chooses a two-, four-, six-, or eight-week plan; four weeks is the default judged path.
3. SakhiCircle returns an editable English/Hindi journey using deterministic generation or a configured Gemini and bounded ADK workflow with a curated bilingual fallback.
4. A configuration-gated YouTube Data API integration can add verified, sequential video guidance without replacing or blocking the written plan.
5. The learner can request an explainable peer or mentor recommendation from deterministic synthetic data, while pseudonymous outcomes feed the analytics proof.

The Today and My Plan journey, matching result, demo circle directory, and demo mentor activity centre are visible product surfaces. Circles and mentor activities remain synthetic demonstrations: real chat, booking, payments, payouts and marketplace operations are not production features.

## Architecture

Firebase Hosting serves the PWA. Firebase Authentication establishes identity, Firebase App Check attests production requests, and the browser sends both tokens to FastAPI on Cloud Run in `asia-south1`. Firestore and Storage client rules deny access by default, so confirmed profiles, journeys, synthetic matching data, quotas and analytics delivery state are handled through the API rather than direct browser reads.

The journey boundary supports deterministic local generation and a configured Gemini + bounded ADK sequence: plan generator, safety/accessibility reviewer, English/Hindi localizer, strict Pydantic validation, one retry, then a curated bilingual fallback. The YouTube Data API path sends only a normalized topic, derived level and preferred language; verified public metadata and generated learning guidance are stored separately from the written journey with a maximum 29-day lifetime.

Successful product endpoints derive allowlisted pseudonymous events on the server. A Firestore analytics outbox passes an opaque delivery handle to Cloud Tasks, which calls an OIDC-protected internal worker. The worker performs an idempotent BigQuery write. Looker Studio reads only an aggregate reporting view, never the row-level table.

See [the as-implemented architecture review](docs/implementation/ARCHITECTURE_REVIEW.md).

## Privacy and failure boundaries

- The current UI accepts text. A browser speech adapter exists behind the interface boundary, but the unfinished microphone control is not exposed.
- Unconfirmed text and drafts stay in browser memory; the verbatim transcript and raw audio are never persisted.
- Production API routes require a verified Firebase ID token and Firebase App Check token. Demo identities are development-only.
- Secrets remain server-side. Analytics excludes identity, transcript, learner text, exact location, credentials, match identities and audio.
- Production settings fail closed when required identity, App Check, Firestore, secret, quota, YouTube or analytics configuration is missing; they never substitute demo credentials.

## Local setup

1. Run `pnpm install`.
2. Create a Python 3.11+ virtual environment and run `pip install -e 'services/api[dev]'`.
3. Run `pnpm dev:local`.
4. Open `http://localhost:5173`; health and readiness are at `http://localhost:8080/health` and `http://localhost:8080/ready`.

The local command binds the website and API to `0.0.0.0`, enables the explicit synthetic demo session, selects deterministic in-memory adapters and disables paid calls. Firebase Auth, Firestore, Hosting and Storage emulator ports are reserved in `firebase.json` for the optional emulator profile. The browser contracts and API shapes remain the same in local and production modes.

## Validation

- Locked acceptance behavior: `docs/validation/acceptance.feature`
- Complete quality gate: `pnpm test:quality`
- Web unit and accessibility tests: `pnpm --filter @sakhicircle/web test`
- Browser journey tests: `pnpm --filter @sakhicircle/web test:e2e`
- Backend tests: `.venv/bin/python -m pytest services/api/tests`

Deployment evidence is recorded in `docs/validation/evidence/web/sc-725`. No real learner data, raw audio, API keys, service-account credentials, payment secrets or confidential work data belongs in this repository.
