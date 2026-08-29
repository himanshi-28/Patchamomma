from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DATASET_VERSION = "synthetic-matching-v1.0.0"
GENERATOR_VERSION = "synthetic-generator-v1.0.0"
SYNTHETIC_SEED = "sakhicircle-sc-510-2026-08-26"

Language = Literal["en", "hi"]
GoalTag = Literal[
    "restart_basics",
    "complete_small_project",
    "build_routine",
    "learn_with_peers",
    "prepare_to_teach",
]
AvailabilityTier = Literal["gentle", "steady", "immersive"]
LearningFormat = Literal["home_individual", "home_online_group", "in_person_group"]


def _to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


class StrictModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        extra="forbid",
        populate_by_name=True,
    )


class LocalizedText(StrictModel):
    en: str
    hi: str


class SyntheticRecord(StrictModel):
    synthetic: Literal[True] = True
    dataset_version: str = DATASET_VERSION


class HobbyCatalogRecord(SyntheticRecord):
    hobby_id: str
    label: LocalizedText
    aliases: tuple[str, ...]


class SyntheticLearnerRecord(SyntheticRecord):
    candidate_id: str
    candidate_type: Literal["partner"] = "partner"
    display_name: str
    active: bool
    matching_consent: bool
    hobby_id: str
    goal_tag: GoalTag | None
    experience_level: int = Field(ge=0, le=2)
    availability_tier: AvailabilityTier
    languages: tuple[Language, ...]
    pace: AvailabilityTier
    learning_format: LearningFormat
    city_code: str | None = None


class SyntheticMentorRecord(SyntheticRecord):
    candidate_id: str
    candidate_type: Literal["mentor"] = "mentor"
    display_name: str
    active: bool
    listing_consent: bool
    status: Literal["verified", "unverified"]
    published: bool
    taught_hobby_ids: tuple[str, ...]
    supported_goal_tags: tuple[GoalTag, ...]
    taught_levels: tuple[int, ...]
    supported_languages: tuple[Language, ...]
    availability_tier: AvailabilityTier
    pace: AvailabilityTier
    supported_formats: tuple[LearningFormat, ...]
    primary_format: LearningFormat
    city_code: str | None = None
    price_inr: Literal[0] = 0


class SyntheticCircleRecord(SyntheticRecord):
    circle_id: str
    hobby_id: str
    starts_on: date
    future: Literal[True] = True
    deferred_from_matching: Literal[True] = True


class SyntheticActivityRecord(SyntheticRecord):
    activity_id: str
    occurred_on: date
    activity_type: Literal["learning", "matching"]


class SyntheticRelationRecord(SyntheticRecord):
    relation_id: str
    kind: Literal["block", "rejection"]
    source_candidate_id: str
    target_candidate_id: str
    active: Literal[True] = True


class SyntheticDataset(StrictModel):
    dataset_version: str
    generator_version: str
    learners: list[SyntheticLearnerRecord]
    mentors: list[SyntheticMentorRecord]
    hobbies: list[HobbyCatalogRecord]
    circles: list[SyntheticCircleRecord]
    activity: list[SyntheticActivityRecord]
    relations: list[SyntheticRelationRecord]


HOBBY_CATALOG = (
    ("watercolour", "Watercolour painting", "वॉटरकलर पेंटिंग", ("watercolour", "watercolours", "watercolor", "watercolor painting", "वॉटरकलर")),
    ("drawing", "Drawing", "ड्रॉइंग", ("sketching", "चित्र बनाना")),
    ("embroidery", "Embroidery", "कढ़ाई", ("hand embroidery", "हैंड एम्ब्रॉयडरी")),
    ("knitting", "Knitting", "बुनाई", ("ऊन बुनाई",)),
    ("crochet", "Crochet", "क्रोशिया", ("crocheting",)),
    ("sewing", "Sewing", "सिलाई", ("stitching",)),
    ("classical_singing", "Classical singing", "शास्त्रीय गायन", ("classical music",)),
    ("folk_singing", "Folk singing", "लोक गायन", ("folk music",)),
    ("harmonium", "Harmonium", "हारमोनियम", ("harmonium playing",)),
    ("gardening", "Gardening", "बागवानी", ("home gardening",)),
    ("baking", "Baking", "बेकिंग", ("cake baking",)),
    ("regional_cooking", "Regional cooking", "क्षेत्रीय खाना बनाना", ("regional recipes",)),
    ("photography", "Photography", "फ़ोटोग्राफ़ी", ("phone photography",)),
    ("creative_writing", "Creative writing", "रचनात्मक लेखन", ("story writing",)),
    ("spoken_english", "Spoken English", "बोली जाने वाली अंग्रेज़ी", ("english speaking",)),
)


