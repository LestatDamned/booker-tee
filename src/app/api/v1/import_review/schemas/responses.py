from datetime import date
from typing import Literal
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.categories.models import CategoryKind
from app.features.imports.application.review.duplicates import (
    ImportReviewDuplicateMatchingField,
    ImportReviewDuplicateMatchReasonCode,
)
from app.features.imports.application.review.read_model import (
    ImportReviewReadonlyReasonCode,
)
from app.features.imports.application.review.transfers import ImportReviewTransferDirection
from app.features.imports.application.review.validation_read_model import (
    ImportReviewRowProblemCode,
    ImportReviewValidationReasonCode,
)
from app.features.imports.domain.review_classification import ReviewClassificationSource
from app.features.imports.domain.review_confirmability import ReviewBlockingReasonCode
from app.features.imports.domain.review_lifecycle import ImportReviewLifecycleAction
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.domain.validation import StatementValidationStatus
from app.features.imports.models import UploadedDocumentStatus
from app.features.ledger.domain.types import OperationType


class ImportReviewAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str


class ImportReviewCapabilitiesApiResponse(ApiModel):
    can_write: bool
    readonly_reason_code: ImportReviewReadonlyReasonCode | None


class ImportReviewQueueApiResponse(ApiModel):
    total: int
    completed: int
    remaining: int
    first_remaining_item_id: UUID | None
    ordered_item_ids: list[UUID]


class ImportReviewRawSourceApiResponse(ApiModel):
    operation_date: str | None
    posting_date: str | None
    description: str | None
    amount: str | None
    currency: str | None
    balance_after: str | None
    account_hint: str | None


class ImportReviewNormalizedSourceApiResponse(ApiModel):
    operation_date: date | None
    posting_date: date | None
    description: str | None
    amount: str | None
    currency: str | None
    balance_after: str | None


class ImportReviewClassificationApiResponse(ApiModel):
    operation_type: OperationType | None
    source: ReviewClassificationSource


class ImportReviewSelectionApiResponse(ApiModel):
    category_id: UUID | None
    property_id: UUID | None


class ImportReviewConfirmabilityApiResponse(ApiModel):
    can_confirm: bool
    blocking_reason_codes: list[ReviewBlockingReasonCode]


class ImportReviewRuleSuggestionApiResponse(ApiModel):
    is_active: bool
    was_auto_applied: bool
    rule_id: UUID | None
    rule_name: str | None
    pattern: str | None
    operation_type: OperationType | None
    category_id: UUID | None
    property_id: UUID | None


class ImportReviewPostingApiResponse(ApiModel):
    operation_id: UUID | None
    can_undo: bool


class ImportReviewTransferAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str


class ImportReviewRawTransferCandidateApiResponse(ApiModel):
    item_id: UUID
    document_id: UUID
    row_index: int
    operation_date: date | None
    description: str | None
    amount: str
    currency: str
    account: ImportReviewTransferAccountApiResponse
    day_distance: int


class ImportReviewExistingTransferCandidateApiResponse(ApiModel):
    operation_id: UUID
    operation_date: date
    description: str | None
    amount: str
    currency: str
    counterparty_account: ImportReviewTransferAccountApiResponse | None
    day_distance: int


class ImportReviewTransferOptionsApiResponse(ApiModel):
    direction: ImportReviewTransferDirection | None
    ordinary_operation_type: Literal[OperationType.INCOME, OperationType.EXPENSE] | None
    source_account: ImportReviewTransferAccountApiResponse | None
    counterparty_account: ImportReviewTransferAccountApiResponse | None
    accounts: list[ImportReviewTransferAccountApiResponse]
    raw_row_candidates: list[ImportReviewRawTransferCandidateApiResponse]
    existing_operation_candidates: list[ImportReviewExistingTransferCandidateApiResponse]


class ImportReviewLifecycleApiResponse(ApiModel):
    allowed_actions: list[ImportReviewLifecycleAction]


class ImportReviewDuplicateCandidateApiResponse(ApiModel):
    item_id: UUID
    document_id: UUID
    document_filename: str
    operation_id: UUID | None
    operation_date: date
    description: str | None
    amount: str
    currency: str


