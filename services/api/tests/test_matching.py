from copy import deepcopy

import pytest

from app.matching import (
    MATCHING_CONTRACT_VERSION,
    SCORE_THRESHOLD,
    candidate_passes_hard_filters,
    canonicalize_profile,
    generate_recommendations,
    score_candidate,
)
from app.profile import LearningWishProfile
from app.synthetic_data import generate_synthetic_dataset

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


def setup_matching():
    dataset = generate_synthetic_dataset()
    profile = LearningWishProfile.model_validate(PROFILE)
    learner = canonicalize_profile(profile, dataset.hobbies)
    assert learner is not None
    return dataset, learner


@pytest.mark.parametrize(
    ("change", "requester_id"),
    [
        ({"active": False}, "syn_requester_0001"),
        ({"matching_consent": False}, "syn_requester_0001"),
        ({"hobby_id": "drawing"}, "syn_requester_0001"),
        ({"languages": ("en",)}, "syn_requester_0001"),
        ({"availability_tier": None}, "syn_requester_0001"),
        ({"learning_format": "home_individual"}, "syn_requester_0001"),
        ({"dataset_version": "foreign-dataset"}, "syn_requester_0001"),
        ({"synthetic": False}, "syn_requester_0001"),
        ({}, "syn_partner_0001"),
    ],
)
def test_each_partner_hard_filter_removes_an_otherwise_eligible_candidate(
    change: dict,
    requester_id: str,
) -> None:
    dataset, learner = setup_matching()
    candidate = dataset.learners[0].model_copy(update=change)

    assert not candidate_passes_hard_filters(
        learner=learner,
        candidate=candidate,
        requester_candidate_id=requester_id,
        dataset_version=dataset.dataset_version,
        relations=(),
    )


def test_city_block_and_bidirectional_rejection_filters_are_private_and_independent() -> None:
    dataset, learner = setup_matching()
    eligible = dataset.learners[0]
    wrong_city = eligible.model_copy(
        update={"learning_format": "in_person_group", "city_code": "jaipur"},
    )
    in_person_learner = learner.model_copy(
        update={"learning_format": "in_person_group", "city_code": "pune"},
    )

    assert not candidate_passes_hard_filters(
        learner=in_person_learner,
        candidate=wrong_city,
        requester_candidate_id="syn_requester_0001",
        dataset_version=dataset.dataset_version,
        relations=(),
    )
    for candidate in dataset.learners[1:3]:
        assert not candidate_passes_hard_filters(
            learner=learner,
            candidate=candidate,
            requester_candidate_id="syn_requester_0001",
            dataset_version=dataset.dataset_version,
            relations=dataset.relations,
        )


@pytest.mark.parametrize(
    "change",
    [
        {"listing_consent": False},
        {"status": "unverified"},
        {"published": False},
        {"taught_hobby_ids": ("drawing",)},
        {"supported_languages": ("en",)},
        {"supported_formats": ("home_individual",)},
    ],
)
def test_each_mentor_listing_filter_removes_an_otherwise_eligible_listing(change: dict) -> None:
    dataset, learner = setup_matching()
    candidate = dataset.mentors[0].model_copy(update=change)

    assert not candidate_passes_hard_filters(
        learner=learner,
        candidate=candidate,
        requester_candidate_id="syn_requester_0001",
        dataset_version=dataset.dataset_version,
        relations=(),
    )


def test_locked_score_weights_sum_to_100_and_reasons_are_the_strongest_three() -> None:
    dataset, learner = setup_matching()

    scored = score_candidate(learner, dataset.learners[0], dataset.hobbies)

    assert scored.score == 100
    assert [(factor.factor, factor.points, factor.max_points) for factor in scored.factor_breakdown] == [
        ("hobbyGoalFit", 30, 30),
        ("schedule", 20, 20),
        ("language", 15, 15),
        ("skillLevel", 15, 15),
        ("pace", 10, 10),
        ("format", 10, 10),
        ("price", 0, 0),
    ]
    assert len(scored.reasons) == 3
    assert [reason.factor for reason in scored.reasons] == [
        "hobbyGoalFit",
        "schedule",
        "language",
    ]


def test_exact_65_threshold_stable_tie_breaking_and_three_result_limit() -> None:
    dataset, learner = setup_matching()
    immersive_profile = LearningWishProfile.model_validate(
        {**PROFILE, "availability": "45 minutes · 5 days a week"},
    )
    immersive = canonicalize_profile(immersive_profile, dataset.hobbies)
    assert immersive is not None
    base = dataset.learners[0].model_copy(
        update={
            "goal_tag": "restart_basics",
            "availability_tier": "gentle",
            "pace": "gentle",
        },
    )
    exact_threshold = score_candidate(immersive, base, dataset.hobbies)
    below_threshold = score_candidate(
        immersive,
        base.model_copy(update={"experience_level": 0}),
        dataset.hobbies,
    )

    assert exact_threshold.score == SCORE_THRESHOLD == 65
    assert below_threshold.score == 60

    tied_candidates = [
        dataset.learners[0].model_copy(update={"candidate_id": f"syn_partner_tie_{suffix}"})
        for suffix in ("e", "d", "c", "b", "a")
    ]
    response = generate_recommendations(
        learner=learner,
        recommendation_type="partner",
        dataset=dataset.model_copy(update={"learners": tied_candidates}),
        requester_candidate_id="syn_requester_0001",
    )

    assert response.contract_version == MATCHING_CONTRACT_VERSION
    assert len(response.results) == 3
    assert [result.candidate_id for result in response.results] == [
        "syn_partner_tie_a",
        "syn_partner_tie_b",
        "syn_partner_tie_c",
    ]


def test_reviewed_english_and_hindi_copy_cannot_change_ids_scores_or_order() -> None:
    dataset, learner = setup_matching()
    response = generate_recommendations(
        learner=learner,
        recommendation_type="partner",
        dataset=dataset,
        requester_candidate_id="syn_requester_0001",
    )
    payload = response.model_dump(by_alias=True)

    invariant = [
        (
            result["candidateId"],
            result["score"],
            [reason["factor"] for reason in result["reasons"]],
        )
        for result in payload["results"]
    ]
    localized_en = deepcopy(payload)
    localized_hi = deepcopy(payload)
    for result in localized_en["results"]:
        result["visibleReasons"] = [reason["text"]["en"] for reason in result["reasons"]]
    for result in localized_hi["results"]:
        result["visibleReasons"] = [reason["text"]["hi"] for reason in result["reasons"]]

    assert invariant == [
        (
            result["candidateId"],
            result["score"],
            [reason["factor"] for reason in result["reasons"]],
        )
        for result in localized_hi["results"]
    ]
    assert localized_en["results"][0]["visibleReasons"] != localized_hi["results"][0]["visibleReasons"]

