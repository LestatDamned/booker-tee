from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.properties.dependencies import get_property_directory_service
from app.features.properties.models import PropertyStatus
from app.features.properties.schemas import (
    CreatePropertyCommand,
    PropertyDirectoryCapabilitiesDto,
    PropertyDirectoryDto,
    PropertyDirectoryReadonlyReason,
    PropertyLifecycleCommand,
    PropertyLifecycleImpactDto,
    PropertyLifecycleResultDto,
    PropertySummaryCapabilitiesDto,
    PropertySummaryDto,
    UpdatePropertyCommand,
)
from app.features.properties.service import PropertyError
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class PropertyDirectoryServiceStub:
    def __init__(self, directory: PropertyDirectoryDto) -> None:
        self.directory = directory
        self.read_calls: list[tuple[UUID, bool]] = []
        self.create_calls: list[tuple[UUID, CreatePropertyCommand]] = []
        self.update_calls: list[tuple[UUID, UUID, UpdatePropertyCommand]] = []
        self.update_error: PropertyError | None = None
        self.lifecycle_calls: list[tuple[UUID, UUID, PropertyStatus, PropertyLifecycleCommand]] = []
        self.lifecycle_error: PropertyError | None = None

    async def read(
        self,
        *,
        workspace_id: UUID,
        can_write: bool,
    ) -> PropertyDirectoryDto:
        self.read_calls.append((workspace_id, can_write))
        return self.directory

    async def create(
        self,
        *,
        workspace_id: UUID,
        command: CreatePropertyCommand,
    ) -> PropertySummaryDto:
        self.create_calls.append((workspace_id, command))
        return self.directory.items[0]

    async def set_status(
        self,
        *,
        workspace_id: UUID,
        property_id: UUID,
        status: PropertyStatus,
        command: PropertyLifecycleCommand,
    ) -> PropertyLifecycleResultDto:
        self.lifecycle_calls.append((workspace_id, property_id, status, command))
        if self.lifecycle_error is not None:
            raise self.lifecycle_error
        source = next(item for item in self.directory.items if item.id == property_id)
        property_ = source.model_copy(
            update={
                "status": status,
                "archived_at": source.updated_at if status == PropertyStatus.ARCHIVED else None,
                "capabilities": PropertySummaryCapabilitiesDto(
                    can_update=True,
                    can_archive=status == PropertyStatus.ACTIVE,
                    can_restore=status == PropertyStatus.ARCHIVED,
                ),
            }
        )
        return PropertyLifecycleResultDto(
            property=property_,
            impact=PropertyLifecycleImpactDto(
                history_preserved=True,
                active_rules_unchanged=True,
                available_for_new_references=status == PropertyStatus.ACTIVE,
            ),
        )

    async def update(
        self,
        *,
        workspace_id: UUID,
        property_id: UUID,
        command: UpdatePropertyCommand,
    ) -> PropertySummaryDto:
        self.update_calls.append((workspace_id, property_id, command))
        if self.update_error is not None:
            raise self.update_error
        return self.directory.items[0]


def properties_app(
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, PropertyDirectoryServiceStub, UUID]:
    context = api_context(role=role)
    can_write = role in {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.EDITOR,
    }
    service = PropertyDirectoryServiceStub(property_directory(can_write=can_write))
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_property_directory_service] = lambda: service
    return app, service, context.workspace.workspace.id


def property_directory(*, can_write: bool) -> PropertyDirectoryDto:
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    return PropertyDirectoryDto(
        items=[
            PropertySummaryDto(
                id=uuid4(),
                name="Квартира",
                short_name="Дом",
                address="Красноярск, ул. Мира, 1",
                status=PropertyStatus.ACTIVE,
                archived_at=None,
                updated_at=updated_at,
                capabilities=PropertySummaryCapabilitiesDto(
                    can_update=can_write,
                    can_archive=can_write,
                    can_restore=False,
                ),
            ),
            PropertySummaryDto(
                id=uuid4(),
                name="Старый проект",
                short_name=None,
                address=None,
                status=PropertyStatus.ARCHIVED,
                archived_at=updated_at,
                updated_at=updated_at,
                capabilities=PropertySummaryCapabilitiesDto(
                    can_update=can_write,
                    can_archive=False,
                    can_restore=can_write,
                ),
            ),
        ],
        capabilities=PropertyDirectoryCapabilitiesDto(
            can_create=can_write,
            readonly_reason_code=(
                None if can_write else PropertyDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
            ),
        ),
    )
