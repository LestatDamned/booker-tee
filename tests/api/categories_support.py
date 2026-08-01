from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.categories.dependencies import get_category_directory_service
from app.features.categories.models import CategoryKind
from app.features.categories.schemas import (
    CategoryArchiveBlockedReason,
    CategoryDirectoryCapabilitiesDto,
    CategoryDirectoryDto,
    CategoryDirectoryReadonlyReason,
    CategoryKindOptionDto,
    CategorySummaryCapabilitiesDto,
    CategorySummaryDto,
    CreateCategoryCommand,
)
from app.features.workspaces.domain.types import WorkspaceRole
from app.features.workspaces.models import WorkspaceType
from app.main import create_app


class CategoryDirectoryServiceStub:
    def __init__(self, directory: CategoryDirectoryDto) -> None:
        self.directory = directory
        self.read_calls: list[tuple[UUID, WorkspaceType, bool]] = []
        self.create_calls: list[tuple[UUID, CreateCategoryCommand]] = []
        self.create_error: ValueError | None = None

    async def read(
        self,
        *,
        workspace_id: UUID,
        workspace_type: WorkspaceType,
        can_write: bool,
    ) -> CategoryDirectoryDto:
        self.read_calls.append((workspace_id, workspace_type, can_write))
        return self.directory

    async def create(
        self,
        *,
        workspace_id: UUID,
        command: CreateCategoryCommand,
    ) -> CategorySummaryDto:
        self.create_calls.append((workspace_id, command))
        if self.create_error is not None:
            raise self.create_error
        return self.directory.items[0]


def categories_app(
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, CategoryDirectoryServiceStub, UUID, WorkspaceType]:
    context = api_context(role=role)
    can_write = role in {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.EDITOR,
    }
    service = CategoryDirectoryServiceStub(category_directory(can_write=can_write))
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_category_directory_service] = lambda: service
    return (
        app,
        service,
        context.workspace.workspace.id,
        context.workspace.workspace.type,
    )


def category_directory(*, can_write: bool) -> CategoryDirectoryDto:
    updated_at = datetime(2026, 8, 1, 8, 30, tzinfo=UTC)
    return CategoryDirectoryDto(
        items=[
            CategorySummaryDto(
                id=uuid4(),
                name="Продукты",
                kind=CategoryKind.EXPENSE,
                is_active=True,
                is_system=False,
                system_key=None,
                notes="Супермаркеты и доставка",
                operation_count=12,
                rule_count=3,
                active_rule_count=1,
                updated_at=updated_at,
                capabilities=CategorySummaryCapabilitiesDto(
                    can_update=can_write,
                    can_archive=False,
                    can_restore=False,
                    archive_blocked_reason_code=CategoryArchiveBlockedReason.ACTIVE_RULES,
                ),
            ),
            CategorySummaryDto(
                id=uuid4(),
                name="Без категории",
                kind=CategoryKind.MIXED,
                is_active=True,
                is_system=True,
                system_key="uncategorized",
                notes=None,
                operation_count=2,
                rule_count=0,
                active_rule_count=0,
                updated_at=updated_at,
                capabilities=CategorySummaryCapabilitiesDto(
                    can_update=False,
                    can_archive=False,
                    can_restore=False,
                    archive_blocked_reason_code=None,
                ),
            ),
        ],
        kind_options=[
            CategoryKindOptionDto(
                value=CategoryKind.EXPENSE,
                label="Расход",
                description="Для списаний.",
            )
        ],
        capabilities=CategoryDirectoryCapabilitiesDto(
            can_create=can_write,
            readonly_reason_code=(
                None if can_write else CategoryDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
            ),
        ),
    )
