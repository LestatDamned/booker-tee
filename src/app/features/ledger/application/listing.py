from dataclasses import dataclass
from datetime import date
from math import ceil
from uuid import UUID

from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType

DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200


@dataclass(frozen=True)
class LedgerPagination:
    page: int = 1
    per_page: int = DEFAULT_PER_PAGE

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass(frozen=True)
class LedgerPage:
    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))

    @property
    def has_previous(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def previous_page(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_page(self) -> int:
        return min(self.total_pages, self.page + 1)


@dataclass(frozen=True)
class AccountEntryFilters:
    date_from: date | None = None
    date_to: date | None = None
    source: OperationSource | None = None
    operation_type: OperationType | None = None
    status: OperationStatus | None = OperationStatus.CONFIRMED
    category_id: UUID | None = None
    property_id: UUID | None = None
    search: str | None = None


@dataclass(frozen=True)
class ManualOperationFilters:
    date_from: date | None = None
    date_to: date | None = None
    operation_type: OperationType | None = None
    status: OperationStatus | None = None
    account_id: UUID | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None
    search: str | None = None

    @property
    def is_active(self) -> bool:
        return any(
            (
                self.date_from,
                self.date_to,
                self.operation_type,
                self.status,
                self.account_id,
                self.category_id,
                self.property_id,
                self.search,
            )
        )


def normalize_pagination(page: int, per_page: int) -> LedgerPagination:
    safe_page = max(1, page)
    safe_per_page = min(MAX_PER_PAGE, max(1, per_page))
    return LedgerPagination(page=safe_page, per_page=safe_per_page)
