from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.properties.models import PropertyStatus
from app.features.reports.application.overview import (
    ReportingFilterError,
    ReportingFilters,
    ReportingOverviewReader,
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
            ReportAccountBalanceRow(self.account_id, "Основной", "RUB", Decimal("1060.00"), True)
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
                Decimal("0.00"),
                Decimal("40.00"),
                Decimal("-40.00"),
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


@pytest.mark.asyncio
async def test_reporting_reader_applies_default_currency_and_constant_read_shape() -> None:
    repository = ReportingRepositoryStub()
    workspace_id = uuid4()
    reader = ReportingOverviewReader(repository)

    overview = await reader.read(
        workspace_id=workspace_id,
        default_currency="rub",
        filters=ReportingFilters(date_to=date(2026, 7, 31)),
    )

    assert overview.filters.currency == "RUB"
    assert overview.summary.currency == "RUB"
    assert overview.balance_as_of == date(2026, 7, 31)
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
    ]
    applied_filters = [call[2] for call in repository.calls[3:7]]
    assert all(filters == overview.filters for filters in applied_filters)


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
