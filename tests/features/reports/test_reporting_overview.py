from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.ledger.domain.types import OperationSource, OperationType
from app.features.properties.models import PropertyStatus
from app.features.reports.application.overview import (
    ReportBalanceSummary,
    ReportingFilterError,
    ReportingFilters,
    ReportingOverviewReader,
    ReportingPagination,
)
from app.features.reports.repository import (
    ReportAccountBalanceRow,
    ReportCategoryAggregateRow,
    ReportFilterAccountRow,
    ReportFilterCategoryRow,
    ReportFilterPropertyRow,
    ReportMoneySummaryRow,
    ReportPropertyAggregateRow,
    ReportsRepository,
    ReportUncategorizedPage,
)


class ReportingRepositoryStub:
    def __init__(self) -> None:
        self.account_id = uuid4()
        self.category_id = uuid4()
        self.property_id = uuid4()
        self.document_id = uuid4()
        self.calls: list[tuple[str, UUID, ReportingFilters | None]] = []

    async def list_filter_accounts(self, workspace_id: UUID) -> list[ReportFilterAccountRow]:
        self.calls.append(("accounts", workspace_id, None))
        return [
            ReportFilterAccountRow(self.account_id, "Основной", "RUB", True),
            ReportFilterAccountRow(uuid4(), "Доллары", "USD", False),
        ]

    async def list_filter_categories(self, workspace_id: UUID) -> list[ReportFilterCategoryRow]:
        self.calls.append(("categories", workspace_id, None))
        return [ReportFilterCategoryRow(self.category_id, "Продукты", True)]

    async def list_filter_properties(self, workspace_id: UUID) -> list[ReportFilterPropertyRow]:
        self.calls.append(("properties", workspace_id, None))
        return [ReportFilterPropertyRow(self.property_id, "Квартира", False)]

    async def read_money_summary(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> ReportMoneySummaryRow:
        self.calls.append(("summary", workspace_id, filters))
        return ReportMoneySummaryRow(
            filters.currency or "", Decimal("100.00"), Decimal("40.00"), Decimal("60.00")
        )

    async def list_account_balances(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> list[ReportAccountBalanceRow]:
        self.calls.append(("balances", workspace_id, filters))
        return [
            ReportAccountBalanceRow(
                account_id=self.account_id,
                name="Основной",
                currency="RUB",
                opening_balance=Decimal("1000.00"),
                closing_balance=Decimal("1060.00"),
                balance_change=Decimal("60.00"),
                is_active=True,
            )
        ]

    async def list_category_aggregates(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> list[ReportCategoryAggregateRow]:
        self.calls.append(("category_rows", workspace_id, filters))
        return [
            ReportCategoryAggregateRow(
                self.category_id,
                "Продукты",
                filters.currency or "",
                Decimal("100.00"),
                Decimal("40.00"),
                Decimal("60.00"),
                True,
            )
        ]

    async def list_property_aggregates(
        self, *, workspace_id: UUID, filters: ReportingFilters
    ) -> list[ReportPropertyAggregateRow]:
        self.calls.append(("property_rows", workspace_id, filters))
        return []

    async def find_next_review_document_id(self, workspace_id: UUID) -> UUID | None:
        self.calls.append(("review", workspace_id, None))
        return self.document_id

    async def read_uncategorized_page(
        self,
        *,
        workspace_id: UUID,
        filters: ReportingFilters,
        page: int,
        page_size: int,
    ) -> ReportUncategorizedPage:
        self.calls.append(("uncategorized", workspace_id, filters))
        return ReportUncategorizedPage(items=[], page=page, page_size=page_size, total=0)


@pytest.mark.asyncio
async def test_reporting_reader_applies_default_currency_and_constant_read_shape() -> None:
    repository = ReportingRepositoryStub()
    workspace_id = uuid4()
    reader = ReportingOverviewReader(repository)

    overview = await reader.read(
        workspace_id=workspace_id,
        default_currency="rub",
        filters=ReportingFilters(date_to=date(2026, 7, 31)),
        pagination=ReportingPagination(page=2, page_size=10),
    )

    assert overview.filters.currency == "RUB"
    assert overview.summary.currency == "RUB"
    assert overview.balance_summary == ReportBalanceSummary(
        currency="RUB",
        opening_balance=Decimal("1000.00"),
        closing_balance=Decimal("1060.00"),
        balance_change=Decimal("60.00"),
    )
    assert overview.balance_as_of == date(2026, 7, 31)
    assert sum(row.income for row in overview.categories) == overview.summary.income
    assert sum(row.expense for row in overview.categories) == overview.summary.expense
    assert sum(row.profit for row in overview.categories) == overview.summary.profit
    assert sum(row.opening_balance for row in overview.account_balances) == (
        overview.balance_summary.opening_balance
    )
    assert sum(row.closing_balance for row in overview.account_balances) == (
        overview.balance_summary.closing_balance
    )
    assert sum(row.balance_change for row in overview.account_balances) == (
        overview.balance_summary.balance_change
    )
    assert overview.filter_options.currencies == ["RUB", "USD"]
    assert overview.filter_options.accounts[1].is_active is False
    assert overview.next_review_document_id == repository.document_id
    assert [call[0] for call in repository.calls] == [
        "accounts",
        "categories",
        "properties",
        "summary",
        "balances",
        "category_rows",
        "property_rows",
        "review",
        "uncategorized",
    ]
    applied_filters = [call[2] for call in repository.calls[3:7]]
    assert all(filters == overview.filters for filters in applied_filters)
    assert overview.uncategorized.page == 2


@pytest.mark.asyncio
async def test_reporting_reader_rejects_inverted_date_range_before_reads() -> None:
    repository = ReportingRepositoryStub()

    with pytest.raises(ReportingFilterError, match="Начало периода") as error:
        await ReportingOverviewReader(repository).read(
            workspace_id=uuid4(),
            default_currency="RUB",
            filters=ReportingFilters(
                date_from=date(2026, 8, 1),
                date_to=date(2026, 7, 31),
            ),
        )

    assert error.value.code == "invalid_date_range"
    assert repository.calls == []


@pytest.mark.asyncio
async def test_reporting_reader_rejects_foreign_workspace_reference() -> None:
    repository = ReportingRepositoryStub()

    with pytest.raises(ReportingFilterError) as error:
        await ReportingOverviewReader(repository).read(
            workspace_id=uuid4(),
            default_currency="RUB",
            filters=ReportingFilters(account_id=uuid4()),
        )

    assert error.value.code == "report_filter_not_found"
    assert [call[0] for call in repository.calls] == [
        "accounts",
        "categories",
        "properties",
    ]


@pytest.mark.asyncio
async def test_reporting_reader_rejects_currency_not_owned_by_workspace_accounts() -> None:
    repository = ReportingRepositoryStub()

    with pytest.raises(ReportingFilterError) as error:
        await ReportingOverviewReader(repository).read(
            workspace_id=uuid4(),
            default_currency="RUB",
            filters=ReportingFilters(currency="EUR"),
        )

    assert error.value.code == "invalid_report_currency"


@pytest.mark.asyncio
async def test_reporting_summary_sql_is_currency_and_profit_scoped() -> None:
    session = SummarySessionCapture()
    workspace_id = uuid4()

    summary = await ReportsRepository(cast(AsyncSession, session)).read_money_summary(
        workspace_id=workspace_id,
        filters=ReportingFilters(currency="USD"),
    )

    assert summary == ReportMoneySummaryRow(
        currency="USD",
        income=Decimal("100.00"),
        expense=Decimal("40.00"),
        profit=Decimal("60.00"),
    )
    query = session.queries[0]
    sql = str(query)
    assert "money_entries.currency" in sql
    assert "operations.status" in sql
    assert "operations.affects_profit IS true" in sql
    assert workspace_id in query.compile().params.values()
    assert "USD" in query.compile().params.values()


class SummaryResult:
    def one(self) -> tuple[Decimal, Decimal]:
        return Decimal("100.00"), Decimal("40.00")


class SummarySessionCapture:
    def __init__(self) -> None:
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> SummaryResult:
        self.queries.append(query)
        return SummaryResult()


@pytest.mark.asyncio
async def test_property_aggregate_keeps_duplicate_names_as_distinct_uuid_rows() -> None:
    first_id = uuid4()
    second_id = uuid4()
    session = AggregateSessionCapture(
        [
            (
                first_id,
                "Квартира",
                PropertyStatus.ACTIVE,
                Decimal("100.00"),
                Decimal("20.00"),
            ),
            (
                second_id,
                "Квартира",
                PropertyStatus.ARCHIVED,
                Decimal("0.00"),
                Decimal("30.00"),
            ),
        ]
    )

    rows = await ReportsRepository(cast(AsyncSession, session)).list_property_aggregates(
        workspace_id=uuid4(),
        filters=ReportingFilters(currency="RUB"),
    )

    assert [row.property_id for row in rows] == [first_id, second_id]
    assert [row.name for row in rows] == ["Квартира", "Квартира"]
    assert rows[0].profit == Decimal("80.00")
    assert rows[1].profit == Decimal("-30.00")
    assert rows[1].is_active is False
    sql = str(session.queries[0])
    assert "GROUP BY properties.id" in sql
    assert "ORDER BY properties.name, properties.id" in sql
    assert "operations.affects_profit IS true" in sql


@pytest.mark.asyncio
async def test_category_aggregate_preserves_uncategorized_and_archived_identity() -> None:
    archived_id = uuid4()
    session = AggregateSessionCapture(
        [
            (None, "Без категории", True, Decimal("0.00"), Decimal("15.00")),
            (
                archived_id,
                "Старый раздел",
                False,
                Decimal("40.00"),
                Decimal("0.00"),
            ),
        ]
    )

    rows = await ReportsRepository(cast(AsyncSession, session)).list_category_aggregates(
        workspace_id=uuid4(),
        filters=ReportingFilters(currency="RUB"),
    )

    assert rows[0].category_id is None
    assert rows[0].name == "Без категории"
    assert rows[0].profit == Decimal("-15.00")
    assert rows[1].category_id == archived_id
    assert rows[1].is_active is False
    sql = str(session.queries[0])
    assert "categories.system_key" in sql
    assert "ORDER BY" in sql
    assert "categories.id" in sql


class AggregateResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[Any, ...]]:
        return self.rows


class AggregateSessionCapture:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> AggregateResult:
        self.queries.append(query)
        return AggregateResult(self.rows)


@pytest.mark.asyncio
async def test_account_balances_use_period_boundaries_currency_and_relevant_accounts() -> None:
    workspace_id = uuid4()
    active_account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной",
        currency="RUB",
        initial_balance=Decimal("100.00"),
        is_active=True,
    )
    inactive_empty_account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Пустой архивный",
        currency="RUB",
        initial_balance=Decimal("0.00"),
        is_active=False,
    )
    session = AggregateSessionCapture(
        [
            (active_account, Decimal("25.00"), Decimal("60.00")),
            (inactive_empty_account, Decimal("0.00"), Decimal("0.00")),
        ]
    )

    rows = await ReportsRepository(cast(AsyncSession, session)).list_account_balances(
        workspace_id=workspace_id,
        filters=ReportingFilters(
            date_from=date(2026, 7, 1),
            date_to=date(2026, 7, 31),
            currency="RUB",
        ),
    )

    assert rows == [
        ReportAccountBalanceRow(
            account_id=active_account.id,
            name="Основной",
            currency="RUB",
            opening_balance=Decimal("125.00"),
            closing_balance=Decimal("160.00"),
            balance_change=Decimal("35.00"),
            is_active=True,
        )
    ]
    query = session.queries[0]
    sql = str(query)
    assert "operations.operation_date <" in sql
    assert "operations.operation_date <=" in sql
    assert "accounts.currency" in sql
    assert workspace_id in query.compile().params.values()
    assert "RUB" in query.compile().params.values()


