import asyncio
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.reports.dependencies import (
    get_monthly_report_reader,
    get_reporting_overview_reader,
)
from app.api.v1.reports.parameters import (
    MonthlyReportParameters,
    ReportParameters,
    parse_monthly_report_parameters,
    parse_report_parameters,
)
from app.api.v1.reports.schemas import (
    ReportAccountBalanceApiResponse,
    ReportAccountOptionApiResponse,
    ReportAppliedFiltersApiResponse,
    ReportBalanceSummaryApiResponse,
    ReportCategoryAggregateApiResponse,
    ReportFilterOptionsApiResponse,
    ReportMoneySummaryApiResponse,
    ReportNamedOptionApiResponse,
    ReportOverviewApiResponse,
    ReportPropertyAggregateApiResponse,
    ReportUncategorizedCapabilitiesApiResponse,
    ReportUncategorizedOperationApiResponse,
    ReportUncategorizedPageApiResponse,
)
from app.features.ledger.domain.types import OperationSource
from app.features.reports.application.monthly_export import (
    InvalidReportMonthError,
    MonthlyExportTooLargeError,
    MonthlyReportReader,
)
from app.features.reports.application.overview import (
    ReportingFilterError,
    ReportingOverviewReader,
)
from app.features.reports.monthly_report_xlsx import build_monthly_report_xlsx
from app.features.reports.repository import (
    ReportMoneySummaryRow,
    ReportUncategorizedOperationRow,
)
from app.features.workspaces.permissions import can_write_financial_data

router = APIRouter(prefix="/reports", tags=["reports"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get(
    "/export.xlsx",
    response_class=Response,
    responses={
        200: {"content": {XLSX_MEDIA_TYPE: {}}},
        **api_error_responses(
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ),
    },
)
async def export_monthly_report(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[
        MonthlyReportParameters,
        Depends(parse_monthly_report_parameters),
    ],
    reader: Annotated[MonthlyReportReader, Depends(get_monthly_report_reader)],
) -> Response:
    workspace = context.workspace.workspace
    try:
        report = await reader.read(
            workspace_id=workspace.id,
            workspace_name=workspace.name,
            default_currency=workspace.default_currency,
            month=parameters.month,
            currency=parameters.currency,
        )
    except InvalidReportMonthError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_report_month",
            message="Параметр month должен быть календарным месяцем YYYY-MM.",
        ) from error
    except ReportingFilterError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
        ) from error
    except MonthlyExportTooLargeError as error:
        raise ApiError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="monthly_export_too_large",
            message="В выбранном месяце больше 10 000 движений.",
        ) from error

    payload = await asyncio.to_thread(build_monthly_report_xlsx, report)
    filename = f"booker-tee_{report.month}_{report.overview.summary.currency}.xlsx"
    return Response(
        content=payload,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "",
    response_model=ReportOverviewApiResponse,
    responses=api_error_responses(
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    ),
)
async def get_report_overview(
    context: Annotated[ApiRequestContext, Depends(get_api_request_context)],
    parameters: Annotated[ReportParameters, Depends(parse_report_parameters)],
    reader: Annotated[
        ReportingOverviewReader,
        Depends(get_reporting_overview_reader),
    ],
) -> ReportOverviewApiResponse:
    workspace = context.workspace.workspace
    try:
        overview = await reader.read(
            workspace_id=workspace.id,
            default_currency=workspace.default_currency,
            filters=parameters.filters,
            pagination=parameters.pagination,
        )
    except ReportingFilterError as error:
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=error.code,
            message=str(error),
        ) from error
    return ReportOverviewApiResponse(
        workspace_name=workspace.name,
        applied_filters=ReportAppliedFiltersApiResponse.model_validate(overview.filters),
        filter_options=ReportFilterOptionsApiResponse(
            accounts=[
                ReportAccountOptionApiResponse.model_validate(item)
                for item in overview.filter_options.accounts
            ],
            categories=[
                ReportNamedOptionApiResponse.model_validate(item)
                for item in overview.filter_options.categories
            ],
            properties=[
                ReportNamedOptionApiResponse.model_validate(item)
                for item in overview.filter_options.properties
            ],
            currencies=overview.filter_options.currencies,
        ),
        summary=money_summary(overview.summary),
        balance_summary=ReportBalanceSummaryApiResponse(
            currency=overview.balance_summary.currency,
            opening_balance=decimal_string(overview.balance_summary.opening_balance),
            closing_balance=decimal_string(overview.balance_summary.closing_balance),
            balance_change=decimal_string(overview.balance_summary.balance_change),
        ),
        account_balances=[
            ReportAccountBalanceApiResponse(
                account_id=item.account_id,
                name=item.name,
                currency=item.currency,
                opening_balance=decimal_string(item.opening_balance),
                closing_balance=decimal_string(item.closing_balance),
                balance_change=decimal_string(item.balance_change),
                is_active=item.is_active,
            )
            for item in overview.account_balances
        ],
        category_rows=[
            ReportCategoryAggregateApiResponse(
                category_id=item.category_id,
                name=item.name,
                currency=item.currency,
                income=decimal_string(item.income),
                expense=decimal_string(item.expense),
                profit=decimal_string(item.profit),
                is_active=item.is_active,
            )
            for item in overview.categories
        ],
        property_rows=[
            ReportPropertyAggregateApiResponse(
                property_id=item.property_id,
                name=item.name,
                currency=item.currency,
                income=decimal_string(item.income),
                expense=decimal_string(item.expense),
                profit=decimal_string(item.profit),
                is_active=item.is_active,
            )
            for item in overview.properties
        ],
        balance_as_of=overview.balance_as_of,
        next_review_document_id=overview.next_review_document_id,
        uncategorized=ReportUncategorizedPageApiResponse(
            items=[
                uncategorized_operation(
                    item,
                    can_write=can_write_financial_data(context.workspace.membership),
                )
                for item in overview.uncategorized.items
            ],
            page=overview.uncategorized.page,
            page_size=overview.uncategorized.page_size,
            total=overview.uncategorized.total,
            total_pages=overview.uncategorized.total_pages,
            has_previous=overview.uncategorized.has_previous,
            has_next=overview.uncategorized.has_next,
        ),
    )


def money_summary(item: ReportMoneySummaryRow) -> ReportMoneySummaryApiResponse:
    return ReportMoneySummaryApiResponse(
        currency=item.currency,
        income=decimal_string(item.income),
        expense=decimal_string(item.expense),
        profit=decimal_string(item.profit),
    )


def decimal_string(value: Decimal) -> str:
    return f"{value:.2f}"


def uncategorized_operation(
    item: ReportUncategorizedOperationRow,
    *,
    can_write: bool,
) -> ReportUncategorizedOperationApiResponse:
    can_correct = can_write and (
        item.source == OperationSource.MANUAL
        or (item.source == OperationSource.BANK_PDF and item.account_id is not None)
    )
    reason: str | None = None
    if not can_write:
        reason = "financial_write_forbidden"
    elif item.source == OperationSource.SYSTEM:
        reason = "system_operation"
    elif item.source == OperationSource.BANK_PDF and item.account_id is None:
        reason = "correction_account_unavailable"
    return ReportUncategorizedOperationApiResponse(
        operation_id=item.operation_id,
        version=item.version,
        operation_date=item.operation_date,
        operation_type=item.operation_type,
        description=item.description,
        source=item.source,
        signed_amount=decimal_string(item.signed_amount),
        currency=item.currency,
        account_id=item.account_id,
        capabilities=ReportUncategorizedCapabilitiesApiResponse(
            can_correct=can_correct,
            readonly_reason_code=reason,
        ),
    )
