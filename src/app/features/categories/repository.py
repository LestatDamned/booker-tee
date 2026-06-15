from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.categories.models import Category


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_workspace(self, workspace_id: UUID) -> list[Category]:
        result = await self.session.execute(
            select(Category)
            .where(Category.workspace_id == workspace_id)
            .order_by(Category.sort_order, Category.name)
        )
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
                Category.name == name,
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

    async def create(self, category: Category) -> Category:
        self.session.add(category)
        await self.session.flush()
        return category
