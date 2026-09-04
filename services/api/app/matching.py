from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .profile import LearningWishProfile
from .synthetic_data import (
    AvailabilityTier,
    GoalTag,
    HobbyCatalogRecord,
    LearningFormat,
    LocalizedText,
    SyntheticDataset,
    SyntheticLearnerRecord,
    SyntheticMentorRecord,
    SyntheticRelationRecord,
)

MATCHING_CONTRACT_VERSION = "matching-v1.0.0"
SCORE_THRESHOLD = 65
RESULT_LIMIT = 3
RecommendationType = Literal["partner", "mentor"]
FactorName = Literal[
    "hobbyGoalFit",
    "schedule",
    "language",
    "skillLevel",
    "pace",
    "format",
    "price",
]
Candidate: TypeAlias = SyntheticLearnerRecord | SyntheticMentorRecord
FACTOR_ORDER: tuple[FactorName, ...] = (
    "hobbyGoalFit",
    "schedule",
    "language",
    "skillLevel",
    "pace",
    "format",
    "price",
)
TIER_ORDER = {"gentle": 0, "steady": 1, "immersive": 2}
TIER_CAPACITY = {
    "gentle": (15, 3),
    "steady": (30, 4),
    "immersive": (45, 5),
}


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class CanonicalLearner(ApiModel):
    hobby_id: str
    goal_tag: GoalTag | None
    experience_level: int
    availability_tier: AvailabilityTier
    languages: tuple[Literal["en", "hi"], ...]
    pace: AvailabilityTier
    learning_format: LearningFormat
    city_code: str | None


class FactorBreakdown(ApiModel):
    factor: FactorName
    points: int = Field(ge=0)
    max_points: int = Field(ge=0)


class MatchReason(FactorBreakdown):
    reason_code: str
    text: LocalizedText


class RecommendationResult(ApiModel):
    candidate_id: str
    candidate_type: RecommendationType
    display_name: str
    synthetic: Literal[True] = True
    score: int = Field(ge=0, le=100)
    score_out_of: Literal[100] = 100
    hobby: LocalizedText
    reasons: list[MatchReason] = Field(min_length=3, max_length=3)
    factor_breakdown: list[FactorBreakdown] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def score_is_breakdown_sum(self) -> RecommendationResult:
        if self.score != sum(factor.points for factor in self.factor_breakdown):
            raise ValueError("Score must equal the factor breakdown sum")
        return self


class RecommendationResponse(ApiModel):
    contract_version: Literal["matching-v1.0.0"] = MATCHING_CONTRACT_VERSION
    recommendation_type: RecommendationType
    source: Literal["deterministic_synthetic"] = "deterministic_synthetic"
    synthetic: Literal[True] = True
    status: Literal["matched", "no_matches"]
    score_threshold: Literal[65] = SCORE_THRESHOLD
    result_limit: Literal[3] = RESULT_LIMIT
    results: list[RecommendationResult] = Field(max_length=3)
    empty_reason: Literal["no_eligible_candidate", "hobby_not_in_catalog"] | None = None


def _normalized(value: str) -> str:
    return " ".join(value.casefold().strip().split())


