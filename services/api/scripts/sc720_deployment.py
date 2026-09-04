"""Pure, fail-closed SC-720 deployment artifact helpers.

Cloud writes remain separately reviewed operator actions. This module only
renders the locked service manifest and the versioned recommendation catalog.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.persistence import MATCHING_DATASET_RECORD_VERSION
from app.synthetic_data import generate_synthetic_dataset

PROJECT_ID = "patchamomma-2026-505415"
PROJECT_NUMBER = "859217028205"
REGION = "asia-south1"
SERVICE_NAME = "sakhicircle-api"
FIREBASE_APP_ID = "1:859217028205:web:eaf322c7cc7555721e0b64"
CLOUD_RUN_URL = f"https://{SERVICE_NAME}-{PROJECT_NUMBER}.{REGION}.run.app"
LIVE_HOSTING_ORIGINS = (
    f"https://{PROJECT_ID}.web.app",
    f"https://{PROJECT_ID}.firebaseapp.com",
)
API_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TEMPLATE = API_ROOT / "cloud-run.service.yaml.tmpl"

_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
_SECRET_VERSION_PATTERN = re.compile(r"[1-9][0-9]*")
_PREVIEW_ORIGIN_PATTERN = re.compile(
    rf"https://{re.escape(PROJECT_ID)}--sc720-preview-[a-z0-9-]+\.web\.app"
)


def _validated_origins(origins: Sequence[str]) -> list[str]:
    normalized = list(origins)
    if len(normalized) != len(set(normalized)):
        raise ValueError("Hosting origins must be unique")
    if not set(LIVE_HOSTING_ORIGINS).issubset(normalized):
        raise ValueError("Hosting origins must include both live domains")
    preview_origins = [
        origin for origin in normalized if origin not in LIVE_HOSTING_ORIGINS
    ]
    if len(preview_origins) > 1 or any(
        _PREVIEW_ORIGIN_PATTERN.fullmatch(origin) is None
        for origin in preview_origins
    ):
        raise ValueError("Hosting origin is outside the approved Firebase site")
    if any(
        origin not in LIVE_HOSTING_ORIGINS and origin not in preview_origins
        for origin in normalized
    ):
        raise ValueError("Hosting origin is outside the approved Firebase site")
    return normalized


def render_cloud_run_manifest(
    *,
    image_digest: str,
    firebase_app_id: str,
    analytics_hmac_secret_version: str,
    allowed_origins: Sequence[str],
) -> str:
    """Render only the exact approved Cloud Run target with immutable inputs."""

    if _DIGEST_PATTERN.fullmatch(image_digest) is None:
        raise ValueError("An immutable lowercase SHA-256 image digest is required")
    if firebase_app_id != FIREBASE_APP_ID:
        raise ValueError("Firebase app does not match the approved web app")
    if _SECRET_VERSION_PATTERN.fullmatch(analytics_hmac_secret_version) is None:
        raise ValueError("A numeric immutable analytics secret version is required")
    origins = _validated_origins(allowed_origins)

    replacements = {
        "${IMAGE_DIGEST}": image_digest,
        "${FIREBASE_APP_ID}": firebase_app_id,
        "${ANALYTICS_TASK_AUDIENCE}": CLOUD_RUN_URL,
        "${ANALYTICS_HMAC_SECRET_VERSION}": analytics_hmac_secret_version,
        "${ALLOWED_ORIGINS}": json.dumps(origins, separators=(",", ":")),
    }
    rendered = MANIFEST_TEMPLATE.read_text(encoding="utf-8")
    for placeholder, value in replacements.items():
        if placeholder not in rendered:
            raise ValueError(f"Required manifest placeholder is missing: {placeholder}")
        rendered = rendered.replace(placeholder, value)
    if "${" in rendered:
        raise ValueError("The Cloud Run manifest contains an unresolved placeholder")
    return rendered


def build_recommendation_catalog_document(
    *,
    published_at: datetime,
) -> dict[str, Any]:
    """Build the one approved, deterministic synthetic catalog document."""

    if published_at.tzinfo is None or published_at.utcoffset() is None:
        raise ValueError("Catalog publication time must include a timezone")
    return {
        "recordVersion": MATCHING_DATASET_RECORD_VERSION,
        "dataset": generate_synthetic_dataset().model_dump(
            by_alias=True,
            mode="json",
        ),
        "publishedAt": published_at.astimezone(UTC),
    }


def catalog_publish_action(
    *,
    existing: Mapping[str, object] | None,
    proposed: Mapping[str, object],
) -> Literal["create", "unchanged"]:
    """Refuse to overwrite a catalog unless it is byte-equivalent in value."""

    if existing is None:
        return "create"
    if existing == proposed:
        return "unchanged"
    raise ValueError("The existing catalog differs from the approved document")
