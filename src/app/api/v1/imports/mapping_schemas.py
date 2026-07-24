from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints

from app.api.schemas import ApiModel, ApiRequestModel
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingBlockingReasonCode,
    MappingDefaultSource,
    MappingRowErrorCode,
)
from app.features.imports.models import UploadedDocumentStatus

CurrencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    ),
]


class MappingTableRefApiModel(ApiRequestModel):
    page_number: int = Field(ge=1)
    table_index: int = Field(ge=0)


class MappingCommandApiModel(ApiRequestModel):
    table_ref: MappingTableRefApiModel
    operation_date_column: int = Field(ge=0)
    posting_date_column: int | None = Field(default=None, ge=0)
    description_column: int = Field(ge=0)
    amount_column: int | None = Field(default=None, ge=0)
    debit_amount_column: int | None = Field(default=None, ge=0)
    credit_amount_column: int | None = Field(default=None, ge=0)
    currency_column: int | None = Field(default=None, ge=0)
    balance_after_column: int | None = Field(default=None, ge=0)
    first_data_row_number: int = Field(ge=1)
    default_currency: CurrencyCode
    unsigned_amount_direction: UnsignedAmountDirection


class MappingPreviewApiRequest(ApiRequestModel):
    mapping: MappingCommandApiModel


class MappingImportApiRequest(ApiRequestModel):
    mapping: MappingCommandApiModel
    template_name: str | None = Field(default=None, min_length=1, max_length=255)


class MappingImportTargetApiResponse(ApiModel):
    kind: Literal["import_review"]
    document_id: UUID


class MappingImportApiResponse(ApiModel):
    document_id: UUID
    status: UploadedDocumentStatus
    imported_row_count: int
    template_id: UUID | None
    replayed: bool
    review_target: MappingImportTargetApiResponse


class MappingAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str


class MappingCapabilityApiResponse(ApiModel):
    allowed: bool
    blocking_reason_codes: list[MappingBlockingReasonCode]


class MappingColumnCandidateApiResponse(ApiModel):
    field: str
    column_index: int
    header: str
    confidence: float | None


class MappingSuggestionReasonApiResponse(ApiModel):
    field: str
    column_index: int
    header: str
    evidence: str
    matched_count: int | None
    sample_count: int | None


class MappingSuggestionApiResponse(ApiModel):
    mapping: MappingCommandApiModel
    confidence: float | None
    reasons: list[MappingSuggestionReasonApiResponse]
    warning_codes: list[str]


class MappingSourceRowApiResponse(ApiModel):
    row_number: int
    cells: list[str]


class MappingSourceTableApiResponse(ApiModel):
    ref: MappingTableRefApiModel
    source_type: str
    row_count: int
    column_count: int
    is_continuation: bool
    sample_rows: list[MappingSourceRowApiResponse]
    candidates: list[MappingColumnCandidateApiResponse]
    suggestion: MappingSuggestionApiResponse | None


class MappingTemplateApiResponse(ApiModel):
    id: UUID
    name: str


class MappingReadApiResponse(ApiModel):
    document_id: UUID
    filename: str
    status: UploadedDocumentStatus
    bank_name: str | None
    statement_type: str | None
    account: MappingAccountApiResponse | None
    default_currency: str
    capability: MappingCapabilityApiResponse
    default_mapping: MappingCommandApiModel
    default_source: MappingDefaultSource
    selected_template_id: UUID | None
    templates: list[MappingTemplateApiResponse]
    tables: list[MappingSourceTableApiResponse]
    total_table_count: int
    tables_truncated: bool


class MappingWarningApiResponse(ApiModel):
    code: str
    severity: Literal["warning", "error"]
    fields: list[str]
    affected_row_count: int | None


class MappingPreviewRowApiResponse(ApiModel):
    table_ref: MappingTableRefApiModel
    source_row_number: int
    operation_date: date | None
    operation_date_raw: str
    posting_date: date | None
    posting_date_raw: str
    description: str
    amount: str | None
    amount_raw: str
    currency: str
    balance_after: str | None
    balance_after_raw: str
    status: Literal["valid", "error"]
    error_codes: list[MappingRowErrorCode]


class MappingPreviewApiResponse(ApiModel):
    rows: list[MappingPreviewRowApiResponse]
    total_row_count: int
    valid_row_count: int
    invalid_row_count: int
    row_limit: int
    rows_truncated: bool
    compatible_tables: list[MappingTableRefApiModel]
    warnings: list[MappingWarningApiResponse]
    can_import: bool
