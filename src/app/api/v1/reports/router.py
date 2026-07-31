from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.errors import ApiError, api_error_responses
from app.api.v1.reports.dependencies import get_reporting_overview_reader
from app.api.v1.reports.parameters import ReportParameters, parse_report_parameters
from app.api.v1.reports.schemas import (
    ReportAccountBalanceApiResponse,
    ReportAccountOptionApiResponse,
    ReportAppliedFiltersApiResponse,
    ReportCategoryAggregateApiResponse,
    ReportFilterOptionsApiResponse,
    ReportMoneySummaryApiResponse,
    ReportNamedOptionApiResponse,
    ReportOverviewApiResponse,
    ReportPropertyAggregateApiResponse,
)
from app.features.reports.application.overview import (
    ReportingFilterError,
    ReportingOverviewReader,
)
from app.features.reports.repository import ReportMoneySummaryRow

router = APIRouter(prefix="/reports", tags=["reports"])


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
        account_balances=[
            ReportAccountBalanceApiResponse(
                account_id=item.account_id,
                name=item.name,
                currency=item.currency,
                balance=decimal_string(item.balance),
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
