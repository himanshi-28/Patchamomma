from datetime import UTC, datetime

import pytest

from app.cost_controls import COST_CONTROLS_SCHEMA_VERSION
from app.persistence import MATCHING_DATASET_RECORD_VERSION
from app.synthetic_data import DATASET_VERSION
from scripts.sc720_cloud_state import (
    plan_cost_controls,
    plan_recommendation_catalog,
)

NOW = datetime(2026, 9, 3, 18, 0, tzinfo=UTC)
SERVER_TIMESTAMP = object()


def test_missing_controls_are_created_in_maintenance_with_paid_calls_disabled() -> None:
    action, document = plan_cost_controls(
        current=None,
        server_timestamp=SERVER_TIMESTAMP,
    )

    assert action == "create"
    assert document == {
        "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
        "geminiProjectDailyAllowance": 0,
        "maintenanceMode": True,
        "updatedAt": SERVER_TIMESTAMP,
    }


def test_existing_controls_are_only_tightened_and_then_idempotent() -> None:
    current = {
        "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
        "geminiProjectDailyAllowance": 20,
        "maintenanceMode": False,
        "updatedAt": NOW,
    }

    action, document = plan_cost_controls(
        current=current,
        server_timestamp=SERVER_TIMESTAMP,
    )
    assert action == "update"
    assert document is not None
    assert document["geminiProjectDailyAllowance"] == 0
    assert document["maintenanceMode"] is True

    action, document = plan_cost_controls(
        current={
            **current,
            "geminiProjectDailyAllowance": 0,
            "maintenanceMode": True,
        },
        server_timestamp=SERVER_TIMESTAMP,
    )
    assert action == "unchanged"
    assert document is None


def test_malformed_controls_fail_closed_without_a_write_plan() -> None:
    with pytest.raises(ValueError):
        plan_cost_controls(
            current={
                "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
                "geminiProjectDailyAllowance": 0,
                "maintenanceMode": True,
                "updatedAt": NOW,
                "unexpected": True,
            },
            server_timestamp=SERVER_TIMESTAMP,
        )


def test_missing_catalog_builds_the_locked_versioned_dataset() -> None:
    action, document = plan_recommendation_catalog(
        current=None,
        published_at=NOW,
    )

    assert action == "create"
    assert document is not None
    assert document["recordVersion"] == MATCHING_DATASET_RECORD_VERSION
    assert document["publishedAt"] == NOW
    assert document["dataset"]["datasetVersion"] == DATASET_VERSION
    assert len(document["dataset"]["learners"]) == 250
    assert len(document["dataset"]["mentors"]) == 40
    assert len(document["dataset"]["hobbies"]) == 16
    assert len(document["dataset"]["circles"]) == 25
    assert len(document["dataset"]["activity"]) == 90


def test_existing_identical_catalog_is_unchanged_and_differences_are_refused() -> None:
    _, current = plan_recommendation_catalog(current=None, published_at=NOW)
    assert current is not None

    action, document = plan_recommendation_catalog(
        current=current,
        published_at=NOW,
    )
    assert action == "unchanged"
    assert document is None

    with pytest.raises(ValueError, match="existing catalog"):
        plan_recommendation_catalog(
            current={**current, "recordVersion": "unexpected"},
            published_at=NOW,
        )
