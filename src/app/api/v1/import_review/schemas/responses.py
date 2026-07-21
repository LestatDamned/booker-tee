from datetime import date
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.imports.application.review.read_model import (
    ImportReviewReadonlyReasonCode,
)
from app.features.imports.application.review.validation_read_model import (
    ImportReviewRowProblemCode,
    ImportReviewValidationReasonCode,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.domain.validation import StatementValidationStatus
from app.features.imports.models import UploadedDocumentStatus


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


class ImportReviewItemApiResponse(ApiModel):
    id: UUID
    row_index: int
    status: RawTransactionStatus
    is_terminal: bool
    is_reviewable: bool
    source_account: ImportReviewAccountApiResponse | None
    raw: ImportReviewRawSourceApiResponse
    normalized: ImportReviewNormalizedSourceApiResponse


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
    validation: ImportReviewValidationApiResponse | None
    capabilities: ImportReviewCapabilitiesApiResponse
