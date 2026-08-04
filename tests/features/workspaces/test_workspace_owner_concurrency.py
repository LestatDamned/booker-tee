from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.features.users.models import User
from app.features.workspaces import service as workspace_service
from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.service import WorkspaceContext, WorkspaceService


async def test_legacy_service_rejects_owner_disable_in_inconsistent_state(monkeypatch) -> None:
    workspace_id = uuid4()
    first_user_id = uuid4()
    second_user_id = uuid4()
    members = {
        first_user_id: owner_member(workspace_id=workspace_id, user_id=first_user_id),
        second_user_id: owner_member(workspace_id=workspace_id, user_id=second_user_id),
    }

    class FakeSession:
        async def commit(self) -> None:
            return None

    class FakeWorkspaceRepository:
        def __init__(self, session: FakeSession) -> None:
            self.session = session

        async def lock_for_update(self, locked_workspace_id: UUID):
            return SimpleNamespace(id=locked_workspace_id)

        async def get_membership_for_update(
            self,
            *,
            user_id: UUID,
            workspace_id: UUID,
        ) -> SimpleNamespace | None:
            member = members.get(user_id)
            return member if member and member.workspace_id == workspace_id else None

        async def get_member_by_id_for_update(
            self,
            *,
            workspace_id: UUID,
            member_id: UUID,
        ) -> SimpleNamespace | None:
            return next(
                (
                    member
                    for member in members.values()
                    if member.workspace_id == workspace_id and member.id == member_id
                ),
                None,
            )

        async def create_audit_event(self, **values: object) -> SimpleNamespace:
            return SimpleNamespace(id=uuid4(), **values)

    monkeypatch.setattr(workspace_service, "WorkspaceRepository", FakeWorkspaceRepository)

    async def disable_other(
        actor_user_id: UUID,
        target_user_id: UUID,
    ) -> WorkspaceMember | BaseException:
        actor_membership = members[actor_user_id]
        service = WorkspaceService(
            cast(AsyncSession, FakeSession()),
            Settings(auth_secret_key="test-secret"),
        )
        try:
            return await service.disable_member(
                context=WorkspaceContext(
                    user=cast(
                        User,
                        SimpleNamespace(id=actor_user_id, email="owner@example.test"),
                    ),
                    workspace=cast(
                        Workspace,
                        SimpleNamespace(id=workspace_id, name="Shared"),
                    ),
                    membership=cast(WorkspaceMember, actor_membership),
                ),
                member_id=members[target_user_id].id,
            )
        except BaseException as error:
            return error

    result = await disable_other(first_user_id, second_user_id)

    assert isinstance(result, BaseException)
    assert "передайте владение" in str(result)
    active_owners = sum(
        member.status == WorkspaceMemberStatus.ACTIVE for member in members.values()
    )
    assert active_owners == 2


def owner_member(*, workspace_id: UUID, user_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=WorkspaceRole.OWNER,
        status=WorkspaceMemberStatus.ACTIVE,
    )
