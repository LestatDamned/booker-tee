from types import SimpleNamespace
from typing import cast

from app.features.workspaces.models import (
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.permissions import can_invite_members, ensure_invitable_role


def test_invitation_permissions_are_small_and_explicit() -> None:
    owner_membership = cast(
        WorkspaceMember,
        SimpleNamespace(
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    )
    viewer_membership = cast(
        WorkspaceMember,
        SimpleNamespace(
            role=WorkspaceRole.VIEWER,
            status=WorkspaceMemberStatus.ACTIVE,
        ),
    )

    assert can_invite_members(owner_membership)
    assert not can_invite_members(viewer_membership)

    try:
        ensure_invitable_role(WorkspaceRole.OWNER)
    except ValueError:
        pass
    else:
        raise AssertionError("owner role was accepted for invite link")
