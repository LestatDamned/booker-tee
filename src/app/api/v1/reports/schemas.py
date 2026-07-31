from datetime import date
from typing import Literal
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.ledger.domain.types import OperationSource, OperationType


class ReportAppliedFiltersApiResponse(ApiModel):
    date_from: date | None
    date_to: date | None
    currency: str
    account_id: UUID | None
    category_id: UUID | None
    property_id: UUID | None


class ReportAccountOptionApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str
    is_active: bool


class ReportNamedOptionApiResponse(ApiModel):
    id: UUID
    name: str
    is_active: bool


class ReportFilterOptionsApiResponse(ApiModel):
    accounts: list[ReportAccountOptionApiResponse]
    categories: list[ReportNamedOptionApiResponse]
    properties: list[ReportNamedOptionApiResponse]
    currencies: list[str]


class ReportMoneySummaryApiResponse(ApiModel):
    currency: str
    income: str
    expense: str
    profit: str


class ReportAccountBalanceApiResponse(ApiModel):
    account_id: UUID
    name: str
    currency: str
    balance: str
    is_active: bool


class ReportCategoryAggregateApiResponse(ReportMoneySummaryApiResponse):
    category_id: UUID | None
    name: str
    is_active: bool


class ReportPropertyAggregateApiResponse(ReportMoneySummaryApiResponse):
    property_id: UUID
    name: str
    is_active: bool


class ReportUncategorizedCapabilitiesApiResponse(ApiModel):
    can_correct: bool
    readonly_reason_code: (
        Literal[
            "financial_write_forbidden",
            "system_operation",
            "correction_account_unavailable",
        ]
        | None
    )


class ReportUncategorizedOperationApiResponse(ApiModel):
    operation_id: UUID
    version: int
    operation_date: date
    operation_type: OperationType
    description: str
    source: OperationSource
    signed_amount: str
    currency: str
    account_id: UUID | None
    capabilities: ReportUncategorizedCapabilitiesApiResponse


class ReportUncategorizedPageApiResponse(ApiModel):
    items: list[ReportUncategorizedOperationApiResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_previous: bool
    has_next: bool


class ReportOverviewApiResponse(ApiModel):
    workspace_name: str
    applied_filters: ReportAppliedFiltersApiResponse
    filter_options: ReportFilterOptionsApiResponse
    summary: ReportMoneySummaryApiResponse
    account_balances: list[ReportAccountBalanceApiResponse]
    category_rows: list[ReportCategoryAggregateApiResponse]
    property_rows: list[ReportPropertyAggregateApiResponse]
    balance_as_of: date | None
    next_review_document_id: UUID | None
    uncategorized: ReportUncategorizedPageApiResponse
