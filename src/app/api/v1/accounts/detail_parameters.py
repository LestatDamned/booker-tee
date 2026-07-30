from datetime import date
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import (
    DEFAULT_PER_PAGE,
    AccountEntryFilters,
    LedgerPagination,
    normalize_pagination,
)


class AccountDetailParameters(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    date_from: date | None = None
    date_to: date | None = None
    source: OperationSource | None = None
    operation_type: OperationType | None = Field(default=None, alias="type")
    status: OperationStatus | None = OperationStatus.CONFIRMED
    category_id: UUID | None = None
    property_id: UUID | None = None
    search: str | None = None
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> date | None:
        if value is None or isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError:
            return None

    @field_validator("source", mode="before")
    @classmethod
    def parse_source(cls, value: Any) -> OperationSource | None:
        return cls._parse_enum(value, OperationSource)

    @field_validator("operation_type", mode="before")
    @classmethod
    def parse_operation_type(cls, value: Any) -> OperationType | None:
        return cls._parse_enum(value, OperationType)

    @field_validator("status", mode="before")
    @classmethod
    def parse_status(cls, value: Any) -> OperationStatus | None:
        return cls._parse_enum(value, OperationStatus)

    @field_validator("category_id", "property_id", mode="before")
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
        cleaned = " ".join(str(value).split())
        return cleaned or None

    @field_validator("page", mode="before")
    @classmethod
    def parse_page(cls, value: Any) -> int:
        return cls._parse_int(value, default=1)

    @field_validator("per_page", mode="before")
    @classmethod
    def parse_per_page(cls, value: Any) -> int:
        return cls._parse_int(value, default=DEFAULT_PER_PAGE)

    @property
    def filters(self) -> AccountEntryFilters:
        return AccountEntryFilters(
            date_from=self.date_from,
            date_to=self.date_to,
            source=self.source,
            operation_type=self.operation_type,
            status=self.status,
            category_id=self.category_id,
            property_id=self.property_id,
            search=self.search,
        )

    @property
    def pagination(self) -> LedgerPagination:
        return normalize_pagination(self.page, self.per_page)

    @staticmethod
    def _parse_enum[T: StrEnum](value: Any, enum_type: type[T]) -> T | None:
        if value is None or isinstance(value, enum_type):
            return value
        try:
            return enum_type(str(value).strip())
        except ValueError:
            return None

    @staticmethod
    def _parse_int(value: Any, *, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def parse_account_detail_parameters(
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    source: Annotated[str | None, Query()] = None,
    operation_type: Annotated[str | None, Query(alias="type")] = None,
    status: Annotated[str | None, Query()] = None,
    category_id: Annotated[str | None, Query()] = None,
    property_id: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[str | None, Query()] = None,
    per_page: Annotated[str | None, Query()] = None,
) -> AccountDetailParameters:
    return AccountDetailParameters.model_validate(
        {
            "date_from": date_from,
            "date_to": date_to,
            "source": source,
            "type": operation_type,
            "status": status if status is not None else OperationStatus.CONFIRMED,
            "category_id": category_id,
            "property_id": property_id,
            "search": search,
            "page": page,
            "per_page": per_page,
        }
    )
