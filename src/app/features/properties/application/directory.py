from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.features.properties.models import Property, PropertyStatus
from app.features.properties.schemas import (
    CreatePropertyCommand,
    PropertyDirectoryCapabilitiesDto,
    PropertyDirectoryDto,
    PropertyDirectoryReadonlyReason,
    PropertySummaryCapabilitiesDto,
    PropertySummaryDto,
)


class PropertyDirectorySource(Protocol):
    async def list_for_workspace(self, workspace_id: UUID) -> Sequence[Property]: ...


class PropertyMutationSource(Protocol):
    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        short_name: str | None,
        address: str | None,
    ) -> Property: ...


class PropertyDirectoryService:
    def __init__(
        self,
        *,
        properties: PropertyDirectorySource,
        creator: PropertyMutationSource,
    ) -> None:
        self._properties = properties
        self._creator = creator

    async def read(
        self,
        *,
        workspace_id: UUID,
        can_write: bool,
    ) -> PropertyDirectoryDto:
        properties = await self._properties.list_for_workspace(workspace_id)
        return PropertyDirectoryDto(
            items=[property_summary(property_, can_write=can_write) for property_ in properties],
            capabilities=PropertyDirectoryCapabilitiesDto(
                can_create=can_write,
                readonly_reason_code=(
                    None if can_write else PropertyDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
                ),
            ),
        )

    async def create(
        self,
        *,
        workspace_id: UUID,
        command: CreatePropertyCommand,
    ) -> PropertySummaryDto:
        property_ = await self._creator.create(
            workspace_id=workspace_id,
            name=command.name,
            short_name=command.short_name,
            address=command.address,
        )
        return property_summary(property_, can_write=True)


def property_summary(property_: Property, *, can_write: bool) -> PropertySummaryDto:
    is_active = property_.status == PropertyStatus.ACTIVE
    is_archived = property_.status == PropertyStatus.ARCHIVED
    return PropertySummaryDto(
        id=property_.id,
        name=property_.name,
        short_name=property_.short_name,
        address=property_.address,
        status=property_.status,
        archived_at=property_.archived_at,
        updated_at=property_.updated_at,
        capabilities=PropertySummaryCapabilitiesDto(
            can_update=can_write,
            can_archive=can_write and is_active,
            can_restore=can_write and is_archived,
        ),
    )
