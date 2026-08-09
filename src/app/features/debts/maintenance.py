from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.accounts.service import clean_required_text
from app.features.debts.domain import DebtPolicy
from app.features.debts.errors import (
    DebtDeleteBlockedError,
    DebtMaintenanceConflictError,
    DebtNotFoundError,
)
from app.features.debts.models import Debt
from app.features.debts.repository import DebtRepository
from app.features.debts.schemas import DeleteDebtCommand, UpdateDebtCommand
from app.features.ledger.domain.types import OperationSource, OperationType
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


@dataclass(frozen=True)
class DeletedDebt:
    account_id: UUID
    name: str


class DebtDetailsEditor:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.debts = DebtRepository(session)
        self.ledger = LedgerRepository(session)

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateDebtCommand,
    ) -> Debt:
        debt, account = await _get_locked_debt(
            context=context,
            account_id=command.debt_account_id,
            accounts=self.accounts,
            debts=self.debts,
        )
        _ensure_snapshot(debt, command.expected_updated_at)
        balance = account.initial_balance + (
            await self.ledger.get_confirmed_account_entries_total(
                workspace_id=context.workspace.id,
                account_id=account.id,
            )
        )
        DebtPolicy.validate_terms(
            kind=debt.kind,
            opening_balance=balance,
            opened_on=command.opened_on,
            maturity_date=command.maturity_date,
            original_principal=debt.original_principal,
            credit_limit=command.credit_limit,
        )
        changed_at = utc_now()
        account.name = clean_required_text(command.name, "Debt name is required.")
        account.notes = _clean_optional_text(command.notes)
        account.updated_at = changed_at
        debt.opened_on = command.opened_on
        debt.maturity_date = command.maturity_date
        debt.credit_limit = command.credit_limit
        debt.updated_at = changed_at
        await self.session.flush()
        return debt


class DebtDeleter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.accounts = AccountRepository(session)
        self.debts = DebtRepository(session)
        self.ledger = LedgerRepository(session)

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        command: DeleteDebtCommand,
    ) -> DeletedDebt:
        debt, account = await _get_locked_debt(
            context=context,
            account_id=command.debt_account_id,
            accounts=self.accounts,
            debts=self.debts,
        )
        _ensure_snapshot(debt, command.expected_updated_at)
        workspace_id = context.workspace.id
        if await self.accounts.has_import_history(workspace_id, account.id) or (
            await self.debts.has_payments(workspace_id, account.id)
        ):
            raise DebtDeleteBlockedError("A debt with financial history cannot be deleted.")
        operations = await self.debts.list_account_operations(workspace_id, account.id)
        if len(operations) > 1 or any(
            operation.source is not OperationSource.DEBT
            or operation.type is not OperationType.TRANSFER
            for operation in operations
        ):
            raise DebtDeleteBlockedError("A debt with financial history cannot be deleted.")
        deleted = DeletedDebt(account_id=account.id, name=account.name)
        try:
            if operations:
                await self.ledger.delete_operation(operations[0])
            await self.accounts.delete(account)
            await self.session.flush()
        except IntegrityError as error:
            raise DebtDeleteBlockedError(
                "A debt with financial history cannot be deleted."
            ) from error
        return deleted


async def _get_locked_debt(
    *,
    context: WorkspaceContext,
    account_id: UUID,
    accounts: AccountRepository,
    debts: DebtRepository,
) -> tuple[Debt, Account]:
    debt = await debts.get_for_workspace_for_update(context.workspace.id, account_id)
    if debt is None:
        raise DebtNotFoundError("Debt was not found.")
    account = await accounts.get_for_workspace(context.workspace.id, debt.account_id)
    if account is None or account.type is not AccountType.DEBT:
        raise DebtNotFoundError("Debt was not found.")
    return debt, account


def _ensure_snapshot(debt: Debt, expected_updated_at: datetime) -> None:
    if debt.updated_at != expected_updated_at:
        raise DebtMaintenanceConflictError("Debt changed after it was loaded.")


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
