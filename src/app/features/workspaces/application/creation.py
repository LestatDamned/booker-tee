from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.features.workspaces.commands import CreateWorkspaceCommand
from app.features.workspaces.errors import (
    WorkspaceIdempotencyConflictError,
    WorkspaceSessionNotFoundError,
)
from app.features.workspaces.models import (
    Workspace,
    WorkspaceAuditEventType,
    WorkspaceMember,
)
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.service import clean_workspace_name, normalize_currency


@dataclass(frozen=True)
class WorkspaceCreationResult:
    user: User
    workspace: Workspace
    membership: WorkspaceMember
    replayed: bool


class WorkspaceCreator:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._workspaces = WorkspaceRepository(session)

    async def create(
        self,
        *,
        actor: User,
        session_token: UUID | str,
        command: CreateWorkspaceCommand,
        idempotency_key: UUID,
    ) -> WorkspaceCreationResult:
        name = clean_workspace_name(command.name)
        currency = normalize_currency(command.default_currency)
        workspace_id = uuid5(actor.id, f"workspace-create:{idempotency_key}")
        existing = await self._workspaces.get_for_owner(
            owner_id=actor.id,
            workspace_id=workspace_id,
        )
        if existing is not None:
            self._validate_replay(existing, command, name=name, currency=currency)
            return await self._select_created_workspace(
                actor=actor,
                session_token=session_token,
                workspace=existing,
                replayed=True,
            )
        try:
            user_session = await self._lock_session(actor=actor, session_token=session_token)
            workspace, membership = await self._workspaces.create_workspace_with_owner_membership(
                owner_id=actor.id,
                name=name,
                workspace_type=command.workspace_type,
                default_currency=currency,
                workspace_id=workspace_id,
            )
            await self._workspaces.create_audit_event(
                workspace_id=workspace.id,
                event_type=WorkspaceAuditEventType.WORKSPACE_CREATED,
                actor_user_id=actor.id,
                entity_type="workspace",
                entity_id=workspace.id,
                details={
                    "name": workspace.name,
                    "type": workspace.type.value,
                    "default_currency": workspace.default_currency,
                },
            )
            user_session.current_workspace_id = workspace.id
            user_session.last_seen_at = utc_now()
            await self._session.commit()
            return WorkspaceCreationResult(
                user=actor,
                workspace=workspace,
                membership=membership,
                replayed=False,
            )
        except IntegrityError:
            await self._session.rollback()
            existing = await self._workspaces.get_for_owner(
                owner_id=actor.id,
                workspace_id=workspace_id,
            )
            if existing is None:
                raise
            self._validate_replay(existing, command, name=name, currency=currency)
            return await self._select_created_workspace(
                actor=actor,
                session_token=session_token,
                workspace=existing,
                replayed=True,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def _select_created_workspace(
        self,
        *,
        actor: User,
        session_token: UUID | str,
        workspace: Workspace,
        replayed: bool,
    ) -> WorkspaceCreationResult:
        try:
            user_session = await self._lock_session(actor=actor, session_token=session_token)
            membership = await self._workspaces.get_active_membership(
                user_id=actor.id,
                workspace_id=workspace.id,
            )
            if membership is None:
                raise WorkspaceSessionNotFoundError("Workspace недоступен.")
            user_session.current_workspace_id = workspace.id
            user_session.last_seen_at = utc_now()
            await self._session.commit()
            return WorkspaceCreationResult(
                user=actor,
                workspace=workspace,
                membership=membership,
                replayed=replayed,
            )
        except Exception:
            await self._session.rollback()
            raise

    async def _lock_session(self, *, actor: User, session_token: UUID | str):
        user_session = await self._users.get_active_session_for_update(
            session_id=session_token,
            user_id=actor.id,
        )
        if user_session is None:
            raise WorkspaceSessionNotFoundError("Сессия не найдена.")
        return user_session

    @staticmethod
    def _validate_replay(
        workspace: Workspace,
        command: CreateWorkspaceCommand,
        *,
        name: str,
        currency: str,
    ) -> None:
        if (
            workspace.name != name
            or workspace.type != command.workspace_type
            or workspace.default_currency != currency
        ):
            raise WorkspaceIdempotencyConflictError(
                "Idempotency-Key уже использован с другими данными workspace."
            )
