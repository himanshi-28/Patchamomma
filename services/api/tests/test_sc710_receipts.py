import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.analytics import (
    ANALYTICS_SCHEMA_VERSION,
    ActionReceiptClaims,
    AnalyticsKeyring,
    AnalyticsReceiptError,
    AnalyticsReceiptRequest,
    AnalyticsService,
    InMemoryAnalyticsBackend,
    JourneyAnalyticsProperties,
    RecommendationAnalyticsProperties,
)

NOW = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
def analytics_service() -> AnalyticsService:
    event_ids = iter(
        (
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d2",
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d3",
            "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d4",
        )
    )
    return AnalyticsService(
        project_id="test-project",
        environment="test",
        keyring=AnalyticsKeyring(
            project_id="test-project",
            keys={"7": b"older-test-key", "8": b"current-test-key"},
            current_version="8",
        ),
        backend=InMemoryAnalyticsBackend(),
        clock=lambda: NOW,
        event_id_factory=lambda _now: next(event_ids),
        nonce_factory=lambda: "fixed-test-nonce",
    )


def _decode_receipt_payload(receipt: str) -> dict[str, object]:
    _version, encoded, _signature = receipt.split(".")
    encoded += "=" * (-len(encoded) % 4)
    return json.loads(base64.urlsafe_b64decode(encoded))


def test_all_four_events_are_server_derived_with_exact_allowlisted_properties() -> None:
    service = analytics_service()

    profile = service.issue_profile_confirmed(subject_uid="firebase-user")
    draft = service.issue_journey_draft_created(
        subject_uid="firebase-user",
        journey_schema_version="1.0.0",
        generator="deterministic_fixture",
        fallback_used=False,
    )
    confirmed = service.issue_journey_confirmed(
        subject_uid="firebase-user",
        journey_schema_version="1.0.0",
        generator="curated_fallback",
        fallback_used=True,
    )
    recommendation = service.issue_recommendation_presented(
        subject_uid="firebase-user",
        matching_contract_version="matching-v1.0.0",
        recommendation_type="partner",
        outcome="matched",
        result_count=2,
    )

    assert [item.event_name for item in (profile, draft, confirmed, recommendation)] == [
        "profile_confirmed",
        "journey_draft_created",
        "journey_confirmed",
        "recommendation_presented",
    ]
    assert profile.properties == {}
    assert draft.properties == {
        "journeySchemaVersion": "1.0.0",
        "generator": "deterministic_fixture",
        "fallbackUsed": False,
    }
    assert confirmed.properties == {
        "journeySchemaVersion": "1.0.0",
        "generator": "curated_fallback",
        "fallbackUsed": True,
    }
    assert recommendation.properties == {
        "matchingContractVersion": "matching-v1.0.0",
        "recommendationType": "partner",
        "outcome": "matched",
        "resultCount": 2,
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (
            {
                "journeySchemaVersion": "1.0.0",
                "generator": "curated_fallback",
                "fallbackUsed": False,
            },
            "fallback",
        ),
        (
            {
                "matchingContractVersion": "matching-v1.0.0",
                "recommendationType": "mentor",
                "outcome": "matched",
                "resultCount": 0,
            },
            "result",
        ),
        (
            {
                "matchingContractVersion": "matching-v1.0.0",
                "recommendationType": "partner",
                "outcome": "no_matches",
                "resultCount": 1,
            },
            "result",
        ),
    ),
)
def test_event_specific_property_combinations_are_strict(
    payload: dict[str, object],
    message: str,
) -> None:
    model = (
        JourneyAnalyticsProperties
        if "journeySchemaVersion" in payload
        else RecommendationAnalyticsProperties
    )
    with pytest.raises(ValidationError, match=message):
        model.model_validate(payload)


def test_request_and_signed_claims_reject_unknown_fields_recursively() -> None:
    with pytest.raises(ValidationError):
        AnalyticsReceiptRequest.model_validate(
            {
                "schemaVersion": ANALYTICS_SCHEMA_VERSION,
                "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
                "actionReceipt": "v1.payload.signature",
                "outcome": "matched",
            }
        )

    valid_claims = {
        "schemaVersion": ANALYTICS_SCHEMA_VERSION,
        "eventId": "01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
        "eventName": "journey_draft_created",
        "properties": {
            "journeySchemaVersion": "1.0.0",
            "generator": "deterministic_fixture",
            "fallbackUsed": False,
        },
        "issuedAt": NOW.isoformat(),
        "expiresAt": (NOW + timedelta(hours=24)).isoformat(),
        "nonce": "receipt-nonce",
        "subjectBinding": "opaque-binding",
        "keyVersion": "8",
    }
    with pytest.raises(ValidationError):
        ActionReceiptClaims.model_validate(
            {**valid_claims, "properties": {**valid_claims["properties"], "city": "Pune"}}
        )


