from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category
from app.features.ledger.models import Operation, OperationStatus
from app.features.transaction_rules.models import TransactionRule


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_workspace(
        self,
        workspace_id: UUID,
        *,
        include_inactive: bool = True,
    ) -> list[Category]:
        query = select(Category).where(Category.workspace_id == workspace_id)
        if not include_inactive:
            query = query.where(Category.is_active.is_(True))
        result = await self.session.execute(query.order_by(Category.sort_order, Category.name))
        return list(result.scalars().all())

    async def get_for_workspace(self, workspace_id: UUID, category_id: UUID) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                Category.id == category_id,
                Category.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_name_for_workspace(
        self,
        workspace_id: UUID,
        name: str,
    ) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                Category.workspace_id == workspace_id,
                func.lower(Category.name) == name.casefold(),
            )
        )
        return result.scalar_one_or_none()

    async def get_system_category(
        self,
        workspace_id: UUID,
        system_key: str,
    ) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                Category.workspace_id == workspace_id,
                Category.system_key == system_key,
            )
        )
        return result.scalar_one_or_none()

    async def count_operations_by_category(self, workspace_id: UUID) -> dict[UUID, int]:
        result = await self.session.execute(
            select(Operation.category_id, func.count(Operation.id))
            .where(
                Operation.workspace_id == workspace_id,
                Operation.category_id.is_not(None),
                Operation.status == OperationStatus.CONFIRMED,
            )
            .group_by(Operation.category_id)
        )
        return {
            category_id: count for category_id, count in result.all() if category_id is not None
        }

    async def count_rules_by_category(self, workspace_id: UUID) -> dict[UUID, int]:
        result = await self.session.execute(
            select(TransactionRule.category_id, func.count(TransactionRule.id))
            .where(
                TransactionRule.workspace_id == workspace_id,
                TransactionRule.category_id.is_not(None),
            )
            .group_by(TransactionRule.category_id)
        )
        return {
            category_id: count for category_id, count in result.all() if category_id is not None
        }

    async def create(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.flush()
        return category
