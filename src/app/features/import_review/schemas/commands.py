"""Commands and committed results for import-review mutations."""

from uuid import UUID

from app.features.import_review.domain.lifecycle import ImportReviewLifecycleAction
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationType
from app.shared.schemas import ApplicationModel


class ConfirmImportReviewItemCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    operation_type: OperationType | None
    category_id: UUID
    property_id: UUID | None
    expected_status: RawTransactionStatus
    remember_rule: bool
    rule_pattern: str | None
    idempotency_key: UUID


class ImportReviewConfirmationResult(ApplicationModel):
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    updated_item_ids: frozenset[UUID]
    replayed: bool


class ImportReviewLifecycleCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    action: ImportReviewLifecycleAction
    expected_status: RawTransactionStatus


class ImportReviewLifecycleResult(ApplicationModel):
    item_id: UUID
    document_id: UUID
    replayed: bool


class LinkImportReviewExistingOperationCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    expected_status: RawTransactionStatus


class ImportReviewExistingOperationLinkResult(ApplicationModel):
    item_id: UUID
    document_id: UUID
    operation_id: UUID
    replayed: bool


class ImportReviewRuleApplicationResult(ApplicationModel):
    checked_count: int
    suggested_count: int
    updated_item_ids: frozenset[UUID]


class CreateImportReviewTransferCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    counterparty_account_id: UUID
    idempotency_key: UUID


class MatchImportReviewRawRowCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    matched_item_id: UUID
    idempotency_key: UUID


class LinkImportReviewExistingTransferCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    idempotency_key: UUID


type ImportReviewTransferCommand = (
    CreateImportReviewTransferCommand
    | MatchImportReviewRawRowCommand
    | LinkImportReviewExistingTransferCommand
)


class ImportReviewTransferResult(ApplicationModel):
    operation_id: UUID
    updated_item_ids: frozenset[UUID]
    affected_document_ids: frozenset[UUID]
    replayed: bool


class UndoImportReviewPostingCommand(ApplicationModel):
    document_id: UUID
    item_id: UUID
    expected_operation_id: UUID


class ImportReviewUndoResult(ApplicationModel):
    document_id: UUID
    item_id: UUID
    operation_id: UUID
    affected_document_ids: frozenset[UUID]
    updated_item_ids: frozenset[UUID]
    replayed: bool