class ImportReviewDuplicateEvidenceApiResponse(ApiModel):
    reason_code: ImportReviewDuplicateMatchReasonCode
    matching_fields: list[ImportReviewDuplicateMatchingField]
    candidate: ImportReviewDuplicateCandidateApiResponse


class ImportReviewItemApiResponse(ApiModel):
    id: UUID
    row_index: int
    status: RawTransactionStatus
    is_terminal: bool
    is_reviewable: bool
    source_account: ImportReviewAccountApiResponse | None
    raw: ImportReviewRawSourceApiResponse
    normalized: ImportReviewNormalizedSourceApiResponse
    classification: ImportReviewClassificationApiResponse
    selection: ImportReviewSelectionApiResponse
    confirmability: ImportReviewConfirmabilityApiResponse
    rule_suggestion: ImportReviewRuleSuggestionApiResponse
    posting: ImportReviewPostingApiResponse
    transfer: ImportReviewTransferOptionsApiResponse
    lifecycle: ImportReviewLifecycleApiResponse
    duplicate_evidence: ImportReviewDuplicateEvidenceApiResponse | None


class ImportReviewCategoryReferenceApiResponse(ApiModel):
    id: UUID
    name: str
    kind: CategoryKind
    is_uncategorized: bool


class ImportReviewPropertyReferenceApiResponse(ApiModel):
    id: UUID
    name: str


class ImportReviewReferencesApiResponse(ApiModel):
    categories: list[ImportReviewCategoryReferenceApiResponse]
    properties: list[ImportReviewPropertyReferenceApiResponse]


class ImportReviewDocumentApiResponse(ApiModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    source_account: ImportReviewAccountApiResponse | None


class ImportReviewBalanceChainApiResponse(ApiModel):
    status: StatementValidationStatus
    direction: str | None
    checked_pair_count: int
    mismatch_count: int


class ImportReviewRowProblemApiResponse(ApiModel):
    item_id: UUID
    row_index: int
    previous_item_id: UUID
    previous_row_index: int
    code: ImportReviewRowProblemCode
    expected_balance_after: str
    actual_balance_after: str


class ImportReviewValidationApiResponse(ApiModel):
    status: StatementValidationStatus
    reason_code: ImportReviewValidationReasonCode
    currency: str | None
    extracted_count: int
    normalized_count: int
    needs_review_count: int
    calculated_total_inflow: str
    calculated_total_outflow: str
    ignored_total_inflow: str
    ignored_total_outflow: str
    statement_total_inflow: str | None
    statement_total_outflow: str | None
    opening_balance: str | None
    closing_balance: str | None
    inflow_difference: str | None
    outflow_difference: str | None
    unexplained_inflow_difference: str | None
    unexplained_outflow_difference: str | None
    balance_chain: ImportReviewBalanceChainApiResponse
    row_problems: list[ImportReviewRowProblemApiResponse]


class ImportReviewApiResponse(ApiModel):
    document: ImportReviewDocumentApiResponse
    queue: ImportReviewQueueApiResponse
    items: list[ImportReviewItemApiResponse]
    references: ImportReviewReferencesApiResponse
    validation: ImportReviewValidationApiResponse | None
    capabilities: ImportReviewCapabilitiesApiResponse


class ImportReviewDraftEvaluationApiResponse(ApiModel):
    item_id: UUID
    classification: ImportReviewClassificationApiResponse
    selection: ImportReviewSelectionApiResponse
    confirmability: ImportReviewConfirmabilityApiResponse
    rule_suggestion: ImportReviewRuleSuggestionApiResponse


class ImportReviewTransferMutationApiResponse(ApiModel):
    primary_document_id: UUID
    updated_item_ids: list[UUID]
    validation_document_ids: list[UUID]
    reviews: list[ImportReviewApiResponse]


class ImportReviewLifecycleMutationApiResponse(ApiModel):
    item_id: UUID
    document_id: UUID
    replayed: bool
    review: ImportReviewApiResponse


class ImportReviewRuleApplicationApiResponse(ApiModel):
    document_id: UUID
    checked_count: int
    suggested_count: int
    updated_item_ids: list[UUID]
    review: ImportReviewApiResponse


class ImportReviewPostingMutationApiResponse(ApiModel):
    primary_document_id: UUID
    item_id: UUID
    operation_id: UUID
    updated_item_ids: list[UUID]
    replayed: bool
    reviews: list[ImportReviewApiResponse]
