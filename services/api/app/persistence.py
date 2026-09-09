from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .config import Settings
from .journey import JourneyDocument, strip_video_recommendation
from .profile import LearningWishProfile
from .synthetic_data import DATASET_VERSION, SyntheticDataset, generate_synthetic_dataset

PROFILE_RECORD_VERSION = "profile-v1.0.0"
JOURNEY_RECORD_VERSION = "journey-v1.0.0"
MATCHING_DATASET_RECORD_VERSION = "matching-dataset-v1.0.0"
PROFILE_COLLECTION = "learner_profiles_v1"
JOURNEY_COLLECTION = "learner_journeys_v1"
RECOMMENDATION_COLLECTION = "recommendation_catalog_v1"
YOUTUBE_RECOMMENDATION_COLLECTION = "youtube_recommendations_v1"
YOUTUBE_RECOMMENDATION_RECORD_VERSION = "youtube-recommendation-v1.0.0"


class OperationalDataUnavailable(RuntimeError):
    """Persistent product data is missing, malformed, or temporarily unreadable."""


class ProfileRepository(Protocol):
    def save_profile(self, uid: str, profile: LearningWishProfile) -> None: ...

    def get_profile(self, uid: str) -> LearningWishProfile | None: ...


class JourneyRepository(Protocol):
    def save_confirmed_journey(self, uid: str, journey: JourneyDocument) -> None: ...

    def get_confirmed_journey(self, uid: str) -> JourneyDocument | None: ...


class RecommendationRepository(Protocol):
    def get_dataset(self) -> SyntheticDataset: ...


def _utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Persistent record timestamps must include a timezone")
    return value.astimezone(UTC)