FORBIDDEN_ANALYTICS_FIELDS = {
    "name",
    "displayName",
    "uid",
    "email",
    "phone",
    "transcript",
    "rawText",
    "normalizedText",
    "hobby",
    "goal",
    "experience",
    "availability",
    "language",
    "locale",
    "accessibility",
    "format",
    "planConsent",
    "matchingConsent",
    "city",
    "location",
    "journeyId",
    "journeyContent",
    "candidateId",
    "candidateName",
    "score",
    "reasons",
    "ipAddress",
    "userAgent",
    "authToken",
    "appCheckToken",
    "traceId",
    "credentials",
    "prompt",
    "modelOutput",
    "rawAudio",
    "paymentData",
}


def test_receipt_and_row_contain_no_forbidden_identifier_or_content_field() -> None:
    service = analytics_service()
    issued = service.issue_recommendation_presented(
        subject_uid="firebase-user",
        matching_contract_version="matching-v1.0.0",
        recommendation_type="mentor",
        outcome="no_matches",
        result_count=0,
    )

    receipt_payload = _decode_receipt_payload(issued.action_receipt)
    row = issued.row.model_dump(by_alias=True)
    serialized = json.dumps(
        {"receipt": receipt_payload, "row": row},
        sort_keys=True,
    )

    assert FORBIDDEN_ANALYTICS_FIELDS.isdisjoint(receipt_payload)
    assert FORBIDDEN_ANALYTICS_FIELDS.isdisjoint(row)
    assert "firebase-user" not in serialized
    assert "test-project:firebase-user" not in serialized


def test_timestamp_uuid_keys_and_environment_are_server_owned() -> None:
    service = analytics_service()

    issued = service.issue_profile_confirmed(subject_uid="firebase-user")
    row = issued.row

    assert UUID(issued.event_id).version == 7
    assert UUID(issued.event_id).int >> 80 == int(NOW.timestamp() * 1000)
    assert row.event_timestamp == NOW
    assert row.event_date.isoformat() == "2026-09-02"
    assert row.environment == "test"
    assert row.schema_version == ANALYTICS_SCHEMA_VERSION
    assert row.subject_key_version == "8"
    assert row.subject_key != "firebase-user"
    assert row.event_key not in {issued.event_id, row.subject_key}
    assert len(row.payload_hash) == 64


def test_receipt_is_bound_to_subject_expires_at_24_hours_and_cannot_be_tampered() -> None:
    service = analytics_service()
    issued = service.issue_profile_confirmed(subject_uid="firebase-user")

    claims = service.verify_receipt(
        subject_uid="firebase-user",
        event_id=issued.event_id,
        action_receipt=issued.action_receipt,
    )
    assert claims.expires_at - claims.issued_at == timedelta(hours=24)

    with pytest.raises(AnalyticsReceiptError, match="subject"):
        service.verify_receipt(
            subject_uid="different-user",
            event_id=issued.event_id,
            action_receipt=issued.action_receipt,
        )
    with pytest.raises(AnalyticsReceiptError):
        service.verify_receipt(
            subject_uid="firebase-user",
            event_id=issued.event_id,
            action_receipt=issued.action_receipt[:-1] + "x",
        )

    service.clock = lambda: NOW + timedelta(hours=24, microseconds=1)
    with pytest.raises(AnalyticsReceiptError, match="expired"):
        service.verify_receipt(
            subject_uid="firebase-user",
            event_id=issued.event_id,
            action_receipt=issued.action_receipt,
        )


def test_key_rotation_verifies_old_receipts_and_resolves_every_deletion_subject_key() -> None:
    service = analytics_service()
    old_keyring = AnalyticsKeyring(
        project_id="test-project",
        keys={"7": b"older-test-key"},
        current_version="7",
    )
    service.keyring = old_keyring
    issued = service.issue_profile_confirmed(subject_uid="firebase-user")

    rotated = AnalyticsKeyring(
        project_id="test-project",
        keys={"7": b"older-test-key", "8": b"current-test-key"},
        current_version="8",
    )
    service.keyring = rotated

    assert service.verify_receipt(
        subject_uid="firebase-user",
        event_id=issued.event_id,
        action_receipt=issued.action_receipt,
    ).key_version == "7"
    resolved = rotated.subject_keys_for_deletion("firebase-user")
    assert set(resolved) == {"7", "8"}
    assert resolved["7"] != resolved["8"]
    assert rotated.deletion_fence_key("firebase-user") not in set(resolved.values())
