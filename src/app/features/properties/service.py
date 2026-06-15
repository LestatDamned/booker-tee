from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.properties.models import Property, PropertyStatus
from app.features.properties.repository import PropertyRepository


class PropertyError(ValueError):
    pass


class PropertyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.properties = PropertyRepository(session)

    async def list_active(self, workspace_id: UUID) -> list[Property]:
        return await self.properties.list_active_for_workspace(workspace_id)

    async def list_all(self, workspace_id: UUID) -> list[Property]:
        return await self.properties.list_for_workspace(workspace_id)

    async def get_for_workspace(
        self,
        workspace_id: UUID,
        property_id: UUID | None,
    ) -> Property | None:
        if property_id is None:
            return None
        property_ = await self.properties.get_for_workspace(workspace_id, property_id)
        if property_ is None:
            raise PropertyError("Property is not available in this workspace.")
        return property_

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        short_name: str | None,
        address: str | None,
    ) -> Property:
        cleaned_name = clean_required_text(name, "Название объекта обязательно.")
        property_ = await self.properties.create(
            Property(
                workspace_id=workspace_id,
                name=cleaned_name,
                short_name=clean_optional_text(short_name),
                address=clean_optional_text(address),
            )
        )
        await self.session.commit()
        return property_

    async def update(
        self,
        *,
        workspace_id: UUID,
        property_id: UUID,
        name: str,
        short_name: str | None,
        address: str | None,
    ) -> Property:
        property_ = await self.properties.get_for_workspace(workspace_id, property_id)
        if property_ is None:
            raise PropertyError("Объект не найден в этом workspace.")
        property_.name = clean_required_text(name, "Название объекта обязательно.")
        property_.short_name = clean_optional_text(short_name)
        property_.address = clean_optional_text(address)
        await self.session.commit()
        return property_

    async def set_status(
        self,
        *,
        workspace_id: UUID,
        property_id: UUID,
        status: PropertyStatus,
    ) -> Property:
        property_ = await self.properties.get_for_workspace(workspace_id, property_id)
        if property_ is None:
            raise PropertyError("Объект не найден в этом workspace.")
        property_.status = status
        property_.archived_at = utc_now() if status == PropertyStatus.ARCHIVED else None
        await self.session.commit()
        return property_


def clean_required_text(value: str, message: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise PropertyError(message)
    return cleaned


def clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None
