from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.commands import UpdateWorkspaceMemberRoleCommand
from app.features.workspaces.errors import WorkspaceError
from app.features.workspaces.models import (
    Workspace,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.service import WorkspaceContext, WorkspaceService


async def test_foreign_and_missing_member_have_same_service_outcome(monkeypatch) -> None:
    context = owner_context()
    foreign_workspace_id = uuid4()
    foreign_member_id = uuid4()
    missing_member_id = uuid4()
    looked_up_workspaces: list[UUID] = []

    class FakeRepository:
        def __init__(self, session: object) -> None:
            self.session = session

        async def lock_for_update(self, workspace_id: UUID):
            return context.workspace if workspace_id == context.workspace.id else None

        async def get_membership_for_update(self, *, user_id: UUID, workspace_id: UUID):
            if user_id == context.user.id and workspace_id == context.workspace.id:
                return context.membership
            return None

        async def get_member_by_id_for_update(
            self,
            *,
            workspace_id: UUID,
            member_id: UUID,
        ) -> SimpleNamespace | None:
            looked_up_workspaces.append(workspace_id)
            if workspace_id == foreign_workspace_id and member_id == foreign_member_id:
                return SimpleNamespace(id=foreign_member_id, workspace_id=foreign_workspace_id)
            return None

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeRepository)
    service = WorkspaceService(
        cast(AsyncSession, NoCommitSession()),
        Settings(auth_secret_key="test-secret"),
    )

    outcomes = []
    for member_id in (foreign_member_id, missing_member_id):
        try:
            await service.update_member_role(
                context=context,
                command=UpdateWorkspaceMemberRoleCommand(
                    member_id=member_id,
                    role=WorkspaceRole.VIEWER,
                ),
            )
        except WorkspaceError as error:
            outcomes.append(str(error))

    assert outcomes == ["Участник не найден.", "Участник не найден."]
    assert looked_up_workspaces == [context.workspace.id, context.workspace.id]


async def test_foreign_and_missing_invitation_have_same_service_outcome(monkeypatch) -> None:
    context = owner_context()
    foreign_workspace_id = uuid4()
    foreign_invitation_id = uuid4()
    missing_invitation_id = uuid4()
    looked_up_workspaces: list[UUID] = []

    class FakeRepository:
        def __init__(self, session: object) -> None:
            self.session = session

        async def get_pending_invitation(
            self,
            *,
            workspace_id: UUID,
            invitation_id: UUID,
        ) -> SimpleNamespace | None:
            looked_up_workspaces.append(workspace_id)
            if workspace_id == foreign_workspace_id and invitation_id == foreign_invitation_id:
                return SimpleNamespace(
                    id=foreign_invitation_id,
                    workspace_id=foreign_workspace_id,
                    status=WorkspaceInvitationStatus.PENDING,
                )
            return None

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeRepository)
    service = WorkspaceService(
        cast(AsyncSession, NoCommitSession()),
        Settings(auth_secret_key="test-secret"),
    )

    outcomes = []
    for invitation_id in (foreign_invitation_id, missing_invitation_id):
        try:
            await service.revoke_invitation(
                context=context,
                invitation_id=invitation_id,
            )
        except WorkspaceError as error:
            outcomes.append(str(error))

    assert outcomes == [
        "Приглашение не найдено или уже недействительно.",
        "Приглашение не найдено или уже недействительно.",
    ]
    assert looked_up_workspaces == [context.workspace.id, context.workspace.id]


class NoCommitSession:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


def owner_context() -> WorkspaceContext:
    workspace_id = uuid4()
    user_id = uuid4()
    return WorkspaceContext(
        user=cast(User, SimpleNamespace(id=user_id, email="owner@example.test")),
        workspace=cast(Workspace, SimpleNamespace(id=workspace_id, name="Current")),
        membership=cast(
            WorkspaceMember,
            SimpleNamespace(
                id=uuid4(),
                workspace_id=workspace_id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            ),
        ),
    )
