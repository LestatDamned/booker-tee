from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.types import RawTransactionStatus

RawTransactionFingerprint = tuple[UUID, date, Decimal, str]

EXACT_DUPLICATE_MESSAGE = "Exact duplicate: another row has the same dedupe hash."
POSSIBLE_DUPLICATE_MESSAGE = "Possible duplicate: same account, date, amount, and currency."


class DuplicateFingerprintSource(Protocol):
    @property
    def account_id(self) -> UUID | None: ...

    @property
    def operation_date(self) -> date | None: ...

    @property
    def amount(self) -> Decimal | None: ...

    @property
    def currency(self) -> str | None: ...


@dataclass(frozen=True)
class DuplicateDecision:
    status: RawTransactionStatus
    message: str


class DuplicatePolicy:
    @staticmethod
    def classify(
        *,
        dedupe_hash: str | None,
        fingerprint: RawTransactionFingerprint | None,
        existing_hashes: set[str],
        existing_fingerprints: set[RawTransactionFingerprint],
    ) -> DuplicateDecision | None:
        if dedupe_hash is not None and dedupe_hash in existing_hashes:
            return DuplicateDecision(
                status=RawTransactionStatus.DUPLICATE,
                message=EXACT_DUPLICATE_MESSAGE,
            )
        if fingerprint is not None and fingerprint in existing_fingerprints:
            return DuplicateDecision(
                status=RawTransactionStatus.POSSIBLE_DUPLICATE,
                message=POSSIBLE_DUPLICATE_MESSAGE,
            )
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
