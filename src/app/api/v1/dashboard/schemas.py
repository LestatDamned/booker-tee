from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.api.schemas import ApiModel
from app.features.imports.documents.dto import ImportDocumentNextStepKind
from app.features.imports.documents.types import UploadedDocumentStatus


class DashboardPeriodApiResponse(ApiModel):
    start: date
    end: date


class DashboardMoneySummaryApiResponse(ApiModel):
    currency: str
    income: str
    expense: str
    profit: str


class DashboardAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str
    balance: str


class DashboardDocumentAccountApiResponse(ApiModel):
    id: UUID
    name: str
    currency: str


class DashboardDocumentApiResponse(ApiModel):
    id: UUID
    filename: str
    status: UploadedDocumentStatus
    created_at: datetime
    account: DashboardDocumentAccountApiResponse | None
    reviewable_row_count: int
    next_step_kind: ImportDocumentNextStepKind
    statement_period_end: date | None


class DashboardAttentionApiResponse(ApiModel):
    total: int
    items: list[DashboardDocumentApiResponse]


class DashboardOnboardingApiResponse(ApiModel):
    has_accounts: bool
    has_documents: bool
    has_confirmed_activity: bool
    is_complete: bool


class DashboardCapabilitiesApiResponse(ApiModel):
    can_upload: bool
    can_write_financial_data: bool
    primary_action: Literal["upload", "manual_operation", "reports"]


class DashboardOverviewApiResponse(ApiModel):
    workspace_name: str
    period: DashboardPeriodApiResponse
    current_period: DashboardPeriodApiResponse
    summary: DashboardMoneySummaryApiResponse
    accounts: list[DashboardAccountApiResponse]
    active_account_count: int
    attention: DashboardAttentionApiResponse
    recent_documents: list[DashboardDocumentApiResponse]
    onboarding: DashboardOnboardingApiResponse
    capabilities: DashboardCapabilitiesApiResponse
