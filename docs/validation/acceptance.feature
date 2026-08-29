Feature: SakhiCircle website/PWA judged vertical slice
  SakhiCircle must let a learner move from sign-in to an editable learning journey
  and an explainable recommendation using bilingual, accessible interactions and synthetic data.

  Rule: Local and deployed application shell
    Scenario: Accessible unauthenticated entry
      Given the application has no authenticated user
      Then the login screen explains SakhiCircle in plain language
      And offers passwordless email and Google sign-in states
      And every input and action has an accessible name
      And the complete sign-in flow fits at 360 by 800 CSS pixels without page scrolling

    Scenario: Demo access is development-only
      Given demo mode is enabled
      Then a synthetic learner can enter with one explicit demo action
      But the demo action is absent when demo mode is disabled

    Scenario: Simple bilingual navigation
      Given the learner is authenticated
      Then narrow-screen navigation has exactly "Today", "My Circle", and "Mentors"
      And Hindi mode uses reviewed Hindi labels for the same destinations
      And at desktop width navigation touches the viewport left edge while content remains centered

    Scenario: Web accessibility baseline
      Given the PWA runs in a supported phone or desktop browser
      Then each screen fits its available width
      And interactive targets are at least 48 CSS pixels in both dimensions
      And all functionality is reachable by touch, keyboard, and screen reader
      And login and app shell have no critical or serious automated accessibility findings
      And 200 percent zoom does not hide required actions

    Scenario: Local and cloud parity
      Given cloud adapters are unavailable
      Then the complete judged flow runs with deterministic local adapters or Firebase emulators
      And no paid API call is made
      When production adapters are explicitly configured
      Then the same browser contracts use Firebase Hosting, Cloud Run, and Firestore

  Rule: Confirmed bilingual learning wish
    Scenario: Voice or text input requires confirmation
      Given a learner uses voice or text
      When SakhiCircle extracts hobby, experience, goal, availability, language, accessibility, format, consent, and optional city
      Then the learner sees an editable transcript and structured summary
      And no data is persisted before explicit confirmation
      And raw audio is never stored

  Rule: Safe four-week journey
    Scenario: Editable journey generation
      Given confirmed learning-wish data
      When a journey is generated
      Then it contains 28 dated activities with duration, instructions, accessible alternative, reflection prompt, and safety note
      And the output conforms to the versioned journey schema
      And the learner can edit or reject it before persistence

    Scenario: Deterministic fallback
      Given the configured Gemini workflow is unavailable or returns invalid output twice
      Then SakhiCircle returns a curated bilingual journey template
      And it clearly identifies that the fallback was used

  Rule: Explainable recommendation
    Scenario: Deterministic match from synthetic data
      Given consented compatible candidates and blocked incompatible candidates
      When recommendations are requested
      Then hard filters remove blocked or incompatible candidates
      And no more than three results score at least 65 out of 100
      And each result shows the strongest three score factors
      And translated explanations cannot change ranking

  Rule: Analytics, privacy, and operations
    Scenario: Pseudonymous checkpoint event
      Given a journey or recommendation event is emitted
      Then analytics contain no name, email, transcript, raw text, exact location, credential, or raw audio
      And an identical event identifier is written at most once

    Scenario: Fail-closed production configuration
      Given required production credentials or project configuration are missing
      When a protected integration is called
      Then it fails with an actionable configuration error
      And it never falls back to demo credentials
