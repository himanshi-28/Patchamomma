# General YouTube-guided journeys

## Learner outcome

Every confirmed learning topic receives an automatic attempt to find one suitable, sequential
YouTube playlist. A verified course is divided into one or two videos per requested week, within
the learner's weekly time budget. Each week includes prerequisites, a learning overview, key
points, expectations, and an observable result in English and Hindi.

The written journey is complete on its own. No match, a safety-sensitive topic, quota exhaustion,
provider failure, malformed metadata, or guide-generation failure returns the reviewed written
plan with an honest status instead of an invented link.

## Data boundary

Only the normalized topic, derived level, and preferred language are sent to YouTube. Transcripts,
goals, city, accessibility choices, learning format, identity, and contact details are not included
in the YouTube query. The learner goal may be used by the bounded Gemini guide workflow after the
public playlist metadata has been retrieved.

Search uses the official YouTube Data API v3 with `type=playlist`, `safeSearch=strict`, `regionCode=IN`,
the preferred language hint, and at most five candidates. Playlist order and metadata come from
`playlists.list`, `playlistItems.list`, and `videos.list`. Private, deleted, duplicated, live,
incomplete, and longer-than-three-hour videos are removed.

## Trust and lifecycle

- Schema `1.2.0` exposes `videoRecommendation.status` as `recommended`, `no_match`, `unavailable`,
  or `not_applicable`.
- YouTube titles, channel names, identifiers, order, durations, and URLs are copied from verified
  API metadata. Generated output can select identifiers but cannot create or alter source metadata.
- SakhiCircle copy is visibly labelled “Learning overview—not a transcript summary.”
- Written journeys and expiring YouTube enrichment are stored separately. Metadata expires after
  at most 29 days; access then returns the retained written plan. Learners can explicitly refresh.
- Searches are limited to five per learner and twenty per project per India day. Identical discovery
  requests use a 15-minute in-memory cache.
- Medical, therapeutic, dietary, financial, hazardous, illegal, and other safety-sensitive topics
  skip external discovery.

## Production configuration

`SAKHI_YOUTUBE_DISCOVERY_ENABLED` defaults to false. Enabling it requires a restricted,
server-only `SAKHI_YOUTUBE_API_KEY`; production also requires an owner-approved
`SAKHI_PRIVACY_POLICY_URL`. Cloud Run reads the API key from Secret Manager. The key must be
restricted to YouTube Data API v3 and must never be exposed to browser code, logs, fixtures, or the
repository. Firestore TTL must be enabled for `youtube_recommendations_v1.expiresAt`.

The interface links to YouTube without autoplay, attributes the source, labels language/caption
confirmation, and links to YouTube Terms and Google's Privacy Policy.
