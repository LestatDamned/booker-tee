from typing import Protocol
from uuid import UUID

from app.features.imports.domain.deduplication import (
    DuplicateDecision,
    DuplicatePolicy,
    RawTransactionFingerprint,
    possible_duplicate_fingerprint,
    possible_duplicate_fingerprints,
)
from app.features.imports.domain.review_messages import append_review_message
from app.features.imports.models import RawTransaction


class DuplicateLookup(Protocol):
    async def find_existing_dedupe_hashes(
        self,
        *,
        workspace_id: UUID,
        dedupe_hashes: set[str],
        exclude_document_id: UUID | None = None,
    ) -> set[str]: ...

    async def find_existing_possible_duplicate_fingerprints(
        self,
        *,
        workspace_id: UUID,
        fingerprints: set[RawTransactionFingerprint],
        exclude_document_id: UUID | None = None,
    ) -> set[RawTransactionFingerprint]: ...


class RawTransactionDeduplicator:
    def __init__(self, lookup: DuplicateLookup) -> None:
        self._lookup = lookup

    async def mark_duplicate_candidates(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        exclude_document_id: UUID | None,
    ) -> None:
        existing_hashes = await self._existing_dedupe_hashes(
            workspace_id=workspace_id,
            raw_transactions=raw_transactions,
            exclude_document_id=exclude_document_id,
        )
        existing_fingerprints = await self._existing_fingerprints(
            workspace_id=workspace_id,
            raw_transactions=raw_transactions,
            exclude_document_id=exclude_document_id,
        )

        for raw_transaction in raw_transactions:
            decision = DuplicatePolicy.classify(
                dedupe_hash=raw_transaction.dedupe_hash,
                fingerprint=possible_duplicate_fingerprint(raw_transaction),
                existing_hashes=existing_hashes,
                existing_fingerprints=existing_fingerprints,
            )
            if decision is not None:
                apply_duplicate_decision(raw_transaction, decision)

    async def _existing_dedupe_hashes(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        exclude_document_id: UUID | None,
    ) -> set[str]:
        exact_hashes = {
            raw_transaction.dedupe_hash
            for raw_transaction in raw_transactions
            if raw_transaction.dedupe_hash
        }
        return await self._lookup.find_existing_dedupe_hashes(
            workspace_id=workspace_id,
            dedupe_hashes=exact_hashes,
            exclude_document_id=exclude_document_id,
        )

    async def _existing_fingerprints(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
        exclude_document_id: UUID | None,
    ) -> set[RawTransactionFingerprint]:
        fingerprints = possible_duplicate_fingerprints(raw_transactions)
        return await self._lookup.find_existing_possible_duplicate_fingerprints(
            workspace_id=workspace_id,
            fingerprints=fingerprints,
            exclude_document_id=exclude_document_id,
        )


def apply_duplicate_decision(
    raw_transaction: RawTransaction,
    decision: DuplicateDecision,
) -> None:
    raw_transaction.status = decision.status
    raw_transaction.normalization_error = append_review_message(
        raw_transaction.normalization_error,
        decision.message,
    )
