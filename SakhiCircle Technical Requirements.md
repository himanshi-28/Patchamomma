# SakhiCircle Build-Phase Technical Requirements

## 1. Current objective

Build an accessible English/Hindi mobile-first progressive web application demonstrating one connected, data-driven journey:

1. A learner signs in through a deterministic demo or configured Firebase Authentication.
2. She speaks or types a skill she wants to begin or restart.
3. SakhiCircle produces an editable four-week learning journey.
4. She receives one explainable peer or mentor recommendation from synthetic data.
5. A pseudonymous event appears in a small BigQuery/Looker Studio analytics proof.

The Patchamomma 2026 idea checkpoint form was submitted on 2026-08-21. The next checkpoint is August 28. The MVP succeeds when the complete journey works locally without paid services and through a shareable Google Cloud deployment without manual data changes during the demonstration.

## 2. Scope and technology

### Current stack

| Layer | Technology |
|---|---|
| Product client | React, TypeScript, Vite, installable PWA in `apps/web` |
| Local experience | Vite, FastAPI, deterministic adapters, Firebase Local Emulator Suite |
| Authentication | Firebase Authentication web SDK; development-only synthetic demo session |
| Operational data | Cloud Firestore in `asia-south1` |
| Backend | Python FastAPI on Cloud Run in `asia-south1` |
| AI | Gemini API through a server-side adapter; one bounded ADK journey workflow after deterministic behavior passes |
| Voice | Browser microphone input with visible transcript, edit, confirmation, and complete text alternative |
| Analytics | BigQuery dataset `sakhi_analytics` and one Looker Studio checkpoint view |
| Hosting | Firebase Hosting for the PWA; Netlify only as a fallback |
| Security | Firebase App Check web provider, Firestore Rules, Secret Manager, Cloud IAM |

`apps/mobile` remains frozen historical Android evidence. Do not extend or delete it during the web build phase without explicit approval.

### August 28 vertical slice

| Capability | Required behavior |
|---|---|
| Entry | Concise no-scroll sign-in at 360×800, English/Hindi switch, configured auth states, explicit development demo |
| Learning wish | Speak or type hobby, experience, goal, available time, language, accessibility need, format, consent, and optional city |
| Confirmation | Show editable transcript and structured fields; persist nothing before explicit confirmation |
| Journey | Generate 28 dated activities containing duration, instructions, accessible alternative, reflection prompt, and safety note |
| Recommendation | Apply deterministic hard filters and scoring; return up to three results with the three strongest reasons |
| Analytics proof | Write an idempotent pseudonymous event and show one checkpoint query or Looker Studio view |
| Local/cloud parity | The same browser flow works with local fakes/emulators and with explicitly configured Google services |

### Deferred until after the vertical slice

- Production mentor payments and Razorpay checkout.
- Full circle posting, real-time chat, notifications, and moderation operations.
- Mentor course-builder workflow and production marketplace operations.
- Native Android distribution and app-store submission.
- Multiple agents beyond the single journey planner/reviewer/localizer workflow.

## 3. Interfaces, data, and intelligence

### Initial API boundary

| Method and endpoint | Responsibility |
|---|---|
| `GET /health` | Public deployment and local readiness check |
| `PUT /api/v1/profile` | Validate and save confirmed onboarding data |
| `POST /api/v1/journeys` | Generate or return a deterministic four-week journey |
| `GET /api/v1/recommendations?type=partner\|mentor` | Return ranked, explainable recommendations |
| `POST /api/v1/analytics/events` | Validate and idempotently write an allowed pseudonymous event |

Protected production endpoints require a Firebase ID token and App Check token. Tests and local demonstration use explicit adapters; missing production configuration fails closed rather than silently using demo credentials.

### Synthetic data source

Generate deterministic data containing 250 learner profiles, 40 mentors, 15 hobbies, 25 future circle records, and 90 days of synthetic learning and matching activity. Every record is labelled synthetic. Do not include real names, emails, transcripts, exact locations, voice recordings, payment credentials, or confidential work data.

### Explainable matching

Apply hard filters first: active consent, compatible hobby, shared language, overlapping availability, compatible format, and no block or previous rejection. Score hobby/goal fit, schedule, language, skill level, pace, format, and price where applicable. Return only candidates scoring at least 65/100 and display the strongest three factors. Gemini may translate an explanation but must never change a deterministic score or ranking.

