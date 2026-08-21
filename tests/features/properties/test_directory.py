from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.features.properties.application.directory import PropertyDirectoryService
from app.features.properties.models import Property, PropertyStatus
from app.features.properties.schemas import (
    CreatePropertyCommand,
    PropertyLifecycleCommand,
    UpdatePropertyCommand,
)


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
        self.update_calls: list[tuple[UUID, UUID, str, str | None, str | None, datetime]] = []
        self.lifecycle_calls: list[tuple[UUID, UUID, PropertyStatus, PropertyStatus, datetime]] = []

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

    async def set_status(
        self,
        *,
        workspace_id: UUID,
        property_id: UUID,
        status: PropertyStatus,
        expected_status: PropertyStatus,
        expected_updated_at: datetime,
    ) -> Property:
        self.lifecycle_calls.append(
            (workspace_id, property_id, status, expected_status, expected_updated_at)
        )
        self.property.status = status
        return self.property

    async def update(
        self,
        *,
        workspace_id: UUID,
        property_id: UUID,
        name: str,
        short_name: str | None,
        address: str | None,
        expected_updated_at: datetime,
    ) -> Property:
        self.update_calls.append(
            (
                workspace_id,
                property_id,
                name,
                short_name,
                address,
                expected_updated_at,
            )
        )
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


async def test_property_directory_update_dispatches_identity_and_optimistic_token() -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    property_ = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Квартира",
        status=PropertyStatus.ACTIVE,
        updated_at=updated_at,
    )
    service, _, mutations = directory_service([property_])

    committed = await service.update(
        workspace_id=workspace_id,
        property_id=property_.id,
        command=UpdatePropertyCommand(
            name="Квартира после ремонта",
            short_name="Дом",
            address="ул. Мира, 1",
            expected_updated_at=updated_at,
        ),
    )

    assert mutations.update_calls == [
        (
            workspace_id,
            property_.id,
            "Квартира после ремонта",
            "Дом",
            "ул. Мира, 1",
            updated_at,
        )
    ]
    assert committed.id == property_.id


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        pytest.param(PropertyStatus.ACTIVE, PropertyStatus.ARCHIVED, id="archive"),
        pytest.param(PropertyStatus.ARCHIVED, PropertyStatus.ACTIVE, id="restore"),
    ],
)
async def test_property_lifecycle_dispatches_token_and_returns_policy_impact(
    current_status: PropertyStatus,
    target_status: PropertyStatus,
) -> None:
    workspace_id = uuid4()
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    property_ = Property(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Квартира",
        status=current_status,
        updated_at=updated_at,
    )
    service, _, mutations = directory_service([property_])

    committed = await service.set_status(
        workspace_id=workspace_id,
        property_id=property_.id,
        status=target_status,
        command=PropertyLifecycleCommand(
            expected_status=current_status,
            expected_updated_at=updated_at,
        ),
    )

    assert mutations.lifecycle_calls == [
        (
            workspace_id,
            property_.id,
            target_status,
            current_status,
            updated_at,
        )
    ]
    assert committed.property.status == target_status
    assert committed.property.capabilities.can_archive is (
        target_status == PropertyStatus.ACTIVE
    )
    assert committed.property.capabilities.can_restore is (
        target_status == PropertyStatus.ARCHIVED
    )
    assert committed.impact.history_preserved
    assert committed.impact.active_rules_unchanged
    assert committed.impact.available_for_new_references is (
        target_status == PropertyStatus.ACTIVE
    )
