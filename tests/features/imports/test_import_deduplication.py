from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.features.imports.domain.deduplication import (
    EXACT_DUPLICATE_MESSAGE,
    POSSIBLE_DUPLICATE_MESSAGE,
    DuplicateDecision,
    DuplicatePolicy,
    RawTransactionFingerprint,
)
from app.features.imports.domain.types import RawTransactionStatus


def test_duplicate_policy_prefers_exact_hash_over_possible_match() -> None:
    fingerprint = _fingerprint()

    decision = DuplicatePolicy.classify(
        dedupe_hash="same-row",
        fingerprint=fingerprint,
        existing_hashes={"same-row"},
        existing_fingerprints={fingerprint},
    )

    assert decision == DuplicateDecision(
        status=RawTransactionStatus.DUPLICATE,
        message=EXACT_DUPLICATE_MESSAGE,
    )


def test_duplicate_policy_marks_matching_fingerprint_as_possible_duplicate() -> None:
    fingerprint = _fingerprint()

    decision = DuplicatePolicy.classify(
        dedupe_hash="new-row",
        fingerprint=fingerprint,
        existing_hashes=set(),
        existing_fingerprints={fingerprint},
    )

    assert decision == DuplicateDecision(
        status=RawTransactionStatus.POSSIBLE_DUPLICATE,
        message=POSSIBLE_DUPLICATE_MESSAGE,
    )


def test_duplicate_policy_leaves_new_transaction_unchanged() -> None:
    decision = DuplicatePolicy.classify(
        dedupe_hash="new-row",
        fingerprint=_fingerprint(),
        existing_hashes=set(),
        existing_fingerprints=set(),
    )

    assert decision is None


def _fingerprint() -> RawTransactionFingerprint:
    return (
        uuid4(),
        date(2026, 7, 15),
        Decimal("1250.00"),
        "RUB",
    )
