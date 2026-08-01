from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.features.categories.models import Category, CategoryKind
from app.features.categories.schemas import (
    CategoryArchiveBlockedReason,
    CategoryDeleteBlockedReason,
    CategoryDeleteBlockersDto,
    CategoryDeleteResultDto,
    CategoryDirectoryCapabilitiesDto,
    CategoryDirectoryDto,
    CategoryDirectoryReadonlyReason,
    CategoryKindOptionDto,
    CategoryLifecycleCommand,
    CategoryLifecycleImpactDto,
    CategoryLifecycleResultDto,
    CategorySummaryCapabilitiesDto,
    CategorySummaryDto,
    CreateCategoryCommand,
    UpdateCategoryCommand,
)
from app.features.categories.service import CategoryManagementRow, DeletedCategory
from app.features.workspaces.models import WorkspaceType


class CategoryManagementSource(Protocol):
    async def list_management_rows(
        self,
        workspace_id: UUID,
        workspace_type: WorkspaceType | None = None,
    ) -> Sequence[CategoryManagementRow]: ...


class CategoryMutationSource(Protocol):
    async def create_custom(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
        notes: str | None = None,
    ) -> Category: ...

    async def update_custom(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        name: str,
        kind: CategoryKind,
        notes: str | None,
        expected_updated_at: datetime,
    ) -> Category: ...

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        is_active: bool,
        expected_status: bool,
        expected_updated_at: datetime,
    ) -> Category: ...

    async def delete_archived_custom(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        expected_status: bool,
        expected_updated_at: datetime,
    ) -> DeletedCategory: ...


