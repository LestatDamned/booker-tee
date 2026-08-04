from dataclasses import dataclass
from typing import NoReturn
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_session_token
from app.db.base import utc_now
from app.features.chat_integrations.repository import ChatIntegrationRepository
from app.features.users.models import User, UserSession
from app.features.users.repository import UserRepository
from app.features.workspaces.commands import TransitionWorkspaceLifecycleCommand
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
)
from app.features.workspaces.errors import (
    WorkspaceLifecycleConflictError,
    WorkspaceLifecycleTransitionError,
    WorkspaceNotFoundError,
    WorkspaceSessionNotFoundError,
    WorkspaceSwitchConflictError,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.schemas import (
    WorkspaceLifecycleBlockingReason,
    WorkspaceLifecycleMutationImpactDto,
)


@dataclass(frozen=True)
class WorkspaceLifecycleResult:
    user: User
    workspace: Workspace
    membership: WorkspaceMember
    impact: WorkspaceLifecycleMutationImpactDto


class WorkspaceLifecycleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._chat = ChatIntegrationRepository(session)
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)

    async def deactivate(
        self,
        *,
        actor: User,
        session_token: str,
        workspace_id: UUID,
        command: TransitionWorkspaceLifecycleCommand,
    ) -> WorkspaceLifecycleResult:
        try:
            workspace, actor_session = await self._locked_authority(
                actor=actor,
                session_token=session_token,
                workspace_id=workspace_id,
                command=command,
            )
            if not workspace.is_active:
                self._blocked(
                    "Пространство уже деактивировано.",
                    WorkspaceLifecycleBlockingReason.ALREADY_INACTIVE,
                )
            affected_sessions = await self._users.list_active_sessions_for_workspace_for_update(
                workspace_id
            )
            fallbacks = await self._fallbacks(
                affected_sessions,
                excluded_workspace_id=workspace_id,
            )
            # ponytail: Replace this guard only when sessions gain an explicit
            # no-workspace recovery state; silently creating one on read is unsafe.
            if len(fallbacks) != len({item.user_id for item in affected_sessions}):
                self._blocked(
                    "Сначала создайте другое активное пространство для затронутых сессий.",
                    WorkspaceLifecycleBlockingReason.FALLBACK_REQUIRED,
                )

            now = utc_now()
            workspace.is_active = False
            workspace.archived_at = now
            await self._session.flush()
            for user_id, fallback in fallbacks.items():
                await self._users.move_active_workspace_sessions(
                    user_id=user_id,
                    from_workspace_id=workspace_id,
                    to_workspace_id=fallback.workspace_id,
                )
            revoked_invitation_count = await self._workspaces.revoke_pending_invitations(
                workspace_id,
                revoked_at=now,
            )
            runtime = await self._chat.deactivate_workspace_runtime(
                workspace_id,
                deactivated_at=now,
            )
            impact = WorkspaceLifecycleMutationImpactDto(
                moved_session_count=len(affected_sessions),
                revoked_invitation_count=revoked_invitation_count,
                disabled_integration_connection_count=runtime.connection_count,
                disabled_chat_conversation_binding_count=runtime.conversation_binding_count,
                disabled_chat_identity_binding_count=runtime.identity_binding_count,
                consumed_chat_conversation_state_count=runtime.conversation_state_count,
                failed_integration_delivery_count=runtime.delivery_count,
            )
            await self._audit(
                workspace=workspace,
                actor_user_id=actor.id,
                action="workspace_deactivated",
                impact=impact,
            )
            membership = await self._result_membership(
                actor_session=actor_session,
                actor_user_id=actor.id,
                deactivated_workspace_id=workspace_id,
                fallbacks=fallbacks,
            )
            await self._session.commit()
            return WorkspaceLifecycleResult(
                user=actor,
                workspace=membership.workspace,
                membership=membership,
                impact=impact,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def restore(
        self,
        *,
        actor: User,
        session_token: str,
        workspace_id: UUID,
        command: TransitionWorkspaceLifecycleCommand,
    ) -> WorkspaceLifecycleResult:
        try:
            workspace, actor_session = await self._locked_authority(
                actor=actor,
                session_token=session_token,
                workspace_id=workspace_id,
                command=command,
            )
            if workspace.is_active:
                self._blocked(
                    "Пространство уже активно.",
                    WorkspaceLifecycleBlockingReason.ALREADY_ACTIVE,
                )
            membership = await self._current_membership(
                actor_session=actor_session,
                actor_user_id=actor.id,
            )
            workspace.is_active = True
            workspace.archived_at = None
            await self._session.flush()
            impact = WorkspaceLifecycleMutationImpactDto(
                moved_session_count=0,
                revoked_invitation_count=0,
                disabled_integration_connection_count=0,
                disabled_chat_conversation_binding_count=0,
                disabled_chat_identity_binding_count=0,
                consumed_chat_conversation_state_count=0,
                failed_integration_delivery_count=0,
            )
            await self._audit(
                workspace=workspace,
                actor_user_id=actor.id,
                action="workspace_restored",
                impact=impact,
            )
            await self._session.commit()
            return WorkspaceLifecycleResult(
                user=actor,
                workspace=membership.workspace,
                membership=membership,
                impact=impact,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def _locked_authority(
        self,
        *,
        actor: User,
        session_token: str,
        workspace_id: UUID,
        command: TransitionWorkspaceLifecycleCommand,
    ) -> tuple[Workspace, UserSession]:
        workspace = await self._workspaces.lock_for_update(workspace_id)
        if workspace is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        membership = await self._workspaces.get_membership_for_update(
            user_id=actor.id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        if (
            membership.status != WorkspaceMemberStatus.ACTIVE
            or membership.role != WorkspaceRole.OWNER
            or workspace.owner_id != actor.id
        ):
            self._blocked(
                "Управление состоянием доступно только владельцу.",
                WorkspaceLifecycleBlockingReason.FORBIDDEN,
            )
        actor_session = await self._users.get_active_session_by_token_hash_for_update(
            hash_session_token(session_token),
            user_id=actor.id,
        )
        if actor_session is None:
            raise WorkspaceSessionNotFoundError("Сессия не найдена.")
        if actor_session.current_workspace_id != command.expected_current_workspace_id:
            raise WorkspaceSwitchConflictError(
                current_workspace_id=actor_session.current_workspace_id
            )
        if workspace.updated_at != command.expected_workspace_updated_at:
            raise WorkspaceLifecycleConflictError(
                "Состояние пространства уже изменилось. Загрузите актуальные данные."
            )
        return workspace, actor_session

    async def _fallbacks(
        self,
        sessions: list[UserSession],
        *,
        excluded_workspace_id: UUID,
    ) -> dict[UUID, WorkspaceMember]:
        fallbacks: dict[UUID, WorkspaceMember] = {}
        for user_id in dict.fromkeys(item.user_id for item in sessions):
            fallback = await (
                self._workspaces.get_first_active_membership_for_user_excluding_for_update(
                    user_id=user_id,
                    excluded_workspace_id=excluded_workspace_id,
                )
            )
            if fallback is not None:
                fallbacks[user_id] = fallback
        return fallbacks

    async def _result_membership(
        self,
        *,
        actor_session: UserSession,
        actor_user_id: UUID,
        deactivated_workspace_id: UUID,
        fallbacks: dict[UUID, WorkspaceMember],
    ) -> WorkspaceMember:
        if actor_session.current_workspace_id == deactivated_workspace_id:
            fallback = fallbacks.get(actor_user_id)
            if fallback is None:
                self._blocked(
                    "Сначала создайте другое активное пространство.",
                    WorkspaceLifecycleBlockingReason.FALLBACK_REQUIRED,
                )
            return fallback
        return await self._current_membership(
            actor_session=actor_session,
            actor_user_id=actor_user_id,
        )

    async def _current_membership(
        self,
        *,
        actor_session: UserSession,
        actor_user_id: UUID,
    ) -> WorkspaceMember:
        current_workspace_id = actor_session.current_workspace_id
        if current_workspace_id is None:
            raise WorkspaceSwitchConflictError(current_workspace_id=None)
        membership = await self._workspaces.get_active_membership_for_update(
            user_id=actor_user_id,
            workspace_id=current_workspace_id,
        )
        if membership is None:
            raise WorkspaceSwitchConflictError(current_workspace_id=current_workspace_id)
        return membership

    async def _audit(
        self,
        *,
        workspace: Workspace,
        actor_user_id: UUID,
        action: str,
        impact: WorkspaceLifecycleMutationImpactDto,
    ) -> None:
        await self._workspaces.create_audit_event(
            workspace_id=workspace.id,
            event_type=WorkspaceAuditEventType.WORKSPACE_UPDATED,
            actor_user_id=actor_user_id,
            entity_type="workspace",
            entity_id=workspace.id,
            details={
                "action": action,
                "moved_sessions": str(impact.moved_session_count),
                "revoked_invitations": str(impact.revoked_invitation_count),
                "disabled_integrations": str(impact.disabled_integration_connection_count),
                "disabled_chat_bindings": str(
                    impact.disabled_chat_identity_binding_count
                    + impact.disabled_chat_conversation_binding_count
                ),
            },
        )

    @staticmethod
    def _blocked(
        message: str,
        reason: WorkspaceLifecycleBlockingReason,
    ) -> NoReturn:
        raise WorkspaceLifecycleTransitionError(message, reason_codes=[reason.value])
