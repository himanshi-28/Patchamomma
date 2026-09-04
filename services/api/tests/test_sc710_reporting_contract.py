import json
from pathlib import Path

API_ROOT = Path(__file__).parents[1]
CONTRACT_PATH = API_ROOT / "analytics" / "bigquery_contract.json"
VIEW_PATH = API_ROOT / "analytics" / "checkpoint_metrics_v1.sql"

RAW_COLUMNS = [
    "event_date",
    "event_timestamp",
    "schema_version",
    "event_name",
    "event_id",
    "event_key",
    "payload_hash",
    "subject_key",
    "subject_key_version",
    "environment",
    "journey_schema_version",
    "journey_generator",
    "journey_fallback_used",
    "matching_contract_version",
    "recommendation_type",
    "recommendation_outcome",
    "result_count",
]
REPORTING_COLUMNS = [
    "event_date",
    "confirmed_profiles",
    "journey_drafts_created",
    "journeys_confirmed",
    "recommendations_matched",
    "recommendations_no_matches",
    "journey_drafts_per_confirmed_profile",
    "journey_confirmations_per_draft",
    "recommendations_per_confirmed_journey",
]
PRIVATE_ONLY_COLUMNS = {
    "event_timestamp",
    "schema_version",
    "event_name",
    "event_id",
    "event_key",
    "payload_hash",
    "subject_key",
    "subject_key_version",
    "environment",
    "journey_schema_version",
    "journey_generator",
    "journey_fallback_used",
    "matching_contract_version",
    "recommendation_type",
    "recommendation_outcome",
    "result_count",
}


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text())


def test_private_table_has_exact_schema_region_partition_retention_and_cost_controls() -> None:
    contract = load_contract()
    table = contract["privateTable"]

    assert contract["location"] == "asia-south1"
    assert contract["billingModel"] == "on_demand"
    assert contract["maximumBytesBilled"] == 20 * 1024 * 1024
    assert contract["datasetTimeTravelHours"] == 48
    assert table["resource"] == "sakhi_analytics.checkpoint_events_v1"
    assert [column["name"] for column in table["schema"]] == RAW_COLUMNS
    assert table["partitionField"] == "event_date"
    assert table["requirePartitionFilter"] is True
    assert table["partitionExpirationDays"] == 90
    assert table["clusteringFields"] == ["event_name", "subject_key"]
    assert contract["exports"] == []
    assert contract["scheduledQueries"] == []
    assert contract["materializedViews"] == []


def test_authorized_view_is_in_second_dataset_and_excludes_every_private_column() -> None:
    contract = load_contract()
    view = contract["reportingView"]
    sql = VIEW_PATH.read_text()

    assert view["resource"] == "sakhi_reporting.checkpoint_metrics_v1"
    assert view["source"] == "sakhi_analytics.checkpoint_events_v1"
    assert view["authorizedAgainst"] == "sakhi_analytics"
    assert view["columns"] == REPORTING_COLUMNS
    assert PRIVATE_ONLY_COLUMNS.isdisjoint(view["columns"])
    assert "INTERVAL 89 DAY" in sql
    assert 'CURRENT_DATE("Asia/Kolkata")' in sql
    assert "event_date" in sql
    assert "GROUP BY event_date" in sql
    assert "SELECT *" not in sql.upper()
    assert "CREATE MATERIALIZED" not in sql.upper()


def test_reporting_identity_can_read_only_the_aggregate_view() -> None:
    contract = load_contract()
    access = contract["reportingAccess"]

    assert access == {
        "credentialMode": "owners_credentials",
        "automaticRefresh": False,
        "publicSharing": False,
        "allowedResources": ["sakhi_reporting.checkpoint_metrics_v1"],
        "deniedResources": [
            "sakhi_analytics",
            "sakhi_analytics.checkpoint_events_v1",
            "firestore",
        ],
    }


def test_checkpoint_query_has_a_fixed_partition_predicate_and_byte_ceiling() -> None:
    contract = load_contract()
    query = contract["checkpointQuery"]

    assert query["resource"] == "sakhi_reporting.checkpoint_metrics_v1"
    assert query["maximumBytesBilled"] == 20 * 1024 * 1024
    assert query["dryRunBytes"] <= query["maximumBytesBilled"]
    assert query["partitionWindowDays"] == 90


def test_delivery_queue_contract_is_bounded_and_regional() -> None:
    queue = load_contract()["deliveryQueue"]

    assert queue == {
        "resource": "analytics-delivery",
        "location": "asia-south1",
        "maxDispatchesPerSecond": 2,
        "maxConcurrentDispatches": 2,
        "maxAttempts": 8,
        "maxRetryDurationSeconds": 24 * 60 * 60,
        "minBackoffSeconds": 10,
        "maxBackoffSeconds": 15 * 60,
        "bodyFields": ["deliveryHandle"],
        "oidcRequired": True,
    }
