from dataclasses import dataclass
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Query, status

from app.api.errors import ApiError
from app.features.reports.application.overview import ReportingFilters, ReportingPagination
from app.features.reports.repository import (
    DEFAULT_UNCATEGORIZED_PAGE_SIZE,
    MAX_UNCATEGORIZED_PAGE_SIZE,
)


@dataclass(frozen=True)
class ReportParameters:
    filters: ReportingFilters
    pagination: ReportingPagination


@dataclass(frozen=True)
class MonthlyReportParameters:
    month: str
    currency: str


def parse_report_parameters(
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    currency: Annotated[str | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    property_id: Annotated[str | None, Query()] = None,
    uncategorized_page: Annotated[str | None, Query()] = None,
    uncategorized_page_size: Annotated[str | None, Query()] = None,
) -> ReportParameters:
    normalized_currency = currency.strip().upper() if currency else None
    if normalized_currency is not None and len(normalized_currency) != 3:
        raise invalid_filter("currency", "трёхбуквенным кодом валюты")
    return ReportParameters(
        filters=ReportingFilters(
            date_from=parse_date(date_from, "date_from"),
            date_to=parse_date(date_to, "date_to"),
            currency=normalized_currency,
            account_id=parse_uuid(account_id, "account_id"),
            category_id=parse_uuid(category_id, "category_id"),
            property_id=parse_uuid(property_id, "property_id"),
        ),
        pagination=ReportingPagination(
            page=parse_positive_int(uncategorized_page, "uncategorized_page", default=1),
            page_size=parse_positive_int(
                uncategorized_page_size,
                "uncategorized_page_size",
                default=DEFAULT_UNCATEGORIZED_PAGE_SIZE,
                maximum=MAX_UNCATEGORIZED_PAGE_SIZE,
            ),
        ),
    )


def parse_monthly_report_parameters(
    month: Annotated[str, Query()],
    currency: Annotated[str, Query()],
) -> MonthlyReportParameters:
    normalized_currency = currency.strip().upper()
    if (
        len(normalized_currency) != 3
        or not normalized_currency.isascii()
        or not normalized_currency.isalpha()
    ):
        raise ApiError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_report_currency",
            message="Параметр currency должен быть трёхбуквенным кодом валюты.",
        )
    return MonthlyReportParameters(month=month.strip(), currency=normalized_currency)


def parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise invalid_filter(field, "датой YYYY-MM-DD") from error


def parse_uuid(value: str | None, field: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as error:
        raise invalid_filter(field, "валидным UUID") from error


def parse_positive_int(
    value: str | None,
    field: str,
    *,
    default: int,
    maximum: int | None = None,
) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise invalid_filter(field, "положительным целым числом") from error
    if parsed < 1 or (maximum is not None and parsed > maximum):
        expected = (
            f"целым числом от 1 до {maximum}"
            if maximum is not None
            else "положительным целым числом"
        )
        raise invalid_filter(field, expected)
    return parsed


def invalid_filter(field: str, expected: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_report_filter",
        message=f"Параметр {field} должен быть {expected}.",
    )
