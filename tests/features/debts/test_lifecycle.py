from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.debts.domain import DebtKind
from app.features.debts.errors import DebtLifecycleConflictError, DebtNotFoundError
from app.features.debts.lifecycle import DebtLifecycleManager
from app.features.debts.models import Debt
from app.features.debts.schemas import DebtLifecycleCommand
from app.features.users.models import User
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext

NOW = datetime(2026, 8, 9, 8, 30, tzinfo=UTC)


class SessionStub:
    def __init__(self) -> None:
        self.flushes = 0

    async def flush(self) -> None:
        self.flushes += 1


class DebtRepositoryStub:
    def __init__(self, debt: Debt | None) -> None:
        self.debt = debt

    async def get_for_workspace_for_update(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> Debt | None:
        if (
            self.debt is not None
            and self.debt.workspace_id == workspace_id
            and self.debt.account_id == account_id
        ):
            return self.debt
        return None


class AccountRepositoryStub:
    def __init__(self, account: Account) -> None:
        self.account = account

    async def get_for_workspace(self, workspace_id: UUID, account_id: UUID) -> Account | None:
        if self.account.workspace_id == workspace_id and self.account.id == account_id:
            return self.account
        return None


class LedgerRepositoryStub:
    def __init__(self, total: Decimal) -> None:
        self.total = total

    async def get_confirmed_account_entries_total(self, **_: Any) -> Decimal:
        return self.total


@pytest.mark.asyncio
async def test_lifecycle_archives_only_settled_debt_and_restores_it() -> None:
    context = workspace_context()
    manager, session, debt, account = lifecycle_manager(context, balance=Decimal("0.00"))

    archived = await manager.archive(
        context=context,
        command=lifecycle_command(debt, expected_active=True),
    )

    assert archived is debt
    assert account.is_active is False
    assert account.archived_at is not None
    assert debt.updated_at != NOW

    restored = await manager.restore(
        context=context,
        command=DebtLifecycleCommand(
            debt_account_id=debt.account_id,
            expected_active=False,
            expected_updated_at=debt.updated_at,
        ),
    )

    assert restored is debt
    assert account.is_active is True
    assert account.archived_at is None
    assert session.flushes == 2


@pytest.mark.asyncio
async def test_lifecycle_rejects_outstanding_and_stale_debt() -> None:
    context = workspace_context()
    manager, _, debt, _ = lifecycle_manager(context, balance=Decimal("-10.00"))

    with pytest.raises(DebtLifecycleConflictError, match="settled"):
        await manager.archive(
            context=context,
            command=lifecycle_command(debt, expected_active=True),
        )

    with pytest.raises(DebtLifecycleConflictError, match="changed"):
        await manager.archive(
            context=context,
            command=DebtLifecycleCommand(
                debt_account_id=debt.account_id,
                expected_active=True,
                expected_updated_at=datetime(2026, 8, 8, tzinfo=UTC),
            ),
        )


@pytest.mark.asyncio
async def test_lifecycle_hides_foreign_debt() -> None:
    context = workspace_context()
    manager, _, debt, _ = lifecycle_manager(context, balance=Decimal("0.00"))

    with pytest.raises(DebtNotFoundError):
        await manager.archive(
            context=workspace_context(),
            command=lifecycle_command(debt, expected_active=True),
        )


def lifecycle_manager(
    context: WorkspaceContext,
    *,
    balance: Decimal,
) -> tuple[DebtLifecycleManager, SessionStub, Debt, Account]:
    account = Account(
        id=uuid4(),
        workspace_id=context.workspace.id,
        name="Кредит",
        type=AccountType.DEBT,
        currency="RUB",
        initial_balance=balance,
        is_active=True,
    )
    debt = Debt(
        account_id=account.id,
        workspace_id=context.workspace.id,
        kind=DebtKind.LOAN_PAYABLE,
        original_principal=Decimal("100.00"),
        creation_idempotency_key=uuid4(),
        creation_fingerprint="a" * 64,
        updated_at=NOW,
    )
    session = SessionStub()
    manager = DebtLifecycleManager(cast(Any, session))
    manager.accounts = cast(Any, AccountRepositoryStub(account))
    manager.debts = cast(Any, DebtRepositoryStub(debt))
    manager.ledger = cast(Any, LedgerRepositoryStub(Decimal("0.00")))
    return manager, session, debt, account


def lifecycle_command(debt: Debt, *, expected_active: bool) -> DebtLifecycleCommand:
    return DebtLifecycleCommand(
        debt_account_id=debt.account_id,
        expected_active=expected_active,
        expected_updated_at=debt.updated_at,
    )


def workspace_context() -> WorkspaceContext:
    user = User(id=uuid4(), email="lifecycle@example.test", password_hash="hash")
    workspace = Workspace(id=uuid4(), owner_id=user.id, name="Личный", default_currency="RUB")
    membership = WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=user.id)
    return WorkspaceContext(user=user, workspace=workspace, membership=membership)
