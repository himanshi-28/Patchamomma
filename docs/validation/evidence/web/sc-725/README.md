# SC-725 Deployed English/Hindi Vertical-Slice Evidence

Started on 2026-09-05 in `Asia/Kolkata`.

## Status

- SC-725 is complete and user-approved on 2026-09-06.
- Firebase Hosting serves the live PWA at `https://patchamomma-2026-505415.web.app`.
- Cloud Run `/health` and `/ready` return HTTP 200 in production mode with paid API calls disabled.
- The 360×800 English sign-in capture is complete with zero horizontal or vertical overflow.
- The user completed the authenticated English/Hindi mobile and desktop flow in regular Chrome and reported that it works as designed. The user explicitly directed that no additional screenshots be requested.

## Completed evidence

`deployed-mobile-sign-in-en-360x800.jpg` shows every production sign-in action in one 360×800 viewport. The page uses Firebase Authentication and contains no development-only demo action.

Read-only Cloud Run inspection found revision `sakhicircle-api-00003-qdv` ready with 100% traffic, minimum instances 0, maximum instances 2, concurrency 20, and timeout 30 seconds.

Read-only request metadata independently verifies the completed production path on revision `sakhicircle-api-00003-qdv`: profile save HTTP 200, journey creation HTTP 200, journey confirmation HTTP 200, recommendation HTTP 200, and associated analytics events HTTP 202. No request body or private user value was read.

## Reproducible verification sequence

1. In regular Chrome, open the Firebase Hosting URL and set DevTools responsive dimensions to 360×800.
2. Sign in with Google, choose the first hobby, and type: `I want to restart watercolours and paint a greeting card. I can practise for 30 minutes, four days a week. I prefer Hindi, larger text, seated alternatives, and a small online group in Pune.`
3. Review the extracted details, mark the transcript correct, enable plan and matching permission, confirm, and review the editable four-week plan before saving.
4. Save the plan, find the learning partner, verify a labelled synthetic Kavita Demo match at 100/100 with exactly three reasons, then switch to Hindi and verify the same result.
5. Set the responsive dimensions to 1280×800, switch back to English, and verify the desktop result with the left navigation rail and no horizontal overflow.

## Privacy boundary

Use typed synthetic words only. No raw audio is recorded or stored. No transcript belongs in this evidence folder; the application discards it after confirmed structured details are saved. Do not capture an account chooser, email address, profile menu, token, credential, or any other personal data.

The authenticated verification is recorded through the user's explicit approval plus independent Cloud Run request metadata. Additional authenticated screenshots are intentionally not required by the user's 2026-09-06 direction.
