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


class ManualLedgerPageParams(BaseModel):
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
    edit: UUID | None = None
    create: bool = False
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
        "edit",
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

    @field_validator("create", mode="before")
    @classmethod
    def parse_create(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 1
        return str(value).strip().lower() in {"1", "true", "on", "yes"}

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
        return self.edit or self.operation_id

    @property
    def create_requested(self) -> bool:
        return self.create and self.edit is None

    @classmethod
    def from_return_to(cls, return_to: str | None) -> ManualLedgerPageParams:
        safe_return_to = safe_manual_ledger_return_to(return_to)
        query = parse_qs(urlsplit(safe_return_to).query, keep_blank_values=True)
        return cls.model_validate({name: values[-1] for name, values in query.items() if values})

    @classmethod
    def from_list_state(
        cls,
        *,
        filters: ManualOperationFilters,
        page: int,
        per_page: int,
        focused_operation_id: UUID | None,
    ) -> ManualLedgerPageParams:
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
        return self._url(include_ui_state=False)

    def with_page(self, page: int) -> ManualLedgerPageParams:
        return self.model_copy(update={"page": max(1, page)})

    def open_edit_url(self, operation_id: UUID) -> str:
        state = self.model_copy(
            update={
                "operation_id": operation_id,
                "edit": operation_id,
                "create": False,
            }
        )
        return state._url(
            include_ui_state=True,
            fragment=f"next-operation-{operation_id}",
        )

    def open_create_url(self) -> str:
        state = self.model_copy(update={"edit": None, "create": True})
        return state._url(include_ui_state=True, fragment="create")

    def target_operation_url(self, operation_id: UUID) -> str:
        state = self.model_copy(
            update={
                "operation_id": operation_id,
                "edit": None,
                "create": False,
            }
        )
        return state._url(
            include_ui_state=True,
            fragment=f"next-operation-{operation_id}",
        )

    def clear_operation_target_url(self) -> str:
        state = self.model_copy(
            update={
                "operation_id": None,
                "edit": None,
                "create": False,
            }
        )
        return state._url(include_ui_state=True)

    def _url(self, *, include_ui_state: bool, fragment: str = "") -> str:
        values = self.model_dump(mode="json", by_alias=True, exclude_none=True)
        query: dict[str, str | int | bool] = {
            "page": self.page,
            "per_page": self.per_page,
        }
        excluded = {"page", "per_page", "edit", "create"}
        query.update({name: value for name, value in values.items() if name not in excluded})
        if include_ui_state:
            if self.edit is not None:
                query["edit"] = str(self.edit)
            if self.create_requested:
                query["create"] = "true"
        return urlunsplit(("", "", MANUAL_LEDGER_URL, urlencode(query), fragment))

    @staticmethod
    def _parse_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


@dataclass(frozen=True)
class ManualLedgerListQuery:
    filters: ManualOperationFilters
    pagination: LedgerPagination
    focused_operation_id: UUID | None = None

    @classmethod
    def from_page_params(
        cls,
        params: ManualLedgerPageParams,
    ) -> ManualLedgerListQuery:
        return cls(
            filters=ManualOperationFilters(
                date_from=params.date_from,
                date_to=params.date_to,
                operation_type=params.operation_type_filter,
                status=params.status_filter,
                account_id=params.account_id,
                category_id=params.category_id,
                property_id=params.property_id,
                search=params.search,
            ),
            pagination=normalize_pagination(params.page, params.per_page),
            focused_operation_id=params.focused_operation_id,
        )


def safe_manual_ledger_return_to(return_to: str | None) -> str:
    if not return_to:
        return MANUAL_LEDGER_URL
    parsed = urlsplit(return_to)
    if parsed.scheme or parsed.netloc or parsed.path != MANUAL_LEDGER_URL:
        return MANUAL_LEDGER_URL
    return urlunsplit(("", "", parsed.path, parsed.query, ""))
