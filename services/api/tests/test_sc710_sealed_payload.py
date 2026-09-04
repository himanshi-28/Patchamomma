from datetime import UTC, date, datetime

import pytest

from app.analytics import (
    AnalyticsKeyring,
    AnalyticsRow,
    SealedDeliveryCodec,
    SealedPayloadError,
)


def keyring(*, current_version: str = "8") -> AnalyticsKeyring:
    return AnalyticsKeyring(
        project_id="test-project",
        keys={"7": b"older-test-key-material-32-byte", "8": b"newer-test-key-material-32-byte"},
        current_version=current_version,
    )


def row() -> AnalyticsRow:
    return AnalyticsRow(
        event_date=date(2026, 9, 2),
        event_timestamp=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        event_name="recommendation_presented",
        event_id="01a06121-cc00-7b41-8aa4-9ce5f2f6e8d1",
        event_key="event-key-value",
        payload_hash="a" * 64,
        subject_key="subject-key-value",
        subject_key_version="8",
        environment="production",
        matching_contract_version="matching-v1.0.0",
        recommendation_type="partner",
        recommendation_outcome="matched",
        result_count=1,
    )


def test_sealed_payload_round_trip_is_randomized_bounded_and_contains_no_plaintext() -> None:
    nonces = iter((b"a" * 12, b"b" * 12))
    codec = SealedDeliveryCodec(keyring(), nonce_factory=lambda: next(nonces))
    analytics_row = row()

    first = codec.seal(
        analytics_row,
        delivery_handle_hash="handle-hash-value",
    )
    second = codec.seal(
        analytics_row,
        delivery_handle_hash="handle-hash-value",
    )

    assert first != second
    assert len(first.encode()) <= 4096
    assert analytics_row.event_id not in first
    assert analytics_row.event_name not in first
    assert analytics_row.event_key not in first
    assert analytics_row.subject_key not in first
    assert (
        codec.open(
            first,
            event_key=analytics_row.event_key,
            payload_hash=analytics_row.payload_hash,
            delivery_handle_hash="handle-hash-value",
        )
        == analytics_row
    )


@pytest.mark.parametrize(
    ("changed_field", "value"),
    (
        ("event_key", "different-event-key"),
        ("payload_hash", "b" * 64),
        ("delivery_handle_hash", "different-handle-hash"),
    ),
)
def test_sealed_payload_rejects_wrong_associated_data(
    changed_field: str,
    value: str,
) -> None:
    codec = SealedDeliveryCodec(keyring(), nonce_factory=lambda: b"a" * 12)
    analytics_row = row()
    sealed = codec.seal(analytics_row, delivery_handle_hash="handle-hash-value")
    associated_data = {
        "event_key": analytics_row.event_key,
        "payload_hash": analytics_row.payload_hash,
        "delivery_handle_hash": "handle-hash-value",
        changed_field: value,
    }

    with pytest.raises(SealedPayloadError, match="sealed_payload_invalid"):
        codec.open(sealed, **associated_data)


def test_sealed_payload_rejects_tampering_oversize_and_unknown_key_version() -> None:
    codec = SealedDeliveryCodec(keyring(), nonce_factory=lambda: b"a" * 12)
    analytics_row = row()
    sealed = codec.seal(analytics_row, delivery_handle_hash="handle-hash-value")
    version, key_version, nonce, ciphertext = sealed.split(".")
    tampered_ciphertext = ("A" if ciphertext[0] != "A" else "B") + ciphertext[1:]

    for invalid in (
        f"{version}.{key_version}.{nonce}.{tampered_ciphertext}",
        f"{version}.99.{nonce}.{ciphertext}",
        "x" * 4097,
    ):
        with pytest.raises(SealedPayloadError, match="sealed_payload_invalid"):
            codec.open(
                invalid,
                event_key=analytics_row.event_key,
                payload_hash=analytics_row.payload_hash,
                delivery_handle_hash="handle-hash-value",
            )


def test_rotated_keyring_opens_old_envelopes_and_uses_current_version_for_new_ones() -> None:
    analytics_row = row().model_copy(update={"subject_key_version": "7"})
    old_codec = SealedDeliveryCodec(
        AnalyticsKeyring(
            project_id="test-project",
            keys={"7": b"older-test-key-material-32-byte"},
            current_version="7",
        ),
        nonce_factory=lambda: b"a" * 12,
    )
    old_sealed = old_codec.seal(
        analytics_row,
        delivery_handle_hash="handle-hash-value",
    )
    rotated = SealedDeliveryCodec(keyring(), nonce_factory=lambda: b"b" * 12)

    opened = rotated.open(
        old_sealed,
        event_key=analytics_row.event_key,
        payload_hash=analytics_row.payload_hash,
        delivery_handle_hash="handle-hash-value",
    )
    new_sealed = rotated.seal(
        row(),
        delivery_handle_hash="handle-hash-value",
    )

    assert opened == analytics_row
    assert old_sealed.startswith("v1.7.")
    assert new_sealed.startswith("v1.8.")


def test_delivery_handle_lookup_is_keyed_non_reversible_and_domain_separated() -> None:
    keys = keyring()
    handle = "random-opaque-delivery-handle"

    lookup = keys.delivery_handle_hash(handle, version="8")

    assert lookup == keys.delivery_handle_hash(handle, version="8")
    assert lookup != handle
    assert lookup != keys.subject_key(handle, version="8")
    assert "random-opaque-delivery-handle" not in lookup
