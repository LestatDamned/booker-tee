from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.features.properties.application.directory import PropertyDirectoryService
from app.features.properties.models import Property, PropertyStatus
from app.features.properties.schemas import CreatePropertyCommand


class PropertyDirectorySourceStub:
    def __init__(self, properties: list[Property]) -> None:
        self.properties = properties
        self.workspace_ids: list[UUID] = []

    async def list_for_workspace(self, workspace_id: UUID) -> list[Property]:
        self.workspace_ids.append(workspace_id)
        return self.properties


class PropertyMutationSourceStub:
    def __init__(self, property_: Property) -> None:
        self.property = property_
        self.create_calls: list[tuple[UUID, str, str | None, str | None]] = []

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        short_name: str | None,
        address: str | None,
    ) -> Property:
        self.create_calls.append((workspace_id, name, short_name, address))
        return self.property


def directory_service(
    properties: list[Property],
) -> tuple[PropertyDirectoryService, PropertyDirectorySourceStub, PropertyMutationSourceStub]:
    source = PropertyDirectorySourceStub(properties)
    creator = PropertyMutationSourceStub(properties[0])
    return (
        PropertyDirectoryService(properties=source, creator=creator),
        source,
        creator,
    )


@pytest.mark.asyncio
async def test_property_directory_preserves_uuid_identity_and_server_capabilities() -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    properties = [
        Property(
            id=uuid4(),
            workspace_id=workspace_id,
            name="Квартира",
            short_name="Дом",
            address="Красноярск",
            status=PropertyStatus.ACTIVE,
            updated_at=updated_at,
        ),
        Property(
            id=uuid4(),
            workspace_id=workspace_id,
            name="Квартира",
            short_name=None,
            address=None,
            status=PropertyStatus.ARCHIVED,
            archived_at=updated_at,
            updated_at=updated_at,
        ),
    ]
    service, source, _ = directory_service(properties)

    directory = await service.read(
        workspace_id=workspace_id,
        can_write=True,
    )

    assert source.workspace_ids == [workspace_id]
    assert [item.id for item in directory.items] == [item.id for item in properties]
    assert [item.name for item in directory.items] == ["Квартира", "Квартира"]
    assert directory.items[0].capabilities.can_update
    assert directory.items[0].capabilities.can_archive
    assert not directory.items[0].capabilities.can_restore
    assert not directory.items[1].capabilities.can_archive
    assert directory.items[1].capabilities.can_restore
    assert directory.capabilities.can_create
    assert directory.capabilities.readonly_reason_code is None


@pytest.mark.asyncio
async def test_property_directory_is_explicitly_readonly_without_write_permission() -> None:
    workspace_id = uuid4()
    service, _, _ = directory_service(
        [
            Property(
                id=uuid4(),
                workspace_id=workspace_id,
                name="Проект",
                status=PropertyStatus.ACTIVE,
                updated_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
            )
        ]
    )

    directory = await service.read(
        workspace_id=workspace_id,
        can_write=False,
    )

    assert not directory.capabilities.can_create
    assert directory.capabilities.readonly_reason_code == "financial_write_forbidden"
    assert not directory.items[0].capabilities.can_update
    assert not directory.items[0].capabilities.can_archive
    assert not directory.items[0].capabilities.can_restore


@pytest.mark.asyncio
async def test_property_directory_create_dispatches_workspace_scoped_command() -> None:
    workspace_id = uuid4()
    property_ = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Два одинаковых имени разрешены",
        short_name=None,
        address=None,
        status=PropertyStatus.ACTIVE,
        updated_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
    )
    service, _, creator = directory_service([property_])

    created = await service.create(
        workspace_id=workspace_id,
        command=CreatePropertyCommand(
            name="Два одинаковых имени разрешены",
            short_name=None,
            address=None,
        ),
    )

    assert creator.create_calls == [(workspace_id, "Два одинаковых имени разрешены", None, None)]
    assert created.id == property_.id
    assert created.status == PropertyStatus.ACTIVE
    assert created.capabilities.can_update
    assert created.capabilities.can_archive