def _stable_index(seed: str, namespace: str, index: int, size: int) -> int:
    digest = sha256(f"{seed}:{namespace}:{index}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % size


def _catalog_records() -> list[HobbyCatalogRecord]:
    return [
        HobbyCatalogRecord(
            hobby_id=hobby_id,
            label=LocalizedText(en=en, hi=hi),
            aliases=(en, hi, *aliases),
        )
        for hobby_id, en, hi, aliases in HOBBY_CATALOG
    ]


def _matched_partner(candidate_id: str, display_name: str) -> SyntheticLearnerRecord:
    return SyntheticLearnerRecord(
        candidate_id=candidate_id,
        display_name=display_name,
        active=True,
        matching_consent=True,
        hobby_id="watercolour",
        goal_tag="complete_small_project",
        experience_level=1,
        availability_tier="steady",
        languages=("hi",),
        pace="steady",
        learning_format="home_online_group",
        city_code="pune",
    )


def _learners(seed: str) -> list[SyntheticLearnerRecord]:
    records = [
        _matched_partner("syn_partner_0001", "Kavita Demo"),
        _matched_partner("syn_partner_0002", "Blocked Demo"),
        _matched_partner("syn_partner_0003", "Rejected Demo"),
    ]
    hobby_ids = [entry[0] for entry in HOBBY_CATALOG]
    goals: tuple[GoalTag, ...] = (
        "restart_basics",
        "complete_small_project",
        "build_routine",
        "learn_with_peers",
        "prepare_to_teach",
    )
    tiers: tuple[AvailabilityTier, ...] = ("gentle", "steady", "immersive")
    cities = ("pune", "jaipur", "lucknow", "indore", "mysuru")
    for index in range(4, 250):
        hobby_id = hobby_ids[(index - 1) % len(hobby_ids)]
        tier = tiers[_stable_index(seed, "learner-tier", index, len(tiers))]
        records.append(
            SyntheticLearnerRecord(
                candidate_id=f"syn_partner_{index:04d}",
                display_name=f"Sakhi Demo {index:03d}",
                active=True,
                matching_consent=index % 11 != 0,
                hobby_id=hobby_id,
                goal_tag=goals[_stable_index(seed, "learner-goal", index, len(goals))],
                experience_level=_stable_index(seed, "learner-level", index, 3),
                availability_tier=tier,
                languages=("en", "hi") if index % 5 == 0 else (("hi",) if index % 2 == 0 else ("en",)),
                pace=tier,
                learning_format="home_individual",
                city_code=cities[_stable_index(seed, "learner-city", index, len(cities))],
            ),
        )
    records.append(
        SyntheticLearnerRecord(
            candidate_id="syn_requester_0001",
            display_name="Meera Demo",
            active=True,
            matching_consent=True,
            hobby_id="watercolour",
            goal_tag="complete_small_project",
            experience_level=1,
            availability_tier="steady",
            languages=("hi",),
            pace="steady",
            learning_format="home_online_group",
            city_code="pune",
        ),
    )
    return records


def _mentors(seed: str) -> list[SyntheticMentorRecord]:
    hobby_ids = [entry[0] for entry in HOBBY_CATALOG]
    goals: tuple[GoalTag, ...] = (
        "restart_basics",
        "complete_small_project",
        "build_routine",
        "learn_with_peers",
        "prepare_to_teach",
    )
    tiers: tuple[AvailabilityTier, ...] = ("gentle", "steady", "immersive")
    records: list[SyntheticMentorRecord] = []
    for index in range(1, 41):
        hobby_id = "watercolour" if index == 1 else hobby_ids[(index - 1) % len(hobby_ids)]
        tier = "steady" if index == 1 else tiers[_stable_index(seed, "mentor-tier", index, 3)]
        records.append(
            SyntheticMentorRecord(
                candidate_id=f"syn_mentor_{index:04d}",
                display_name="Leela Mentor Demo" if index == 1 else f"Mentor Demo {index:03d}",
                active=True,
                listing_consent=True,
                status="verified",
                published=True,
                taught_hobby_ids=(hobby_id,),
                supported_goal_tags=("complete_small_project",) if index == 1 else (goals[index % len(goals)],),
                taught_levels=(0, 1, 2) if index == 1 else (index % 3,),
                supported_languages=("en", "hi") if index == 1 or index % 4 == 0 else (("hi",) if index % 2 == 0 else ("en",)),
                availability_tier=tier,
                pace=tier,
                supported_formats=("home_online_group", "home_individual") if index == 1 else ("home_individual",),
                primary_format="home_online_group" if index == 1 else "home_individual",
                city_code="pune",
                price_inr=0,
            ),
        )
    return records


def generate_synthetic_dataset(
    seed: str = SYNTHETIC_SEED,
    generator_version: str = GENERATOR_VERSION,
) -> SyntheticDataset:
    hobbies = _catalog_records()
    circles = [
        SyntheticCircleRecord(
            circle_id=f"syn_circle_{index:04d}",
            hobby_id=hobbies[(index - 1) % len(hobbies)].hobby_id,
            starts_on=date(2026, 9, 1) + timedelta(days=index - 1),
        )
        for index in range(1, 26)
    ]
    activity = [
        SyntheticActivityRecord(
            activity_id=f"syn_activity_{offset + 1:04d}",
            occurred_on=date(2026, 6, 1) + timedelta(days=offset),
            activity_type="learning" if offset % 3 else "matching",
        )
        for offset in range(90)
    ]
    relations = [
        SyntheticRelationRecord(
            relation_id="syn_relation_block_0001",
            kind="block",
            source_candidate_id="syn_partner_0002",
            target_candidate_id="syn_requester_0001",
        ),
        SyntheticRelationRecord(
            relation_id="syn_relation_rejection_0001",
            kind="rejection",
            source_candidate_id="syn_requester_0001",
            target_candidate_id="syn_partner_0003",
        ),
    ]
    return SyntheticDataset(
        dataset_version=DATASET_VERSION,
        generator_version=generator_version,
        learners=_learners(seed),
        mentors=_mentors(seed),
        hobbies=hobbies,
        circles=circles,
        activity=activity,
        relations=relations,
    )

