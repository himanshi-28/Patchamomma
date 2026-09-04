"""Publish or inspect the two approved SC-720 Firestore documents.

The OAuth access token is accepted only over stdin so it is never placed in a
process argument, environment variable, repository file, or operator output.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from google.cloud import firestore
from google.oauth2.credentials import Credentials

from app.cost_controls import (
    COST_CONTROLS_COLLECTION,
    COST_CONTROLS_DOCUMENT,
    COST_CONTROLS_SCHEMA_VERSION,
    CostControlState,
)
from app.persistence import MATCHING_DATASET_RECORD_VERSION, RECOMMENDATION_COLLECTION
from app.synthetic_data import DATASET_VERSION
from scripts.sc720_deployment import (
    PROJECT_ID,
    build_recommendation_catalog_document,
    catalog_publish_action,
)

DATABASE_ID = "(default)"
RECOMMENDATION_DOCUMENT = DATASET_VERSION

Action = Literal["create", "update", "unchanged"]


def plan_cost_controls(
    *,
    current: Mapping[str, object] | None,
    server_timestamp: object,
) -> tuple[Action, dict[str, object] | None]:
    """Plan the only approved transition: paid calls off and maintenance on."""

    if current is not None:
        state = CostControlState.model_validate(current)
        if (
            state.gemini_project_daily_allowance == 0
            and state.maintenance_mode is True
        ):
            return "unchanged", None

    document: dict[str, object] = {
        "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
        "geminiProjectDailyAllowance": 0,
        "maintenanceMode": True,
        "updatedAt": server_timestamp,
    }
    return ("create" if current is None else "update"), document


def plan_recommendation_catalog(
    *,
    current: Mapping[str, object] | None,
    published_at: datetime,
) -> tuple[Literal["create", "unchanged"], dict[str, Any] | None]:
    """Plan creation of the deterministic catalog without permitting overwrite."""

    effective_published_at = published_at
    if current is not None:
        stored_published_at = current.get("publishedAt")
        if not isinstance(stored_published_at, datetime):
            raise ValueError("The existing catalog has an invalid publication time")
        effective_published_at = stored_published_at

    proposed = build_recommendation_catalog_document(
        published_at=effective_published_at,
    )
    action = catalog_publish_action(existing=current, proposed=proposed)
    return action, proposed if action == "create" else None


def _snapshot_value(snapshot: Any) -> Mapping[str, object] | None:
    if not snapshot.exists:
        return None
    value = snapshot.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError("Approved Firestore document is malformed")
    return value


def _catalog_counts(document: Mapping[str, object]) -> dict[str, int]:
    dataset = document.get("dataset")
    if not isinstance(dataset, Mapping):
        raise TypeError("The recommendation catalog dataset is malformed")
    names = ("learners", "mentors", "hobbies", "circles", "activity")
    counts: dict[str, int] = {}
    for name in names:
        records = dataset.get(name)
        if not isinstance(records, list):
            raise TypeError("The recommendation catalog dataset is malformed")
        counts[name] = len(records)
    return counts


def _safe_summary(
    *,
    mode: str,
    controls: Mapping[str, object] | None,
    catalog: Mapping[str, object] | None,
    controls_action: Action,
    catalog_action: Literal["create", "unchanged"],
) -> dict[str, object]:
    catalog_for_summary = (
        catalog
        if catalog is not None
        else build_recommendation_catalog_document(published_at=datetime.now(UTC))
    )
    dataset = catalog_for_summary.get("dataset")
    if not isinstance(dataset, Mapping):
        raise TypeError("The recommendation catalog dataset is malformed")
    return {
        "projectId": PROJECT_ID,
        "databaseId": DATABASE_ID,
        "mode": mode,
        "costControls": {
            "path": f"{COST_CONTROLS_COLLECTION}/{COST_CONTROLS_DOCUMENT}",
            "exists": controls is not None,
            "action": controls_action,
            "schemaVersion": COST_CONTROLS_SCHEMA_VERSION,
            "geminiProjectDailyAllowance": 0,
            "maintenanceMode": True,
            "updatedAtPresent": controls is not None and "updatedAt" in controls,
        },
        "recommendationCatalog": {
            "path": f"{RECOMMENDATION_COLLECTION}/{RECOMMENDATION_DOCUMENT}",
            "exists": catalog is not None,
            "action": catalog_action,
            "recordVersion": MATCHING_DATASET_RECORD_VERSION,
            "datasetVersion": dataset.get("datasetVersion"),
            "counts": _catalog_counts(catalog_for_summary),
        },
    }


def _references(client: firestore.Client) -> tuple[Any, Any]:
    return (
        client.collection(COST_CONTROLS_COLLECTION).document(COST_CONTROLS_DOCUMENT),
        client.collection(RECOMMENDATION_COLLECTION).document(RECOMMENDATION_DOCUMENT),
    )


def _inspect(client: firestore.Client) -> dict[str, object]:
    controls_reference, catalog_reference = _references(client)
    controls = _snapshot_value(controls_reference.get())
    catalog = _snapshot_value(catalog_reference.get())
    controls_action, _ = plan_cost_controls(
        current=controls,
        server_timestamp=firestore.SERVER_TIMESTAMP,
    )
    catalog_action, _ = plan_recommendation_catalog(
        current=catalog,
        published_at=datetime.now(UTC),
    )
    return _safe_summary(
        mode="inspect",
        controls=controls,
        catalog=catalog,
        controls_action=controls_action,
        catalog_action=catalog_action,
    )


def _apply(client: firestore.Client) -> dict[str, object]:
    controls_reference, catalog_reference = _references(client)
    transaction = client.transaction()

    @firestore.transactional
    def commit_approved_documents(
        active_transaction: Any,
    ) -> tuple[Action, Literal["create", "unchanged"]]:
        controls = _snapshot_value(controls_reference.get(transaction=active_transaction))
        catalog = _snapshot_value(catalog_reference.get(transaction=active_transaction))
        controls_action, controls_document = plan_cost_controls(
            current=controls,
            server_timestamp=firestore.SERVER_TIMESTAMP,
        )
        catalog_action, catalog_document = plan_recommendation_catalog(
            current=catalog,
            published_at=datetime.now(UTC),
        )
        if controls_document is not None:
            active_transaction.set(controls_reference, controls_document)
        if catalog_document is not None:
            active_transaction.set(catalog_reference, catalog_document)
        return controls_action, catalog_action

    controls_action, catalog_action = commit_approved_documents(transaction)

    controls = _snapshot_value(controls_reference.get())
    catalog = _snapshot_value(catalog_reference.get())
    verified_controls_action, _ = plan_cost_controls(
        current=controls,
        server_timestamp=firestore.SERVER_TIMESTAMP,
    )
    verified_catalog_action, _ = plan_recommendation_catalog(
        current=catalog,
        published_at=datetime.now(UTC),
    )
    if verified_controls_action != "unchanged" or verified_catalog_action != "unchanged":
        raise RuntimeError("Approved Firestore state did not verify after publication")

    return _safe_summary(
        mode="apply",
        controls=controls,
        catalog=catalog,
        controls_action=controls_action,
        catalog_action=catalog_action,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect or apply approved SC-720 state.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--confirm-project", required=True)
    parser.add_argument("--mode", choices=("inspect", "apply"), required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.project != PROJECT_ID or args.confirm_project != PROJECT_ID:
        raise ValueError("The active and confirmed projects must match the approved project")

    access_token = sys.stdin.readline().strip()
    if not access_token:
        raise ValueError("A Firebase CLI OAuth access token is required on stdin")
    credentials = Credentials(token=access_token)
    client = firestore.Client(
        project=PROJECT_ID,
        database=DATABASE_ID,
        credentials=credentials,
    )
    result = _inspect(client) if args.mode == "inspect" else _apply(client)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 - never expose credentials or cloud payloads
        print("SC-720 Firestore state operation failed.", file=sys.stderr)
        raise SystemExit(1) from None
