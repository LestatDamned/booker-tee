from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import api_error_responses
from app.api.v1.dashboard.schemas import (
    DashboardAccountApiResponse,
    DashboardAttentionApiResponse,
    DashboardCapabilitiesApiResponse,
    DashboardDocumentAccountApiResponse,
    DashboardDocumentApiResponse,
    DashboardMoneySummaryApiResponse,
    DashboardOnboardingApiResponse,
    DashboardOverviewApiResponse,
    DashboardPeriodApiResponse,
)
from app.db.session import get_session
from app.features.accounts.repository import AccountRepository
from app.features.dashboard.application.overview import (
    DashboardDocument,
    DashboardOverviewReader,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.reports.repository import ReportsRepository
from app.features.workspaces.permissions import permission_flags_for

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_dashboard_overview_reader(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DashboardOverviewReader:
    return DashboardOverviewReader(
        reports=ReportsRepository(session),
        accounts=AccountRepository(session),
        documents=DocumentRepository(session),
    )


@router.get(
    "",
    response_model=DashboardOverviewApiResponse,
    responses=api_error_responses(
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def get_dashboard_overview(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    reader: Annotated[DashboardOverviewReader, Depends(get_dashboard_overview_reader)],
) -> DashboardOverviewApiResponse:
    workspace = context.workspace.workspace
    permissions = permission_flags_for(context.workspace.membership)
    overview = await reader.read(
        workspace_id=workspace.id,
        default_currency=workspace.default_currency,
        can_upload=permissions.can_manage_imports,
    )
    return DashboardOverviewApiResponse(
        workspace_name=workspace.name,
        period=DashboardPeriodApiResponse(
            start=overview.period_start,
            end=overview.period_end,
        ),
        current_period=DashboardPeriodApiResponse(
            start=overview.current_period_start,
            end=overview.current_period_end,
        ),
        summary=DashboardMoneySummaryApiResponse(
            currency=overview.summary.currency,
            income=decimal_string(overview.summary.income),
            expense=decimal_string(overview.summary.expense),
            profit=decimal_string(overview.summary.profit),
        ),
        accounts=[
            DashboardAccountApiResponse(
                id=account.id,
                name=account.name,
                currency=account.currency,
                balance=decimal_string(account.balance),
            )
            for account in overview.accounts
        ],
        active_account_count=overview.active_account_count,
        attention=DashboardAttentionApiResponse(
            total=overview.attention_document_count,
            items=[document_response(item) for item in overview.attention_documents],
        ),
        recent_documents=[document_response(item) for item in overview.recent_documents],
        onboarding=DashboardOnboardingApiResponse(
            has_accounts=overview.onboarding.has_accounts,
            has_documents=overview.onboarding.has_documents,
            has_confirmed_activity=overview.onboarding.has_confirmed_activity,
            is_complete=overview.onboarding.is_complete,
        ),
        capabilities=DashboardCapabilitiesApiResponse(
            can_upload=permissions.can_manage_imports,
            can_write_financial_data=permissions.can_write_financial_data,
            primary_action=primary_action(
                can_upload=permissions.can_manage_imports,
                can_write=permissions.can_write_financial_data,
            ),
        ),
    )


def document_response(document: DashboardDocument) -> DashboardDocumentApiResponse:
    return DashboardDocumentApiResponse(
        id=document.id,
        filename=document.filename,
        status=document.status,
        created_at=document.created_at,
        account=(
            DashboardDocumentAccountApiResponse(
                id=document.account.id,
                name=document.account.name,
                currency=document.account.currency,
            )
            if document.account is not None
            else None
        ),
        reviewable_row_count=document.reviewable_row_count,
        next_step_kind=document.next_step_kind,
        statement_period_end=document.statement_period_end,
    )


def primary_action(
    *,
    can_upload: bool,
    can_write: bool,
) -> Literal["upload", "manual_operation", "reports"]:
    if can_upload:
        return "upload"
    if can_write:
        return "manual_operation"
    return "reports"


def decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"
