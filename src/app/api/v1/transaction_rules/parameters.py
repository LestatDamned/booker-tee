from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Query, status

from app.api.errors import ApiError
from app.features.transaction_rules.schemas import TransactionRuleDirectoryStatus

DEFAULT_TRANSACTION_RULE_PAGE_SIZE = 50
MAX_TRANSACTION_RULE_PAGE_SIZE = 100


@dataclass(frozen=True)
class TransactionRuleDirectoryParameters:
    search: str | None
    category_id: UUID | None
    status: TransactionRuleDirectoryStatus
    page: int
    page_size: int
    rule_id: UUID | None


def parse_transaction_rule_directory_parameters(
    q: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    status_: Annotated[str | None, Query(alias="status")] = None,
    page: Annotated[str | None, Query()] = None,
    page_size: Annotated[str | None, Query()] = None,
    rule_id: Annotated[str | None, Query()] = None,
) -> TransactionRuleDirectoryParameters:
    return TransactionRuleDirectoryParameters(
        search=parse_search(q),
        category_id=parse_uuid(category_id, "category_id"),
        status=parse_status(status_),
        page=parse_positive_int(page, "page", default=1),
        page_size=parse_positive_int(
            page_size,
            "page_size",
            default=DEFAULT_TRANSACTION_RULE_PAGE_SIZE,
            maximum=MAX_TRANSACTION_RULE_PAGE_SIZE,
        ),
        rule_id=parse_uuid(rule_id, "rule_id"),
    )


def parse_search(value: str | None) -> str | None:
    normalized = " ".join(value.split()) if value else ""
    if len(normalized) > 200:
        raise invalid_transaction_rule_filter("q", "строкой не длиннее 200 символов")
    return normalized or None


def parse_uuid(value: str | None, field: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as error:
        raise invalid_transaction_rule_filter(field, "UUID") from error


def parse_status(value: str | None) -> TransactionRuleDirectoryStatus:
    if not value:
        return TransactionRuleDirectoryStatus.ALL
    try:
        return TransactionRuleDirectoryStatus(value)
    except ValueError as error:
        raise invalid_transaction_rule_filter(
            "status",
            "значением all, active или disabled",
        ) from error


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
        raise invalid_transaction_rule_filter(field, "положительным целым числом") from error
    if parsed < 1 or (maximum is not None and parsed > maximum):
        expected = (
            f"целым числом от 1 до {maximum}"
            if maximum is not None
            else "положительным целым числом"
        )
        raise invalid_transaction_rule_filter(field, expected)
    return parsed


def invalid_transaction_rule_filter(field: str, expected: str) -> ApiError:
    return ApiError(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="invalid_transaction_rule_filter",
        message=f"Параметр {field} должен быть {expected}.",
    )
