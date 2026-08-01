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
    PropertySummaryCapabilitiesDto,
    PropertySummaryDto,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.main import create_app


class PropertyDirectoryServiceStub:
    def __init__(self, directory: PropertyDirectoryDto) -> None:
        self.directory = directory
        self.read_calls: list[tuple[UUID, bool]] = []
        self.create_calls: list[tuple[UUID, CreatePropertyCommand]] = []

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
