---
name: SakhiCircle
description: A dignified, voice-first learning circle for women beginning again.
platform: "Mobile-first responsive web/PWA using React and Vite"
units: "CSS pixels and rem; typography respects browser zoom and user font settings"
colors:
  olive-primary: "#7A8450"
  olive-primary-hover: "#697343"
  cream-canvas: "#F8EFDA"
  cream-surface: "#EFE2C4"
  cream-selected: "#E5D5AD"
  rooted-ink: "#10140B"
  steady-muted: "#4D5338"
  gentle-border: "#7A8450"
  focus-ink: "#10140B"
  error-red: "#A12B32"
  google-blue: "oklch(0.48 0.18 255)"
typography:
  hero:
    fontFamily: "Noto Sans Devanagari"
    fontSize: "3rem desktop / 2rem narrow"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-0.025em"
  display:
    fontFamily: "Noto Sans Devanagari"
    fontSize: "2.125rem"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-0.5px"
  headline:
    fontFamily: "Noto Sans Devanagari"
    fontSize: "1.563rem"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-0.4px"
  body:
    fontFamily: "Noto Sans Devanagari"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Noto Sans Devanagari"
    fontSize: "1.063rem"
    fontWeight: 750
    lineHeight: 1.55
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.olive-primary}"
    textColor: "{colors.rooted-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "12px 20px"
    height: "54px"
  button-primary-pressed:
    backgroundColor: "{colors.olive-primary-hover}"
    textColor: "{colors.rooted-ink}"
  button-secondary:
    backgroundColor: "{colors.cream-canvas}"
    textColor: "{colors.rooted-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "12px 20px"
    height: "54px"
  text-input:
    backgroundColor: "{colors.cream-canvas}"
    textColor: "{colors.rooted-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "12px 16px 12px 50px"
    height: "54px"
---

# Design System: SakhiCircle

## 1. Overview

**Creative North Star: "The Trusted Clubhouse"**

SakhiCircle feels like entering a well-run community space where the welcome is immediate, the next activity is obvious, and help is always within reach. It carries Evergreen Club’s clarity, familiar real-world mental models, and strong icon-plus-label cues without reproducing its branding or layout.

The current Olive Cream revision uses cream for the application canvas, olive for actions and brand emphasis, and near-black Rooted Ink for accessible reading. The two requested colors are not used directly as normal-text/background pairs because their 3.50:1 contrast is below the 4.5:1 requirement. The system treats users as experienced adults and rejects generic social feeds, patronizing senior-wellness visuals, clinical dashboards, voice-only control, and dense enterprise navigation.

**Current visual evidence:** `docs/ui-review/mobile-shell.png` and `docs/ui-review/desktop-shell.png` (Olive Cream revision awaiting SC-081 approval on August 21, 2026). The earlier Tonal Sage reference remains preserved in `docs/ui-options/15-tonal-sage.png` as history.

**Key Characteristics:**

- Three clearly labelled primary destinations: Today, My Circle, and Mentors.
- 18px-equivalent body copy, 48px minimum targets, high contrast, and visible focus.
- A portrait-first sign-in screen whose required actions fit without page scrolling on supported phones.
- A 360×800 authenticated default view that fits without page scrolling; its optional three-step guide expands on demand and resets closed when the viewport becomes narrow.
- Voice assistance paired with transcripts, editing, confirmation, and text alternatives.
- Real-world confirmations such as a plainly structured session ticket.
- Respectful, people-centred imagery of Indian women aged 45 and above.

## 2. Colors

The palette pairs a cream application canvas and reading surfaces with restrained olive actions, near-black Rooted Ink, and olive-tinted neutrals.

### Primary

- **Olive Primary** (`#7A8450`): brand mark, primary buttons, emphasis, and action indicators.
- **Olive Primary Hover** (`#697343`): pressed and hover state for olive actions.
- **Cream Canvas** (`#F8EFDA`): application background and dominant reading surface.

### Secondary

- **Steady Muted** (`#4D5338`): secondary copy and inactive navigation on cream; it exceeds 4.5:1 on cream.

### Neutral

- **Cream Canvas** (`#F8EFDA`): application and reading background.
- **Cream Surface** (`#EFE2C4`): inputs, cards, navigation, and grouped content.
- **Cream Selected** (`#E5D5AD`): stronger tonal separation for selected states.
- **Rooted Ink** (`#10140B`): primary text, focus, and outlined controls; it reaches 4.65:1 on Olive Primary and 16.28:1 on Cream Canvas.
- **Olive Primary** (`#7A8450`): cream-surface dividers and field borders as well as the action color.
- **Google Blue** (`oklch(0.48 0.18 255)`): reserved exclusively for the official Google initial inside its authentication control.

**The Calm Shell Rule.** Brand and category colors never compete with navigation, labels, or reading content.

**The Meaningful Color Rule.** Color communicates action, category, or state; it is never scattered as decoration.

## 3. Typography

**Display and body font:** self-hosted Noto Sans Devanagari with Noto Sans fallback, rendered through the browser text system.