GOAL_ALIASES: dict[str, GoalTag] = {
    _normalized("Restart the basics"): "restart_basics",
    _normalized("मूल बातें फिर शुरू करना"): "restart_basics",
    _normalized("Paint a greeting card"): "complete_small_project",
    _normalized("शुभकामना कार्ड बनाना"): "complete_small_project",
    _normalized("Complete a small project"): "complete_small_project",
    _normalized("Build a regular practice routine"): "build_routine",
    _normalized("नियमित अभ्यास की आदत बनाना"): "build_routine",
    _normalized("Learn with peers"): "learn_with_peers",
    _normalized("साथियों के साथ सीखना"): "learn_with_peers",
    _normalized("Prepare to teach"): "prepare_to_teach",
    _normalized("सिखाने की तैयारी करना"): "prepare_to_teach",
}
EXPERIENCE_LEVELS = {
    "New to this": 0,
    "पहली बार सीख रही हूँ": 0,
    "Restarting after many years": 1,
    "कई वर्षों बाद फिर शुरू कर रही हूँ": 1,
    "Some recent practice": 2,
    "हाल में थोड़ा अभ्यास किया है": 2,
}
AVAILABILITY_TIERS: dict[str, AvailabilityTier] = {
    "15 minutes · 3 days a week": "gentle",
    "15 मिनट · सप्ताह में 3 दिन": "gentle",
    "30 minutes · 4 days a week": "steady",
    "30 मिनट · सप्ताह में 4 दिन": "steady",
    "45 minutes · 5 days a week": "immersive",
    "45 मिनट · सप्ताह में 5 दिन": "immersive",
}
LANGUAGES = {
    "English": ("en",),
    "अंग्रेज़ी": ("en",),
    "Hindi": ("hi",),
    "हिंदी": ("hi",),
    "English and Hindi": ("en", "hi"),
    "अंग्रेज़ी और हिंदी": ("en", "hi"),
}
FORMATS: dict[str, LearningFormat] = {
    "At home · individual": "home_individual",
    "घर पर · अकेले": "home_individual",
    "At home · small online group": "home_online_group",
    "घर पर · छोटा ऑनलाइन समूह": "home_online_group",
    "In person · small group": "in_person_group",
    "सामने · छोटा समूह": "in_person_group",
}
CITY_CODES = {
    _normalized("Pune"): "pune",
    _normalized("पुणे"): "pune",
    _normalized("Jaipur"): "jaipur",
    _normalized("जयपुर"): "jaipur",
    _normalized("Lucknow"): "lucknow",
    _normalized("लखनऊ"): "lucknow",
    _normalized("Indore"): "indore",
    _normalized("इंदौर"): "indore",
    _normalized("Mysuru"): "mysuru",
    _normalized("मैसूर"): "mysuru",
}


def canonicalize_profile(
    profile: LearningWishProfile,
    hobbies: list[HobbyCatalogRecord],
) -> CanonicalLearner | None:
    hobby_aliases = {
        _normalized(alias): hobby.hobby_id
        for hobby in hobbies
        for alias in hobby.aliases
    }
    hobby_id = hobby_aliases.get(_normalized(profile.hobby))
    if hobby_id is None:
        return None
    tier = AVAILABILITY_TIERS[profile.availability]
    return CanonicalLearner(
        hobby_id=hobby_id,
        goal_tag=GOAL_ALIASES.get(_normalized(profile.goal)),
        experience_level=EXPERIENCE_LEVELS.get(profile.experience, 0),
        availability_tier=tier,
        languages=LANGUAGES[profile.language],
        pace=tier,
        learning_format=FORMATS[profile.format],
        city_code=CITY_CODES.get(_normalized(profile.city)) if profile.city else None,
    )


def _candidate_hobbies(candidate: Candidate) -> tuple[str, ...]:
    if isinstance(candidate, SyntheticLearnerRecord):
        return (candidate.hobby_id,)
    return candidate.taught_hobby_ids


def _candidate_languages(candidate: Candidate) -> tuple[str, ...]:
    if isinstance(candidate, SyntheticLearnerRecord):
        return candidate.languages
    return candidate.supported_languages


def _candidate_formats(candidate: Candidate) -> tuple[str, ...]:
    if isinstance(candidate, SyntheticLearnerRecord):
        return (candidate.learning_format,)
    return candidate.supported_formats


def _is_excluded_by_relation(
    requester_candidate_id: str,
    candidate_id: str,
    relations: tuple[SyntheticRelationRecord, ...] | list[SyntheticRelationRecord],
) -> bool:
    pair = {requester_candidate_id, candidate_id}
    return any(
        relation.active
        and relation.kind in {"block", "rejection"}
        and {relation.source_candidate_id, relation.target_candidate_id} == pair
        for relation in relations
    )


