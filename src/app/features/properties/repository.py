from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.properties.models import Property, PropertyStatus


class PropertyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_workspace(self, workspace_id: UUID) -> list[Property]:
        result = await self.session.execute(
            select(Property)
            .where(Property.workspace_id == workspace_id)
            .order_by(Property.status, Property.name)
        )
        return list(result.scalars().all())

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Property]:
        result = await self.session.execute(
            select(Property)
            .where(
                Property.workspace_id == workspace_id,
                Property.status == PropertyStatus.ACTIVE,
            )
            .order_by(Property.name)
        )
        return list(result.scalars().all())

    async def get_for_workspace(self, workspace_id: UUID, property_id: UUID) -> Property | None:
        result = await self.session.execute(
            select(Property).where(
                Property.id == property_id,
                Property.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, property_: Property) -> Property:
        self.session.add(property_)
        await self.session.flush()
        return property_
