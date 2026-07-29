from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.imports.models import RawTransaction
from app.features.imports.statements.types import RawTransactionStatus

RawTransactionFingerprint = tuple[UUID, date, Decimal, str]


class DuplicateFingerprintSource(Protocol):
    @property
    def account_id(self) -> UUID | None: ...

    @property
    def operation_date(self) -> date | None: ...

    @property
    def amount(self) -> Decimal | None: ...

    @property
    def currency(self) -> str | None: ...


class DuplicatePolicy:
    @staticmethod
    def classify(
        *,
        dedupe_hash: str | None,
        fingerprint: RawTransactionFingerprint | None,
        existing_hashes: set[str],
        existing_fingerprints: set[RawTransactionFingerprint],
    ) -> RawTransactionStatus | None:
        if dedupe_hash is not None and dedupe_hash in existing_hashes:
            return RawTransactionStatus.DUPLICATE
        if fingerprint is not None and fingerprint in existing_fingerprints:
            return RawTransactionStatus.POSSIBLE_DUPLICATE
        return None


def possible_duplicate_fingerprints(
    raw_transactions: Iterable[DuplicateFingerprintSource],
) -> set[RawTransactionFingerprint]:
    return {
        fingerprint
        for raw_transaction in raw_transactions
        if (fingerprint := possible_duplicate_fingerprint(raw_transaction)) is not None
    }


def possible_duplicate_fingerprint(
    raw_transaction: DuplicateFingerprintSource,
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
            duplicate_status = DuplicatePolicy.classify(
                dedupe_hash=raw_transaction.dedupe_hash,
                fingerprint=possible_duplicate_fingerprint(raw_transaction),
                existing_hashes=existing_hashes,
                existing_fingerprints=existing_fingerprints,
            )
            if duplicate_status is not None:
                raw_transaction.status = duplicate_status

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
