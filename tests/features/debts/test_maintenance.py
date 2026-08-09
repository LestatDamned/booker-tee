from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.debts.domain import DebtKind, DebtValidationError
from app.features.debts.errors import (
    DebtDeleteBlockedError,
    DebtMaintenanceConflictError,
)
from app.features.debts.maintenance import DebtDeleter, DebtDetailsEditor
from app.features.debts.models import Debt
from app.features.debts.schemas import DeleteDebtCommand, UpdateDebtCommand
from app.features.ledger.domain.types import OperationSource, OperationType
from app.features.ledger.models import Operation
from app.features.users.models import User
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext

NOW = datetime(2026, 8, 9, 8, 30, tzinfo=UTC)


class SessionStub:
    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> None:
        self.flushes += 1


class AccountRepositoryStub:
    def __init__(self, account: Account, *, has_history: bool = False) -> None:
        self.account = account
        self.has_history = has_history
        self.deleted = False

    async def get_for_workspace(self, workspace_id: UUID, account_id: UUID) -> Account | None:
        if self.account.workspace_id == workspace_id and self.account.id == account_id:
            return self.account
        return None

    async def has_import_history(self, workspace_id: UUID, account_id: UUID) -> bool:
        return self.has_history

    async def delete(self, account: Account) -> None:
        self.deleted = True


