from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from app.features.reports.repository import (
    ReportAccountBalanceRow,
    ReportCategoryAggregateRow,
    ReportFilterAccountRow,
    ReportFilterCategoryRow,
    ReportFilterPropertyRow,
    ReportMoneySummaryRow,
    ReportPropertyAggregateRow,
    ReportUncategorizedPage,
)


@dataclass(frozen=True)
class ReportingFilters:
    date_from: date | None = None
    date_to: date | None = None
    currency: str | None = None
    account_id: UUID | None = None
    category_id: UUID | None = None
    property_id: UUID | None = None


@dataclass(frozen=True)
class ReportingPagination:
    page: int = 1
    page_size: int = 10


@dataclass(frozen=True)
class ReportingFilterOptions:
    accounts: list[ReportFilterAccountRow]
    categories: list[ReportFilterCategoryRow]
    properties: list[ReportFilterPropertyRow]
    currencies: list[str]


@dataclass(frozen=True)
class ReportingOverview:
    filters: ReportingFilters
    filter_options: ReportingFilterOptions
    summary: ReportMoneySummaryRow
    account_balances: list[ReportAccountBalanceRow]
    categories: list[ReportCategoryAggregateRow]
    properties: list[ReportPropertyAggregateRow]
    balance_as_of: date | None
    next_review_document_id: UUID | None
    uncategorized: ReportUncategorizedPage


class ReportingFilterError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ReportingOverviewRepository(Protocol):
    async def list_filter_accounts(self, workspace_id: UUID) -> list[ReportFilterAccountRow]: ...

    async def list_filter_categories(self, workspace_id: UUID) -> list[ReportFilterCategoryRow]: ...

    async def list_filter_properties(self, workspace_id: UUID) -> list[ReportFilterPropertyRow]: ...

    async def read_money_summary(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> ReportMoneySummaryRow: ...

    async def list_account_balances(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> list[ReportAccountBalanceRow]: ...

    async def list_category_aggregates(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> list[ReportCategoryAggregateRow]: ...

    async def list_property_aggregates(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> list[ReportPropertyAggregateRow]: ...

    async def find_next_review_document_id(self, workspace_id: UUID) -> UUID | None: ...

    async def read_uncategorized_page(
        self,
        *,
        workspace_id: UUID,
        filters: ReportingFilters,
        page: int,
        page_size: int,
    ) -> ReportUncategorizedPage: ...


class ReportingOverviewReader:
    def __init__(self, repository: ReportingOverviewRepository) -> None:
        self.repository = repository

    async def read(
        self,
        *,
        workspace_id: UUID,
        default_currency: str,
        filters: ReportingFilters,
        pagination: ReportingPagination = ReportingPagination(),
    ) -> ReportingOverview:
        if filters.date_from and filters.date_to and filters.date_from > filters.date_to:
            raise ReportingFilterError(
                "invalid_date_range",
                "Начало периода не может быть позже конца периода.",
            )

        accounts = await self.repository.list_filter_accounts(workspace_id)
        categories = await self.repository.list_filter_categories(workspace_id)
        properties = await self.repository.list_filter_properties(workspace_id)
        currencies = sorted({default_currency.upper(), *(item.currency for item in accounts)})
        applied = ReportingFilters(
            date_from=filters.date_from,
            date_to=filters.date_to,
            currency=(filters.currency or default_currency).upper(),
            account_id=filters.account_id,
            category_id=filters.category_id,
            property_id=filters.property_id,
        )
        self._validate_references(
            filters=applied,
            accounts=accounts,
            categories=categories,
            properties=properties,
            currencies=currencies,
        )
        return ReportingOverview(
            filters=applied,
            filter_options=ReportingFilterOptions(
                accounts=accounts,
                categories=categories,
                properties=properties,
                currencies=currencies,
            ),
            summary=await self.repository.read_money_summary(
                workspace_id=workspace_id,
                filters=applied,
            ),
            account_balances=await self.repository.list_account_balances(
                workspace_id=workspace_id,
                filters=applied,
            ),
            categories=await self.repository.list_category_aggregates(
                workspace_id=workspace_id,
                filters=applied,
            ),
            properties=await self.repository.list_property_aggregates(
                workspace_id=workspace_id,
                filters=applied,
            ),
            balance_as_of=applied.date_to,
            next_review_document_id=(
                await self.repository.find_next_review_document_id(workspace_id)
            ),
            uncategorized=await self.repository.read_uncategorized_page(
                workspace_id=workspace_id,
                filters=applied,
                page=pagination.page,
                page_size=pagination.page_size,
            ),
        )

    @staticmethod
    def _validate_references(
        *,
        filters: ReportingFilters,
        accounts: list[ReportFilterAccountRow],
        categories: list[ReportFilterCategoryRow],
        properties: list[ReportFilterPropertyRow],
        currencies: list[str],
    ) -> None:
        if filters.currency not in currencies:
            raise ReportingFilterError(
                "invalid_report_currency",
                "Эта валюта недоступна в текущем workspace.",
            )
        references = (
            (filters.account_id, {item.id for item in accounts}, "account"),
            (filters.category_id, {item.id for item in categories}, "category"),
            (filters.property_id, {item.id for item in properties}, "property"),
        )
        for selected_id, available_ids, kind in references:
            if selected_id is not None and selected_id not in available_ids:
                raise ReportingFilterError(
                    "report_filter_not_found",
                    f"Фильтр {kind} недоступен в текущем workspace.",
                )