class CategoryDirectoryService:
    def __init__(
        self,
        source: CategoryManagementSource,
        mutations: CategoryMutationSource,
    ) -> None:
        self._source = source
        self._mutations = mutations

    async def read(
        self,
        *,
        workspace_id: UUID,
        workspace_type: WorkspaceType,
        can_write: bool,
    ) -> CategoryDirectoryDto:
        rows = await self._source.list_management_rows(workspace_id, workspace_type)
        return CategoryDirectoryDto(
            items=[category_summary(row, can_write=can_write) for row in rows],
            kind_options=category_kind_options(),
            capabilities=CategoryDirectoryCapabilitiesDto(
                can_create=can_write,
                readonly_reason_code=(
                    None if can_write else CategoryDirectoryReadonlyReason.FINANCIAL_WRITE_FORBIDDEN
                ),
            ),
        )

    async def create(
        self,
        *,
        workspace_id: UUID,
        command: CreateCategoryCommand,
    ) -> CategorySummaryDto:
        category = await self._mutations.create_custom(
            workspace_id=workspace_id,
            name=command.name,
            kind=command.kind,
            notes=command.notes,
        )
        return category_summary(
            CategoryManagementRow(
                category=category,
                operation_count=0,
                rule_count=0,
                active_rule_count=0,
            ),
            can_write=True,
        )

    async def update(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        command: UpdateCategoryCommand,
    ) -> CategorySummaryDto:
        category = await self._mutations.update_custom(
            workspace_id=workspace_id,
            category_id=category_id,
            name=command.name,
            kind=command.kind,
            notes=command.notes,
            expected_updated_at=command.expected_updated_at,
        )
        rows = await self._source.list_management_rows(workspace_id)
        row = next((item for item in rows if item.category.id == category.id), None)
        if row is None:
            row = CategoryManagementRow(
                category=category,
                operation_count=0,
                rule_count=0,
                active_rule_count=0,
            )
        return category_summary(row, can_write=True)

    async def set_active(
        self,
        *,
        workspace_id: UUID,
        category_id: UUID,
        is_active: bool,
        command: CategoryLifecycleCommand,
    ) -> CategoryLifecycleResultDto:
        category = await self._mutations.set_active(
            workspace_id=workspace_id,
            category_id=category_id,
            is_active=is_active,
            expected_status=command.expected_status,
            expected_updated_at=command.expected_updated_at,
        )
        row = await self._management_row(workspace_id, category)
        return CategoryLifecycleResultDto(
            category=category_summary(row, can_write=True),
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
        deleted = await self._mutations.delete_archived_custom(
            workspace_id=workspace_id,
            category_id=category_id,
            expected_status=command.expected_status,
            expected_updated_at=command.expected_updated_at,
        )
        return CategoryDeleteResultDto(deleted_id=deleted.id, name=deleted.name)

    async def _management_row(
        self,
        workspace_id: UUID,
        category: Category,
    ) -> CategoryManagementRow:
        rows = await self._source.list_management_rows(workspace_id)
        row = next((item for item in rows if item.category.id == category.id), None)
        return row or CategoryManagementRow(
            category=category,
            operation_count=0,
            rule_count=0,
            active_rule_count=0,
        )


def category_summary(
    row: CategoryManagementRow,
    *,
    can_write: bool,
) -> CategorySummaryDto:
    category = row.category
    is_custom = not category.is_system
    archive_blocked = is_custom and category.is_active and row.active_rule_count > 0
    delete_reason_codes: list[CategoryDeleteBlockedReason] = []
    if category.is_active:
        delete_reason_codes.append(CategoryDeleteBlockedReason.ACTIVE_CATEGORY)
    if row.delete_operation_count > 0:
        delete_reason_codes.append(CategoryDeleteBlockedReason.OPERATIONS)
    if row.rule_count > 0:
        delete_reason_codes.append(CategoryDeleteBlockedReason.RULES)
    if row.raw_suggestion_count > 0:
        delete_reason_codes.append(CategoryDeleteBlockedReason.RAW_SUGGESTIONS)
    if row.child_category_count > 0:
        delete_reason_codes.append(CategoryDeleteBlockedReason.CHILD_CATEGORIES)
    return CategorySummaryDto(
        id=category.id,
        name=category.name,
        kind=category.kind,
        is_active=category.is_active,
        is_system=category.is_system,
        system_key=category.system_key,
        notes=category.notes,
        operation_count=row.operation_count,
        rule_count=row.rule_count,
        active_rule_count=row.active_rule_count,
        delete_blockers=CategoryDeleteBlockersDto(
            operation_count=row.delete_operation_count,
            rule_count=row.rule_count,
            raw_suggestion_count=row.raw_suggestion_count,
            child_category_count=row.child_category_count,
            reason_codes=delete_reason_codes,
        ),
        updated_at=category.updated_at,
        capabilities=CategorySummaryCapabilitiesDto(
            can_update=can_write and is_custom,
            can_archive=(can_write and is_custom and category.is_active and not archive_blocked),
            can_restore=can_write and is_custom and not category.is_active,
            can_delete=(
                can_write and is_custom and not category.is_active and not delete_reason_codes
            ),
            archive_blocked_reason_code=(
                CategoryArchiveBlockedReason.ACTIVE_RULES if archive_blocked else None
            ),
        ),
    )


def category_kind_options() -> list[CategoryKindOptionDto]:
    return [
        CategoryKindOptionDto(
            value=CategoryKind.INCOME,
            label="Доход",
            description="Для поступлений, которые могут влиять на финансовый результат.",
        ),
        CategoryKindOptionDto(
            value=CategoryKind.EXPENSE,
            label="Расход",
            description="Для списаний, которые могут влиять на финансовый результат.",
        ),
        CategoryKindOptionDto(
            value=CategoryKind.TRANSFER,
            label="Перевод",
            description="Для перемещения денег между счетами без влияния на прибыль.",
        ),
        CategoryKindOptionDto(
            value=CategoryKind.ADJUSTMENT,
            label="Корректировка",
            description=(
                "Для технических изменений баланса, которые не считаются доходом или расходом."
            ),
        ),
        CategoryKindOptionDto(
            value=CategoryKind.MIXED,
            label="Смешанная",
            description="Для категории, применимой и к поступлениям, и к списаниям.",
        ),
    ]