class DebtRepositoryStub:
    def __init__(
        self,
        debt: Debt,
        *,
        has_payments: bool = False,
        operations: list[Operation] | None = None,
    ) -> None:
        self.debt = debt
        self.payments = has_payments
        self.operations = operations or []

    async def get_for_workspace_for_update(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> Debt | None:
        if self.debt.workspace_id == workspace_id and self.debt.account_id == account_id:
            return self.debt
        return None

    async def has_payments(self, workspace_id: UUID, debt_account_id: UUID) -> bool:
        return self.payments

    async def list_account_operations(
        self,
        workspace_id: UUID,
        debt_account_id: UUID,
    ) -> list[Operation]:
        return self.operations


class LedgerRepositoryStub:
    def __init__(self, total: Decimal = Decimal("0.00")) -> None:
        self.total = total
        self.deleted: list[Operation] = []

    async def get_confirmed_account_entries_total(self, **_: Any) -> Decimal:
        return self.total

    async def delete_operation(self, operation: Operation) -> None:
        self.deleted.append(operation)


@pytest.mark.asyncio
async def test_editor_updates_only_safe_debt_details() -> None:
    context, debt, account = debt_fixture()
    editor = DebtDetailsEditor(cast(Any, SessionStub()))
    editor.accounts = cast(Any, AccountRepositoryStub(account))
    editor.debts = cast(Any, DebtRepositoryStub(debt))
    editor.ledger = cast(Any, LedgerRepositoryStub())

    updated = await editor.update(
        context=context,
        command=UpdateDebtCommand(
            debt_account_id=account.id,
            name="  Кредит   на ремонт ",
            opened_on=date(2026, 1, 2),
            maturity_date=date(2028, 1, 2),
            credit_limit=None,
            notes="  Уточнено  ",
            expected_updated_at=NOW,
        ),
    )

    assert updated is debt
    assert account.name == "Кредит на ремонт"
    assert account.notes == "Уточнено"
    assert account.currency == "RUB"
    assert account.initial_balance == Decimal("-100.00")
    assert debt.kind is DebtKind.LOAN_PAYABLE
    assert debt.original_principal == Decimal("100.00")
    assert debt.updated_at != NOW


@pytest.mark.asyncio
async def test_editor_validates_terms_and_snapshot_against_current_debt() -> None:
    context, debt, account = debt_fixture(kind=DebtKind.CREDIT_CARD)
    editor = DebtDetailsEditor(cast(Any, SessionStub()))
    editor.accounts = cast(Any, AccountRepositoryStub(account))
    editor.debts = cast(Any, DebtRepositoryStub(debt))
    editor.ledger = cast(Any, LedgerRepositoryStub())
    command = UpdateDebtCommand(
        debt_account_id=account.id,
        name="Кредитка",
        opened_on=None,
        maturity_date=None,
        credit_limit=Decimal("50.00"),
        notes=None,
        expected_updated_at=NOW,
    )

    with pytest.raises(DebtValidationError, match="credit limit"):
        await editor.update(context=context, command=command)
    with pytest.raises(DebtMaintenanceConflictError):
        await editor.update(
            context=context,
            command=command.model_copy(
                update={
                    "credit_limit": Decimal("200.00"),
                    "expected_updated_at": datetime(2026, 8, 8, tzinfo=UTC),
                }
            ),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(("has_history", "has_payments"), [(True, False), (False, True)])
async def test_deleter_blocks_every_kind_of_financial_history(
    has_history: bool,
    has_payments: bool,
) -> None:
    context, debt, account = debt_fixture()
    accounts = AccountRepositoryStub(account, has_history=has_history)
    deleter = DebtDeleter(cast(Any, SessionStub()))
    deleter.accounts = cast(Any, accounts)
    deleter.debts = cast(Any, DebtRepositoryStub(debt, has_payments=has_payments))
    deleter.ledger = cast(Any, LedgerRepositoryStub())

    with pytest.raises(DebtDeleteBlockedError):
        await deleter.delete(
            context=context,
            command=DeleteDebtCommand(
                debt_account_id=account.id,
                expected_updated_at=NOW,
            ),
        )

    assert accounts.deleted is False


@pytest.mark.asyncio
async def test_deleter_removes_unused_debt_even_with_opening_balance() -> None:
    context, debt, account = debt_fixture()
    accounts = AccountRepositoryStub(account)
    deleter = DebtDeleter(cast(Any, SessionStub()))
    deleter.accounts = cast(Any, accounts)
    deleter.debts = cast(Any, DebtRepositoryStub(debt))
    deleter.ledger = cast(Any, LedgerRepositoryStub())

    deleted = await deleter.delete(
        context=context,
        command=DeleteDebtCommand(
            debt_account_id=account.id,
            expected_updated_at=NOW,
        ),
    )

    assert deleted.account_id == account.id
    assert deleted.name == account.name
    assert accounts.deleted is True


@pytest.mark.asyncio
async def test_deleter_removes_the_single_opening_transfer_with_the_debt() -> None:
    context, debt, account = debt_fixture()
    opening_transfer = Operation(
        id=uuid4(),
        workspace_id=context.workspace.id,
        type=OperationType.TRANSFER,
        source=OperationSource.DEBT,
    )
    accounts = AccountRepositoryStub(account)
    ledger = LedgerRepositoryStub()
    deleter = DebtDeleter(cast(Any, SessionStub()))
    deleter.accounts = cast(Any, accounts)
    deleter.debts = cast(
        Any,
        DebtRepositoryStub(debt, operations=[opening_transfer]),
    )
    deleter.ledger = cast(Any, ledger)

    await deleter.delete(
        context=context,
        command=DeleteDebtCommand(
            debt_account_id=account.id,
            expected_updated_at=NOW,
        ),
    )

    assert ledger.deleted == [opening_transfer]
    assert accounts.deleted is True


@pytest.mark.asyncio
async def test_deleter_keeps_debt_with_non_creation_operation() -> None:
    context, debt, account = debt_fixture(kind=DebtKind.CREDIT_CARD)
    expense = Operation(
        id=uuid4(),
        workspace_id=context.workspace.id,
        type=OperationType.EXPENSE,
        source=OperationSource.MANUAL,
    )
    accounts = AccountRepositoryStub(account)
    deleter = DebtDeleter(cast(Any, SessionStub()))
    deleter.accounts = cast(Any, accounts)
    deleter.debts = cast(Any, DebtRepositoryStub(debt, operations=[expense]))
    deleter.ledger = cast(Any, LedgerRepositoryStub())

    with pytest.raises(DebtDeleteBlockedError):
        await deleter.delete(
            context=context,
            command=DeleteDebtCommand(
                debt_account_id=account.id,
                expected_updated_at=NOW,
            ),
        )

    assert accounts.deleted is False


def debt_fixture(
    *,
    kind: DebtKind = DebtKind.LOAN_PAYABLE,
) -> tuple[WorkspaceContext, Debt, Account]:
    user = User(id=uuid4(), email="maintenance@example.test", password_hash="hash")
    workspace = Workspace(id=uuid4(), owner_id=user.id, name="Личный", default_currency="RUB")
    context = WorkspaceContext(
        user=user,
        workspace=workspace,
        membership=WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=user.id),
    )
    account = Account(
        id=uuid4(),
        workspace_id=workspace.id,
        name="Кредит",
        type=AccountType.DEBT,
        currency="RUB",
        initial_balance=Decimal("-100.00"),
        is_active=True,
    )
    debt = Debt(
        account_id=account.id,
        workspace_id=workspace.id,
        kind=kind,
        original_principal=(None if kind is DebtKind.CREDIT_CARD else Decimal("100.00")),
        credit_limit=(Decimal("200.00") if kind is DebtKind.CREDIT_CARD else None),
        creation_idempotency_key=uuid4(),
        creation_fingerprint="a" * 64,
        updated_at=NOW,
    )
    return context, debt, account