def _document_path(collection: str, document_id: str) -> str:
    if (
        not document_id
        or len(document_id) > 128
        or "/" in document_id
        or any(ord(character) < 32 for character in document_id)
    ):
        raise ValueError("The authenticated subject identifier is invalid")
    return f"{collection}/{document_id}"


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class _ProfileRecord(_Record):
    record_version: Literal["profile-v1.0.0"] = Field(alias="recordVersion")
    profile: LearningWishProfile
    updated_at: datetime = Field(alias="updatedAt")

    @field_validator("updated_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return _utc_timestamp(value)


class _JourneyRecord(_Record):
    record_version: Literal["journey-v1.0.0"] = Field(alias="recordVersion")
    journey: JourneyDocument
    confirmed_at: datetime = Field(alias="confirmedAt")

    @field_validator("confirmed_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return _utc_timestamp(value)


class _YouTubeRecommendationRecord(_Record):
    record_version: Literal["youtube-recommendation-v1.0.0"] = Field(alias="recordVersion")
    journey_id: str = Field(alias="journeyId")
    enrichment: dict[str, object]
    expires_at: datetime = Field(alias="expiresAt")

    @field_validator("expires_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return _utc_timestamp(value)


def _video_enrichment(
    journey: JourneyDocument,
    *,
    now: datetime,
) -> tuple[dict[str, object], datetime] | None:
    if journey.video_recommendation is None:
        return None
    payload = journey.model_dump(by_alias=True, mode="json")
    enrichment: dict[str, object] = {
        "videoRecommendation": payload["videoRecommendation"],
        "recommendedPlaylist": payload.get("recommendedPlaylist"),
        "weeklyGuides": [week.get("videoGuide") for week in payload["weeks"]],
    }
    expires_at = (
        journey.recommended_playlist.expires_at
        if journey.recommended_playlist is not None
        else _utc_timestamp(now) + timedelta(days=1)
    )
    return enrichment, expires_at


def _join_video_enrichment(
    journey: JourneyDocument,
    record: _YouTubeRecommendationRecord,
) -> JourneyDocument:
    if record.journey_id != journey.journey_id:
        return journey
    payload = journey.model_dump(by_alias=True)
    payload["schemaVersion"] = "1.2.0"
    payload["videoRecommendation"] = record.enrichment["videoRecommendation"]
    playlist = record.enrichment.get("recommendedPlaylist")
    if playlist is not None:
        payload["recommendedPlaylist"] = playlist
    weekly_guides = record.enrichment.get("weeklyGuides", [])
    if isinstance(weekly_guides, list):
        for week, guide in zip(payload["weeks"], weekly_guides, strict=False):
            if guide is not None:
                week["videoGuide"] = guide
    return JourneyDocument.model_validate(payload)


class _MatchingDatasetRecord(_Record):
    record_version: Literal["matching-dataset-v1.0.0"] = Field(alias="recordVersion")
    dataset: SyntheticDataset
    published_at: datetime = Field(alias="publishedAt")

    @field_validator("published_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return _utc_timestamp(value)


def _snapshot_value(reference: Any, *, missing_allowed: bool) -> Mapping[str, object] | None:
    try:
        snapshot = reference.get()
        if not snapshot.exists:
            if missing_allowed:
                return None
            raise ValueError("Required persistent document is missing")
        value = snapshot.to_dict()
        if not isinstance(value, Mapping):
            raise TypeError("Persistent document is malformed")
        return value
    except OperationalDataUnavailable:
        raise
    except Exception as error:
        raise OperationalDataUnavailable("operational data unavailable") from error


class InMemoryProfileRepository:
    """Deterministic local-only profile repository."""

    def __init__(self) -> None:
        self.profiles: dict[str, LearningWishProfile] = {}

    def save_profile(self, uid: str, profile: LearningWishProfile) -> None:
        _document_path(PROFILE_COLLECTION, uid)
        self.profiles[uid] = profile

    def get_profile(self, uid: str) -> LearningWishProfile | None:
        _document_path(PROFILE_COLLECTION, uid)
        return self.profiles.get(uid)


class InMemoryJourneyRepository:
    """Deterministic local-only confirmed-journey repository."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self.journeys: dict[str, JourneyDocument] = {}
        self.video_recommendations: dict[str, _YouTubeRecommendationRecord] = {}
        self._clock = clock or (lambda: datetime.now(UTC))

    def save_confirmed_journey(self, uid: str, journey: JourneyDocument) -> None:
        _document_path(JOURNEY_COLLECTION, uid)
        if journey.status != "confirmed":
            raise ValueError("Only a confirmed journey may be persisted")
        self.journeys[uid] = strip_video_recommendation(journey)
        enrichment = _video_enrichment(journey, now=self._clock())
        if enrichment is None:
            self.video_recommendations.pop(uid, None)
        else:
            payload, expires_at = enrichment
            self.video_recommendations[uid] = _YouTubeRecommendationRecord(
                recordVersion=YOUTUBE_RECOMMENDATION_RECORD_VERSION,
                journeyId=journey.journey_id,
                enrichment=payload,
                expiresAt=expires_at,
            )

    def get_confirmed_journey(self, uid: str) -> JourneyDocument | None:
        _document_path(JOURNEY_COLLECTION, uid)
        journey = self.journeys.get(uid)
        if journey is None:
            return None
        recommendation = self.video_recommendations.get(uid)
        if recommendation is None:
            return journey
        if _utc_timestamp(self._clock()) >= recommendation.expires_at:
            self.video_recommendations.pop(uid, None)
            return journey
        return _join_video_enrichment(journey, recommendation)


class InMemoryRecommendationRepository:
    """Deterministic local-only read adapter for the committed synthetic catalog."""

    def __init__(self, dataset: SyntheticDataset | None = None) -> None:
        self.dataset = dataset if dataset is not None else generate_synthetic_dataset()

    def get_dataset(self) -> SyntheticDataset:
        if self.dataset is None:
            raise OperationalDataUnavailable("operational data unavailable")
        return self.dataset


class FirestoreProfileRepository:
    def __init__(
        self,
        client: Any,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    def save_profile(self, uid: str, profile: LearningWishProfile) -> None:
        path = _document_path(PROFILE_COLLECTION, uid)
        record = {
            "recordVersion": PROFILE_RECORD_VERSION,
            "profile": profile.model_dump(by_alias=True, mode="json"),
            "updatedAt": _utc_timestamp(self._clock()),
        }
        try:
            self.client.document(path).set(record)
        except Exception as error:
            raise OperationalDataUnavailable("operational data unavailable") from error

    def get_profile(self, uid: str) -> LearningWishProfile | None:
        path = _document_path(PROFILE_COLLECTION, uid)
        raw = _snapshot_value(self.client.document(path), missing_allowed=True)
        if raw is None:
            return None
        try:
            return _ProfileRecord.model_validate(raw).profile
        except Exception as error:
            raise OperationalDataUnavailable("operational data unavailable") from error


class FirestoreJourneyRepository:
    def __init__(
        self,
        client: Any,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    def save_confirmed_journey(self, uid: str, journey: JourneyDocument) -> None:
        if journey.status != "confirmed":
            raise ValueError("Only a confirmed journey may be persisted")
        path = _document_path(JOURNEY_COLLECTION, uid)
        record = {
            "recordVersion": JOURNEY_RECORD_VERSION,
            "journey": strip_video_recommendation(journey).model_dump(by_alias=True, mode="json"),
            "confirmedAt": _utc_timestamp(self._clock()),
        }
        try:
            self.client.document(path).set(record)
            enrichment = _video_enrichment(journey, now=self._clock())
            recommendation_path = _document_path(YOUTUBE_RECOMMENDATION_COLLECTION, uid)
            if enrichment is not None:
                payload, expires_at = enrichment
                self.client.document(recommendation_path).set(
                    {
                        "recordVersion": YOUTUBE_RECOMMENDATION_RECORD_VERSION,
                        "journeyId": journey.journey_id,
                        "enrichment": payload,
                        "expiresAt": expires_at,
                    }
                )
        except Exception as error:
            raise OperationalDataUnavailable("operational data unavailable") from error

    def get_confirmed_journey(self, uid: str) -> JourneyDocument | None:
        path = _document_path(JOURNEY_COLLECTION, uid)
        raw = _snapshot_value(self.client.document(path), missing_allowed=True)
        if raw is None:
            return None
        try:
            journey = _JourneyRecord.model_validate(raw).journey
            recommendation_path = _document_path(YOUTUBE_RECOMMENDATION_COLLECTION, uid)
            recommendation_raw = _snapshot_value(
                self.client.document(recommendation_path), missing_allowed=True
            )
            if recommendation_raw is None:
                return journey
            recommendation = _YouTubeRecommendationRecord.model_validate(recommendation_raw)
            if _utc_timestamp(self._clock()) >= recommendation.expires_at:
                return journey
            return _join_video_enrichment(journey, recommendation)
        except Exception as error:
            raise OperationalDataUnavailable("operational data unavailable") from error


class FirestoreRecommendationRepository:
    """Reads the approved synthetic catalog; recommendation outcomes stay transient."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def get_dataset(self) -> SyntheticDataset:
        path = _document_path(RECOMMENDATION_COLLECTION, DATASET_VERSION)
        raw = _snapshot_value(self.client.document(path), missing_allowed=False)
        assert raw is not None
        try:
            record = _MatchingDatasetRecord.model_validate(raw)
        except Exception as error:
            raise OperationalDataUnavailable("operational data unavailable") from error
        if record.dataset.dataset_version != DATASET_VERSION:
            raise OperationalDataUnavailable("operational data unavailable")
        return record.dataset


class _LazyFirestoreClient:
    """Defers ADC and network-sensitive client creation until an endpoint uses Firestore."""

    def __init__(self, *, project: str, database: str) -> None:
        self._project = project
        self._database = database
        self._client: Any | None = None
        self._lock = Lock()

    def _resolve(self) -> Any:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                from google.cloud import firestore

                self._client = firestore.Client(
                    project=self._project,
                    database=self._database,
                )
        return self._client

    def document(self, path: str) -> Any:
        return self._resolve().document(path)


@dataclass(frozen=True)
class FirestoreRepositories:
    profile: FirestoreProfileRepository
    journey: FirestoreJourneyRepository
    recommendation: FirestoreRecommendationRepository


def build_firestore_repositories(
    settings: Settings,
    *,
    client_factory: Callable[..., Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> FirestoreRepositories:
    environment = os.environ if environ is None else environ
    emulator_host = environment.get("FIRESTORE_EMULATOR_HOST")
    if settings.adapter_mode not in {"firebase_emulator", "production"}:
        raise ValueError("Firestore repositories require an explicit Firestore adapter mode")
    if not settings.firebase_project_id or not settings.firestore_database_id:
        raise ValueError("Firestore project and database configuration are required")
    if settings.adapter_mode == "firebase_emulator" and not emulator_host:
        raise ValueError("Firestore emulator configuration is required")
    if settings.adapter_mode == "production" and emulator_host:
        raise ValueError("FIRESTORE_EMULATOR_HOST is forbidden in production")

    if client_factory is None:
        client = _LazyFirestoreClient(
            project=settings.firebase_project_id,
            database=settings.firestore_database_id,
        )
    else:
        client = client_factory(
            project=settings.firebase_project_id,
            database=settings.firestore_database_id,
        )
    return FirestoreRepositories(
        profile=FirestoreProfileRepository(client),
        journey=FirestoreJourneyRepository(client),
        recommendation=FirestoreRecommendationRepository(client),
    )
