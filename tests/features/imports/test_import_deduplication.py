from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.features.imports.application.pipelines.deduplication import (
    RawTransactionDeduplicator,
)
from app.features.imports.domain.deduplication import (
    DuplicatePolicy,
    RawTransactionFingerprint,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.models import RawTransaction


def test_duplicate_policy_prefers_exact_hash_over_possible_match() -> None:
    fingerprint = _fingerprint()

    decision = DuplicatePolicy.classify(
        dedupe_hash="same-row",
        fingerprint=fingerprint,
        existing_hashes={"same-row"},
        existing_fingerprints={fingerprint},
    )

    assert decision is RawTransactionStatus.DUPLICATE


def test_duplicate_policy_marks_matching_fingerprint_as_possible_duplicate() -> None:
    fingerprint = _fingerprint()

    decision = DuplicatePolicy.classify(
        dedupe_hash="new-row",
        fingerprint=fingerprint,
        existing_hashes=set(),
        existing_fingerprints={fingerprint},
    )

    assert decision is RawTransactionStatus.POSSIBLE_DUPLICATE


def test_duplicate_policy_leaves_new_transaction_unchanged() -> None:
    decision = DuplicatePolicy.classify(
        dedupe_hash="new-row",
        fingerprint=_fingerprint(),
        existing_hashes=set(),
        existing_fingerprints=set(),
    )

    assert decision is None


@pytest.mark.asyncio
async def test_overlapping_statement_uses_status_without_polluting_normalization_error() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    account_id = uuid4()
    row = RawTransaction(
        workspace_id=workspace_id,
        uploaded_document_id=document_id,
        parse_attempt_id=uuid4(),
        row_index=0,
        status=RawTransactionStatus.NORMALIZED,
        raw_payload={},
        account_id=account_id,
        operation_date=date(2026, 7, 15),
        amount=Decimal("1250.00"),
        currency="RUB",
        normalization_error="Existing parser issue.",
    )

    await RawTransactionDeduplicator(OverlappingStatementLookup()).mark_duplicate_candidates(
        workspace_id=workspace_id,
        raw_transactions=[row],
        exclude_document_id=document_id,
    )

    assert row.status is RawTransactionStatus.POSSIBLE_DUPLICATE
    assert row.normalization_error == "Existing parser issue."


class OverlappingStatementLookup:
    async def find_existing_dedupe_hashes(
        self,
        **_: object,
    ) -> set[str]:
        return set()

    async def find_existing_possible_duplicate_fingerprints(
        self,
        *,
        fingerprints: set[RawTransactionFingerprint],
        **_: object,
    ) -> set[RawTransactionFingerprint]:
        return fingerprints


def _fingerprint() -> RawTransactionFingerprint:
    return (
        uuid4(),
        date(2026, 7, 15),
        Decimal("1250.00"),
        "RUB",
    )
