from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceAuditEventType,
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.errors import (
    WorkspaceActivityForbiddenError,
    WorkspaceNotFoundError,
)
from app.features.workspaces.models import WorkspaceAuditEvent
from app.features.workspaces.permissions import can_view_workspace_activity
from app.features.workspaces.repository import WorkspaceRepository
from app.features.workspaces.schemas import (
    WorkspaceActivityActorDto,
    WorkspaceActivityCursorDto,
    WorkspaceActivityDetailsDto,
    WorkspaceActivityDto,
    WorkspaceActivityItemDto,
    WorkspaceActivitySummaryCode,
)

DEFAULT_ACTIVITY_LIMIT = 50
MAX_ACTIVITY_LIMIT = 100


class WorkspaceActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self._workspaces = WorkspaceRepository(session)

    async def read(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        limit: int = DEFAULT_ACTIVITY_LIMIT,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> WorkspaceActivityDto:
        membership = await self._workspaces.get_visible_membership_for_user(
            user_id=actor_user_id,
            workspace_id=workspace_id,
        )
        if membership is None:
            raise WorkspaceNotFoundError("Workspace не найден.")
        if not can_view_workspace_activity(membership):
            raise WorkspaceActivityForbiddenError("Просмотр активности workspace недоступен.")
        page_limit = min(max(limit, 1), MAX_ACTIVITY_LIMIT)
        events = await self._workspaces.list_recent_audit_events(
            workspace_id,
            limit=page_limit + 1,
            before_created_at=before_created_at,
            before_id=before_id,
        )
        page = events[:page_limit]
        last = page[-1] if len(events) > page_limit else None
        return WorkspaceActivityDto(
            workspace_id=workspace_id,
            items=[activity_item(event) for event in page],
            next_cursor=(
                WorkspaceActivityCursorDto(
                    before_created_at=last.created_at,
                    before_id=last.id,
                )
                if last is not None
                else None
            ),
        )


def activity_item(event: WorkspaceAuditEvent) -> WorkspaceActivityItemDto:
    details = event.details or {}
    return WorkspaceActivityItemDto(
        id=event.id,
        event_type=event.event_type,
        actor=activity_actor(event.actor),
        target=activity_actor(event.target_user),
        summary_code=activity_summary(event.event_type, details.get("action")),
        details=WorkspaceActivityDetailsDto(
            role=_enum_value(WorkspaceRole, details.get("role")),
            invitee_email=details.get("invitee_email") or None,
            old_role=_enum_value(WorkspaceRole, details.get("old_role")),
            new_role=_enum_value(WorkspaceRole, details.get("new_role")),
            old_status=_enum_value(WorkspaceMemberStatus, details.get("old_status")),
            new_status=_enum_value(WorkspaceMemberStatus, details.get("new_status")),
            old_name=details.get("old_name"),
            new_name=details.get("new_name"),
            old_type=_enum_value(WorkspaceType, details.get("old_type")),
            new_type=_enum_value(WorkspaceType, details.get("new_type")),
            old_default_currency=details.get("old_default_currency"),
            new_default_currency=details.get("new_default_currency"),
            moved_session_count=_integer(details.get("moved_sessions")),
            revoked_invitation_count=_integer(details.get("revoked_invitations")),
        ),
        created_at=event.created_at,
    )


def activity_summary(
    event_type: WorkspaceAuditEventType,
    historical_action: str | None,
) -> WorkspaceActivitySummaryCode:
    if historical_action in {
        "workspace_deactivated",
        "workspace_restored",
        "ownership_transferred",
        "member_left",
    }:
        return WorkspaceActivitySummaryCode(historical_action)
    return WorkspaceActivitySummaryCode(event_type.value)


def activity_actor(user: User | None) -> WorkspaceActivityActorDto | None:
    if user is None:
        return None
    return WorkspaceActivityActorDto(
        id=user.id,
        display_name=user.name.strip() if user.name and user.name.strip() else user.email,
    )


def _enum_value[EnumValue: StrEnum](
    enum_type: type[EnumValue],
    value: str | None,
) -> EnumValue | None:
    try:
        return enum_type(value) if value else None
    except (TypeError, ValueError):
        return None


def _integer(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
