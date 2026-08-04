from datetime import datetime
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEvent,
    WorkspaceAuditEventType,
    WorkspaceInvitation,
    WorkspaceInvitationStatus,
    WorkspaceMember,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)


class WorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_for_update(self, workspace_id: UUID) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace).where(Workspace.id == workspace_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_first_active_membership_for_user(
        self,
        user_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .order_by(Workspace.created_at, Workspace.name)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_first_active_membership_for_user_excluding(
        self,
        *,
        user_id: UUID,
        excluded_workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id != excluded_workspace_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .order_by(func.lower(Workspace.name), Workspace.id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_first_active_membership_for_user_excluding_for_update(
        self,
        *,
        user_id: UUID,
        excluded_workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.workspace_id != excluded_workspace_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .order_by(func.lower(Workspace.name), Workspace.id)
            .with_for_update(of=WorkspaceMember)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_membership(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_membership_for_update(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
                Workspace.is_active.is_(True),
            )
            .with_for_update(of=WorkspaceMember)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_membership(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_visible_membership_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_visible_membership_for_user_for_update(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
            .with_for_update(of=Workspace)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_member_by_id(
        self,
        *,
        workspace_id: UUID,
        member_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(
                WorkspaceMember.id == member_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_member_by_id_for_update(
        self,
        *,
        workspace_id: UUID,
        member_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(
                WorkspaceMember.id == member_id,
                WorkspaceMember.workspace_id == workspace_id,
            )
            .with_for_update()
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_members_for_workspace_for_update(
        self,
        workspace_id: UUID,
    ) -> list[WorkspaceMember]:
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def get_membership_for_update(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> WorkspaceMember | None:
        result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
            .with_for_update()
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_active_owners(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.role == WorkspaceRole.OWNER,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
        )
        return result.scalar_one()

    async def list_members_for_workspace(
        self,
        workspace_id: UUID,
        *,
        limit: int | None = None,
    ) -> list[WorkspaceMember]:
        statement = (
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.user))
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(
                case((WorkspaceMember.role == WorkspaceRole.OWNER, 0), else_=1),
                case((WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE, 0), else_=1),
                WorkspaceMember.created_at,
                WorkspaceMember.id,
            )
        )
        if limit is not None:
            statement = statement.limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def list_pending_invitations(
        self,
        workspace_id: UUID,
    ) -> list[WorkspaceInvitation]:
        result = await self.session.execute(
            select(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == WorkspaceInvitationStatus.PENDING,
            )
            .order_by(WorkspaceInvitation.created_at)
        )
        return list(result.scalars().all())

    async def count_pending_invitations(self, workspace_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == WorkspaceInvitationStatus.PENDING,
            )
        )
        return result.scalar_one()

    async def list_recent_audit_events(
        self,
        workspace_id: UUID,
        *,
        limit: int = 20,
    ) -> list[WorkspaceAuditEvent]:
        result = await self.session.execute(
            select(WorkspaceAuditEvent)
            .options(
                selectinload(WorkspaceAuditEvent.actor),
                selectinload(WorkspaceAuditEvent.target_user),
            )
            .where(WorkspaceAuditEvent.workspace_id == workspace_id)
            .order_by(WorkspaceAuditEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_invitation(
        self,
        *,
        workspace_id: UUID,
        invitation_id: UUID,
    ) -> WorkspaceInvitation | None:
        result = await self.session.execute(
            select(WorkspaceInvitation)
            .where(
                WorkspaceInvitation.id == invitation_id,
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == WorkspaceInvitationStatus.PENDING,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_invitation_by_token_hash(
        self,
        token_hash: str,
    ) -> WorkspaceInvitation | None:
        result = await self.session.execute(
            select(WorkspaceInvitation)
            .options(selectinload(WorkspaceInvitation.workspace))
            .where(WorkspaceInvitation.token_hash == token_hash)
            .limit(1)
        )
        return result.scalar_one_or_none()

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

    async def list_visible_memberships_for_user(
        self,
        user_id: UUID,
        *,
        current_workspace_id: UUID,
    ) -> list[WorkspaceMember]:
        """List active memberships, including workspaces that are inactive."""
        result = await self.session.execute(
            select(WorkspaceMember)
            .join(Workspace)
            .options(selectinload(WorkspaceMember.workspace))
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
            .order_by(
                case((Workspace.id == current_workspace_id, 0), else_=1),
                case((Workspace.is_active.is_(True), 0), else_=1),
                func.lower(Workspace.name),
                Workspace.id,
            )
        )
        return list(result.scalars().all())

    async def get_for_owner(self, *, owner_id: UUID, workspace_id: UUID) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace)
            .where(
                Workspace.id == workspace_id,
                Workspace.owner_id == owner_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_owner(self, owner_id: UUID) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace)
            .where(Workspace.owner_id == owner_id)
            .order_by(Workspace.is_active.desc(), Workspace.created_at, Workspace.name)
        )
        return list(result.scalars().all())

    async def create_personal_workspace_with_owner_membership(
        self,
        user_id: UUID,
    ) -> tuple[Workspace, WorkspaceMember]:
        return await self.create_workspace_with_owner_membership(
            owner_id=user_id,
            name="Personal",
            workspace_type=WorkspaceType.PERSONAL,
            default_currency="RUB",
        )

    async def create_personal_workspace(self, user_id: UUID) -> Workspace:
        workspace, _membership = await self.create_personal_workspace_with_owner_membership(user_id)
        return workspace

    async def create_workspace_with_owner_membership(
        self,
        *,
        owner_id: UUID,
        name: str,
        workspace_type: WorkspaceType,
        default_currency: str,
        workspace_id: UUID | None = None,
    ) -> tuple[Workspace, WorkspaceMember]:
        workspace = Workspace(
            owner_id=owner_id,
            name=name,
            type=workspace_type,
            default_currency=default_currency,
        )
        if workspace_id is not None:
            workspace.id = workspace_id
        self.session.add(workspace)
        await self.session.flush()

        membership = WorkspaceMember(
            workspace=workspace,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        )
        self.session.add(membership)
        await self.session.flush()
        return workspace, membership

    async def create_workspace(
        self,
        *,
        owner_id: UUID,
        name: str,
        workspace_type: WorkspaceType,
        default_currency: str,
    ) -> Workspace:
        workspace, _membership = await self.create_workspace_with_owner_membership(
            owner_id=owner_id,
            name=name,
            workspace_type=workspace_type,
            default_currency=default_currency,
        )
        return workspace

    async def create_invitation(
        self,
        *,
        workspace_id: UUID,
        role: WorkspaceRole,
        token_hash: str,
        invited_by_user_id: UUID,
        expires_at: datetime,
    ) -> WorkspaceInvitation:
        invitation = WorkspaceInvitation(
            workspace_id=workspace_id,
            role=role,
            token_hash=token_hash,
            invited_by_user_id=invited_by_user_id,
            expires_at=expires_at,
        )
        self.session.add(invitation)
        await self.session.flush()
        return invitation

    async def create_member(
        self,
        *,
        workspace_id: UUID,
        user_id: UUID,
        role: WorkspaceRole,
        invited_by_user_id: UUID | None = None,
    ) -> WorkspaceMember:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status=WorkspaceMemberStatus.ACTIVE,
            invited_by_user_id=invited_by_user_id,
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def create_audit_event(
        self,
        *,
        workspace_id: UUID,
        event_type: WorkspaceAuditEventType,
        actor_user_id: UUID | None,
        entity_type: str,
        entity_id: UUID | None = None,
        target_user_id: UUID | None = None,
        details: dict[str, str] | None = None,
    ) -> WorkspaceAuditEvent:
        event = WorkspaceAuditEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
        self.session.add(event)
        await self.session.flush()
        return event
