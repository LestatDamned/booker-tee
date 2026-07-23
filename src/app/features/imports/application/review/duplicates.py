from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.features.imports.domain.deduplication import (
    RawTransactionFingerprint,
    possible_duplicate_fingerprint,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.models import RawTransaction, UploadedDocument


class ImportReviewDuplicateMatchReasonCode(StrEnum):
    SAME_ACCOUNT_DATE_AMOUNT_CURRENCY = "same_account_date_amount_currency"


class ImportReviewDuplicateMatchingField(StrEnum):
    ACCOUNT = "account"
    OPERATION_DATE = "operation_date"
    AMOUNT = "amount"
    CURRENCY = "currency"


@dataclass(frozen=True)
class ImportReviewDuplicateCandidateDto:
    item_id: UUID
    document_id: UUID
    document_filename: str
    operation_id: UUID | None
    operation_date: date
    description: str | None
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class ImportReviewDuplicateEvidenceDto:
    reason_code: ImportReviewDuplicateMatchReasonCode
    matching_fields: tuple[ImportReviewDuplicateMatchingField, ...]
    candidate: ImportReviewDuplicateCandidateDto


class ImportReviewDuplicateSource(Protocol):
    async def list_possible_duplicate_candidates(
        self,
        *,
        workspace_id: UUID,
        fingerprints: set[RawTransactionFingerprint],
        exclude_document_id: UUID,
    ) -> list[RawTransaction]: ...


class ImportReviewDuplicateReader:
    def __init__(self, source: ImportReviewDuplicateSource) -> None:
        self._source = source

    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewDuplicateEvidenceDto]:
        targets = [
            row
            for row in document.raw_transactions
            if row.status is RawTransactionStatus.POSSIBLE_DUPLICATE
        ]
        target_fingerprints = {
            fingerprint
            for row in targets
            if (fingerprint := possible_duplicate_fingerprint(row)) is not None
        }
        candidates = await self._source.list_possible_duplicate_candidates(
            workspace_id=workspace_id,
            fingerprints=target_fingerprints,
            exclude_document_id=document.id,
        )
        candidates_by_fingerprint: dict[RawTransactionFingerprint, RawTransaction] = {}
        for candidate in candidates:
            fingerprint = possible_duplicate_fingerprint(candidate)
            if fingerprint is not None:
                candidates_by_fingerprint.setdefault(fingerprint, candidate)

        evidence: dict[UUID, ImportReviewDuplicateEvidenceDto] = {}
        for target in targets:
            fingerprint = possible_duplicate_fingerprint(target)
            candidate = candidates_by_fingerprint.get(fingerprint) if fingerprint else None
            if candidate is None:
                continue
            candidate_document = candidate.uploaded_document
            if (
                candidate.operation_date is None
                or candidate.amount is None
                or candidate.currency is None
            ):
                continue
            evidence[target.id] = ImportReviewDuplicateEvidenceDto(
                reason_code=(
                    ImportReviewDuplicateMatchReasonCode.SAME_ACCOUNT_DATE_AMOUNT_CURRENCY
                ),
                matching_fields=(
                    ImportReviewDuplicateMatchingField.ACCOUNT,
                    ImportReviewDuplicateMatchingField.OPERATION_DATE,
                    ImportReviewDuplicateMatchingField.AMOUNT,
                    ImportReviewDuplicateMatchingField.CURRENCY,
                ),
                candidate=ImportReviewDuplicateCandidateDto(
                    item_id=candidate.id,
                    document_id=candidate.uploaded_document_id,
                    document_filename=candidate_document.original_filename,
                    operation_id=candidate.linked_operation_id,
                    operation_date=candidate.operation_date,
                    description=candidate.description_normalized,
                    amount=candidate.amount,
                    currency=candidate.currency,
                ),
            )
        return evidence