def candidate_passes_hard_filters(
    *,
    learner: CanonicalLearner,
    candidate: Candidate,
    requester_candidate_id: str,
    dataset_version: str,
    relations: tuple[SyntheticRelationRecord, ...] | list[SyntheticRelationRecord],
) -> bool:
    if not candidate.synthetic or candidate.dataset_version != dataset_version:
        return False
    if candidate.candidate_id == requester_candidate_id or not candidate.active:
        return False
    if isinstance(candidate, SyntheticLearnerRecord):
        if not candidate.matching_consent:
            return False
    elif not (candidate.listing_consent and candidate.status == "verified" and candidate.published):
        return False
    if learner.hobby_id not in _candidate_hobbies(candidate):
        return False
    if not set(learner.languages).intersection(_candidate_languages(candidate)):
        return False
    candidate_tier = getattr(candidate, "availability_tier", None)
    if candidate_tier not in TIER_CAPACITY:
        return False
    if min(TIER_CAPACITY[learner.availability_tier][0], TIER_CAPACITY[candidate_tier][0]) < 15:
        return False
    if learner.learning_format not in _candidate_formats(candidate):
        return False
    if learner.learning_format == "in_person_group" and (
        not learner.city_code
        or not candidate.city_code
        or learner.city_code != candidate.city_code
    ):
        return False
    return not _is_excluded_by_relation(
        requester_candidate_id,
        candidate.candidate_id,
        relations,
    )


def _distance_points(distance: int, values: tuple[int, int, int]) -> int:
    return values[min(distance, 2)]


def _breakdown(learner: CanonicalLearner, candidate: Candidate) -> list[FactorBreakdown]:
    if isinstance(candidate, SyntheticLearnerRecord):
        goal_match = learner.goal_tag is not None and candidate.goal_tag == learner.goal_tag
        skill_distance = abs(candidate.experience_level - learner.experience_level)
        skill_points = _distance_points(skill_distance, (15, 10, 5))
        format_points = 10
    else:
        goal_match = learner.goal_tag is not None and learner.goal_tag in candidate.supported_goal_tags
        if learner.experience_level in candidate.taught_levels:
            skill_points = 15
        elif any(abs(level - learner.experience_level) == 1 for level in candidate.taught_levels):
            skill_points = 8
        else:
            skill_points = 0
        format_points = 10 if candidate.primary_format == learner.learning_format else 6

    tier_distance = abs(TIER_ORDER[learner.availability_tier] - TIER_ORDER[candidate.availability_tier])
    _, learner_days = TIER_CAPACITY[learner.availability_tier]
    _, candidate_days = TIER_CAPACITY[candidate.availability_tier]
    duration_distance = abs(TIER_ORDER[learner.availability_tier] - TIER_ORDER[candidate.availability_tier])
    day_distance = abs(learner_days - candidate_days)
    schedule_points = _distance_points(duration_distance, (10, 7, 4)) + _distance_points(day_distance, (10, 7, 4))
    candidate_languages = _candidate_languages(candidate)
    language_points = (
        15
        if len(learner.languages) == 1 or set(learner.languages).issubset(candidate_languages)
        else 8
    )
    pace_points = _distance_points(tier_distance, (10, 6, 2))
    return [
        FactorBreakdown(factor="hobbyGoalFit", points=15 + (15 if goal_match else 0), max_points=30),
        FactorBreakdown(factor="schedule", points=schedule_points, max_points=20),
        FactorBreakdown(factor="language", points=language_points, max_points=15),
        FactorBreakdown(factor="skillLevel", points=skill_points, max_points=15),
        FactorBreakdown(factor="pace", points=pace_points, max_points=10),
        FactorBreakdown(factor="format", points=format_points, max_points=10),
        FactorBreakdown(factor="price", points=0, max_points=0),
    ]


