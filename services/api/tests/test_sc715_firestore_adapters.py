import os
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

import pytest
from app.persistence import (
    JOURNEY_RECORD_VERSION,
    MATCHING_DATASET_RECORD_VERSION,
    PROFILE_RECORD_VERSION,
    FirestoreJourneyRepository,
    FirestoreProfileRepository,
    FirestoreRecommendationRepository,
    OperationalDataUnavailable,
    build_firestore_repositories,
)

from app.config import Settings
from app.journey import build_deterministic_journey
from app.profile import LearningWishProfile
from app.synthetic_data import DATASET_VERSION, generate_synthetic_dataset

PROFILE = {
    "hobby": "Watercolour painting",
    "experience": "Restarting after many years",
    "goal": "Paint a greeting card",
    "availability": "30 minutes · 4 days a week",
    "language": "Hindi",
    "accessibility": "Larger text · seated alternatives",
    "format": "At home · small online group",
    "planConsent": True,
    "matchingConsent": True,
    "city": "Pune",
}
NOW = datetime(2026, 9, 3, 10, 30, tzinfo=UTC)
PROFILE_PATH = "learner_profiles_v1/member-1"
JOURNEY_PATH = "learner_journeys_v1/member-1"
CATALOG_PATH = f"recommendation_catalog_v1/{DATASET_VERSION}"


class FakeSnapshot:
    def __init__(self, value: dict[str, Any] | None) -> None:
        self.exists = value is not None
        self._value = deepcopy(value)

    def to_dict(self) -> dict[str, Any] | None:
        return deepcopy(self._value)


class FakeDocumentReference:
    def __init__(self, client: "FakeFirestoreClient", path: str) -> None:
        self.client = client
        self.path = path

    def get(self) -> FakeSnapshot:
        self.client.reads.append(self.path)
        if self.client.read_error is not None:
            raise self.client.read_error
        return FakeSnapshot(self.client.documents.get(self.path))

    def set(self, value: dict[str, Any]) -> None:
        self.client.writes.append(self.path)
        self.client.documents[self.path] = deepcopy(value)


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.reads: list[str] = []
        self.writes: list[str] = []
        self.read_error: Exception | None = None

    def document(self, path: str) -> FakeDocumentReference:
        return FakeDocumentReference(self, path)


def confirmed_journey(profile: LearningWishProfile):
    draft = build_deterministic_journey(
        profile=profile,
        starts_on=datetime(2026, 9, 7, tzinfo=UTC).date(),
        uid="member-1",
    )
    return draft.model_copy(update={"status": "confirmed"})


def test_profile_repository_round_trips_only_the_confirmed_structured_profile() -> None:
    client = FakeFirestoreClient()
    profile = LearningWishProfile.model_validate(PROFILE)

    FirestoreProfileRepository(client, clock=lambda: NOW).save_profile("member-1", profile)

    assert client.documents[PROFILE_PATH] == {
        "recordVersion": PROFILE_RECORD_VERSION,
        "profile": PROFILE,
        "updatedAt": NOW,
    }
    forbidden = {"uid", "email", "transcript", "rawAudio", "credentials"}
    assert forbidden.isdisjoint(client.documents[PROFILE_PATH])
    restarted_repository = FirestoreProfileRepository(client, clock=lambda: NOW)
    assert restarted_repository.get_profile("member-1") == profile


def test_journey_repository_rejects_drafts_and_round_trips_only_a_confirmed_journey() -> None:
    client = FakeFirestoreClient()
    profile = LearningWishProfile.model_validate(PROFILE)
    draft = build_deterministic_journey(
        profile=profile,
        starts_on=datetime(2026, 9, 7, tzinfo=UTC).date(),
        uid="member-1",
    )
    repository = FirestoreJourneyRepository(client, clock=lambda: NOW)

    with pytest.raises(ValueError, match="confirmed"):
        repository.save_confirmed_journey("member-1", draft)
    assert client.writes == []

    confirmed = draft.model_copy(update={"status": "confirmed"})
    repository.save_confirmed_journey("member-1", confirmed)

    assert client.documents[JOURNEY_PATH] == {
        "recordVersion": JOURNEY_RECORD_VERSION,
        "journey": confirmed.model_dump(by_alias=True, mode="json"),
        "confirmedAt": NOW,
    }
    restarted_repository = FirestoreJourneyRepository(client, clock=lambda: NOW)
    assert restarted_repository.get_confirmed_journey("member-1") == confirmed


