from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.features.ledger.application.listing import (
    LedgerPagination,
    ManualOperationFilters,
    normalize_pagination,
)
from app.features.ledger.models import OperationStatus, OperationType
from app.shared.query_params import (
    clean_optional_query_text,
    parse_optional_query_date,
    parse_optional_query_enum,
    parse_optional_query_uuid,
)

MANUAL_LEDGER_URL = "/_next/ledger/manual"


@dataclass(frozen=True)
class ManualLedgerListQuery:
    filters: ManualOperationFilters
    pagination: LedgerPagination
    focused_operation_id: UUID | None = None


class ManualLedgerPageParams(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date_from: str | None = None
    date_to: str | None = None
    operation_type_filter: str | None = Field(default=None, alias="type")
    status_filter: str | None = Field(default=None, alias="status")
    search: str | None = None
    operation_id: str | None = None
    edit: str | None = None
    create: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=200)


def build_list_query(params: ManualLedgerPageParams) -> ManualLedgerListQuery:
    return ManualLedgerListQuery(
        filters=ManualOperationFilters(
            date_from=parse_optional_query_date(params.date_from, field_name="date_from"),
            date_to=parse_optional_query_date(params.date_to, field_name="date_to"),
            operation_type=parse_optional_query_enum(
                params.operation_type_filter,
                OperationType,
                field_name="type",
            ),
            status=parse_optional_query_enum(
                params.status_filter,
                OperationStatus,
                field_name="status",
            ),
            search=clean_optional_query_text(params.search),
        ),
        pagination=normalize_pagination(params.page, params.per_page),
        focused_operation_id=parse_optional_query_uuid(
            params.operation_id,
            field_name="operation_id",
        ),
    )


def list_query_from_return_to(return_to: str) -> ManualLedgerListQuery:
    query = parse_qs(urlsplit(return_to).query)
    return build_list_query(
        ManualLedgerPageParams(
            date_from=first_query_value(query, "date_from"),
            date_to=first_query_value(query, "date_to"),
            type=first_query_value(query, "type"),
            status=first_query_value(query, "status"),
            search=first_query_value(query, "search"),
            operation_id=first_query_value(query, "operation_id"),
            page=max(1, parse_query_int(query, "page", default=1)),
            per_page=min(200, max(1, parse_query_int(query, "per_page", default=50))),
        )
    )


def safe_manual_ledger_return_to(return_to: str | None) -> str:
    if not return_to:
        return MANUAL_LEDGER_URL
    parsed = urlsplit(return_to)
    if parsed.scheme or parsed.netloc or parsed.path != MANUAL_LEDGER_URL:
        return MANUAL_LEDGER_URL
    return urlunsplit(("", "", parsed.path, parsed.query, ""))


def open_edit_url(return_to: str, operation_id: UUID) -> str:
    parsed = urlsplit(return_to)
    query = parse_qs(parsed.query)
    query["operation_id"] = [str(operation_id)]
    query["edit"] = [str(operation_id)]
    return urlunsplit(
        ("", "", MANUAL_LEDGER_URL, urlencode(query, doseq=True), f"next-operation-{operation_id}")
    )


def open_create_url(return_to: str) -> str:
    parsed = urlsplit(return_to)
    query = parse_qs(parsed.query)
    query["create"] = ["true"]
    return urlunsplit(("", "", MANUAL_LEDGER_URL, urlencode(query, doseq=True), "create"))


def target_operation_url(return_to: str, operation_id: UUID) -> str:
    parsed = urlsplit(return_to)
    query = parse_qs(parsed.query)
    query.pop("edit", None)
    query["operation_id"] = [str(operation_id)]
    return urlunsplit(
        ("", "", MANUAL_LEDGER_URL, urlencode(query, doseq=True), f"next-operation-{operation_id}")
    )


def clear_operation_target_url(return_to: str) -> str:
    parsed = urlsplit(return_to)
    query = parse_qs(parsed.query)
    query.pop("operation_id", None)
    query.pop("edit", None)
    query.pop("create", None)
    return urlunsplit(("", "", MANUAL_LEDGER_URL, urlencode(query, doseq=True), ""))


def first_query_value(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name)
    return values[0] if values else None


def parse_query_int(query: dict[str, list[str]], name: str, *, default: int) -> int:
    raw_value = first_query_value(query, name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default
