from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.debts.domain import (
    DebtKind,
    DebtPaymentBlockedReason,
    DebtStatus,
)
from app.features.debts.reader import DebtReader, DebtReadSource
from app.features.debts.repository import (
    DebtOperationReadRow,
    DebtPaymentHistoryRow,
    DebtPaymentHistoryStats,
    DebtReadRow,
    DebtRepository,
)
from app.features.ledger.domain.types import OperationStatus, OperationType

NOW = datetime(2026, 8, 8, tzinfo=UTC)


class DebtReadSourceStub:
    def __init__(
        self,
        rows: list[DebtReadRow],
        history: list[DebtPaymentHistoryRow] | None = None,
        history_total: int | None = None,
        principal_total: Decimal = Decimal("0.00"),
        interest_total: Decimal = Decimal("0.00"),
    ) -> None:
        self.rows = rows
        self.history = history or []
        self.history_total = len(self.history) if history_total is None else history_total
        self.principal_total = principal_total
        self.interest_total = interest_total
        self.list_calls = 0
        self.detail_calls = 0
        self.count_calls = 0
        self.history_calls: list[tuple[int, int]] = []

    async def list_read_rows(self, workspace_id: UUID) -> list[DebtReadRow]:
        self.list_calls += 1
        return self.rows

    async def get_read_row(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> DebtReadRow | None:
        self.detail_calls += 1
        return next((row for row in self.rows if row.account_id == account_id), None)

    async def list_payment_history(
        self,
        *,
        workspace_id: UUID,
        debt_account_id: UUID,
        offset: int,
        limit: int,
    ) -> list[DebtPaymentHistoryRow]:
        self.history_calls.append((offset, limit))
        return self.history

    async def get_payment_history_stats(
        self,
        *,
        workspace_id: UUID,
        debt_account_id: UUID,
    ) -> DebtPaymentHistoryStats:
        self.count_calls += 1
        return DebtPaymentHistoryStats(
            total=self.history_total,
            principal=self.principal_total,
            interest=self.interest_total,
        )


async def test_debt_reader_builds_balances_totals_and_readonly_capabilities() -> None:
    rows = [
        debt_row(
            kind=DebtKind.LOAN_RECEIVABLE,
            currency="RUB",
            initial_balance="100.00",
            confirmed_entry_total="-20.00",
        ),
        debt_row(
            kind=DebtKind.LOAN_PAYABLE,
            currency="RUB",
            initial_balance="-50.00",
            confirmed_entry_total="10.00",
        ),
        debt_row(
            kind=DebtKind.MORTGAGE,
            currency="USD",
            initial_balance="-10.00",
            confirmed_entry_total="0.00",
            is_active=False,
        ),
    ]
    source = DebtReadSourceStub(rows)

    portfolio = await DebtReader(cast(DebtReadSource, source)).list(
        workspace_id=uuid4(),
        can_write=False,
    )

    assert [item.balance for item in portfolio.items] == [
        Decimal("80.00"),
        Decimal("-40.00"),
        Decimal("-10.00"),
    ]
    assert portfolio.items[2].status is DebtStatus.ARCHIVED
    assert all(not item.capabilities.can_record_payment for item in portfolio.items)
    assert all(
        item.capabilities.payment_blocked_reason
        is DebtPaymentBlockedReason.FINANCIAL_WRITE_FORBIDDEN
        for item in portfolio.items
    )
    assert [total.model_dump() for total in portfolio.totals] == [
        {
            "currency": "RUB",
            "receivable": Decimal("80.00"),
            "payable": Decimal("40.00"),
            "net_position": Decimal("40.00"),
        },
        {
            "currency": "USD",
            "receivable": Decimal("0.00"),
            "payable": Decimal("10.00"),
            "net_position": Decimal("-10.00"),
        },
    ]
    assert source.list_calls == 1


async def test_debt_reader_builds_detail_and_bounded_payment_history() -> None:
    row = debt_row(
        kind=DebtKind.CREDIT_CARD,
        initial_balance="-500.00",
        confirmed_entry_total="-250.00",
        credit_limit="1000.00",
        has_payment_account=True,
    )
    principal_id = uuid4()
    interest_id = uuid4()
    history = [
        DebtPaymentHistoryRow(
            payment_id=uuid4(),
            principal=operation_row(principal_id, OperationType.TRANSFER, "200.00"),
            interest=operation_row(interest_id, OperationType.EXPENSE, "30.00"),
            notes="Ежемесячный платёж",
            created_at=NOW,
            reversed_at=None,
        )
    ]
    source = DebtReadSourceStub(
        [row],
        history,
        history_total=21,
        principal_total=Decimal("200.00"),
        interest_total=Decimal("30.00"),
    )

    detail = await DebtReader(cast(DebtReadSource, source)).get_detail(
        workspace_id=uuid4(),
        account_id=row.account_id,
        can_write=True,
        payments_page=1,
        payments_page_size=20,
    )

    assert detail is not None
    assert detail.debt.balance == Decimal("-750.00")
    assert detail.debt.outstanding == Decimal("750.00")
    assert detail.debt.available_credit == Decimal("250.00")
    assert detail.debt.capabilities.can_record_payment is True
    assert detail.payment_totals.principal == Decimal("200.00")
    assert detail.payment_totals.interest == Decimal("30.00")
    assert detail.payments.total == 21
    assert detail.payments.total_pages == 2
    assert detail.payments.has_next is True
    assert detail.payments.items[0].principal is not None
    assert detail.payments.items[0].principal.operation_id == principal_id
    assert detail.payments.items[0].interest is not None
    assert detail.payments.items[0].interest.operation_id == interest_id
    assert detail.payments.items[0].can_undo is True
    assert source.detail_calls == 1
    assert source.count_calls == 1
    assert source.history_calls == [(0, 20)]


async def test_debt_reader_hides_undo_capability_from_readonly_member() -> None:
    row = debt_row(
        kind=DebtKind.LOAN_PAYABLE,
        initial_balance="-100.00",
        confirmed_entry_total="0.00",
    )
    source = DebtReadSourceStub(
        [row],
        [
            DebtPaymentHistoryRow(
                payment_id=uuid4(),
                principal=operation_row(uuid4(), OperationType.TRANSFER, "10.00"),
                interest=None,
                notes=None,
                created_at=NOW,
                reversed_at=None,
            )
        ],
    )

    detail = await DebtReader(cast(DebtReadSource, source)).get_detail(
        workspace_id=uuid4(),
        account_id=row.account_id,
        can_write=False,
    )

    assert detail is not None
    assert detail.payments.items[0].can_undo is False


async def test_debt_reader_keeps_total_on_an_empty_out_of_range_page() -> None:
    row = debt_row(
        kind=DebtKind.LOAN_PAYABLE,
        initial_balance="-100.00",
        confirmed_entry_total="0.00",
    )
    source = DebtReadSourceStub([row], history_total=21)

    detail = await DebtReader(cast(DebtReadSource, source)).get_detail(
        workspace_id=uuid4(),
        account_id=row.account_id,
        can_write=True,
        payments_page=3,
        payments_page_size=10,
    )

    assert detail is not None
    assert detail.payments.items == []
    assert detail.payments.total == 21
    assert detail.payments.total_pages == 3
    assert detail.payments.has_previous is True
    assert detail.payments.has_next is False


async def test_debt_reader_returns_none_without_querying_foreign_history() -> None:
    source = DebtReadSourceStub([])

    detail = await DebtReader(cast(DebtReadSource, source)).get_detail(
        workspace_id=uuid4(),
        account_id=uuid4(),
        can_write=True,
    )

    assert detail is None
    assert source.count_calls == 0
    assert source.history_calls == []


class EmptyQueryResult:
    def all(self) -> list[Any]:
        return []

    def one_or_none(self) -> None:
        return None

    def one(self) -> tuple[int, Decimal, Decimal]:
        return 0, Decimal("0.00"), Decimal("0.00")


class QuerySession:
    def __init__(self) -> None:
        self.queries: list[Any] = []

    async def execute(self, query: Any) -> EmptyQueryResult:
        self.queries.append(query)
        return EmptyQueryResult()


async def test_debt_read_queries_are_workspace_scoped_and_confirmed_only() -> None:
    workspace_id = uuid4()
    session = QuerySession()
    repository = DebtRepository(cast(AsyncSession, session))

    await repository.list_read_rows(workspace_id)
    await repository.get_read_row(workspace_id, uuid4())
    await repository.list_payment_history(
        workspace_id=workspace_id,
        debt_account_id=uuid4(),
        offset=0,
        limit=20,
    )
    await repository.get_payment_history_stats(
        workspace_id=workspace_id,
        debt_account_id=uuid4(),
    )

    assert len(session.queries) == 4
    for query in session.queries:
        compiled = query.compile()
        assert "workspace_id" in str(compiled)
        assert workspace_id in compiled.params.values()
    assert OperationStatus.CONFIRMED in session.queries[0].compile().params.values()
    assert OperationStatus.CONFIRMED in session.queries[3].compile().params.values()


def debt_row(
    *,
    kind: DebtKind,
    currency: str = "RUB",
    initial_balance: str,
    confirmed_entry_total: str,
    is_active: bool = True,
    credit_limit: str | None = None,
    has_payment_account: bool = False,
    has_delete_blockers: bool = False,
) -> DebtReadRow:
    return DebtReadRow(
        account_id=uuid4(),
        name="Долг",
        kind=kind,
        currency=currency,
        initial_balance=Decimal(initial_balance),
        confirmed_entry_total=Decimal(confirmed_entry_total),
        is_active=is_active,
        opened_on=date(2026, 1, 1),
        original_principal=(
            None if kind is DebtKind.CREDIT_CARD else abs(Decimal(initial_balance))
        ),
        maturity_date=None,
        credit_limit=Decimal(credit_limit) if credit_limit is not None else None,
        notes="Заметка",
        updated_at=NOW,
        has_payment_account=has_payment_account,
        has_delete_blockers=has_delete_blockers,
    )


def operation_row(
    operation_id: UUID,
    operation_type: OperationType,
    amount: str,
) -> DebtOperationReadRow:
    return DebtOperationReadRow(
        operation_id=operation_id,
        version=1,
        operation_date=date(2026, 8, 8),
        operation_type=operation_type,
        status=OperationStatus.CONFIRMED,
        description="Платёж",
        amount=Decimal(amount),
    )
