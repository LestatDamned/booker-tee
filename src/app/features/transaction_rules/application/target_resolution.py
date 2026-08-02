from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category
from app.features.categories.repository import CategoryRepository
from app.features.properties.models import Property, PropertyStatus
from app.features.properties.repository import PropertyRepository
from app.features.transaction_rules.errors import (
    TransactionRuleActivationBlockedError,
    TransactionRuleValidationError,
)
from app.features.transaction_rules.models import TransactionRule


@dataclass(frozen=True)
class ResolvedTransactionRuleTargets:
    category: Category | None
    property: Property | None
    account: Account | None


class TransactionRuleTargetResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.categories = CategoryRepository(session)
        self.properties = PropertyRepository(session)
        self.accounts = AccountRepository(session)

    async def resolve_for_create(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID | None,
        property_id: UUID | None,
        account_id: UUID | None,
    ) -> ResolvedTransactionRuleTargets:
        return await self._resolve(
            workspace_id=workspace_id,
            category_id=category_id,
            property_id=property_id,
            account_id=account_id,
            retained_rule=None,
            activation=False,
        )

    async def resolve_for_update(
        self,
        *,
        workspace_id: UUID,
        rule: TransactionRule,
        category_id: UUID | None,
        property_id: UUID | None,
    ) -> ResolvedTransactionRuleTargets:
        return await self._resolve(
            workspace_id=workspace_id,
            category_id=category_id,
            property_id=property_id,
            account_id=rule.account_id,
            retained_rule=rule,
            activation=False,
        )

    async def validate_for_activation(
        self,
        *,
        workspace_id: UUID,
        rule: TransactionRule,
    ) -> None:
        await self._resolve(
            workspace_id=workspace_id,
            category_id=rule.category_id,
            property_id=rule.property_id,
            account_id=rule.account_id,
            retained_rule=None,
            activation=True,
        )

    async def _resolve(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID | None,
        property_id: UUID | None,
        account_id: UUID | None,
        retained_rule: TransactionRule | None,
        activation: bool,
    ) -> ResolvedTransactionRuleTargets:
        error_type = (
            TransactionRuleActivationBlockedError if activation else TransactionRuleValidationError
        )
        category = await self._category(workspace_id, category_id, error_type)
        if category is not None and not category.is_active:
            retained = retained_rule is not None and retained_rule.category_id == category.id
            if not retained:
                raise error_type(
                    "Category is not available for an active rule.", field="categoryId"
                )

        property_ = await self._property(workspace_id, property_id, error_type)
        if property_ is not None and property_.status != PropertyStatus.ACTIVE:
            retained = retained_rule is not None and retained_rule.property_id == property_.id
            if not retained:
                raise error_type(
                    "Property is not available for an active rule.", field="propertyId"
                )

        account = await self._account(workspace_id, account_id, error_type)
        if account is not None and not account.is_active:
            retained = retained_rule is not None and retained_rule.account_id == account.id
            if not retained:
                raise error_type("Account is not available for an active rule.", field="accountId")

        return ResolvedTransactionRuleTargets(
            category=category,
            property=property_,
            account=account,
        )

    async def _category(
        self,
        workspace_id: UUID,
        category_id: UUID | None,
        error_type: type[TransactionRuleValidationError],
    ) -> Category | None:
        if category_id is None:
            return None
        category = await self.categories.get_for_workspace(workspace_id, category_id)
        if category is None:
            raise error_type("Category is not available in this workspace.", field="categoryId")
        return category

    async def _property(
        self,
        workspace_id: UUID,
        property_id: UUID | None,
        error_type: type[TransactionRuleValidationError],
    ) -> Property | None:
        if property_id is None:
            return None
        property_ = await self.properties.get_for_workspace(workspace_id, property_id)
        if property_ is None:
            raise error_type("Property is not available in this workspace.", field="propertyId")
        return property_

    async def _account(
        self,
        workspace_id: UUID,
        account_id: UUID | None,
        error_type: type[TransactionRuleValidationError],
    ) -> Account | None:
        if account_id is None:
            return None
        account = await self.accounts.get_for_workspace(workspace_id, account_id)
        if account is None:
            raise error_type("Account is not available in this workspace.", field="accountId")
        return account
