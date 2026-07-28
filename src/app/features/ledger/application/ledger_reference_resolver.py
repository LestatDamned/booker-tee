from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category
from app.features.categories.service import CategoryError, CategoryService
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
        self.categories = CategoryService(session)
        self.properties = PropertyService(session)

    async def get_account(self, workspace_id: UUID, account_id: UUID) -> Account:
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise AccountUnavailableError()
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
            return await self.categories.get_uncategorized(workspace_id)
        except CategoryError as exc:
            raise LedgerPostingError(str(exc)) from exc

    async def get_transfer_category(self, workspace_id: UUID) -> Category:
        try:
            return await self.categories.get_system(workspace_id, "transfer")
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
