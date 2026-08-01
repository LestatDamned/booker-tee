from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from app.features.categories.models import CategoryKind
from app.features.categories.schemas import (
    CategoryArchiveBlockedReason,
    CategoryDirectoryCapabilitiesDto,
    CategoryDirectoryDto,
    CategoryDirectoryReadonlyReason,
    CategoryKindOptionDto,
    CategorySummaryCapabilitiesDto,
    CategorySummaryDto,
)
from app.features.categories.service import CategoryManagementRow
from app.features.workspaces.models import WorkspaceType


class CategoryManagementSource(Protocol):
    async def list_management_rows(
        self,
        workspace_id: UUID,
        workspace_type: WorkspaceType | None = None,
    ) -> Sequence[CategoryManagementRow]: ...


class CategoryDirectoryService:
    def __init__(self, source: CategoryManagementSource) -> None:
        self._source = source

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


def category_summary(
    row: CategoryManagementRow,
    *,
    can_write: bool,
) -> CategorySummaryDto:
    category = row.category
    is_custom = not category.is_system
    archive_blocked = is_custom and category.is_active and row.active_rule_count > 0
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
        updated_at=category.updated_at,
        capabilities=CategorySummaryCapabilitiesDto(
            can_update=can_write and is_custom,
            can_archive=(can_write and is_custom and category.is_active and not archive_blocked),
            can_restore=can_write and is_custom and not category.is_active,
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
