from datetime import date, timedelta

from app.synthetic_data import (
    DATASET_VERSION,
    GENERATOR_VERSION,
    SYNTHETIC_SEED,
    generate_synthetic_dataset,
)


def test_generator_is_byte_stable_for_the_committed_seed_and_version() -> None:
    first = generate_synthetic_dataset(
        seed=SYNTHETIC_SEED,
        generator_version=GENERATOR_VERSION,
    )
    second = generate_synthetic_dataset(
        seed=SYNTHETIC_SEED,
        generator_version=GENERATOR_VERSION,
    )

    assert first.dataset_version == DATASET_VERSION
    assert first.model_dump_json(by_alias=True) == second.model_dump_json(by_alias=True)


def test_dataset_has_the_exact_checkpoint_counts_dates_and_deferred_circles() -> None:
    dataset = generate_synthetic_dataset()

    assert len(dataset.learners) == 250
    assert len(dataset.mentors) == 40
    assert len(dataset.hobbies) == 15
    assert len(dataset.circles) == 25
    assert len(dataset.activity) == 90
    assert [record.occurred_on for record in dataset.activity] == [
        date(2026, 6, 1) + timedelta(days=offset) for offset in range(90)
    ]
    assert all(circle.future and circle.starts_on >= date(2026, 9, 1) for circle in dataset.circles)
    assert all(circle.deferred_from_matching for circle in dataset.circles)


def test_every_record_is_synthetic_versioned_and_contains_no_forbidden_field() -> None:
    dataset = generate_synthetic_dataset()
    collections = (
        dataset.learners,
        dataset.mentors,
        dataset.hobbies,
        dataset.circles,
        dataset.activity,
        dataset.relations,
    )
    forbidden_fields = {
        "uid",
        "email",
        "transcript",
        "rawAudio",
        "exactLocation",
        "voiceRecording",
        "credential",
        "paymentCredential",
        "confidentialWorkData",
        "productionIdentifier",
    }

    for collection in collections:
        assert collection
        for record in collection:
            payload = record.model_dump(by_alias=True)
            assert payload["synthetic"] is True
            assert payload["datasetVersion"] == DATASET_VERSION
            assert forbidden_fields.isdisjoint(payload)

    assert all("Demo" in learner.display_name for learner in dataset.learners)
    assert all("Demo" in mentor.display_name for mentor in dataset.mentors)
    assert {relation.kind for relation in dataset.relations} == {"block", "rejection"}

