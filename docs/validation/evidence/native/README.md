# Frozen native shell validation evidence

Date: 2026-08-21

Status: `FROZEN HISTORICAL REFERENCE — ACTIVE PRODUCT IS THE WEB/PWA`

This directory records the superseded Android implementation. It is not an active delivery gate for the website-first Patchamomma build phase.

## What now works

- Portrait-only Expo Router application for Android with no iOS or web target.
- One-viewport sign-in at 360×800 with keyboard compaction and no `ScrollView`.
- English/Hindi copy, guided Sakhi dialog, deterministic demo session, Today, My Circle, Mentors, and exactly three safe-area-aware tabs.
- Reduced-motion-aware 180ms state transitions and bounded large-text behavior.
- Existing FastAPI endpoints and schemas are unchanged.

## Automated evidence

| Gate | Result | Evidence |
| --- | --- | --- |
| React Native unit tests | PASS | 3 suites, 14 tests |
| TypeScript | PASS | `tsc --noEmit` |
| Android JavaScript export | PASS | Android bundle and 31 assets exported |
| Android native build | PASS | Gradle, 511 tasks; debug APK at `apps/mobile/android/app/build/outputs/apk/debug/app-debug.apk` |
| FastAPI regression | PASS | 3 tests |
| Expo Doctor | PARTIAL | 20/21 checks; SDK 56's documented Hermes V1 memory regression remains |
| Maestro | BLOCKED | Three attempts stopped after Maestro 2.8 lost its API 36/ADB 37 device connection; direct ADB remains stable |
| Frozen web regression | PARTIAL | 7/9 pass; two locked legacy expectations are stale (`Today` heading and `Upcoming in your circle`) |

## Android portrait evidence

- [Sign-in at 360×800](android/sign-in-360x800.png)
- [Keyboard-visible compact sign-in](android/keyboard-visible-360x800.png)
- [Portrait lock after a landscape request](android/portrait-lock-landscape-request.png)
- [Guided Sakhi help with three topics](android/sakhi-help-360x800.png)
- [Today with exactly three tabs](android/today-360x800.png)
- [Hindi Today state](android/today-hindi-360x800.png)
- [Sign-in at 200% text with reduced motion](android/sign-in-text-200-reduced-motion.png)

The orientation diagnostic reported `mLastOrientation=1` and `DisplayRotation=ROTATION_0` after requesting a 90-degree user rotation, confirming that the activity remained portrait.

## Manual checks still required

1. Complete TalkBack and external-keyboard focus audits.
2. Restore a stable Maestro host/device connection and run every flow in `apps/mobile/.maestro`.
3. Review screenshots without development-client overlays using an Android preview build.

## Android-only cleanup

On 2026-08-21 the user replaced the Android/iOS target with Android-only React Native. The generated iOS project, CocoaPods installation/cache, and project-downloaded iOS Simulator runtime were removed. Xcode remains because the user installed it directly and it is outside the authorized cleanup target.

## Preservation lock

`apps/mobile` and this evidence remain intact as historical reference. Do not add product features to the Android client or delete it without explicit user approval. Current work resumes in `apps/web` under `SC-080`.
