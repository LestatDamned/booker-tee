from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.features.categories.application.directory import CategoryDirectoryService
from app.features.categories.models import Category, CategoryKind
from app.features.categories.service import CategoryManagementRow
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

    directory = await CategoryDirectoryService(source).read(
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

    directory = await CategoryDirectoryService(source).read(
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

    directory = await CategoryDirectoryService(source).read(
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
    )
