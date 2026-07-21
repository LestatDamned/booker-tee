from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.features.accounts.models import Account
from app.features.imports.application.review.validation_read_model import (
    ImportReviewValidationDto,
    build_import_review_validation,
)
from app.features.imports.domain.review_queue import (
    is_review_terminal,
    is_reviewable,
    review_queue_snapshot,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.models import RawTransaction, UploadedDocument, UploadedDocumentStatus


class ImportReviewDocumentSource(Protocol):
    async def get_document_for_workspace(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> UploadedDocument | None: ...


class ImportReviewReadonlyReasonCode(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


@dataclass(frozen=True)
class ImportReviewAccountDto:
    id: UUID
    name: str
    currency: str


@dataclass(frozen=True)
class ImportReviewCapabilitiesDto:
    can_write: bool
    readonly_reason_code: ImportReviewReadonlyReasonCode | None


@dataclass(frozen=True)
class ImportReviewQueueDto:
    total: int
    completed: int
    remaining: int
    first_remaining_item_id: UUID | None
    ordered_item_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class ImportReviewRawSourceDto:
    operation_date: str | None
    posting_date: str | None
    description: str | None
    amount: str | None
    currency: str | None
    balance_after: str | None
    account_hint: str | None


@dataclass(frozen=True)
class ImportReviewNormalizedSourceDto:
    operation_date: date | None
    posting_date: date | None
    description: str | None
    amount: Decimal | None
    currency: str | None
    balance_after: Decimal | None


@dataclass(frozen=True)
class ImportReviewItemDto:
    id: UUID
    row_index: int
    status: RawTransactionStatus
    is_terminal: bool
    is_reviewable: bool
    source_account: ImportReviewAccountDto | None
    raw: ImportReviewRawSourceDto
    normalized: ImportReviewNormalizedSourceDto


@dataclass(frozen=True)
class ImportReviewDocumentDto:
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    source_account: ImportReviewAccountDto | None


@dataclass(frozen=True)
class ImportReviewReadModel:
    document: ImportReviewDocumentDto
    queue: ImportReviewQueueDto
    items: list[ImportReviewItemDto]
    validation: ImportReviewValidationDto | None
    capabilities: ImportReviewCapabilitiesDto


class ImportReviewReader:
    def __init__(self, documents: ImportReviewDocumentSource) -> None:
        self._documents = documents

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        can_write: bool,
    ) -> ImportReviewReadModel | None:
        document = await self._documents.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            return None
        return build_import_review_read_model(document, can_write=can_write)


def build_import_review_read_model(
    document: UploadedDocument,
    *,
    can_write: bool,
) -> ImportReviewReadModel:
    queue = review_queue_snapshot(document.raw_transactions)
    rows_by_id = {row.id: row for row in document.raw_transactions}
    document_account = _account_dto(document.account)
    items = [
        _item_dto(rows_by_id[item_id], document_account=document_account)
        for item_id in queue.ordered_item_ids
    ]
    return ImportReviewReadModel(
        document=ImportReviewDocumentDto(
            id=document.id,
            filename=document.original_filename,
            status=document.status,
            source_account=document_account,
        ),
        queue=ImportReviewQueueDto(
            total=queue.total,
            completed=queue.completed,
            remaining=queue.remaining,
            first_remaining_item_id=queue.first_remaining_item_id,
            ordered_item_ids=queue.ordered_item_ids,
        ),
        items=items,
        validation=build_import_review_validation(document),
        capabilities=ImportReviewCapabilitiesDto(
            can_write=can_write,
            readonly_reason_code=(
                None if can_write else ImportReviewReadonlyReasonCode.FINANCIAL_WRITE_FORBIDDEN
            ),
        ),
    )


def _item_dto(
    row: RawTransaction,
    *,
    document_account: ImportReviewAccountDto | None,
) -> ImportReviewItemDto:
    status = row.status
    return ImportReviewItemDto(
        id=row.id,
        row_index=row.row_index,
        status=status,
        is_terminal=is_review_terminal(status),
        is_reviewable=is_reviewable(status),
        source_account=_account_dto(row.account) or document_account,
        raw=ImportReviewRawSourceDto(
            operation_date=row.operation_date_raw,
            posting_date=row.posting_date_raw,
            description=row.description_raw,
            amount=row.amount_raw,
            currency=row.currency_raw,
            balance_after=row.balance_after_raw,
            account_hint=row.account_hint_raw,
        ),
        normalized=ImportReviewNormalizedSourceDto(
            operation_date=row.operation_date,
            posting_date=row.posting_date,
            description=row.description_normalized,
            amount=row.amount,
            currency=row.currency,
            balance_after=row.balance_after,
        ),
    )


def _account_dto(account: Account | None) -> ImportReviewAccountDto | None:
    if account is None:
        return None
    return ImportReviewAccountDto(
        id=account.id,
        name=account.name,
        currency=account.currency,
    )
