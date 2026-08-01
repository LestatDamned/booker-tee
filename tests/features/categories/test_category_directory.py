from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.features.categories.application.directory import CategoryDirectoryService
from app.features.categories.models import Category, CategoryKind
from app.features.categories.schemas import (
    CategoryLifecycleCommand,
    CreateCategoryCommand,
    UpdateCategoryCommand,
)
from app.features.categories.service import CategoryManagementRow, DeletedCategory
from app.features.workspaces.models import WorkspaceType


class CategoryManagementSourceStub:
    def __init__(self, rows: list[CategoryManagementRow]) -> None:
        self.rows = rows
        self.calls: list[tuple[UUID, WorkspaceType | None]] = []

    async def list_management_rows(
        self,
        workspace_id: UUID,
        workspace_type: WorkspaceType | None = None,
    ) -> list[CategoryManagementRow]:
        self.calls.append((workspace_id, workspace_type))
        return self.rows

    async def create_custom(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
        notes: str | None = None,
    ) -> Category:
        raise AssertionError("Read-only test source must not create categories.")

    async def update_custom(self, **_kwargs: object) -> Category:
        raise AssertionError("Read-only test source must not update categories.")

    async def set_active(self, **_kwargs: object) -> Category:
        raise AssertionError("Read-only test source must not change categories.")

    async def delete_archived_custom(self, **_kwargs: object) -> DeletedCategory:
        raise AssertionError("Read-only test source must not delete categories.")


class CategoryMutationSourceStub:
    def __init__(self, category: Category) -> None:
        self.category = category
        self.calls: list[tuple[UUID, str, CategoryKind, str | None]] = []
        self.update_calls: list[dict[str, object]] = []
        self.lifecycle_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    async def create_custom(
        self,
        *,
        workspace_id: UUID,
        name: str,
        kind: CategoryKind,
        notes: str | None = None,
    ) -> Category:
        self.calls.append((workspace_id, name, kind, notes))
        return self.category

    async def update_custom(self, **kwargs: object) -> Category:
        self.update_calls.append(kwargs)
        return self.category

    async def set_active(self, **kwargs: object) -> Category:
        self.lifecycle_calls.append(kwargs)
        self.category.is_active = bool(kwargs["is_active"])
        return self.category

    async def delete_archived_custom(self, **kwargs: object) -> DeletedCategory:
        self.delete_calls.append(kwargs)
        return DeletedCategory(id=self.category.id, name=self.category.name)


@pytest.mark.asyncio
async def test_category_directory_preserves_identity_usage_and_kind_options() -> None:
    workspace_id = uuid4()
    source = CategoryManagementSourceStub(
        [
            category_row(
                workspace_id=workspace_id,
                kind=CategoryKind.EXPENSE,
                operation_count=12,
                rule_count=3,
                active_rule_count=0,
            )
        ]
    )

    directory = await CategoryDirectoryService(source, source).read(
        workspace_id=workspace_id,
        workspace_type=WorkspaceType.PERSONAL,
        can_write=True,
    )

    assert source.calls == [(workspace_id, WorkspaceType.PERSONAL)]
    assert directory.items[0].name == "Продукты"
    assert directory.items[0].operation_count == 12
    assert directory.items[0].rule_count == 3
    assert directory.items[0].capabilities.can_update
    assert directory.items[0].capabilities.can_archive
    assert [option.value for option in directory.kind_options] == list(CategoryKind)
    assert directory.kind_options[2].description.endswith("без влияния на прибыль.")
    assert directory.capabilities.can_create


@pytest.mark.asyncio
async def test_category_directory_blocks_archive_while_active_rules_exist() -> None:
    workspace_id = uuid4()
    source = CategoryManagementSourceStub(
        [
            category_row(
                workspace_id=workspace_id,
                rule_count=2,
                active_rule_count=1,
            )
        ]
    )

    directory = await CategoryDirectoryService(source, source).read(
        workspace_id=workspace_id,
        workspace_type=WorkspaceType.PERSONAL,
        can_write=True,
    )

    item = directory.items[0]
    assert not item.capabilities.can_archive
    assert item.capabilities.archive_blocked_reason_code == "active_rules"
    assert item.active_rule_count == 1


@pytest.mark.asyncio
async def test_system_category_is_immutable_and_viewer_has_no_write_capabilities() -> None:
    workspace_id = uuid4()
    source = CategoryManagementSourceStub(
        [
            category_row(
                workspace_id=workspace_id,
                is_system=True,
                system_key="expense",
            ),
            category_row(workspace_id=workspace_id, name="Продукты"),
        ]
    )

    directory = await CategoryDirectoryService(source, source).read(
        workspace_id=workspace_id,
        workspace_type=WorkspaceType.PERSONAL,
        can_write=False,
    )

    assert directory.capabilities.readonly_reason_code == "financial_write_forbidden"
    assert not directory.capabilities.can_create
    for item in directory.items:
        assert not item.capabilities.can_update
        assert not item.capabilities.can_archive
        assert not item.capabilities.can_restore
        assert not item.capabilities.can_delete


