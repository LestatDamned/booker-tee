from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.debts.domain import DebtPolicy
from app.features.debts.errors import DebtLifecycleConflictError, DebtNotFoundError
from app.features.debts.models import Debt
from app.features.debts.repository import DebtRepository
from app.features.debts.schemas import DebtLifecycleCommand
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


class DebtLifecycleManager:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.debts = DebtRepository(session)
        self.ledger = LedgerRepository(session)

    async def archive(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        debt, account = await self._get_locked(context, command)
        self._ensure_snapshot(debt, account, command, expected_active=True)
        balance = account.initial_balance + (
            await self.ledger.get_confirmed_account_entries_total(
                workspace_id=context.workspace.id,
                account_id=debt.account_id,
            )
        )
        if DebtPolicy.outstanding(debt.kind, balance) != 0:
            raise DebtLifecycleConflictError("Only a settled debt can be archived.")
        self._set_active(debt, account, is_active=False)
        await self.session.flush()
        return debt

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        debt, account = await self._get_locked(context, command)
        self._ensure_snapshot(debt, account, command, expected_active=False)
        self._set_active(debt, account, is_active=True)
        await self.session.flush()
        return debt

    async def _get_locked(
        self,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> tuple[Debt, Account]:
        debt = await self.debts.get_for_workspace_for_update(
            context.workspace.id,
            command.debt_account_id,
        )
        if debt is None:
            raise DebtNotFoundError("Debt was not found.")
        account = await self.accounts.get_for_workspace(context.workspace.id, debt.account_id)
        if account is None or account.type is not AccountType.DEBT:
            raise DebtNotFoundError("Debt was not found.")
        return debt, account

    @staticmethod
    def _ensure_snapshot(
        debt: Debt,
        account: Account,
        command: DebtLifecycleCommand,
        *,
        expected_active: bool,
    ) -> None:
        if command.expected_active is not expected_active:
            raise DebtLifecycleConflictError("Unexpected lifecycle action.")
        if (
            account.is_active is not expected_active
            or debt.updated_at != command.expected_updated_at
        ):
            raise DebtLifecycleConflictError("Debt changed after it was loaded.")

    @staticmethod
    def _set_active(debt: Debt, account: Account, *, is_active: bool) -> None:
        changed_at = utc_now()
        account.is_active = is_active
        account.archived_at = None if is_active else changed_at
        debt.updated_at = changed_at
