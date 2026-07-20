from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.ledger.application.listing import (
    LedgerPagination,
    ManualOperationFilters,
    normalize_pagination,
)
from app.features.ledger.models import OperationStatus, OperationType

MANUAL_LEDGER_URL = "/_next/ledger/manual"


class ManualLedgerUrlState(BaseModel):
    """Typed, tolerant state of the manual-ledger page URL."""

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        populate_by_name=True,
    )

    date_from: date | None = None
    date_to: date | None = None
    operation_type_filter: OperationType | None = Field(default=None, alias="type")
    status_filter: OperationStatus | None = Field(default=None, alias="status")
    account_id: UUID | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None
    search: str | None = None
    operation_id: UUID | None = None
    page: int = 1
    per_page: int = 50

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> date | None:
        if value is None or isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError:
            return None

    @field_validator("operation_type_filter", mode="before")
    @classmethod
    def parse_operation_type(cls, value: Any) -> OperationType | None:
        if value is None or isinstance(value, OperationType):
            return value
        try:
            return OperationType(str(value).strip())
        except ValueError:
            return None

    @field_validator("status_filter", mode="before")
    @classmethod
    def parse_operation_status(cls, value: Any) -> OperationStatus | None:
        if value is None or isinstance(value, OperationStatus):
            return value
        try:
            return OperationStatus(str(value).strip())
        except ValueError:
            return None

    @field_validator(
        "account_id",
        "category_id",
        "property_id",
        "operation_id",
        mode="before",
    )
    @classmethod
    def parse_uuid(cls, value: Any) -> UUID | None:
        if value is None or isinstance(value, UUID):
            return value
        try:
            return UUID(str(value).strip())
        except ValueError:
            return None

    @field_validator("search", mode="before")
    @classmethod
    def clean_search(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("page", mode="before")
    @classmethod
    def normalize_page(cls, value: Any) -> int:
        return max(1, cls._parse_int(value, default=1))

    @field_validator("per_page", mode="before")
    @classmethod
    def normalize_per_page(cls, value: Any) -> int:
        return min(200, max(1, cls._parse_int(value, default=50)))

    @property
    def focused_operation_id(self) -> UUID | None:
        return self.operation_id

    @classmethod
    def from_return_to(cls, return_to: str | None) -> ManualLedgerUrlState:
        safe_return_to = safe_manual_ledger_return_to(return_to)
        query = parse_qs(urlsplit(safe_return_to).query, keep_blank_values=True)
        return cls.model_validate({name: values[-1] for name, values in query.items() if values})

    @classmethod
    def for_list_page(
        cls,
        *,
        filters: ManualOperationFilters,
        page: int,
        per_page: int,
        focused_operation_id: UUID | None,
    ) -> ManualLedgerUrlState:
        return cls(
            date_from=filters.date_from,
            date_to=filters.date_to,
            type=filters.operation_type,
            status=filters.status,
            account_id=filters.account_id,
            category_id=filters.category_id,
            property_id=filters.property_id,
            search=filters.search,
            operation_id=focused_operation_id,
            page=page,
            per_page=per_page,
        )

    def list_url(self) -> str:
        return self._url()

    def with_page(self, page: int) -> ManualLedgerUrlState:
        return self.model_copy(update={"page": max(1, page)})

    def target_operation_url(self, operation_id: UUID) -> str:
        state = self.model_copy(update={"operation_id": operation_id})
        return state._url(
            fragment=f"next-operation-{operation_id}",
        )

    def clear_operation_target_url(self) -> str:
        state = self.model_copy(update={"operation_id": None})
        return state._url()

    def _url(self, *, fragment: str = "") -> str:
        values = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        query: dict[str, str | int | bool] = {
            "page": self.page,
            "per_page": self.per_page,
        }
        excluded = {"page", "per_page"}
        query.update({name: value for name, value in values.items() if name not in excluded})
        return urlunsplit(("", "", MANUAL_LEDGER_URL, urlencode(query), fragment))

    @staticmethod
    def _parse_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


@dataclass(frozen=True)
class ManualLedgerPageParams:
    filters: ManualOperationFilters
    pagination: LedgerPagination

    @classmethod
    def from_url_state(
        cls,
        state: ManualLedgerUrlState,
    ) -> ManualLedgerPageParams:
        return cls(
            filters=ManualOperationFilters(
                date_from=state.date_from,
                date_to=state.date_to,
                operation_type=state.operation_type_filter,
                status=state.status_filter,
                account_id=state.account_id,
                category_id=state.category_id,
                property_id=state.property_id,
                search=state.search,
            ),
            pagination=normalize_pagination(state.page, state.per_page),
        )


def safe_manual_ledger_return_to(return_to: str | None) -> str:
    if not return_to:
        return MANUAL_LEDGER_URL
    parsed = urlsplit(return_to)
    if parsed.scheme or parsed.netloc or parsed.path != MANUAL_LEDGER_URL:
        return MANUAL_LEDGER_URL
    return urlunsplit(("", "", parsed.path, parsed.query, ""))
