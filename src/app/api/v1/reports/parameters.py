from dataclasses import dataclass
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Query, status

from app.api.errors import ApiError
from app.features.reports.application.overview import ReportingFilters


@dataclass(frozen=True)
class ReportParameters:
    filters: ReportingFilters


def parse_report_parameters(
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    currency: Annotated[str | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    property_id: Annotated[str | None, Query()] = None,
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
        )
    )


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


def invalid_filter(field: str, expected: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_report_filter",
        message=f"Параметр {field} должен быть {expected}.",
    )
