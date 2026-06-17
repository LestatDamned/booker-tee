from datetime import date
from decimal import Decimal
from uuid import UUID

from app.features.imports.models import RawTransaction, RawTransactionStatus
from app.features.imports.repository import ImportRepository

RawTransactionFingerprint = tuple[UUID, date, Decimal, str]


class RawTransactionDeduplicator:
    def __init__(self, imports: ImportRepository) -> None:
        self.imports = imports

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
            if raw_transaction.dedupe_hash in existing_hashes:
                mark_raw_transaction_duplicate(
                    raw_transaction,
                    RawTransactionStatus.DUPLICATE,
                    "Exact duplicate: another row has the same dedupe hash.",
                )
                continue

            fingerprint = possible_duplicate_fingerprint(raw_transaction)
            if fingerprint in existing_fingerprints:
                mark_raw_transaction_duplicate(
                    raw_transaction,
                    RawTransactionStatus.POSSIBLE_DUPLICATE,
                    "Possible duplicate: same account, date, amount, and currency.",
                )

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
        return await self.imports.find_existing_dedupe_hashes(
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
        return await self.imports.find_existing_possible_duplicate_fingerprints(
            workspace_id=workspace_id,
            fingerprints=fingerprints,
            exclude_document_id=exclude_document_id,
        )


def possible_duplicate_fingerprints(
    raw_transactions: list[RawTransaction],
) -> set[RawTransactionFingerprint]:
    return {
        fingerprint
        for raw_transaction in raw_transactions
        if (fingerprint := possible_duplicate_fingerprint(raw_transaction)) is not None
    }


def possible_duplicate_fingerprint(
    raw_transaction: RawTransaction,
) -> RawTransactionFingerprint | None:
    if (
        raw_transaction.account_id is None
        or raw_transaction.operation_date is None
        or raw_transaction.amount is None
        or raw_transaction.currency is None
    ):
        return None
    return (
        raw_transaction.account_id,
        raw_transaction.operation_date,
        raw_transaction.amount,
        raw_transaction.currency,
    )


def mark_raw_transaction_duplicate(
    raw_transaction: RawTransaction,
    status: RawTransactionStatus,
    message: str,
) -> None:
    raw_transaction.status = status
    raw_transaction.normalization_error = append_review_message(
        raw_transaction.normalization_error,
        message,
    )


def append_review_message(existing: str | None, message: str) -> str:
    if not existing:
        return message
    if message in existing:
        return existing
    return f"{existing}; {message}"
