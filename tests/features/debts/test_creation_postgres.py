import os
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
from app.features.debts.domain import DebtKind
from app.features.debts.errors import DebtIdempotencyConflictError
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.repository import DebtRepository
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    DeleteDebtCommand,
    GiveLoanCommand,
    RecordDebtPaymentCommand,
    UndoDebtPaymentCommand,
)
from app.features.debts.service import DebtService
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import MoneyEntry, Operation
from app.features.users.models import User
from app.features.workspaces.domain.types import WorkspaceRole, WorkspaceType
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL debt creation tests.",
)


async def test_postgres_deletes_unused_debt_and_its_opening_transfer(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    context, funding_account = await seed_context(sessions)

    async with sessions() as session:
        service = DebtService(session)
        unused = await service.add_existing_debt(
            context=context,
            command=AddExistingDebtCommand(
                name="Mistaken debt",
                kind=DebtKind.LOAN_PAYABLE,
                currency="RUB",
                opening_balance=Decimal("100.00"),
                original_principal=Decimal("100.00"),
                opened_on=None,
                maturity_date=None,
                notes=None,
                idempotency_key=uuid4(),
            ),
        )
        await service.delete(
            context=context,
            command=DeleteDebtCommand(
                debt_account_id=unused.account_id,
                expected_updated_at=unused.updated_at,
            ),
        )
        assert await session.get(Account, unused.account_id) is None
        assert (
            await session.scalar(
                select(func.count(Debt.account_id)).where(Debt.account_id == unused.account_id)
            )
            == 0
        )

        transferred = await service.give_loan(
            context=context,
            command=GiveLoanCommand(
                name="Used debt",
                currency="RUB",
                amount=Decimal("100.00"),
                funding_account_id=funding_account.id,
                operation_date=date(2026, 8, 9),
                opened_on=None,
                maturity_date=None,
                description=None,
                notes=None,
                idempotency_key=uuid4(),
            ),
        )
        read_row = await DebtRepository(session).get_read_row(
            context.workspace.id,
            transferred.account_id,
        )
        assert read_row is not None
        assert read_row.has_delete_blockers is False
        await service.delete(
            context=context,
            command=DeleteDebtCommand(
                debt_account_id=transferred.account_id,
                expected_updated_at=transferred.updated_at,
            ),
        )
        assert (
            await session.scalar(
                select(func.count(Operation.id)).where(
                    Operation.workspace_id == context.workspace.id,
                    Operation.source == OperationSource.DEBT,
                )
            )
            == 0
        )
        assert (
            await session.scalar(
                select(func.count(MoneyEntry.id)).where(
                    MoneyEntry.workspace_id == context.workspace.id,
                    MoneyEntry.account_id == funding_account.id,
                )
            )
            == 0
        )


async def test_postgres_give_loan_is_balanced_atomic_and_idempotent(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    context, funding_account = await seed_context(sessions)
    command = GiveLoanCommand(
        name="Postgres loan",
        currency="RUB",
        amount=Decimal("100.00"),
        funding_account_id=funding_account.id,
        operation_date=date(2026, 8, 9),
        opened_on=date(2026, 8, 9),
        maturity_date=date(2027, 8, 9),
        description="Loan transfer",
        notes=None,
        idempotency_key=uuid4(),
    )

    async with sessions() as session:
        service = DebtService(session)
        created = await service.give_loan(context=context, command=command)
        replay = await service.give_loan(context=context, command=command)
        assert replay.account_id == created.account_id

        with pytest.raises(DebtIdempotencyConflictError):
            await service.give_loan(
                context=context,
                command=command.model_copy(update={"amount": Decimal("101.00")}),
            )

    async with sessions() as session:
        debt_count = await session.scalar(
            select(func.count(Debt.account_id)).where(Debt.workspace_id == context.workspace.id)
        )
        operations = list(
            (
                await session.scalars(
                    select(Operation).where(
                        Operation.workspace_id == context.workspace.id,
                        Operation.source == OperationSource.DEBT,
                    )
                )
            ).all()
        )
        entries = list(
            (
                await session.scalars(
                    select(MoneyEntry).where(
                        MoneyEntry.workspace_id == context.workspace.id,
                        MoneyEntry.operation_id == operations[0].id,
                    )
                )
            ).all()
        )

    assert debt_count == 1
    assert len(operations) == 1
    assert operations[0].affects_profit is False
    assert [entry.amount for entry in sorted(entries, key=lambda entry: entry.entry_order)] == [
        Decimal("-100.00"),
        Decimal("100.00"),
    ]
    assert sum((entry.amount for entry in entries), start=Decimal("0.00")) == Decimal("0.00")


async def test_postgres_creation_failure_rolls_back_the_debt_account(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    context, _ = await seed_context(sessions)
    failed_name = f"Failed debt {uuid4()}"

    async with sessions() as session:
        service = DebtService(session)

        async def fail_after_account(_: Debt) -> Debt:
            raise RuntimeError("forced debt failure")

        debt_repository: Any = service.creator.debts
        debt_repository.create = fail_after_account
        with pytest.raises(RuntimeError, match="forced debt failure"):
            await service.add_existing_debt(
                context=context,
                command=AddExistingDebtCommand(
                    name=failed_name,
                    kind=DebtKind.LOAN_PAYABLE,
                    currency="RUB",
                    opening_balance=Decimal("100.00"),
                    original_principal=Decimal("100.00"),
                    opened_on=None,
                    maturity_date=None,
                    notes=None,
                    idempotency_key=uuid4(),
                ),
            )

    async with sessions() as session:
        account_count = await session.scalar(
            select(func.count(Account.id)).where(
                Account.workspace_id == context.workspace.id,
                Account.name == failed_name,
            )
        )
    assert account_count == 0


async def test_postgres_payment_retry_and_undo_keep_ledger_consistent(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    context, settlement_account = await seed_context(sessions)
    category = Category(
        id=uuid4(),
        workspace_id=context.workspace.id,
        name="Debt interest",
        kind=CategoryKind.EXPENSE,
    )
    async with sessions() as session:
        session.add(category)
        await session.commit()

    async with sessions() as session:
        service = DebtService(session)
        debt = await service.add_existing_debt(
            context=context,
            command=AddExistingDebtCommand(
                name="Payable loan",
                kind=DebtKind.LOAN_PAYABLE,
                currency="RUB",
                opening_balance=Decimal("100.00"),
                original_principal=Decimal("100.00"),
                opened_on=date(2026, 8, 9),
                maturity_date=None,
                notes=None,
                idempotency_key=uuid4(),
            ),
        )
        command = RecordDebtPaymentCommand(
            debt_account_id=debt.account_id,
            settlement_account_id=settlement_account.id,
            principal_amount=Decimal("25.00"),
            interest_amount=Decimal("10.00"),
            operation_date=date(2026, 8, 9),
            interest_category_id=category.id,
            description="Monthly payment",
            notes=None,
            idempotency_key=uuid4(),
        )
        payment = await service.record_payment(context=context, command=command)
        replay = await service.record_payment(context=context, command=command)
        assert replay.id == payment.id

    async with sessions() as session:
        payment = await session.get(DebtPayment, payment.id)
        assert payment is not None
        operations = list(
            (
                await session.scalars(
                    select(Operation).where(
                        Operation.id.in_(
                            [
                                payment.principal_operation_id,
                                payment.interest_operation_id,
                            ]
                        )
                    )
                )
            ).all()
        )
        principal = next(item for item in operations if item.type is OperationType.TRANSFER)
        interest = next(item for item in operations if item.type is OperationType.EXPENSE)
        debt_entries_total = await session.scalar(
            select(func.sum(MoneyEntry.amount)).where(
                MoneyEntry.workspace_id == context.workspace.id,
                MoneyEntry.account_id == payment.debt_account_id,
            )
        )
        settlement_entries_total = await session.scalar(
            select(func.sum(MoneyEntry.amount)).where(
                MoneyEntry.workspace_id == context.workspace.id,
                MoneyEntry.account_id == settlement_account.id,
            )
        )
        payment_count = await session.scalar(
            select(func.count(DebtPayment.id)).where(
                DebtPayment.workspace_id == context.workspace.id
            )
        )

        assert debt_entries_total == Decimal("25.00")
        assert settlement_entries_total == Decimal("-35.00")
        assert payment_count == 1
        assert principal.affects_profit is False
        assert interest.affects_profit is True

        undo = UndoDebtPaymentCommand(
            payment_id=payment.id,
            expected_principal_operation_version=principal.version,
            expected_interest_operation_version=interest.version,
        )

    async with sessions() as session:
        service = DebtService(session)
        reversed_payment = await service.undo_payment(context=context, command=undo)
        replay = await service.undo_payment(context=context, command=undo)
        assert replay.id == reversed_payment.id

    async with sessions() as session:
        payment = await session.get(DebtPayment, payment.id)
        assert payment is not None
        statuses = list(
            (
                await session.scalars(
                    select(Operation.status).where(
                        Operation.id.in_(
                            [
                                payment.principal_operation_id,
                                payment.interest_operation_id,
                            ]
                        )
                    )
                )
            ).all()
        )
        confirmed_debt_total = await session.scalar(
            select(func.coalesce(func.sum(MoneyEntry.amount), Decimal("0.00")))
            .join(Operation)
            .where(
                MoneyEntry.workspace_id == context.workspace.id,
                MoneyEntry.account_id == payment.debt_account_id,
                Operation.status == OperationStatus.CONFIRMED,
            )
        )

        assert payment.reversed_at is not None
        assert len(statuses) == 2
        assert set(statuses) == {OperationStatus.IGNORED}
        assert confirmed_debt_total == Decimal("0.00")


async def test_postgres_payment_failure_rolls_back_principal_operation(
    postgres_rollback_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_rollback_sessions
    context, settlement_account = await seed_context(sessions)
    category = Category(
        id=uuid4(),
        workspace_id=context.workspace.id,
        name="Failed debt interest",
        kind=CategoryKind.EXPENSE,
    )
    async with sessions() as session:
        session.add(category)
        await session.commit()

    async with sessions() as session:
        service = DebtService(session)
        debt = await service.add_existing_debt(
            context=context,
            command=AddExistingDebtCommand(
                name="Rollback loan",
                kind=DebtKind.LOAN_PAYABLE,
                currency="RUB",
                opening_balance=Decimal("100.00"),
                original_principal=Decimal("100.00"),
                opened_on=None,
                maturity_date=None,
                notes=None,
                idempotency_key=uuid4(),
            ),
        )

        async def fail_interest(**_: Any) -> Operation:
            raise RuntimeError("forced interest failure")

        posting: Any = service.payment_recorder.posting
        posting.post_debt_interest = fail_interest
        with pytest.raises(RuntimeError, match="forced interest failure"):
            await service.record_payment(
                context=context,
                command=RecordDebtPaymentCommand(
                    debt_account_id=debt.account_id,
                    settlement_account_id=settlement_account.id,
                    principal_amount=Decimal("25.00"),
                    interest_amount=Decimal("10.00"),
                    operation_date=date(2026, 8, 9),
                    interest_category_id=category.id,
                    description=None,
                    notes=None,
                    idempotency_key=uuid4(),
                ),
            )

    async with sessions() as session:
        operation_count = await session.scalar(
            select(func.count(Operation.id)).where(
                Operation.workspace_id == context.workspace.id,
                Operation.source == OperationSource.DEBT,
            )
        )
        payment_count = await session.scalar(
            select(func.count(DebtPayment.id)).where(
                DebtPayment.workspace_id == context.workspace.id
            )
        )
        assert operation_count == 0
        assert payment_count == 0


async def seed_context(
    sessions: async_sessionmaker,
) -> tuple[WorkspaceContext, Account]:
    user = User(id=uuid4(), email=f"debts-{uuid4()}@example.test", password_hash="hash")
    workspace = Workspace(
        id=uuid4(),
        owner_id=user.id,
        name="Debt creation test",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    membership = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
    )
    account = Account(
        id=uuid4(),
        workspace_id=workspace.id,
        name="Funding",
        type=AccountType.CARD,
        currency="RUB",
        initial_balance=Decimal("1000.00"),
    )
    async with sessions() as session:
        session.add_all([user, workspace, membership, account])
        await session.commit()
    return WorkspaceContext(user=user, workspace=workspace, membership=membership), account
