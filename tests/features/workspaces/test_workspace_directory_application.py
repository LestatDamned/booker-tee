from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.features.workspaces.application.directory import WorkspaceDirectoryReader
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.schemas import WorkspaceBlockingReason


async def test_directory_lists_only_source_memberships_without_writes() -> None:
    current_id = uuid4()
    actor_id = uuid4()
    updated_at = datetime(2026, 8, 3, tzinfo=UTC)
    memberships = [
        membership(
            workspace_id=current_id,
            name="Дом",
            role=WorkspaceRole.OWNER,
            active=True,
            updated_at=updated_at,
        ),
        membership(
            workspace_id=uuid4(),
            name="Архив проекта",
            role=WorkspaceRole.VIEWER,
            active=False,
            updated_at=updated_at,
        ),
    ]

    class Source:
        def __init__(self) -> None:
            self.calls = []

        async def list_visible_memberships_for_user(
            self,
            user_id,
            *,
            current_workspace_id,
        ):
            self.calls.append((user_id, current_workspace_id))
            return memberships

    source = Source()
    directory = await WorkspaceDirectoryReader(cast(Any, source)).read_for_user(
        user_id=actor_id,
        current_workspace_id=current_id,
    )

    assert source.calls == [(actor_id, current_id)]
    assert [item.name for item in directory.items] == ["Дом", "Архив проекта"]
    assert directory.items[0].is_current is True
    assert directory.items[0].capabilities.can_select is False
    assert directory.items[0].capabilities.can_deactivate is False
    assert WorkspaceBlockingReason.FALLBACK_REQUIRED in directory.items[0].blocking_reason_codes
    assert directory.items[1].is_active is False
    assert directory.items[1].capabilities.can_select is False
    assert directory.items[1].capabilities.can_restore is False
    assert directory.items[1].blocking_reason_codes == ["workspace_inactive"]


@pytest.mark.parametrize(
    ("role", "manage", "leave"),
    [
        pytest.param(WorkspaceRole.OWNER, True, False, id="owner"),
        pytest.param(WorkspaceRole.ADMIN, True, True, id="admin"),
        pytest.param(WorkspaceRole.EDITOR, False, True, id="editor"),
        pytest.param(WorkspaceRole.UPLOADER, False, True, id="uploader"),
        pytest.param(WorkspaceRole.ANALYST, False, True, id="analyst"),
        pytest.param(WorkspaceRole.VIEWER, False, True, id="viewer"),
    ],
)
async def test_directory_capabilities_are_server_owned(
    role: WorkspaceRole,
    manage: bool,
    leave: bool,
) -> None:
    current_id = uuid4()
    source = SimpleNamespace(list_visible_memberships_for_user=lambda *args, **kwargs: None)

    async def list_memberships(*args, **kwargs):
        return [
            membership(
                workspace_id=current_id,
                name="Shared",
                role=role,
                active=True,
                updated_at=datetime(2026, 8, 3, tzinfo=UTC),
            )
        ]

    source.list_visible_memberships_for_user = list_memberships
    directory = await WorkspaceDirectoryReader(cast(Any, source)).read_for_user(
        user_id=uuid4(),
        current_workspace_id=current_id,
    )

    capabilities = directory.items[0].capabilities
    assert capabilities.can_manage_members is manage
    assert capabilities.can_invite is manage
    assert capabilities.can_leave is leave
    assert capabilities.can_update is (role == WorkspaceRole.OWNER)


def membership(
    *,
    workspace_id,
    name: str,
    role: WorkspaceRole,
    active: bool,
    updated_at: datetime,
):
    workspace = SimpleNamespace(
        id=workspace_id,
        name=name,
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
        is_active=active,
        archived_at=None if active else updated_at,
        updated_at=updated_at,
    )
    return SimpleNamespace(
        workspace=workspace,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
        updated_at=updated_at,
    )
