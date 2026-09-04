WITH daily_counts AS (
  SELECT
    event_date,
    COUNTIF(event_name = 'profile_confirmed') AS confirmed_profiles,
    COUNTIF(event_name = 'journey_draft_created') AS journey_drafts_created,
    COUNTIF(event_name = 'journey_confirmed') AS journeys_confirmed,
    COUNTIF(
      event_name = 'recommendation_presented'
      AND recommendation_outcome = 'matched'
    ) AS recommendations_matched,
    COUNTIF(
      event_name = 'recommendation_presented'
      AND recommendation_outcome = 'no_matches'
    ) AS recommendations_no_matches
  FROM `sakhi_analytics.checkpoint_events_v1`
  WHERE event_date BETWEEN DATE_SUB(CURRENT_DATE("Asia/Kolkata"), INTERVAL 89 DAY)
    AND CURRENT_DATE("Asia/Kolkata")
  GROUP BY event_date
)
SELECT
  event_date,
  confirmed_profiles,
  journey_drafts_created,
  journeys_confirmed,
  recommendations_matched,
  recommendations_no_matches,
  SAFE_DIVIDE(journey_drafts_created, confirmed_profiles)
    AS journey_drafts_per_confirmed_profile,
  SAFE_DIVIDE(journeys_confirmed, journey_drafts_created)
    AS journey_confirmations_per_draft,
  SAFE_DIVIDE(
    recommendations_matched + recommendations_no_matches,
    journeys_confirmed
  ) AS recommendations_per_confirmed_journey
FROM daily_counts
