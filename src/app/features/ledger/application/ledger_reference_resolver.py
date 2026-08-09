from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category
from app.features.categories.service import CategoryError, CategoryService
from app.features.debts.domain import DebtKind
from app.features.debts.repository import DebtRepository
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import (
    AccountUnavailableError,
    CategoryUnavailableError,
    LedgerPostingError,
    PropertyUnavailableError,
)
from app.features.properties.models import Property
from app.features.properties.service import PropertyError, PropertyService


class LedgerReferenceResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.accounts = AccountRepository(session)
        self.debts = DebtRepository(session)
        self.categories = CategoryService(session)
        self.properties = PropertyService(session)

    async def list_manual_accounts(self, workspace_id: UUID) -> list[Account]:
        return [
            *await self.accounts.list_active_for_workspace(workspace_id),
            *await self.debts.list_active_credit_card_accounts(workspace_id),
        ]

    async def get_account(self, workspace_id: UUID, account_id: UUID) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise AccountUnavailableError()
        return account

    async def get_income_expense_account(
        self,
        workspace_id: UUID,
        account_id: UUID,
        operation_type: OperationType,
    ) -> Account:
        account = await self.get_account(workspace_id, account_id)
        await self.ensure_income_expense_account(workspace_id, account, operation_type)
        return account

    async def ensure_income_expense_account(
        self,
        workspace_id: UUID,
        account: Account,
        operation_type: OperationType,
    ) -> None:
        if account.type is not AccountType.DEBT:
            return
        if not account.is_active:
            raise LedgerPostingError("An archived debt account is not available here.")
        debt = await self.debts.get_for_workspace(workspace_id, account.id)
        if debt is None or debt.kind is not DebtKind.CREDIT_CARD:
            raise LedgerPostingError("Loan and mortgage accounts are managed in Debts.")
        if operation_type is not OperationType.EXPENSE:
            raise LedgerPostingError("A credit card account can only record an expense here.")

    async def get_transfer_account(self, workspace_id: UUID, account_id: UUID) -> Account:
        account = await self.get_account(workspace_id, account_id)
        if account.type is AccountType.DEBT:
            raise LedgerPostingError("Debt principal transfers are managed in Debts.")
        return account

    async def get_import_account(self, workspace_id: UUID, account_id: UUID) -> Account:
        account = await self.get_account(workspace_id, account_id)
        if account.type is not AccountType.DEBT:
            return account
        if not account.is_active:
            raise LedgerPostingError("An archived debt account is not available for import.")
        debt = await self.debts.get_for_workspace(workspace_id, account_id)
        if debt is None or debt.kind is not DebtKind.CREDIT_CARD:
            raise LedgerPostingError("Only credit card debt statements can be imported.")
        return account

    async def get_category_or_uncategorized(
        self,
        workspace_id: UUID,
        category_id: UUID | None,
    ) -> Category:
        try:
            if category_id is not None:
                category = await self.categories.get_for_workspace(workspace_id, category_id)
                if category is None:
                    raise CategoryUnavailableError()
                return category
            return await self.categories.ensure_uncategorized(workspace_id)
        except CategoryError as exc:
            raise LedgerPostingError(str(exc)) from exc

    async def get_transfer_category(self, workspace_id: UUID) -> Category:
        try:
            return await self.categories.ensure_system(workspace_id, "transfer")
        except CategoryError as exc:
            raise LedgerPostingError(str(exc)) from exc

    async def get_property(
        self,
        workspace_id: UUID,
        property_id: UUID | None,
    ) -> Property | None:
        try:
            return await self.properties.get_for_workspace(workspace_id, property_id)
        except PropertyError as exc:
            raise PropertyUnavailableError() from exc
