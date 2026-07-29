from datetime import date
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import Query
from pydantic import BaseModel, ConfigDict, field_validator

from app.features.imports.documents.dto import (
    DEFAULT_IMPORT_DOCUMENTS_PER_PAGE,
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListSort,
    ImportDocumentListState,
)
from app.features.imports.documents.queries.list import (
    normalize_import_document_pagination,
)


class ImportDocumentListParameters(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    state: ImportDocumentListState | None = None
    account_id: UUID | None = None
    period_from: date | None = None
    period_to: date | None = None
    sort: ImportDocumentListSort = ImportDocumentListSort.CREATED_AT_DESC
    page: int = 1
    per_page: int = DEFAULT_IMPORT_DOCUMENTS_PER_PAGE

    @field_validator("state", mode="before")
    @classmethod
    def parse_state(cls, value: Any) -> ImportDocumentListState | None:
        return cls._parse_enum(value, ImportDocumentListState)

    @field_validator("sort", mode="before")
    @classmethod
    def parse_sort(cls, value: Any) -> ImportDocumentListSort:
        return (
            cls._parse_enum(value, ImportDocumentListSort) or ImportDocumentListSort.CREATED_AT_DESC
        )

    @field_validator("account_id", mode="before")
    @classmethod
    def parse_account_id(cls, value: Any) -> UUID | None:
        if value is None or isinstance(value, UUID):
            return value
        try:
            return UUID(str(value).strip())
        except ValueError:
            return None

    @field_validator("period_from", "period_to", mode="before")
    @classmethod
    def parse_date(cls, value: Any) -> date | None:
        if value is None or isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value).strip())
        except ValueError:
            return None

    @field_validator("page", mode="before")
    @classmethod
    def parse_page(cls, value: Any) -> int:
        return cls._parse_int(value, default=1)

    @field_validator("per_page", mode="before")
    @classmethod
    def parse_per_page(cls, value: Any) -> int:
        return cls._parse_int(value, default=DEFAULT_IMPORT_DOCUMENTS_PER_PAGE)

    @property
    def filters(self) -> ImportDocumentListFilters:
        return ImportDocumentListFilters(
            state=self.state,
            account_id=self.account_id,
            period_from=self.period_from,
            period_to=self.period_to,
            sort=self.sort,
        )

    @property
    def pagination(self) -> ImportDocumentListPagination:
        return normalize_import_document_pagination(
            ImportDocumentListPagination(
                page=self.page,
                per_page=self.per_page,
            )
        )

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


def parse_import_document_list_parameters(
    state: Annotated[str | None, Query()] = None,
    account_id: Annotated[str | None, Query()] = None,
    period_from: Annotated[str | None, Query()] = None,
    period_to: Annotated[str | None, Query()] = None,
    sort: Annotated[str | None, Query()] = None,
    page: Annotated[str | None, Query()] = None,
    per_page: Annotated[str | None, Query()] = None,
) -> ImportDocumentListParameters:
    return ImportDocumentListParameters.model_validate(
        {
            "state": state,
            "account_id": account_id,
            "period_from": period_from,
            "period_to": period_to,
            "sort": sort,
            "page": page,
            "per_page": per_page,
        }
    )
