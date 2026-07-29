"""Internal Pydantic contracts for import-review reads."""

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from uuid import UUID

from app.features.categories.models import CategoryKind
from app.features.import_review.domain.classification import (
    ReviewBlockingReasonCode,
    ReviewClassificationSource,
)
from app.features.import_review.domain.lifecycle import ImportReviewLifecycleSnapshot
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.statements.types import RawTransactionStatus
from app.features.imports.statements.validation import StatementValidationStatus
from app.features.ledger.domain.types import OperationType
from app.shared.schemas import ApplicationModel


class ImportReviewCategoryReferenceDto(ApplicationModel):
    id: UUID
    name: str
    kind: CategoryKind
    is_uncategorized: bool


class ImportReviewPropertyReferenceDto(ApplicationModel):
    id: UUID
    name: str


class ImportReviewReferencesDto(ApplicationModel):
    categories: tuple[ImportReviewCategoryReferenceDto, ...]
    properties: tuple[ImportReviewPropertyReferenceDto, ...]


class ImportReviewClassificationDto(ApplicationModel):
    operation_type: OperationType | None
    source: ReviewClassificationSource


class ImportReviewSelectionDto(ApplicationModel):
    category_id: UUID | None
    property_id: UUID | None


class ImportReviewConfirmabilityDto(ApplicationModel):
    can_confirm: bool
    blocking_reason_codes: tuple[ReviewBlockingReasonCode, ...]


class ImportReviewRuleSuggestionDto(ApplicationModel):
    is_active: bool
    was_auto_applied: bool
    rule_id: UUID | None
    rule_name: str | None = None
    pattern: str | None = None
    operation_type: OperationType | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None


class ImportReviewDraftEvaluationDto(ApplicationModel):
    item_id: UUID
    classification: ImportReviewClassificationDto
    selection: ImportReviewSelectionDto
    confirmability: ImportReviewConfirmabilityDto
    rule_suggestion: ImportReviewRuleSuggestionDto


class ImportReviewDuplicateMatchReasonCode(StrEnum):
    SAME_ACCOUNT_DATE_AMOUNT_CURRENCY = "same_account_date_amount_currency"


class ImportReviewDuplicateMatchingField(StrEnum):
    ACCOUNT = "account"
    OPERATION_DATE = "operation_date"
    AMOUNT = "amount"
    CURRENCY = "currency"


class ImportReviewDuplicateCandidateDto(ApplicationModel):
    item_id: UUID
    document_id: UUID
    document_filename: str
    operation_id: UUID | None
    operation_date: date
    description: str | None
    amount: Decimal
    currency: str


class ImportReviewDuplicateEvidenceDto(ApplicationModel):
    reason_code: ImportReviewDuplicateMatchReasonCode
    matching_fields: tuple[ImportReviewDuplicateMatchingField, ...]
    candidate: ImportReviewDuplicateCandidateDto


class ImportReviewAccountDto(ApplicationModel):
    id: UUID
    name: str
    currency: str


class ImportReviewTransferDirection(StrEnum):
    SOURCE_TO_COUNTERPARTY = "source_to_counterparty"
    COUNTERPARTY_TO_SOURCE = "counterparty_to_source"


class ImportReviewRawTransferCandidateDto(ApplicationModel):
    item_id: UUID
    document_id: UUID
    row_index: int
    operation_date: date | None
    description: str | None
    amount: Decimal
    currency: str
    account: ImportReviewAccountDto
    day_distance: int


class ImportReviewExistingTransferCandidateDto(ApplicationModel):
    operation_id: UUID
    operation_date: date
    description: str | None
    amount: Decimal
    currency: str
    counterparty_account: ImportReviewAccountDto | None
    day_distance: int


class ImportReviewTransferOptionsDto(ApplicationModel):
    direction: ImportReviewTransferDirection | None
    ordinary_operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE] | None
    source_account: ImportReviewAccountDto | None
    counterparty_account: ImportReviewAccountDto | None
    accounts: tuple[ImportReviewAccountDto, ...]
    raw_row_candidates: tuple[ImportReviewRawTransferCandidateDto, ...]
    existing_operation_candidates: tuple[ImportReviewExistingTransferCandidateDto, ...]


EMPTY_TRANSFER_OPTIONS = ImportReviewTransferOptionsDto(
    direction=None,
    ordinary_operation_type=None,
    source_account=None,
    counterparty_account=None,
    accounts=(),
    raw_row_candidates=(),
    existing_operation_candidates=(),
)


