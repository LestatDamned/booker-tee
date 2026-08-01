from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.properties.models import Property, PropertyStatus
from app.features.properties.repository import PropertyRepository
from app.features.properties.service import (
    PropertyLifecycleConflictError,
    PropertyNotFoundError,
    PropertyService,
    PropertyUpdateConflictError,
)


@pytest.mark.asyncio
async def test_property_update_rejects_foreign_or_missing_identity() -> None:
    property_ = existing_property()
    service = property_service(property_)

    with pytest.raises(PropertyNotFoundError):
        await service.update(
            workspace_id=uuid4(),
            property_id=property_.id,
            name="Чужое изменение",
            short_name=None,
            address=None,
            expected_updated_at=property_.updated_at,
        )

    assert property_.name == "Квартира"


@pytest.mark.asyncio
async def test_property_update_rejects_stale_write_before_mutation() -> None:
    property_ = existing_property()
    service = property_service(property_)

    with pytest.raises(PropertyUpdateConflictError):
        await service.update(
            workspace_id=property_.workspace_id,
            property_id=property_.id,
            name="Устаревшее изменение",
            short_name=None,
            address=None,
            expected_updated_at=property_.updated_at - timedelta(seconds=1),
        )

    assert property_.name == "Квартира"


@pytest.mark.asyncio
async def test_property_update_normalizes_commits_and_returns_refreshed_snapshot() -> None:
    property_ = existing_property()
    refreshed_at = property_.updated_at + timedelta(seconds=1)
    events: list[str] = []

    class SessionStub:
        async def commit(self) -> None:
            events.append("commit")

        async def refresh(self, refreshed: Property) -> None:
            events.append("refresh")
            refreshed.updated_at = refreshed_at

    class RepositoryStub:
        async def get_for_workspace(self, workspace_id, property_id):
            assert (workspace_id, property_id) == (property_.workspace_id, property_.id)
            return property_

    service = PropertyService(cast(AsyncSession, SessionStub()))
    service.properties = cast(PropertyRepository, RepositoryStub())

    result = await service.update(
        workspace_id=property_.workspace_id,
        property_id=property_.id,
        name="  Квартира   после ремонта ",
        short_name="   ",
        address="  ул. Мира,   2 ",
        expected_updated_at=property_.updated_at,
    )

    assert result is property_
    assert result.name == "Квартира после ремонта"
    assert result.short_name is None
    assert result.address == "ул. Мира, 2"
    assert result.updated_at == refreshed_at
    assert events == ["commit", "refresh"]


@pytest.mark.asyncio
async def test_property_lifecycle_rejects_missing_stale_and_wrong_status() -> None:
    property_ = existing_property()
    service = property_service(property_)

    with pytest.raises(PropertyNotFoundError):
        await service.set_status(
            workspace_id=uuid4(),
            property_id=property_.id,
            status=PropertyStatus.ARCHIVED,
            expected_status=PropertyStatus.ACTIVE,
            expected_updated_at=property_.updated_at,
        )
    with pytest.raises(PropertyLifecycleConflictError):
        await service.set_status(
            workspace_id=property_.workspace_id,
            property_id=property_.id,
            status=PropertyStatus.ARCHIVED,
            expected_status=PropertyStatus.ARCHIVED,
            expected_updated_at=property_.updated_at,
        )
    with pytest.raises(PropertyLifecycleConflictError):
        await service.set_status(
            workspace_id=property_.workspace_id,
            property_id=property_.id,
            status=PropertyStatus.ARCHIVED,
            expected_status=PropertyStatus.ACTIVE,
            expected_updated_at=property_.updated_at - timedelta(seconds=1),
        )

    assert property_.status == PropertyStatus.ACTIVE


@pytest.mark.asyncio
async def test_property_lifecycle_archives_and_restores_without_changing_identity() -> None:
    property_ = existing_property()
    service = property_service(property_)

    archived = await service.set_status(
        workspace_id=property_.workspace_id,
        property_id=property_.id,
        status=PropertyStatus.ARCHIVED,
        expected_status=PropertyStatus.ACTIVE,
        expected_updated_at=property_.updated_at,
    )

    assert archived is property_
    assert archived.status == PropertyStatus.ARCHIVED
    assert archived.archived_at is not None
    archived_at = archived.archived_at

    restored = await service.set_status(
        workspace_id=property_.workspace_id,
        property_id=property_.id,
        status=PropertyStatus.ACTIVE,
        expected_status=PropertyStatus.ARCHIVED,
        expected_updated_at=property_.updated_at,
    )

    assert restored is property_
    assert restored.id == archived.id
    assert restored.status == PropertyStatus.ACTIVE
    assert restored.archived_at is None
    assert archived_at is not None


@pytest.mark.asyncio
async def test_archived_property_remains_resolvable_for_existing_links_and_rules() -> None:
    property_ = existing_property()
    property_.status = PropertyStatus.ARCHIVED
    service = property_service(property_)

    resolved = await service.get_for_workspace(
        property_.workspace_id,
        property_.id,
    )

    assert resolved is property_
    assert resolved.status == PropertyStatus.ARCHIVED


def existing_property() -> Property:
    return Property(
        id=uuid4(),
        workspace_id=uuid4(),
        name="Квартира",
        short_name="Дом",
        address="ул. Мира, 1",
        status=PropertyStatus.ACTIVE,
        updated_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
    )


def property_service(property_: Property) -> PropertyService:
    class SessionStub:
        async def commit(self) -> None:
            return None

        async def refresh(self, _: Property) -> None:
            return None

    class RepositoryStub:
        async def get_for_workspace(self, workspace_id, property_id):
            if (workspace_id, property_id) == (property_.workspace_id, property_.id):
                return property_
            return None

    service = PropertyService(cast(AsyncSession, SessionStub()))
    service.properties = cast(PropertyRepository, RepositoryStub())
    return service