@pytest.mark.asyncio
async def test_uncategorized_page_is_bounded_stable_and_normalizes_last_page() -> None:
    first_id = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
    second_id = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
    account_id = uuid4()
    session = UncategorizedSessionCapture(
        total=31,
        rows=[
            (
                first_id,
                2,
                date(2026, 7, 31),
                OperationType.EXPENSE,
                "Кофе",
                OperationSource.MANUAL,
                Decimal("-250.00"),
                str(account_id),
            ),
            (
                second_id,
                1,
                date(2026, 7, 31),
                OperationType.INCOME,
                None,
                OperationSource.BANK_PDF,
                Decimal("1000.00"),
                str(account_id),
            ),
        ],
    )
    workspace_id = uuid4()
    property_id = uuid4()

    page = await ReportsRepository(cast(AsyncSession, session)).read_uncategorized_page(
        workspace_id=workspace_id,
        filters=ReportingFilters(currency="RUB", property_id=property_id),
        page=99,
        page_size=10,
    )

    assert page.page == 4
    assert page.total_pages == 4
    assert page.has_previous is True
    assert page.has_next is False
    assert [item.operation_id for item in page.items] == [first_id, second_id]
    assert page.items[1].description == "Без описания"
    assert page.items[0].account_id == account_id
    assert len(session.queries) == 2
    count_sql = str(session.queries[0])
    page_sql = str(session.queries[1])
    assert "count(distinct(operations.id))" in count_sql
    assert "categories.system_key" in count_sql
    assert "operations.status" in count_sql
    assert "operations.affects_profit IS true" in count_sql
    assert "operations.property_id" in count_sql
    assert "ORDER BY operations.operation_date DESC, operations.id DESC" in page_sql
    compiled = session.queries[1].compile()
    assert workspace_id in compiled.params.values()
    assert property_id in compiled.params.values()
    assert "RUB" in compiled.params.values()
    assert 10 in compiled.params.values()
    assert 30 in compiled.params.values()


class ScalarResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class UncategorizedSessionCapture:
    def __init__(self, *, total: int, rows: list[tuple[Any, ...]]) -> None:
        self.total = total
        self.rows = rows
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> ScalarResult | AggregateResult:
        self.queries.append(query)
        if len(self.queries) == 1:
            return ScalarResult(self.total)
        return AggregateResult(self.rows)
