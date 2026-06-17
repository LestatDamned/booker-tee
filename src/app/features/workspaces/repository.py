from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workspaces.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_first_active_for_user(self, user_id: UUID) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace)
            .join(WorkspaceMember)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .order_by(Workspace.created_at)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_for_user(self, user_id: UUID, workspace_id: UUID) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace)
            .join(WorkspaceMember)
            .where(
                Workspace.id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: UUID) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace)
            .join(WorkspaceMember)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .order_by(Workspace.created_at, Workspace.name)
        )
        return list(result.scalars().all())

    async def list_for_owner(self, owner_id: UUID) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace)
            .where(Workspace.owner_id == owner_id)
            .order_by(Workspace.is_active.desc(), Workspace.created_at, Workspace.name)
        )
        return list(result.scalars().all())

    async def create_personal_workspace(self, user_id: UUID) -> Workspace:
        workspace = Workspace(
            owner_id=user_id,
            name="Personal",
            type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )
        self.session.add(workspace)
        await self.session.flush()

        self.session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=user_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
        )
        await self.session.flush()
        return workspace

    async def create_workspace(
        self,
        *,
        owner_id: UUID,
        name: str,
        workspace_type: WorkspaceType,
        default_currency: str,
    ) -> Workspace:
        workspace = Workspace(
            owner_id=owner_id,
            name=name,
            type=workspace_type,
            default_currency=default_currency,
        )
        self.session.add(workspace)
        await self.session.flush()

        self.session.add(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=owner_id,
                role=WorkspaceRole.OWNER,
                status=WorkspaceMemberStatus.ACTIVE,
            )
        )
        await self.session.flush()
        return workspace
