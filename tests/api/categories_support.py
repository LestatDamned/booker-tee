from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import api_context

from app.api.dependencies import get_api_request_context
from app.api.v1.categories.dependencies import (
    get_category_detail_reader,
    get_category_directory_service,
)
from app.features.categories.application.detail import (
    CategoryDetailFilterError,
    CategoryDetailNotFoundError,
)
from app.features.categories.models import CategoryKind
from app.features.categories.schemas import (
    CategoryArchiveBlockedReason,
    CategoryDeleteBlockedReason,
    CategoryDeleteBlockersDto,
    CategoryDeleteResultDto,
    CategoryDetailDto,
    CategoryDetailFiltersDto,
    CategoryDirectoryCapabilitiesDto,
    CategoryDirectoryDto,
    CategoryDirectoryReadonlyReason,
    CategoryKindChangeImpactDto,
    CategoryKindOptionDto,
    CategoryLifecycleCommand,
    CategoryLifecycleImpactDto,
    CategoryLifecycleResultDto,
    CategoryMoneySummaryDto,
    CategoryOperationPageDto,
    CategoryRulePreviewDto,
    CategorySummaryCapabilitiesDto,
    CategorySummaryDto,
    CreateCategoryCommand,
    UpdateCategoryCommand,
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
        self.update_calls: list[tuple[UUID, UUID, UpdateCategoryCommand]] = []
        self.update_error: ValueError | None = None
        self.lifecycle_calls: list[tuple[UUID, UUID, bool, CategoryLifecycleCommand]] = []
        self.lifecycle_error: ValueError | None = None
        self.delete_calls: list[tuple[UUID, UUID, CategoryLifecycleCommand]] = []
        self.delete_error: ValueError | None = None

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

    async def update(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        command: UpdateCategoryCommand,
    ) -> CategorySummaryDto:
        self.update_calls.append((workspace_id, category_id, command))
        if self.update_error is not None:
            raise self.update_error
        return self.directory.items[0]

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        is_active: bool,
        command: CategoryLifecycleCommand,
    ) -> CategoryLifecycleResultDto:
        self.lifecycle_calls.append((workspace_id, category_id, is_active, command))
        if self.lifecycle_error is not None:
            raise self.lifecycle_error
        remaining_delete_blockers = [
            reason
            for reason in self.directory.items[0].delete_blockers.reason_codes
            if reason != "active_category"
        ]
        category = self.directory.items[0].model_copy(
            update={
                "id": category_id,
                "is_active": is_active,
                "capabilities": self.directory.items[0].capabilities.model_copy(
                    update={
                        "can_archive": is_active,
                        "can_restore": not is_active,
                        "can_delete": not is_active and not remaining_delete_blockers,
                    }
                ),
            }
        )
        return CategoryLifecycleResultDto(
            category=category,
            impact=CategoryLifecycleImpactDto(
                history_preserved=True,
                rules_unchanged=True,
                available_for_new_references=is_active,
            ),
        )

    async def delete(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        command: CategoryLifecycleCommand,
    ) -> CategoryDeleteResultDto:
        self.delete_calls.append((workspace_id, category_id, command))
        if self.delete_error is not None:
            raise self.delete_error
        return CategoryDeleteResultDto(deleted_id=category_id, name="Продукты")


class CategoryDetailReaderStub:
    def __init__(self, detail: CategoryDetailDto) -> None:
        self.detail = detail
        self.calls: list[dict[str, object]] = []
        self.not_found = False
        self.filter_error: CategoryDetailFilterError | None = None

    async def read(self, **kwargs: object) -> CategoryDetailDto:
        self.calls.append(kwargs)
        if self.not_found:
            raise CategoryDetailNotFoundError
        if self.filter_error is not None:
            raise self.filter_error
        return self.detail


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


def category_detail_app(
    *, role: WorkspaceRole = WorkspaceRole.OWNER
) -> tuple[FastAPI, CategoryDirectoryServiceStub, CategoryDetailReaderStub, UUID, UUID]:
    context = api_context(role=role)
    category_id = uuid4()
    can_write = role in {
        WorkspaceRole.OWNER,
        WorkspaceRole.ADMIN,
        WorkspaceRole.EDITOR,
    }
    directory = category_directory(can_write=can_write)
    service = CategoryDirectoryServiceStub(directory)
    summary = directory.items[0].model_copy(update={"id": category_id})
    reader = CategoryDetailReaderStub(
        CategoryDetailDto(
            category=summary,
            kind_options=category_directory(can_write=True).kind_options,
            kind_change_impact=CategoryKindChangeImpactDto(
                existing_operations_unchanged=True,
                picker_compatibility_may_change=True,
                operation_count=12,
                rule_count=3,
                requires_confirmation=True,
            ),
            applied_filters=CategoryDetailFiltersDto(
                date_from=None,
                date_to=None,
                currency="RUB",
                operation_type=None,
                search=None,
            ),
            available_currencies=["RUB", "USD"],
            summary=CategoryMoneySummaryDto(
                currency="RUB",
                income=Decimal("100.00"),
                expense=Decimal("35.00"),
                profit=Decimal("65.00"),
            ),
            operations=CategoryOperationPageDto(
                items=[],
                page=1,
                page_size=20,
                total=0,
                total_pages=1,
                has_previous=False,
                has_next=False,
            ),
            rules=CategoryRulePreviewDto(items=[], total=0, active_count=0),
        )
    )
    app = create_app()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_category_directory_service] = lambda: service
    app.dependency_overrides[get_category_detail_reader] = lambda: reader
    return app, service, reader, context.workspace.workspace.id, category_id


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
                delete_blockers=CategoryDeleteBlockersDto(
                    operation_count=12,
                    rule_count=3,
                    raw_suggestion_count=0,
                    child_category_count=0,
                    reason_codes=[
                        CategoryDeleteBlockedReason.ACTIVE_CATEGORY,
                        CategoryDeleteBlockedReason.OPERATIONS,
                        CategoryDeleteBlockedReason.RULES,
                    ],
                ),
                updated_at=updated_at,
                capabilities=CategorySummaryCapabilitiesDto(
                    can_update=can_write,
                    can_archive=False,
                    can_restore=False,
                    can_delete=False,
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
                delete_blockers=CategoryDeleteBlockersDto(
                    operation_count=2,
                    rule_count=0,
                    raw_suggestion_count=0,
                    child_category_count=0,
                    reason_codes=[
                        CategoryDeleteBlockedReason.ACTIVE_CATEGORY,
                        CategoryDeleteBlockedReason.OPERATIONS,
                    ],
                ),
                updated_at=updated_at,
                capabilities=CategorySummaryCapabilitiesDto(
                    can_update=False,
                    can_archive=False,
                    can_restore=False,
                    can_delete=False,
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
