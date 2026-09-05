# SakhiCircle MVP Workboard

This file is the cross-chat source of truth. Each task targets one independently reviewable outcome, normally 20–60 minutes, and stops after evidence and any required approval.

## Status vocabulary

- `DONE`: evidence produced and required approval received.
- `SUPERSEDED`: preserved history replaced by a later approved direction.
- `READY`: dependencies and approvals satisfied.
- `AWAITING APPROVAL`: evidence or decision is ready for the user.
- `BLOCKED`: a named dependency is missing.
- `PENDING`: not ready to start.

## Non-negotiable workflow

1. Read `AGENTS.md`, `PRODUCT.md`, `DESIGN.md`, `SakhiCircle Technical Requirements.md`, `docs/validation/acceptance.feature`, and this file.
2. Work on one task ID only and add or update the relevant test first.
3. Confirm the focused test fails for the missing behavior before implementation.
4. Run focused tests, then complete web-client and backend suites.
5. Update this workboard and `CHAT_HANDOFF.md`, show UI/API/test evidence, and stop.

## Approval gates

| Gate | Decision | Status | Unlocks |
|---|---|---|---|
| G1 | Olive Cream visual revision | `DONE` — approved 2026-08-21 | Revised web design system |
| G2 | Mobile-first website/PWA, local-first and Google Cloud architecture | `DONE` — directed 2026-08-21 | Web foundation |
| G3 | Local responsive web shell and one-command environment | `DONE` — approved 2026-08-22 | Authentication and onboarding |
| G4 | Authentication, data, voice and privacy boundary | `DONE` — approved 2026-08-22 | Confirmed profile and journey flow |
| G5 | Journey schema, deterministic fallback and bounded ADK workflow | `DONE` — approved 2026-08-25 | Gemini integration |
| G6 | Explainable matching and synthetic data contract | `DONE` — approved 2026-08-26 | Recommendation flow |
| G7 | Analytics schema, deployment and cost controls | `DONE` — approved 2026-08-28 | BigQuery/Looker and final deployment |

## 0 — Governance and platform history

| ID | Outcome | Validation | Status |
|---|---|---|---|
| SC-000 | Create workboard, architecture review and handoff protocol | Documents link correctly | `DONE` |
| SC-010 | Select Tonal Sage visual direction | User approved visual board | `DONE` |
| SC-020–SC-030 | Lock and approve original browser architecture | Historical browser evidence | `DONE` — later superseded |
| SC-040–SC-060 | Plan, build and validate Android-only migration | Android source and evidence preserved | `SUPERSEDED` for active product work |
| SC-065 | Submit Patchamomma idea checkpoint form | User confirmed submission | `DONE` — 2026-08-21 |
| SC-070 | Restore website/PWA as primary product and record narrowed build-phase plan | Active documents agree; Android labelled frozen | `DONE` — directed 2026-08-21 |

## 1 — Local website foundation

| ID | Small outcome | Depends on | Validation | Status |
|---|---|---|---|---|
| SC-080 | Lock tests for the primary web shell, mobile no-scroll sign-in and desktop alignment | G2 | New assertions fail only for missing current behavior | `DONE` — approved 2026-08-21 |
| SC-081 | Reconcile and polish the responsive web shell and user-requested Olive Cream palette | SC-080 | Focused unit/browser tests pass at 360×800 and desktop | `DONE` — approved 2026-08-21 |
| SC-082 | Add one local command for website, FastAPI and deterministic adapters/emulators | SC-081 | Clean start exposes health/readiness and no paid calls | `DONE` — approved 2026-08-22 |
| SC-083 | Verify local access from `localhost` and a phone on the same Wi-Fi | SC-082 | Both clients complete sign-in/demo entry | `DONE` — approved 2026-08-22 |
| SC-084 | Present local responsive shell evidence for G3 | SC-083 | User approves screenshots and startup evidence | `DONE` — approved 2026-08-22 |

## 2 — August 28 vertical slice

