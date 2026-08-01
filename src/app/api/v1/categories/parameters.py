from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Query, status

from app.api.errors import ApiError
from app.features.categories.application.detail import (
    DEFAULT_CATEGORY_OPERATION_PAGE_SIZE,
    MAX_CATEGORY_OPERATION_PAGE_SIZE,
)
from app.features.ledger.domain.types import OperationType


@dataclass(frozen=True)
class CategoryDetailParameters:
    date_from: date | None
    date_to: date | None
    currency: str | None
    operation_type: OperationType | None
    search: str | None
    operations_page: int
    operations_page_size: int


def parse_category_detail_parameters(
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    currency: Annotated[str | None, Query()] = None,
    type_: Annotated[str | None, Query(alias="type")] = None,
    operations_page: Annotated[str | None, Query()] = None,
    operations_page_size: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> CategoryDetailParameters:
    normalized_currency = currency.strip().upper() if currency else None
    if normalized_currency is not None and len(normalized_currency) != 3:
        raise invalid_category_filter("currency", "трёхбуквенным кодом валюты")
    return CategoryDetailParameters(
        date_from=parse_date(date_from, "date_from"),
        date_to=parse_date(date_to, "date_to"),
        currency=normalized_currency,
        operation_type=parse_operation_type(type_),
        search=parse_search(search),
        operations_page=parse_positive_int(
            operations_page,
            "operations_page",
            default=1,
        ),
        operations_page_size=parse_positive_int(
            operations_page_size,
            "operations_page_size",
            default=DEFAULT_CATEGORY_OPERATION_PAGE_SIZE,
            maximum=MAX_CATEGORY_OPERATION_PAGE_SIZE,
        ),
    )


def parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise invalid_category_filter(field, "датой YYYY-MM-DD") from error


def parse_operation_type(value: str | None) -> OperationType | None:
    if not value:
        return None
    if value not in {OperationType.INCOME, OperationType.EXPENSE}:
        raise invalid_category_filter("type", "значением income или expense")
    return OperationType(value)


def parse_search(value: str | None) -> str | None:
    normalized = " ".join(value.split()) if value else ""
    if len(normalized) > 200:
        raise invalid_category_filter("search", "строкой не длиннее 200 символов")
    return normalized or None


def parse_positive_int(
    value: str | None,
    field: str,
    *,
    default: int,
    maximum: int | None = None,
) -> int:
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as error:
        raise invalid_category_filter(field, "положительным целым числом") from error
    if parsed < 1 or (maximum is not None and parsed > maximum):
        expected = (
            f"целым числом от 1 до {maximum}"
            if maximum is not None
            else "положительным целым числом"
        )
        raise invalid_category_filter(field, expected)
    return parsed


def invalid_category_filter(field: str, expected: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_category_filter",
        message=f"Параметр {field} должен быть {expected}.",
    )
