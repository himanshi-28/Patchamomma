# SC-300 — Speak-or-type onboarding and confirmation UX

Status: **DONE — APPROVED 2026-08-24**  
Scope: design contract only; no product data, microphone access, API call, or persistence is implemented in this task.

## Approval decision

Approve one two-stage flow for English and Hindi:

1. **Share your learning wish.** The learner can speak or type in her own words. Voice always produces a visible, editable transcript; text uses the same field. Microphone permission is requested only after she chooses “Start speaking”.
2. **Review before saving.** The learner first marks the editable transcript as correct, then checks three grouped sections: Learning; Time & comfort; Preferences & permission. Every structured field has an explicit, field-specific Edit action. The primary action says exactly what confirmation will do.

The mobile flow is one readable accordion above the existing three-destination navigation; it does not present all fields at once. Only one task group is open at a time: transcript first, then Learning, Time & comfort, and Preferences & permission. Desktop uses a sticky transcript column and the same three grouped sections inside the existing centered canvas. The bottom navigation remains in use below 900px. This is a normal page, not a modal.

English and Hindi views share one in-memory draft. Switching interface language changes labels, instructions, and accessible names but never replaces or translates the learner's transcript or edits. Focus moves to the active screen heading and the language change is announced.

## Fields shown before confirmation

| Field key | English label | Hindi label | Requirement |
|---|---|---|---|
| <span data-field="hobby">hobby</span> | What would you like to learn? | आप क्या सीखना चाहती हैं? | Required free text; never inferred without being shown |
| <span data-field="experience">experience</span> | Your experience | आपका अनुभव | Required choice plus optional clarification |
| <span data-field="goal">goal</span> | Your first goal | आपका पहला लक्ष्य | Required free text |
| <span data-field="availability">availability</span> | Time you can give | आप कितना समय दे सकती हैं? | Required duration and weekly frequency |
| <span data-field="language">language</span> | Plan language | योजना की भाषा | Required: English, Hindi, or both |
| <span data-field="accessibility">accessibility</span> | What would make learning easier? | सीखना आसान बनाने के लिए क्या चाहिए? | Required answer; “No support needed right now” is valid |
| <span data-field="format">format</span> | How you prefer to learn | आप कैसे सीखना पसंद करेंगी? | Required: individual/group and online/in-person preference |
| <span data-field="consent">consent</span> | Permission to create the plan | योजना बनाने की अनुमति | Required unchecked checkbox; not inferred from voice or text |
| <span data-field="city">city</span> | City (optional) | शहर (वैकल्पिक) | Optional broad city only; never exact location |

Matching permission is a separate optional unchecked checkbox. It may use hobby, language, schedule, format, and city to suggest compatible people. It is not required to create a plan and can be changed later.

## Capture states

- **Empty:** one labelled textarea, “Start speaking” secondary action, and “Review my details” disabled until the learner has entered words.
- **Listening:** the same button becomes “Stop listening”; a live status says “Listening…” and the transcript remains visible as it changes.
- **Permission denied / unsupported:** keep the textarea active, move focus to a short inline message, and say how to continue by typing. No dead end.
- **Transcript ready:** do not auto-advance. The learner chooses “Review my details”.
- **Missing detail:** review may open, but the missing structured row is marked “Please add this” and confirmation stays disabled.
- **Changed detail:** deterministic re-extraction marks the changed row and announces it; it never silently replaces a reviewed value.
- **Save error:** the draft remains visible, the failure is named without claiming success, and Retry preserves the draft.
- **Success:** only the reviewed fields cross the save boundary; the temporary transcript is discarded.

Capture privacy copy:

- English: **SakhiCircle never records or stores raw audio. Nothing is saved until you confirm.** A browser speech provider may process audio under its own terms. Before microphone permission, the implemented experience must name the selected provider and show its policy.
- Hindi: **SakhiCircle कच्ची ऑडियो रिकॉर्ड या सेव नहीं करता। आपकी पुष्टि तक कुछ भी सेव नहीं होता।** ब्राउज़र की स्पीच सेवा अपनी शर्तों पर ऑडियो संसाधित कर सकती है। माइक्रोफ़ोन की अनुमति से पहले लागू अनुभव सेवा का नाम और उसकी नीति दिखाएगा।

## Review and editing behavior

- Lead with **“Nothing has been saved” / “अभी कुछ भी सेव नहीं हुआ है”**.
- The transcript is a labelled textarea, not read-only display text. “My words look right” / “मेरे शब्द सही हैं” explicitly completes this check and collapses the transcript on mobile.
- “Update details from my words” re-runs local/deterministic extraction and visibly marks any structured row that changed. It does not persist anything.
- Each non-consent structured row has a field-specific Edit action and a native input. Experience, availability, language, accessibility, and format accept only reviewed choices; an arbitrary value produces an inline accessible error and is not saved. Editing happens inline in that row; an unsaved edit survives language switching, and saving returns focus to the same row.
- Plan consent is always an explicit required unchecked checkbox: **“I agree SakhiCircle may use these reviewed details to create my private 4-week plan.” / “मैं सहमत हूँ कि SakhiCircle इन जाँचे हुए विवरणों से मेरी निजी 4-सप्ताह की योजना बनाए।”**
- Matching consent is a second, optional unchecked checkbox: **“Also use hobby, language, schedule, format and city to suggest compatible people. You can change this later.” / “शौक, भाषा, समय, सीखने का तरीका और शहर इस्तेमाल करके उपयुक्त लोगों के सुझाव भी दें। इसे बाद में बदल सकती हैं।”**
- Voice and transcript content cannot select either checkbox. Matching remains optional and is not needed to create the private 4-week plan.
- “Back to my words” preserves the in-memory draft for this session.
- Confirmation uses **“Confirm and create my 4-week plan” / “पुष्टि करें और मेरी 4-सप्ताह की योजना बनाएँ”**.
- After confirmation, only the nine reviewed structured fields are sent to the profile boundary. **The transcript is discarded after confirmation.**
- Hindi equivalent: **पुष्टि के बाद ट्रांसक्रिप्ट हटा दी जाएगी।**

## Persistence boundary

Before confirmation:

- raw microphone audio: never stored;
- transcript and field draft: browser memory only;
- Firestore, localStorage, sessionStorage, analytics, and FastAPI profile writes: none.

The prototype also exposes deterministic review queries for `data-scenario="empty"`, `data-scenario="mic-denied"`, `data-scenario="unsupported"`, `data-scenario="missing"`, `data-scenario="changed"`, `data-scenario="save-error"`, and `data-scenario="success"` so every recovery state can be approved without external services.

After confirmation:

- save only the reviewed structured fields through the authenticated profile API;
- discard the raw audio and verbatim transcript;
- emit no raw text or transcript in analytics;
- if the save fails, keep the review screen visible, identify the failure, and provide one retry action without claiming success.
- after a successful save, clear the transcript from the shared in-memory draft and every synchronized transcript control before showing and focusing the success state.

## Review evidence

The standalone prototype is `docs/ui-review/sc-300-onboarding-prototype.html`. It contains English and Hindi capture/review states and intentionally cannot access the microphone or save data. Core captures use 360×800 and 1280×800 viewports; focused state evidence also covers narrow/reflow behavior and recovery paths.

User approval of this design contract on 2026-08-24 unlocked SC-310. Any later copy, field, or layout change requires a newly scoped revision rather than silently changing the approved contract.