| ID | Small outcome | Depends on | Validation | Status |
|---|---|---|---|---|
| SC-200 | Present web authentication/data/voice/privacy boundary for G4 | G3 | User approves token, App Check, transcript and deletion boundaries | `DONE` — approved 2026-08-22 |
| SC-210 | Implement deterministic demo and configured Firebase Auth/App Check states | G4 | Auth, App Check and demo-gating tests pass; missing production config fails closed | `DONE` — approved 2026-08-24 |
| SC-300 | Approve English/Hindi speak-or-type onboarding fields and confirmation UX | SC-210 | Mobile/desktop designs show edit-before-save | `DONE` — approved 2026-08-24 |
| SC-310 | Implement text-first onboarding with deterministic voice transcript adapter | SC-300 | Nothing persists before confirmation; raw audio absent | `DONE` — approved 2026-08-25 |
| SC-400 | Approve versioned 28-day journey schema and fallback contract for G5 | SC-310 | Schema, reviewer, retry and bilingual fallback approved | `DONE` — approved 2026-08-25 |
| SC-410 | Implement deterministic journey generation and editable confirmation | G5 | English/Hindi fixtures and browser journey pass | `DONE` — approved 2026-08-26 |
| SC-500 | Approve matching filters, weights and explanation contract for G6 | SC-410 | Hard filters, score threshold and explanation factors approved | `DONE` — approved 2026-08-26 |
| SC-510 | Generate synthetic profiles and implement one explainable recommendation | G6 | Deterministic ranking and forbidden-candidate tests pass | `DONE` — approved 2026-08-26 |
| SC-590 | Capture and approve the August 28 local vertical-slice evidence | SC-510 | End-to-end local browser flow, tests and screenshots recorded | `DONE` — approved 2026-08-26 |

## 3 — September checkpoints

| ID | Small outcome | Depends on | Validation | Status |
|---|---|---|---|---|
| SC-600 | Connect one bounded Gemini/ADK journey workflow behind deterministic fallback | SC-590 | Versioned output passes English/Hindi safety evaluation | `DONE` — approved 2026-08-27 |
| SC-700 | Approve pseudonymous analytics schema and cloud-cost controls for G7 | SC-600 | Allowed properties, retention, budgets and quotas approved | `DONE` — approved 2026-08-28 |
| SC-705 | Provision the Google Cloud/Firebase project and approved cost guardrails | G7 | Auth, App Check, private/reporting datasets, Cloud Tasks, Mumbai IAM and approved billing-currency alerts verified | `DONE` — approved 2026-09-02; no product traffic deployed |
| SC-706 | Implement persistent application quotas and operator cost switches | SC-705 | India-day counters, Gemini zero-allowance, maintenance and fail-closed tests pass | `DONE` — approved 2026-09-02 |
| SC-710 | Implement server-authoritative idempotent BigQuery event and one Looker Studio proof | SC-706 | Signed-receipt, durable-task, duplicate, forged-outcome and reporting-isolation integration tests pass | `DONE` — configured phases 1–8 and approved Looker proof complete 2026-09-03 |
| SC-715 | Implement persistent Firestore profile, journey and recommendation adapters | SC-710 | Emulator integration tests pass; production never uses process-memory state or demo credentials | `DONE` — approved 2026-09-03 |
| SC-720 | Deploy PWA to Firebase Hosting and FastAPI to Cloud Run | SC-715 | Preview/live URLs, `/health`, 0–2 runtime controls, maintenance, secret scan and local fallback pass | `DONE` — completed 2026-09-05; authenticated live profile save returned 200 |
| SC-725 | Capture and approve the deployed English/Hindi vertical-slice evidence | SC-720 | Real browser flow, Cloud Run API evidence and mobile/desktop screenshots recorded | `DONE` — user approved 2026-09-06; authenticated screenshots waived by explicit direction |
| SC-730 | Complete accessibility/usability QA and backup demonstration video | SC-725 | Keyboard, screen reader, 200% zoom and judged flow pass | `READY` |
| SC-750 | Lock September 7 submission | SC-730 | Tagged release, README, architecture diagram and demo script approved | `PENDING` |

## Deferred after the vertical slice

Production payments, full circle posting/chat, mentor marketplace operations, native distribution, and additional agent workflows remain outside the active build-phase critical path.

## Current next task

`SC-725` is complete and user-approved. Firebase Hosting sign-in fits 360×800 with zero overflow; the user verified the authenticated English/Hindi flow at mobile and desktop sizes and reported that it works as designed. Cloud Run request metadata independently confirms HTTP 200 for profile save, journey creation, journey confirmation, and recommendation on revision `sakhicircle-api-00003-qdv`. Additional authenticated screenshots were waived by explicit user direction. `SC-730` is ready. Keep the Mumbai queue and Looker Studio report paused.
