from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.features.users.models import User
from app.features.workspaces.dependencies import require_financial_write_context
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.permissions import (
    can_manage_imports,
    can_manage_members,
    can_manage_workspace,
    can_read_workspace,
    can_view_member_directory,
    can_view_raw_import_data,
    can_view_workspace_activity,
    can_write_financial_data,
)
from app.features.workspaces.service import WorkspaceContext


@pytest.mark.parametrize(
    ("role", "expected_permissions"),
    [
        pytest.param(WorkspaceRole.VIEWER, {"read", "raw_imports"}, id="viewer"),
        pytest.param(WorkspaceRole.ANALYST, {"read"}, id="analyst"),
        pytest.param(
            WorkspaceRole.UPLOADER,
            {"read", "imports", "raw_imports"},
            id="uploader",
        ),
        pytest.param(
            WorkspaceRole.EDITOR,
            {"read", "write", "imports", "raw_imports"},
            id="editor",
        ),
        pytest.param(
            WorkspaceRole.ADMIN,
            {"read", "write", "imports", "raw_imports", "member_directory", "members", "activity"},
            id="admin",
        ),
        pytest.param(
            WorkspaceRole.OWNER,
            {
                "read",
                "write",
                "imports",
                "raw_imports",
                "member_directory",
                "members",
                "activity",
                "workspace",
            },
            id="owner",
        ),
    ],
)
def test_workspace_permission_matrix_is_explicit(
    role: WorkspaceRole,
    expected_permissions: set[str],
) -> None:
    permissions = role_permissions(role)

    assert {name for name, allowed in permissions.items() if allowed} == expected_permissions


@pytest.mark.parametrize(
    "membership_status",
    [
        pytest.param(WorkspaceMemberStatus.PENDING, id="pending"),
        pytest.param(WorkspaceMemberStatus.DISABLED, id="disabled"),
        pytest.param(WorkspaceMemberStatus.REMOVED, id="removed"),
    ],
)
def test_inactive_membership_has_no_permissions(
    membership_status: WorkspaceMemberStatus,
) -> None:
    membership = fake_membership(
        role=WorkspaceRole.OWNER,
        status=membership_status,
    )

    assert not can_read_workspace(membership)
    assert not can_write_financial_data(membership)
    assert not can_manage_imports(membership)
    assert not can_view_raw_import_data(membership)
    assert not can_view_member_directory(membership)
    assert not can_manage_members(membership)
    assert not can_view_workspace_activity(membership)
    assert not can_manage_workspace(membership)


async def test_financial_write_dependency_rejects_viewer() -> None:
    context = fake_context(role=WorkspaceRole.VIEWER)

    with pytest.raises(HTTPException) as error:
        await require_financial_write_context(context)

    assert error.value.status_code == 403
    assert "финансовых данных" in str(error.value.detail)


def role_permissions(role: WorkspaceRole) -> dict[str, bool]:
    membership = fake_membership(role=role)
    return {
        "read": can_read_workspace(membership),
        "write": can_write_financial_data(membership),
        "imports": can_manage_imports(membership),
        "raw_imports": can_view_raw_import_data(membership),
        "member_directory": can_view_member_directory(membership),
        "members": can_manage_members(membership),
        "activity": can_view_workspace_activity(membership),
        "workspace": can_manage_workspace(membership),
    }


def fake_context(role: WorkspaceRole) -> WorkspaceContext:
    return WorkspaceContext(
        user=cast(
            User,
            SimpleNamespace(id=uuid4(), email="user@example.com", is_active=True),
        ),
        workspace=cast(
            Workspace,
            SimpleNamespace(id=uuid4(), name="Personal", is_active=True),
        ),
        membership=fake_membership(role=role),
    )


def fake_membership(
    *,
    role: WorkspaceRole,
    status: WorkspaceMemberStatus = WorkspaceMemberStatus.ACTIVE,
) -> WorkspaceMember:
    return cast(
        WorkspaceMember,
        SimpleNamespace(role=role, status=status),
    )
