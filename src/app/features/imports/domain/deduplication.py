from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.types import RawTransactionStatus

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