def test_recommendation_repository_reads_the_versioned_catalog_without_storing_results() -> None:
    client = FakeFirestoreClient()
    dataset = generate_synthetic_dataset()
    client.documents[CATALOG_PATH] = {
        "recordVersion": MATCHING_DATASET_RECORD_VERSION,
        "dataset": dataset.model_dump(by_alias=True, mode="json"),
        "publishedAt": NOW,
    }
    repository = FirestoreRecommendationRepository(client)

    loaded = repository.get_dataset()

    assert loaded == dataset
    assert client.reads == [CATALOG_PATH]
    assert client.writes == []
    assert not hasattr(repository, "save_recommendation_result")


@pytest.mark.parametrize("repository_name", ["profile", "journey", "recommendation"])
def test_missing_malformed_or_unreadable_firestore_state_fails_closed(
    repository_name: str,
) -> None:
    client = FakeFirestoreClient()
    repositories = {
        "profile": lambda: FirestoreProfileRepository(client).get_profile("member-1"),
        "journey": lambda: FirestoreJourneyRepository(client).get_confirmed_journey("member-1"),
        "recommendation": lambda: FirestoreRecommendationRepository(client).get_dataset(),
    }

    if repository_name in {"profile", "journey"}:
        assert repositories[repository_name]() is None
    else:
        with pytest.raises(OperationalDataUnavailable):
            repositories[repository_name]()

    path = {
        "profile": PROFILE_PATH,
        "journey": JOURNEY_PATH,
        "recommendation": CATALOG_PATH,
    }[repository_name]
    client.documents[path] = {"recordVersion": "wrong-version"}
    with pytest.raises(OperationalDataUnavailable):
        repositories[repository_name]()

    client.read_error = RuntimeError("provider detail must not escape")
    with pytest.raises(OperationalDataUnavailable, match="operational data unavailable"):
        repositories[repository_name]()


def test_firestore_builder_uses_only_the_explicit_project_database_and_emulator() -> None:
    client = FakeFirestoreClient()
    calls: list[dict[str, str]] = []

    def client_factory(**kwargs: str) -> FakeFirestoreClient:
        calls.append(kwargs)
        return client

    settings = Settings(
        app_env="test",
        adapter_mode="firebase_emulator",
        firebase_project_id="sakhicircle-sc715-emulator",
        firestore_database_id="(default)",
    )
    repositories = build_firestore_repositories(
        settings,
        client_factory=client_factory,
        environ={"FIRESTORE_EMULATOR_HOST": "127.0.0.1:8085"},
    )

    assert calls == [
        {"project": "sakhicircle-sc715-emulator", "database": "(default)"},
    ]
    assert repositories.profile.client is client
    assert repositories.journey.client is client
    assert repositories.recommendation.client is client


def test_firestore_builder_refuses_implicit_targets_or_an_emulator_in_production() -> None:
    complete_production = Settings(
        app_env="production",
        adapter_mode="production",
        firebase_project_id="patchamomma-2026-505415",
        firebase_app_id="web-app",
        firestore_database_id="(default)",
    )

    with pytest.raises(ValueError, match="FIRESTORE_EMULATOR_HOST"):
        build_firestore_repositories(
            complete_production,
            client_factory=lambda **_kwargs: FakeFirestoreClient(),
            environ={"FIRESTORE_EMULATOR_HOST": "127.0.0.1:8085"},
        )

    for settings in (
        Settings(app_env="test", adapter_mode="firebase_emulator"),
        complete_production.model_copy(update={"firestore_database_id": None}),
    ):
        with pytest.raises(ValueError, match="Firestore"):
            build_firestore_repositories(
                settings,
                client_factory=lambda **_kwargs: FakeFirestoreClient(),
                environ={},
            )


@pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator is not running",
)
def test_real_firestore_emulator_persists_across_repository_instances() -> None:
    from google.cloud import firestore

    project_id = os.environ.get("GCLOUD_PROJECT", "sakhicircle-sc715-emulator")
    settings = Settings(
        app_env="test",
        adapter_mode="firebase_emulator",
        firebase_project_id=project_id,
        firestore_database_id="(default)",
    )
    first = build_firestore_repositories(settings)
    profile = LearningWishProfile.model_validate(PROFILE)
    journey = confirmed_journey(profile)
    first.profile.save_profile("member-1", profile)
    first.journey.save_confirmed_journey("member-1", journey)

    seed_client = firestore.Client(project=project_id, database="(default)")
    seed_client.document(CATALOG_PATH).set(
        {
            "recordVersion": MATCHING_DATASET_RECORD_VERSION,
            "dataset": generate_synthetic_dataset().model_dump(by_alias=True, mode="json"),
            "publishedAt": NOW,
        },
    )
    restarted = build_firestore_repositories(settings)

    assert restarted.profile.get_profile("member-1") == profile
    assert restarted.journey.get_confirmed_journey("member-1") == journey
    assert restarted.recommendation.get_dataset().dataset_version == DATASET_VERSION
