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


def test_workspace_permission_matrix_is_explicit() -> None:
    assert role_permissions(WorkspaceRole.VIEWER) == {
        "read": True,
        "write": False,
        "imports": False,
        "raw_imports": True,
        "member_directory": False,
        "members": False,
        "activity": False,
        "workspace": False,
    }
    assert role_permissions(WorkspaceRole.ANALYST) == {
        "read": True,
        "write": False,
        "imports": False,
        "raw_imports": False,
        "member_directory": False,
        "members": False,
        "activity": False,
        "workspace": False,
    }
    assert role_permissions(WorkspaceRole.UPLOADER) == {
        "read": True,
        "write": False,
        "imports": True,
        "raw_imports": True,
        "member_directory": False,
        "members": False,
        "activity": False,
        "workspace": False,
    }
    assert role_permissions(WorkspaceRole.EDITOR) == {
        "read": True,
        "write": True,
        "imports": True,
        "raw_imports": True,
        "member_directory": False,
        "members": False,
        "activity": False,
        "workspace": False,
    }
    assert role_permissions(WorkspaceRole.ADMIN) == {
        "read": True,
        "write": True,
        "imports": True,
        "raw_imports": True,
        "member_directory": True,
        "members": True,
        "activity": True,
        "workspace": False,
    }
    assert role_permissions(WorkspaceRole.OWNER) == {
        "read": True,
        "write": True,
        "imports": True,
        "raw_imports": True,
        "member_directory": True,
        "members": True,
        "activity": True,
        "workspace": True,
    }


@pytest.mark.parametrize(
    "membership_status",
    [
        WorkspaceMemberStatus.PENDING,
        WorkspaceMemberStatus.DISABLED,
        WorkspaceMemberStatus.REMOVED,
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

    try:
        await require_financial_write_context(context)
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "финансовых данных" in str(exc.detail)
    else:
        raise AssertionError("viewer was allowed to write financial data")


async def test_financial_write_dependency_accepts_editor() -> None:
    context = fake_context(role=WorkspaceRole.EDITOR)

    assert await require_financial_write_context(context) is context


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
