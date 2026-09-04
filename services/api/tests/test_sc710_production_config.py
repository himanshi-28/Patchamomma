import pytest
from app.analytics_google import ProductionAnalyticsConfig
from pydantic import ValidationError

VALID_CONFIG = {
    "projectId": "test-project",
    "firestoreDatabaseId": "(default)",
    "location": "asia-south1",
    "privateDatasetId": "sakhi_analytics",
    "analyticsTableId": "checkpoint_events_v1",
    "reportingDatasetId": "sakhi_reporting",
    "reportingViewId": "checkpoint_metrics_v1",
    "queueId": "analytics-delivery",
    "taskServiceAccount": "sakhi-task-delivery@test-project.iam.gserviceaccount.com",
    "taskAudience": "https://api.example.test/internal/v1/analytics/deliver",
    "hmacSecretName": "sakhi-analytics-hmac-key",
    "hmacSecretVersions": ["7", "8"],
    "currentHmacSecretVersion": "8",
}


@pytest.mark.parametrize("required_field", tuple(VALID_CONFIG))
def test_every_production_analytics_binding_is_required(required_field: str) -> None:
    incomplete = {key: value for key, value in VALID_CONFIG.items() if key != required_field}

    with pytest.raises(ValidationError):
        ProductionAnalyticsConfig.model_validate(incomplete)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("location", "us-central1"),
        ("privateDatasetId", "different_private_dataset"),
        ("analyticsTableId", "events"),
        ("reportingDatasetId", "sakhi_analytics"),
        ("reportingViewId", "different_view"),
        ("queueId", "default"),
        ("hmacSecretName", "inline-key"),
        ("currentHmacSecretVersion", "9"),
    ),
)
def test_production_analytics_cannot_drift_from_the_approved_resources(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        ProductionAnalyticsConfig.model_validate({**VALID_CONFIG, field: value})