### Journey workflow

Implement deterministic journey fixtures before connecting Gemini. The later bounded ADK workflow is:

`plan generator → accessibility/safety reviewer → English/Hindi localizer`

All outputs use versioned Pydantic JSON. Validate dates, activity count, durations, required fields, language, and safety constraints. Retry invalid AI output once, then return a curated bilingual template. The learner can edit or reject the result before persistence.

For every confirmed, non-sensitive learning topic, attempt automatic discovery through the official YouTube Data API v3 using only normalized topic, derived level, and preferred language. Schema `1.2.0` carries a recommendation status plus, when verified, exact playlist/video metadata and bilingual weekly guidance. Every week receives one or two ordered videos within the learner's weekly time budget, with prerequisites, a clearly labelled non-transcript learning overview, key points, expectations, and an observable result. Written journeys and expiring YouTube metadata are stored separately; failure or expiry must never remove or block the written journey. Production enablement requires a restricted server-only key, an approved privacy-policy URL, daily quotas, and a maximum 29-day metadata TTL.

### Analytics

Send allowlisted backend events to partitioned BigQuery tables using pseudonymous identifiers. The checkpoint dashboard covers journey creation, match recommendation, and confirmation rates. It must not contain names, emails, transcripts, exact locations, raw text, or raw audio.

## 4. Experience, security, and quality

### Web and accessibility requirements

- Meet WCAG 2.2 AA with visible keyboard focus, semantic landmarks, screen-reader names, 48×48 CSS-pixel targets, 200% zoom/text scaling, reduced motion, and text alternatives for voice.
- Keep every sign-in action visible without page scrolling at a supported 360×800 viewport.
- Below 900px, use exactly three safe-area-aware bottom destinations: Today, My Circle, and Mentors.
- At wider widths, place navigation at the viewport’s left edge and center the content within the remaining canvas.
- Show a usable sign-in screen within 2.5 seconds on a representative mid-range phone browser.
- Cache the application shell and current confirmed journey for read-only offline access; show pending/synchronized state for queued progress later.

### Security and cost controls

- Keep Gemini credentials and service-account material only in Secret Manager and server runtime configuration.
- Use deny-by-default Firestore and Storage rules, least-privilege identities, and production App Check.
- Never store raw voice audio; hold transcripts only until confirmation unless the user explicitly saves the text.
- Set Cloud Run minimum instances to `0`, maximum to `2`, and configure budget alerts at USD 10, 25, and 40.
- Automated tests use deterministic fakes and make no paid API calls.

### Required verification

| Test group | Checkpoint cases |
|---|---|
| Unit | Bilingual copy, journey schema, matching filters/weights, event allowlist and idempotency |
| Integration | Firebase Emulator rules, authenticated FastAPI calls, deterministic journey and analytics adapters |
| Browser | 360×800 no-scroll sign-in, 200% zoom, keyboard navigation, English/Hindi, journey confirmation and match explanation |
| Accessibility | Automated axe checks plus manual keyboard and screen-reader smoke tests |
| Deployment | Firebase Hosting URL, Cloud Run `/health`, production configuration failure, secret scan and local fallback |

## 5. Checkpoints

| Date | Demonstrable outcome |
|---|---|
| August 21 | Idea form submitted; website/PWA direction and narrowed vertical slice recorded |
| August 28 | Local and deployed sign-in → learning wish → editable journey flow, plus explainable synthetic match |
| September 5 | Gemini workflow, analytics proof, bilingual/accessibility QA, architecture diagram and backup video |
| September 7 | Submission lock: tagged release, live URLs, README, demo script and reproducible local fallback |

## 6. Boundaries

- One primary developer; prioritize a polished judged path over broad feature count.
- India, INR, `Asia/Kolkata`, English, and Hindi remain the product defaults.
- No real payments, production payouts, exact-location discovery, video calling, direct messaging, or health claims in the checkpoint MVP.
- Firebase Hosting and Cloud Run are the primary deployment targets; the complete flow must also remain locally demonstrable.
- Existing Android source and evidence remain available only as a frozen reference.
