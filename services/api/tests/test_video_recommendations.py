import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.journey import JourneyDocument
from app.main import create_app
from app.persistence import (
    InMemoryJourneyRepository,
    InMemoryProfileRepository,
    InMemoryRecommendationRepository,
)
from app.quotas import InMemoryQuotaCounterStore, QuotaExceeded, QuotaService
from app.video_recommendations import (
    DiscoveredPlaylist,
    DiscoveredVideo,
    DiscoveryRequest,
    GeneratedVideoRecommendation,
    GeneratedWeeklyVideoGuide,
    GoogleYouTubeDiscovery,
    VideoDiscoveryUnavailable,
    VideoRecommendationService,
)

AUTH_HEADERS = {"Authorization": "Bearer demo-learner-token"}
NOW = datetime(2026, 9, 9, 10, 0, tzinfo=UTC)


def profile(hobby: str = "Piano", *, weeks: int = 4, language: str = "Hindi") -> dict:
    return {
        "hobby": hobby,
        "experience": "New to this",
        "goal": f"Learn the foundations of {hobby}",
        "availability": "30 minutes · 4 days a week",
        "language": language,
        "accessibility": "Larger text · seated alternatives",
        "format": "At home · individual",
        "planWeeks": weeks,
        "planConsent": True,
        "matchingConsent": False,
        "city": "Pune",
    }


def candidate(topic: str = "Piano", *, video_count: int = 8) -> DiscoveredPlaylist:
    return DiscoveredPlaylist(
        playlistId="PLgeneralCourse12345",
        title=f"{topic} beginner course",
        channelTitle="Example Teacher",
        description=f"A sequential beginner {topic} course.",
        totalVideoCount=video_count,
        defaultLanguage="en",
        videos=[
            DiscoveredVideo(
                videoId=f"lesson{i:05d}",
                title=f"{topic} lesson {i}",
                description=f"Foundation lesson {i}.",
                position=i - 1,
                durationSeconds=12 * 60,
                defaultLanguage="en",
                captionsAvailable=True,
            )
            for i in range(1, video_count + 1)
        ],
    )


def generated(weeks: int = 4) -> GeneratedVideoRecommendation:
    return GeneratedVideoRecommendation(
        playlistId="PLgeneralCourse12345",
        languageMatch="fallback",
        selectionNote={
            "en": "A sequential beginner course divided across your plan.",
            "hi": "क्रमिक शुरुआती पाठ्यक्रम आपकी योजना में बाँटा गया है।",
        },
        weeks=[
            GeneratedWeeklyVideoGuide(
                videoIds=[f"lesson{week:05d}"],
                prerequisites={
                    "en": ["Prepare a quiet practice space."],
                    "hi": ["शांत अभ्यास स्थान तैयार रखें।"],
                },
                summary={"en": f"Build foundation {week}.", "hi": f"आधार {week} बनाएँ।"},
                keyPoints={"en": ["Practise slowly."], "hi": ["धीरे अभ्यास करें।"]},
                whatToExpect={
                    "en": "The first attempt may feel unfamiliar.",
                    "hi": "पहला प्रयास नया लग सकता है।",
                },
                expectedResult={
                    "en": "Demonstrate one small skill.",
                    "hi": "एक छोटा कौशल करके दिखाएँ।",
                },
            )
            for week in range(1, weeks + 1)
        ],
    )


class ScriptedDiscovery:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    async def discover(self, request):
        self.requests.append(request)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class ScriptedGenerator:
    def __init__(self, outcome):
        self.outcome = outcome
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return self.outcome


def service(discovery_outcome=None, generator_outcome=None) -> VideoRecommendationService:
    return VideoRecommendationService(
        discovery=ScriptedDiscovery(
            discovery_outcome if discovery_outcome is not None else [candidate()]
        ),
        generator=ScriptedGenerator(
            generator_outcome if generator_outcome is not None else generated()
        ),
        clock=lambda: NOW,
    )