@pytest.mark.asyncio
async def test_category_directory_creates_committed_writable_summary() -> None:
    workspace_id = uuid4()
    category = Category(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Питомцы",
        kind=CategoryKind.EXPENSE,
        is_active=True,
        is_system=False,
        updated_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
    )
    mutations = CategoryMutationSourceStub(category)
    directory = CategoryDirectoryService(
        CategoryManagementSourceStub([]),
        mutations,
    )

    result = await directory.create(
        workspace_id=workspace_id,
        command=CreateCategoryCommand(
            name="Питомцы",
            kind=CategoryKind.EXPENSE,
            notes="Корм и ветеринар",
        ),
    )

    assert mutations.calls == [(workspace_id, "Питомцы", CategoryKind.EXPENSE, "Корм и ветеринар")]
    assert result.name == "Питомцы"
    assert result.operation_count == 0
    assert result.rule_count == 0
    assert result.capabilities.can_update
    assert result.capabilities.can_archive
    assert not result.capabilities.can_delete


@pytest.mark.asyncio
async def test_category_directory_updates_with_optimistic_token_and_usage_counts() -> None:
    workspace_id = uuid4()
    row = category_row(
        workspace_id=workspace_id,
        operation_count=12,
        rule_count=3,
    )
    mutations = CategoryMutationSourceStub(row.category)
    directory = CategoryDirectoryService(
        CategoryManagementSourceStub([row]),
        mutations,
    )

    result = await directory.update(
        workspace_id=workspace_id,
        category_id=row.category.id,
        command=UpdateCategoryCommand(
            name="Еда",
            kind=CategoryKind.MIXED,
            notes="Покупки и возвраты",
            expected_updated_at=row.category.updated_at,
        ),
    )

    assert mutations.update_calls == [
        {
            "workspace_id": workspace_id,
            "category_id": row.category.id,
            "name": "Еда",
            "kind": CategoryKind.MIXED,
            "notes": "Покупки и возвраты",
            "expected_updated_at": row.category.updated_at,
        }
    ]
    assert result.operation_count == 12
    assert result.rule_count == 3


@pytest.mark.asyncio
async def test_category_directory_lifecycle_and_delete_use_server_policy() -> None:
    workspace_id = uuid4()
    row = category_row(workspace_id=workspace_id, is_active=False)
    mutations = CategoryMutationSourceStub(row.category)
    directory = CategoryDirectoryService(CategoryManagementSourceStub([row]), mutations)
    command = CategoryLifecycleCommand(
        expected_status=False,
        expected_updated_at=row.category.updated_at,
    )

    lifecycle = await directory.set_active(
        workspace_id=workspace_id,
        category_id=row.category.id,
        is_active=True,
        command=command,
    )
    deleted = await directory.delete(
        workspace_id=workspace_id,
        category_id=row.category.id,
        command=command,
    )

    assert lifecycle.category.is_active
    assert lifecycle.impact.history_preserved
    assert lifecycle.impact.rules_unchanged
    assert lifecycle.impact.available_for_new_references
    assert deleted.deleted_id == row.category.id
    assert mutations.lifecycle_calls[0]["expected_status"] is False
    assert mutations.delete_calls[0]["expected_updated_at"] == row.category.updated_at


def category_row(
    *,
    workspace_id: UUID,
    name: str = "Продукты",
    kind: CategoryKind = CategoryKind.EXPENSE,
    is_active: bool = True,
    is_system: bool = False,
    system_key: str | None = None,
    operation_count: int = 0,
    rule_count: int = 0,
    active_rule_count: int = 0,
    delete_operation_count: int = 0,
    raw_suggestion_count: int = 0,
    child_category_count: int = 0,
) -> CategoryManagementRow:
    return CategoryManagementRow(
        category=Category(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name,
            kind=kind,
            is_active=is_active,
            is_system=is_system,
            system_key=system_key,
            updated_at=datetime(2026, 8, 1, 8, 30, tzinfo=UTC),
        ),
        operation_count=operation_count,
        rule_count=rule_count,
        active_rule_count=active_rule_count,
        delete_operation_count=delete_operation_count,
        raw_suggestion_count=raw_suggestion_count,
        child_category_count=child_category_count,
    )