def _reason_text(factor: FactorName, full_points: bool) -> tuple[str, LocalizedText]:
    values: dict[FactorName, tuple[str, str, str, str]] = {
        "hobbyGoalFit": (
            "same_hobby_and_goal" if full_points else "same_hobby",
            "You share the same hobby and first goal." if full_points else "You are both learning the same hobby.",
            "आपका शौक और पहला लक्ष्य समान है।" if full_points else "आप दोनों एक ही शौक सीख रही हैं।",
            "",
        ),
        "schedule": (
            "same_practice_rhythm" if full_points else "compatible_practice_capacity",
            "Your practice rhythms match." if full_points else "Your practice capacity is compatible.",
            "आप दोनों के अभ्यास की गति समान है।" if full_points else "आप दोनों की अभ्यास क्षमता अनुकूल है।",
            "",
        ),
        "language": (
            "preferred_language_shared",
            "You share a preferred learning language.",
            "आप दोनों की पसंदीदा सीखने की भाषा समान है।",
            "",
        ),
        "skillLevel": (
            "compatible_skill_level",
            "Your experience levels support learning together.",
            "आप दोनों के अनुभव का स्तर साथ सीखने के लिए अनुकूल है।",
            "",
        ),
        "pace": (
            "compatible_pace",
            "Your preferred learning pace is compatible.",
            "आप दोनों की पसंदीदा सीखने की गति अनुकूल है।",
            "",
        ),
        "format": (
            "compatible_format",
            "This match supports your chosen learning format.",
            "यह साथी आपके चुने हुए सीखने के तरीके के अनुकूल है।",
            "",
        ),
        "price": ("not_applicable", "", "", ""),
    }
    reason_code, en, hi, _unused = values[factor]
    return reason_code, LocalizedText(en=en, hi=hi)


def score_candidate(
    learner: CanonicalLearner,
    candidate: Candidate,
    hobbies: list[HobbyCatalogRecord],
) -> RecommendationResult:
    factors = _breakdown(learner, candidate)
    by_factor = {factor.factor: factor for factor in factors}
    reasons: list[MatchReason] = []
    for factor in sorted(
        (item for item in factors if item.points > 0 and item.factor != "price"),
        key=lambda item: (-item.points, FACTOR_ORDER.index(item.factor)),
    )[:3]:
        reason_code, text = _reason_text(factor.factor, factor.points == factor.max_points)
        reasons.append(
            MatchReason(
                factor=factor.factor,
                reason_code=reason_code,
                points=factor.points,
                max_points=factor.max_points,
                text=text,
            ),
        )
    hobby = next(item.label for item in hobbies if item.hobby_id == learner.hobby_id)
    return RecommendationResult(
        candidate_id=candidate.candidate_id,
        candidate_type=candidate.candidate_type,
        display_name=candidate.display_name,
        score=sum(item.points for item in factors),
        hobby=hobby,
        reasons=reasons,
        factor_breakdown=[by_factor[name] for name in FACTOR_ORDER],
    )


def generate_recommendations(
    *,
    learner: CanonicalLearner,
    recommendation_type: RecommendationType,
    dataset: SyntheticDataset,
    requester_candidate_id: str,
) -> RecommendationResponse:
    candidates: list[Candidate] = (
        list(dataset.learners) if recommendation_type == "partner" else list(dataset.mentors)
    )
    scored = [
        score_candidate(learner, candidate, dataset.hobbies)
        for candidate in candidates
        if candidate_passes_hard_filters(
            learner=learner,
            candidate=candidate,
            requester_candidate_id=requester_candidate_id,
            dataset_version=dataset.dataset_version,
            relations=dataset.relations,
        )
    ]
    eligible = [result for result in scored if result.score >= SCORE_THRESHOLD]

    def ranking_key(result: RecommendationResult) -> tuple[int, int, int, int, str]:
        factors = {factor.factor: factor.points for factor in result.factor_breakdown}
        return (
            -result.score,
            -factors["hobbyGoalFit"],
            -factors["schedule"],
            -factors["language"],
            result.candidate_id,
        )

    results = sorted(eligible, key=ranking_key)[:RESULT_LIMIT]
    return RecommendationResponse(
        recommendation_type=recommendation_type,
        status="matched" if results else "no_matches",
        results=results,
        empty_reason=None if results else "no_eligible_candidate",
    )


def empty_recommendation(
    recommendation_type: RecommendationType,
    reason: Literal["hobby_not_in_catalog", "no_eligible_candidate"],
) -> RecommendationResponse:
    return RecommendationResponse(
        recommendation_type=recommendation_type,
        status="no_matches",
        results=[],
        empty_reason=reason,
    )