**Character:** One warm humanist stack carries English and Hindi consistently. Strong weight creates confidence; generous leading prevents density.

### Hierarchy

- **Hero** (800, `3rem` desktop / `2rem` narrow, 1.18): the single authenticated next-step promise; fixed per breakpoint rather than fluid.
- **Display** (800, `2.125rem`, 1.18): one screen-level promise or next step.
- **Headline** (800, `1.563rem`, 1.18): section headings.
- **Title** (800, `1.25rem`, 1.18): brand and component titles.
- **Body** (400, `1.125rem`, 1.55): all reading copy; cap wide-screen lines near 60 characters.
- **Label** (700–800, `1.063rem`, 1.45, sentence case): controls, navigation, and field labels.

**The Read-It-Once Rule.** A user should understand every heading, label, and confirmation on the first reading.

## 4. Elevation

The system is flat by default. Tonal surfaces and 1px borders create grouping; shadows are reserved for temporary overlays and fixed navigation.

### Shadow Vocabulary

- **Raised Mobile Navigation:** subtle CSS shadow equivalent to 12% Rooted Ink; separates the fixed three-item bar from content.

**The Flat-Until-Needed Rule.** If a surface is understandable without a shadow, it must not have one.

## 5. Components

Components are familiar and confident: 8–16px radii, visible labels, 48px or larger targets, pointer/touch/keyboard states, and restrained 180ms state feedback.

### Buttons

- **Shape:** confident soft rectangle (`8px` radius), minimum `54px` height for primary form actions.
- **Primary:** Olive Primary with Rooted Ink text and a 1px Olive Primary Hover border, `12px 20px` padding, weight 800.
- **Secondary:** Cream Canvas with a 1px Olive border; demo access and federated sign-in never compete with the primary action.
- **Pressed / Focus:** Olive Primary Hover while pressed; a visible Rooted Ink focus treatment for keyboard and switch access.
- **Secondary:** Cream Surface with a 2px Rooted Ink border; Cream Selected while pressed.

### Cards / Containers

- **Corner Style:** `12px` for compact status surfaces; `16px` for feature and empty-state cards.
- **Background:** Cream Surface or Cream Selected according to hierarchy.
- **Shadow Strategy:** none at rest; use borders and tonal changes.
- **Internal Padding:** `18–48px`, scaled by importance and window size.

### Inputs / Fields

- **Style:** 2px Olive Primary border, Cream Surface background, 8px radius, 54px minimum height.
- **Focus:** Rooted Ink border plus an external focus treatment visible to keyboard and switch users.
- **Error / Disabled:** Error Red for errors; disabled controls retain labels and use reduced opacity.

### Navigation

Exactly three icon-plus-label destinations: Today, My Circle, and Mentors. Below 900px, the PWA uses a safe-area-aware fixed cream bottom tab bar with at least 62px-high items. At wider widths, navigation becomes a cream viewport-left rail while the main content remains centered in the remaining canvas. The active item uses Rooted Ink on Cream Selected.

### Sign-in

The unauthenticated screen keeps the SakhiCircle logo, concise welcome copy, passwordless email, Google sign-in, and the explicit local-demo action in one portrait viewport on supported phones. The sign-in controls are the main visual focus; the illustrated Sakhi helper is compact and opens contextual help without pushing authentication below the fold.

### Session Ticket

The signature booking confirmation uses a familiar ticket structure and lists mentor, topic, language, date, time, payment status, and joining instructions in that order. It remains readable without color and never exposes card details.

### Video-guided Week

An automatically discovered playlist appears as a clearly labelled source block with its channel, language and caption confirmation, selection explanation, external-link action, API-data date, and YouTube privacy note. Inside an expanded week, assigned videos appear before daily practice. The week then exposes preparation, “Learning overview—not a transcript summary,” key points, what to expect, and expected result in that order. Video rows use familiar play and external-link cues, open in a new tab, and never autoplay or replace the written activities. A calm status card preserves the written plan when no suitable course is found or discovery is unavailable, and a saved plan offers an explicit refresh action.

## 6. Do's and Don'ts

### Do:

- **Do** keep default body text at 1.125rem and every interactive target at least 48px.
- **Do** pair every important icon with a visible text label.
- **Do** expose contextual “Need help?” and “How this works” guidance.
- **Do** show transcripts, editing, and confirmation beside every voice interaction.
- **Do** test core tasks with women aged 45 and above.

### Don't:

- **Don't** reproduce a generic social-media feed or hobby marketplace where popularity replaces purposeful learning.
- **Don't** use infantilizing “senior wellness” imagery, patronizing copy, oversized decoration, or assumptions about frailty.
- **Don't** create clinical mental-health dashboards or medicalized claims about loneliness and well-being.
- **Don't** ship voice-only experiences that hide transcripts, remove user control, or fail without speech input.
- **Don't** create dense enterprise dashboards with tiny text, weak contrast, unexplained scores, or complex navigation.
