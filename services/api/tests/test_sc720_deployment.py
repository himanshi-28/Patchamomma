import json
from datetime import UTC, datetime

import pytest
import yaml

from app.persistence import MATCHING_DATASET_RECORD_VERSION
from app.synthetic_data import DATASET_VERSION
from scripts.sc720_deployment import (
    build_recommendation_catalog_document,
    catalog_publish_action,
    render_cloud_run_manifest,
)

PROJECT_ID = "patchamomma-2026-505415"
PROJECT_NUMBER = "859217028205"
REGION = "asia-south1"
SERVICE_NAME = "sakhicircle-api"
PRIMARY_HOSTING_SITE_ID = "sakhi-circle"
FIREBASE_APP_ID = "1:859217028205:web:eaf322c7cc7555721e0b64"
CLOUD_RUN_URL = (
    f"https://{SERVICE_NAME}-{PROJECT_NUMBER}.{REGION}.run.app"
)
LIVE_ORIGINS = [
    f"https://{PROJECT_ID}.web.app",
    f"https://{PROJECT_ID}.firebaseapp.com",
    f"https://{PRIMARY_HOSTING_SITE_ID}.web.app",
    f"https://{PRIMARY_HOSTING_SITE_ID}.firebaseapp.com",
]
PREVIEW_ORIGIN = f"https://{PROJECT_ID}--sc720-preview-a1b2c3.web.app"
NOW = datetime(2026, 9, 3, 13, 0, tzinfo=UTC)


def _environment(manifest: dict) -> dict[str, object]:
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    return {
        item["name"]: item.get("value", item.get("valueFrom"))
        for item in container["env"]
    }


def test_renderer_binds_the_immutable_image_and_exact_production_origins() -> None:
    digest = "a" * 64

    rendered = render_cloud_run_manifest(
        image_digest=digest,
        firebase_app_id=FIREBASE_APP_ID,
        analytics_hmac_secret_version="1",
        allowed_origins=[*LIVE_ORIGINS, PREVIEW_ORIGIN],
    )
    manifest = yaml.safe_load(rendered)
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    environment = _environment(manifest)

    assert container["image"] == (
        f"{REGION}-docker.pkg.dev/{PROJECT_ID}/sakhi-containers/"
        f"{SERVICE_NAME}@sha256:{digest}"
    )
    assert environment["SAKHI_FIREBASE_APP_ID"] == FIREBASE_APP_ID
    assert environment["SAKHI_ANALYTICS_TASK_AUDIENCE"] == CLOUD_RUN_URL
    assert environment["SAKHI_ANALYTICS_HMAC_SECRET_VERSIONS"] == '["1"]'
    assert environment["SAKHI_ANALYTICS_CURRENT_HMAC_SECRET_VERSION"] == "1"
    assert json.loads(environment["SAKHI_ALLOWED_ORIGINS"]) == [
        *LIVE_ORIGINS,
        PREVIEW_ORIGIN,
    ]
    assert "${" not in rendered


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("image_digest", "latest", "digest"),
        ("firebase_app_id", "1:wrong:web:app", "Firebase app"),
        ("analytics_hmac_secret_version", "latest", "secret version"),
        ("allowed_origins", ["https://example.com"], "Hosting origin"),
    ],
)
def test_renderer_rejects_mutable_or_cross_project_inputs(
    field: str,
    value: object,
    message: str,
) -> None:
    inputs: dict[str, object] = {
        "image_digest": "a" * 64,
        "firebase_app_id": FIREBASE_APP_ID,
        "analytics_hmac_secret_version": "1",
        "allowed_origins": LIVE_ORIGINS,
    }
    inputs[field] = value

    with pytest.raises(ValueError, match=message):
        render_cloud_run_manifest(**inputs)


def test_catalog_document_is_versioned_bounded_and_idempotent() -> None:
    document = build_recommendation_catalog_document(published_at=NOW)
    dataset = document["dataset"]

    assert document["recordVersion"] == MATCHING_DATASET_RECORD_VERSION
    assert document["publishedAt"] == NOW
    assert dataset["datasetVersion"] == DATASET_VERSION
    assert len(dataset["learners"]) == 250
    assert len(dataset["mentors"]) == 40
    assert len(dataset["hobbies"]) == 16
    assert len(dataset["circles"]) == 25
    assert len(dataset["activity"]) == 90
    assert len(json.dumps(document, default=str).encode("utf-8")) < 900_000

    assert catalog_publish_action(existing=None, proposed=document) == "create"
    assert catalog_publish_action(existing=document, proposed=document) == "unchanged"
    with pytest.raises(ValueError, match="existing catalog"):
        catalog_publish_action(
            existing={**document, "recordVersion": "unexpected"},
            proposed=document,
        )