class ImportReviewValidationReasonCode(StrEnum):
    TOTALS_MATCH = "totals_match"
    ROWS_NEED_REVIEW = "rows_need_review"
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"
    CONTROL_TOTALS_UNAVAILABLE = "control_totals_unavailable"
    CONTROL_TOTALS_MISMATCH = "control_totals_mismatch"
    IGNORED_ROWS_EXPLAIN_MISMATCH = "ignored_rows_explain_mismatch"


class ImportReviewRowProblemCode(StrEnum):
    BALANCE_CHAIN_MISMATCH = "balance_chain_mismatch"


class ImportReviewBalanceChainDto(ApplicationModel):
    status: StatementValidationStatus
    direction: str | None
    checked_pair_count: int
    mismatch_count: int


class ImportReviewRowProblemDto(ApplicationModel):
    item_id: UUID
    row_index: int
    previous_item_id: UUID
    previous_row_index: int
    code: ImportReviewRowProblemCode
    expected_balance_after: Decimal
    actual_balance_after: Decimal


class ImportReviewValidationDto(ApplicationModel):
    status: StatementValidationStatus
    reason_code: ImportReviewValidationReasonCode
    currency: str | None
    extracted_count: int
    normalized_count: int
    needs_review_count: int
    calculated_total_inflow: Decimal
    calculated_total_outflow: Decimal
    ignored_total_inflow: Decimal
    ignored_total_outflow: Decimal
    statement_total_inflow: Decimal | None
    statement_total_outflow: Decimal | None
    opening_balance: Decimal | None
    closing_balance: Decimal | None
    inflow_difference: Decimal | None
    outflow_difference: Decimal | None
    unexplained_inflow_difference: Decimal | None
    unexplained_outflow_difference: Decimal | None
    balance_chain: ImportReviewBalanceChainDto
    row_problems: tuple[ImportReviewRowProblemDto, ...]


class ImportReviewReadonlyReasonCode(StrEnum):
    FINANCIAL_WRITE_FORBIDDEN = "financial_write_forbidden"


class ImportReviewCapabilitiesDto(ApplicationModel):
    can_write: bool
    readonly_reason_code: ImportReviewReadonlyReasonCode | None


class ImportReviewQueueDto(ApplicationModel):
    total: int
    completed: int
    remaining: int
    first_remaining_item_id: UUID | None
    ordered_item_ids: tuple[UUID, ...]


class ImportReviewRawSourceDto(ApplicationModel):
    operation_date: str | None
    posting_date: str | None
    description: str | None
    amount: str | None
    currency: str | None
    balance_after: str | None
    account_hint: str | None


class ImportReviewNormalizedSourceDto(ApplicationModel):
    operation_date: date | None
    posting_date: date | None
    description: str | None
    amount: Decimal | None
    currency: str | None
    balance_after: Decimal | None


class ImportReviewPostingDto(ApplicationModel):
    operation_id: UUID | None
    can_undo: bool


EMPTY_IMPORT_REVIEW_POSTING = ImportReviewPostingDto(
    operation_id=None,
    can_undo=False,
)


class ImportReviewItemDto(ApplicationModel):
    id: UUID
    row_index: int
    status: RawTransactionStatus
    is_terminal: bool
    is_reviewable: bool
    source_account: ImportReviewAccountDto | None
    raw: ImportReviewRawSourceDto
    normalized: ImportReviewNormalizedSourceDto
    classification: ImportReviewClassificationDto
    selection: ImportReviewSelectionDto
    confirmability: ImportReviewConfirmabilityDto
    rule_suggestion: ImportReviewRuleSuggestionDto
    posting: ImportReviewPostingDto = EMPTY_IMPORT_REVIEW_POSTING
    transfer: ImportReviewTransferOptionsDto = EMPTY_TRANSFER_OPTIONS
    lifecycle: ImportReviewLifecycleSnapshot = ImportReviewLifecycleSnapshot(allowed_actions=())
    duplicate_evidence: ImportReviewDuplicateEvidenceDto | None = None


class ImportReviewDocumentDto(ApplicationModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    source_account: ImportReviewAccountDto | None


class ImportReviewReadModel(ApplicationModel):
    document: ImportReviewDocumentDto
    queue: ImportReviewQueueDto
    items: list[ImportReviewItemDto]
    references: ImportReviewReferencesDto
    validation: ImportReviewValidationDto | None
    capabilities: ImportReviewCapabilitiesDto