def create_journey(
    hobby: str, *, recommendation_service, weeks: int = 4, language: str = "Hindi"
) -> dict:
    app = create_app(
        Settings(app_env="test", demo_mode=True),
        video_recommendation_service=recommendation_service,
    )
    client = TestClient(app)
    assert (
        client.put(
            "/api/v1/profile",
            headers=AUTH_HEADERS,
            json=profile(hobby, weeks=weeks, language=language),
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/journeys", headers=AUTH_HEADERS, json={"startsOn": "2026-09-10"}
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize("topic", ["Piano", "Gardening", "Microsoft Excel", "Kathak"])
def test_every_general_learning_topic_can_receive_a_verified_playlist(topic: str) -> None:
    journey = create_journey(
        topic,
        recommendation_service=service([candidate(topic)], generated()),
    )

    assert journey["schemaVersion"] == "1.2.0"
    assert journey["videoRecommendation"]["status"] == "recommended"
    assert journey["recommendedPlaylist"]["selectionMethod"] == "automatic"
    assert journey["recommendedPlaylist"]["languageMatch"] == "fallback"
    assert journey["recommendedPlaylist"]["fetchedAt"] == NOW.isoformat().replace("+00:00", "Z")
    assert journey["recommendedPlaylist"]["expiresAt"] == (
        NOW + timedelta(days=29)
    ).isoformat().replace("+00:00", "Z")
    assert [len(week["videoGuide"]["videos"]) for week in journey["weeks"]] == [1, 1, 1, 1]
    assert journey["weeks"][0]["videoGuide"]["videos"][0]["title"] == f"{topic} lesson 1"


@pytest.mark.parametrize("weeks", [2, 4, 6, 8])
def test_video_assignment_covers_every_requested_week_within_the_time_budget(weeks: int) -> None:
    journey = create_journey(
        "Piano",
        weeks=weeks,
        recommendation_service=service([candidate(video_count=weeks)], generated(weeks)),
    )

    assert len(journey["weeks"]) == weeks
    assert all(len(week["videoGuide"]["videos"]) in {1, 2} for week in journey["weeks"])
    assert all(
        sum(video["durationSeconds"] for video in week["videoGuide"]["videos"]) <= 30 * 60 * 4
        for week in journey["weeks"]
    )


def test_no_match_and_provider_failure_keep_the_written_plan() -> None:
    no_match = create_journey("Origami", recommendation_service=service([], None))
    unavailable = create_journey(
        "Pottery",
        recommendation_service=service(VideoDiscoveryUnavailable("secret provider detail"), None),
    )

    assert no_match["videoRecommendation"]["status"] == "no_match"
    assert unavailable["videoRecommendation"]["status"] == "unavailable"
    assert "recommendedPlaylist" not in no_match
    assert "recommendedPlaylist" not in unavailable
    assert all(len(journey["weeks"]) == 4 for journey in [no_match, unavailable])
    assert "secret provider detail" not in str(unavailable)


@pytest.mark.parametrize(
    "topic", ["investment advice", "medical treatment", "dangerous chemical experiments"]
)
def test_safety_sensitive_topics_never_call_youtube(topic: str) -> None:
    discovery = ScriptedDiscovery([candidate(topic)])
    recommendation_service = VideoRecommendationService(
        discovery=discovery,
        generator=ScriptedGenerator(generated()),
        clock=lambda: NOW,
    )

    journey = create_journey(topic, recommendation_service=recommendation_service)

    assert journey["videoRecommendation"]["status"] == "not_applicable"
    assert discovery.requests == []


def test_generated_ids_must_belong_to_one_discovered_playlist() -> None:
    invalid = generated()
    invalid.weeks[0].video_ids = ["notInCourse"]

    journey = create_journey(
        "Piano",
        recommendation_service=service([candidate()], invalid),
    )

    assert journey["videoRecommendation"]["status"] == "unavailable"
    assert "recommendedPlaylist" not in journey


def test_enabled_youtube_discovery_requires_a_server_key() -> None:
    with pytest.raises(ValueError, match="SAKHI_YOUTUBE_API_KEY"):
        Settings(youtube_discovery_enabled=True)


def test_confirmed_journey_contract_rejects_tampered_youtube_urls() -> None:
    journey = create_journey("Piano", recommendation_service=service())
    journey["recommendedPlaylist"]["url"] = "https://example.com/playlist"

    with pytest.raises(ValueError, match="YouTube"):
        JourneyDocument.model_validate(journey)


def test_current_journey_and_explicit_video_refresh_are_available() -> None:
    recommendation_service = service()
    app = create_app(
        Settings(app_env="test", demo_mode=True),
        video_recommendation_service=recommendation_service,
    )
    client = TestClient(app)
    client.put("/api/v1/profile", headers=AUTH_HEADERS, json=profile())
    draft = client.post(
        "/api/v1/journeys",
        headers=AUTH_HEADERS,
        json={"startsOn": "2026-09-10"},
    ).json()
    client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        headers=AUTH_HEADERS,
        json=draft,
    )

    current = client.get("/api/v1/journeys/current", headers=AUTH_HEADERS)
    refreshed = client.post(
        f"/api/v1/journeys/{draft['journeyId']}/video-recommendation",
        headers=AUTH_HEADERS,
    )

    assert current.status_code == 200
    assert current.json()["status"] == "confirmed"
    assert refreshed.status_code == 200
    assert refreshed.json()["videoRecommendation"]["status"] == "recommended"


def test_learner_can_delete_video_metadata_without_deleting_the_written_plan() -> None:
    repository = InMemoryJourneyRepository()
    app = create_app(
        Settings(app_env="test", demo_mode=True),
        journey_repository=repository,
        profile_repository=InMemoryProfileRepository(),
        recommendation_repository=InMemoryRecommendationRepository(),
        video_recommendation_service=service([candidate()], generated(4)),
    )
    client = TestClient(app)
    client.put("/api/v1/profile", json=profile(), headers=AUTH_HEADERS)
    draft = client.post("/api/v1/journeys", json={"startsOn": "2026-09-10"}, headers=AUTH_HEADERS).json()
    saved = client.put(
        f"/api/v1/journeys/{draft['journeyId']}",
        json=draft,
        headers=AUTH_HEADERS,
    ).json()

    removed = client.delete(
        f"/api/v1/journeys/{saved['journeyId']}/video-recommendation",
        headers=AUTH_HEADERS,
    )

    assert removed.status_code == 200
    assert removed.json()["status"] == "confirmed"
    assert "videoRecommendation" not in removed.json()
    assert "recommendedPlaylist" not in removed.json()
    assert len(removed.json()["weeks"]) == 4
    assert repository.video_recommendations == {}


def test_expired_video_metadata_is_removed_without_losing_the_written_plan() -> None:
    current_time = [NOW]
    repository = InMemoryJourneyRepository(clock=lambda: current_time[0])
    enriched = JourneyDocument.model_validate(
        create_journey("Piano", recommendation_service=service())
    ).model_copy(update={"status": "confirmed"})

    repository.save_confirmed_journey("member-1", enriched)
    current_time[0] = NOW + timedelta(days=30)
    restored = repository.get_confirmed_journey("member-1")

    assert restored is not None
    assert restored.status == "confirmed"
    assert restored.video_recommendation is None
    assert restored.recommended_playlist is None
    assert len(restored.weeks) == 4


def test_youtube_search_quota_is_five_per_learner_and_twenty_per_project() -> None:
    quotas = QuotaService(InMemoryQuotaCounterStore(), clock=lambda: NOW)
    for index in range(5):
        quotas.reserve_youtube_search("member-1", idempotency_key=f"journey-{index}")
    with pytest.raises(QuotaExceeded, match="youtube_subject_daily_quota_exceeded"):
        quotas.reserve_youtube_search("member-1", idempotency_key="journey-6")

    project_quotas = QuotaService(InMemoryQuotaCounterStore(), clock=lambda: NOW)
    for index in range(20):
        project_quotas.reserve_youtube_search(f"member-{index}", idempotency_key=f"journey-{index}")
    with pytest.raises(QuotaExceeded, match="youtube_project_daily_quota_exceeded"):
        project_quotas.reserve_youtube_search("member-21", idempotency_key="journey-21")


def test_youtube_adapter_sends_only_a_bounded_topic_query_and_filters_bad_videos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, dict, dict]] = []

    class Response:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self.payload

    class Client:
        def __init__(self, **_kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def get(self, url: str, *, params: dict, headers: dict):
            requests.append((url, params, headers))
            if url.endswith("/search"):
                return Response({"items": [{"id": {"playlistId": "PLgeneralCourse12345"}}]})
            if url.endswith("/playlists"):
                return Response({"items": [{
                    "snippet": {
                        "title": "Piano foundations",
                        "channelTitle": "Public Teacher",
                        "description": "Sequential lessons",
                        "defaultLanguage": "en",
                    },
                    "contentDetails": {"itemCount": 3},
                    "status": {"privacyStatus": "public"},
                }]})
            if url.endswith("/playlistItems"):
                return Response({"items": [
                    {
                        "snippet": {"title": "Lesson one", "position": 0},
                        "contentDetails": {"videoId": "lesson00001"},
                        "status": {"privacyStatus": "public"},
                    },
                    {
                        "snippet": {"title": "Private video", "position": 1},
                        "contentDetails": {"videoId": "lesson00002"},
                        "status": {"privacyStatus": "private"},
                    },
                    {
                        "snippet": {"title": "Lesson one duplicate", "position": 2},
                        "contentDetails": {"videoId": "lesson00001"},
                        "status": {"privacyStatus": "public"},
                    },
                ]})
            return Response({"items": [{
                "id": "lesson00001",
                "snippet": {
                    "title": "Lesson one",
                    "description": "Start here",
                    "liveBroadcastContent": "none",
                    "defaultAudioLanguage": "en",
                },
                "contentDetails": {"duration": "PT12M", "caption": "true"},
                "status": {"privacyStatus": "public"},
            }]})

    monkeypatch.setattr("app.video_recommendations.httpx.AsyncClient", Client)
    adapter = GoogleYouTubeDiscovery(api_key="server-secret", timeout_seconds=8)

    result = asyncio.run(
        adapter.discover(
            DiscoveryRequest(topic="Piano", level="beginner", preferredLanguage="hi")
        )
    )

    search_params = requests[0][1]
    assert search_params == {
        "part": "snippet",
        "type": "playlist",
        "safeSearch": "strict",
        "regionCode": "IN",
        "relevanceLanguage": "hi",
        "maxResults": 5,
        "q": "Piano beginner course",
    }
    assert requests[0][2] == {"X-Goog-Api-Key": "server-secret"}
    assert all("key" not in params for _, params, _ in requests)
    assert [video.video_id for video in result[0].videos] == ["lesson00001"]
    assert result[0].videos[0].duration_seconds == 720
