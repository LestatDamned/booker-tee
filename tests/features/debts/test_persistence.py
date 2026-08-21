from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Numeric, Table
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import AccountType
from app.features.debts.domain import DebtKind
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.repository import DebtRepository
from app.features.ledger.domain.types import OperationSource


class QueryResult:
    def __init__(self, row: Debt | DebtPayment | None = None) -> None:
        self.row = row

    def scalar_one_or_none(self) -> Debt | DebtPayment | None:
        return self.row


class SessionCapture:
    def __init__(self) -> None:
        self.queries: list[Any] = []
        self.added: list[Debt | DebtPayment] = []
        self.flush_count = 0

    async def execute(self, query: Any) -> QueryResult:
        self.queries.append(query)
        return QueryResult()

    def add(self, record: Debt | DebtPayment) -> None:
        self.added.append(record)

    async def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.parametrize(
    "method_name",
    [
        "get_for_workspace",
        "get_for_workspace_for_update",
        "get_by_creation_idempotency_key",
        "get_payment_for_workspace",
        "get_payment_for_workspace_for_update",
        "get_payment_by_idempotency_key",
    ],
)
async def test_debt_repository_lookup_is_workspace_scoped(method_name: str) -> None:
    workspace_id = uuid4()
    session = SessionCapture()
    repository = DebtRepository(cast(AsyncSession, session))

    await getattr(repository, method_name)(workspace_id, uuid4())

    assert len(session.queries) == 1
    compiled = session.queries[0].compile()
    assert "workspace_id" in str(compiled)
    assert workspace_id in compiled.params.values()


async def test_debt_repository_create_adds_and_flushes_debt() -> None:
    workspace_id = uuid4()
    account_id = uuid4()
    debt = debt_record(workspace_id=workspace_id, account_id=account_id)
    session = SessionCapture()
    repository = DebtRepository(cast(AsyncSession, session))

    assert await repository.create(debt) is debt

    assert session.added == [debt]
    assert session.flush_count == 1


async def test_debt_repository_create_payment_adds_and_flushes_payment() -> None:
    workspace_id = uuid4()
    account_id = uuid4()
    payment = DebtPayment(
        id=uuid4(),
        workspace_id=workspace_id,
        debt_account_id=account_id,
        principal_operation_id=uuid4(),
        interest_operation_id=None,
        idempotency_key=uuid4(),
        idempotency_fingerprint="b" * 64,
    )
    session = SessionCapture()
    repository = DebtRepository(cast(AsyncSession, session))

    assert await repository.create_payment(payment) is payment

    assert session.added == [payment]
    assert session.flush_count == 1


def test_debt_models_keep_money_as_decimal_and_register_constraints() -> None:
    debt = debt_record(workspace_id=uuid4(), account_id=uuid4())
    debt_table = cast(Table, Debt.__table__)
    payment_table = cast(Table, DebtPayment.__table__)

    assert isinstance(debt.original_principal, Decimal)
    assert cast(Numeric, debt_table.c.original_principal.type).scale == 2
    assert cast(Numeric, debt_table.c.credit_limit.type).scale == 2
    assert {
        "ck_debts_original_principal_positive",
        "ck_debts_credit_limit_positive",
        "ck_debts_valid_dates",
        "ck_debts_valid_terms_for_kind",
        "uq_debts_workspace_creation_idempotency",
    } <= {constraint.name for constraint in debt_table.constraints}
    assert {
        "ck_debt_payments_has_operation",
        "ck_debt_payments_distinct_operations",
        "uq_debt_payments_workspace_idempotency",
    } <= {constraint.name for constraint in payment_table.constraints}


def test_debt_foreign_keys_protect_parent_records() -> None:
    targets = {
        foreign_key.target_fullname
        for table in (Debt.__table__, DebtPayment.__table__)
        for column in table.columns
        for foreign_key in column.foreign_keys
    }

    assert {
        "accounts.id",
        "workspaces.id",
        "debts.account_id",
        "operations.id",
    } <= targets


def test_debt_enum_values_do_not_become_user_managed_account_types() -> None:
    assert AccountType.DEBT not in AccountType.user_managed()
    assert AccountType.DEBT.is_user_managed() is False
    assert OperationSource.DEBT.value == "debt"


def debt_record(*, workspace_id: UUID, account_id: UUID) -> Debt:
    return Debt(
        account_id=account_id,
        workspace_id=workspace_id,
        kind=DebtKind.MORTGAGE,
        opened_on=date(2025, 1, 1),
        original_principal=Decimal("5000000.00"),
        maturity_date=date(2045, 1, 1),
        credit_limit=None,
        creation_idempotency_key=uuid4(),
        creation_fingerprint="a" * 64,
    )
