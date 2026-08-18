from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.debts.domain import DebtKind
from app.features.ledger.domain.types import OperationType
from app.features.users.models import User
from app.features.workspaces.activity_repository import WorkspaceActivityRepository
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
    WorkspaceActivityEntityDto,
    WorkspaceActivityEntityType,
    WorkspaceActivityItemDto,
    WorkspaceActivityItemScope,
    WorkspaceActivityScope,
    WorkspaceActivitySummaryCode,
)

DEFAULT_ACTIVITY_LIMIT = 50
MAX_ACTIVITY_LIMIT = 100
TEAM_ACTIVITY_EVENT_TYPES = frozenset(
    {
        WorkspaceAuditEventType.WORKSPACE_CREATED,
        WorkspaceAuditEventType.WORKSPACE_UPDATED,
        WorkspaceAuditEventType.WORKSPACE_DEACTIVATED,
        WorkspaceAuditEventType.WORKSPACE_RESTORED,
        WorkspaceAuditEventType.OWNERSHIP_TRANSFERRED,
        WorkspaceAuditEventType.INVITATION_CREATED,
        WorkspaceAuditEventType.INVITATION_ACCEPTED,
        WorkspaceAuditEventType.INVITATION_REVOKED,
        WorkspaceAuditEventType.MEMBER_ROLE_CHANGED,
        WorkspaceAuditEventType.MEMBER_DISABLED,
        WorkspaceAuditEventType.MEMBER_REACTIVATED,
        WorkspaceAuditEventType.MEMBER_LEFT,
    }
)
FINANCE_ACTIVITY_EVENT_TYPES = frozenset(
    {
        WorkspaceAuditEventType.MANUAL_OPERATION_CREATED,
        WorkspaceAuditEventType.MANUAL_OPERATION_UPDATED,
        WorkspaceAuditEventType.MANUAL_OPERATION_CANCELLED,
        WorkspaceAuditEventType.MANUAL_OPERATION_RESTORED,
        WorkspaceAuditEventType.MANUAL_OPERATION_DELETED,
        WorkspaceAuditEventType.IMPORT_REVIEW_ITEM_CONFIRMED,
        WorkspaceAuditEventType.IMPORT_REVIEW_TRANSFER_CREATED,
        WorkspaceAuditEventType.IMPORT_REVIEW_OPERATION_LINKED,
        WorkspaceAuditEventType.IMPORT_REVIEW_POSTING_UNDONE,
        WorkspaceAuditEventType.IMPORT_REVIEW_OPERATION_UNLINKED,
        WorkspaceAuditEventType.IMPORTED_OPERATION_UPDATED,
        WorkspaceAuditEventType.DEBT_CREATED,
        WorkspaceAuditEventType.DEBT_PAYMENT_RECORDED,
        WorkspaceAuditEventType.DEBT_PAYMENT_UNDONE,
        WorkspaceAuditEventType.DEBT_UPDATED,
        WorkspaceAuditEventType.DEBT_ARCHIVED,
        WorkspaceAuditEventType.DEBT_RESTORED,
        WorkspaceAuditEventType.DEBT_DELETED,
        WorkspaceAuditEventType.DOCUMENT_UPLOADED,
    }
)
ACTIVITY_EVENT_TYPES_BY_SCOPE = {
    WorkspaceActivityScope.ALL: None,
    WorkspaceActivityScope.FINANCE: FINANCE_ACTIVITY_EVENT_TYPES,
    WorkspaceActivityScope.TEAM: TEAM_ACTIVITY_EVENT_TYPES,
}
ACTIVITY_ITEM_SCOPE_BY_EVENT_TYPE = {
    event_type: (
        WorkspaceActivityItemScope.TEAM
        if event_type in TEAM_ACTIVITY_EVENT_TYPES
        else WorkspaceActivityItemScope.FINANCE
    )
    for event_type in WorkspaceAuditEventType
}
SUPPORTED_ENTITY_TYPES = frozenset(WorkspaceActivityEntityType)


class WorkspaceActivityService:
    def __init__(self, session: AsyncSession) -> None:
        self._workspaces = WorkspaceRepository(session)
        self._activity = WorkspaceActivityRepository(session)

    async def read(
        self,
        *,
        actor_user_id: UUID,
        workspace_id: UUID,
        limit: int = DEFAULT_ACTIVITY_LIMIT,
        scope: WorkspaceActivityScope = WorkspaceActivityScope.ALL,
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
        events = await self._activity.list_recent(
            workspace_id,
            limit=page_limit + 1,
            before_created_at=before_created_at,
            before_id=before_id,
            event_types=ACTIVITY_EVENT_TYPES_BY_SCOPE[scope],
        )
        page = events[:page_limit]
        available_entities = await self._activity.available_entity_keys(
            workspace_id,
            activity_entity_ids(page),
        )
        last = page[-1] if len(events) > page_limit else None
        return WorkspaceActivityDto(
            workspace_id=workspace_id,
            items=[activity_item(event, available_entities) for event in page],
            next_cursor=(
                WorkspaceActivityCursorDto(
                    before_created_at=last.created_at,
                    before_id=last.id,
                    scope=scope,
                )
                if last is not None
                else None
            ),
        )


def activity_item(
    event: WorkspaceAuditEvent,
    available_entities: frozenset[tuple[WorkspaceActivityEntityType, UUID]] = frozenset(),
) -> WorkspaceActivityItemDto:
    details = event.details or {}
    return WorkspaceActivityItemDto(
        id=event.id,
        event_type=event.event_type,
        scope=ACTIVITY_ITEM_SCOPE_BY_EVENT_TYPE[event.event_type],
        actor=activity_actor(event.actor),
        target=activity_actor(event.target_user),
        entity=activity_entity(event, details, available_entities),
        summary_code=activity_summary(event.event_type, _string(details.get("action"))),
        details=WorkspaceActivityDetailsDto(
            payload_version=_integer(details.get("payload_version")),
            display_label=_string(details.get("display_label")),
            operation_type=_enum_value(
                OperationType,
                _string(details.get("operation_type")),
            ),
            document_id=_uuid(details.get("document_id")),
            item_id=_uuid(details.get("item_id")),
            affected_item_count=_integer(details.get("affected_item_count")),
            affected_document_count=_integer(details.get("affected_document_count")),
            debt_kind=_enum_value(DebtKind, _string(details.get("debt_kind"))),
            payment_id=_uuid(details.get("payment_id")),
            display_filename=_string(details.get("display_filename")),
            role=_enum_value(WorkspaceRole, _string(details.get("role"))),
            invitee_email=_string(details.get("invitee_email")),
            old_role=_enum_value(WorkspaceRole, _string(details.get("old_role"))),
            new_role=_enum_value(WorkspaceRole, _string(details.get("new_role"))),
            old_status=_enum_value(
                WorkspaceMemberStatus,
                _string(details.get("old_status")),
            ),
            new_status=_enum_value(
                WorkspaceMemberStatus,
                _string(details.get("new_status")),
            ),
            old_name=_string(details.get("old_name")),
            new_name=_string(details.get("new_name")),
            old_type=_enum_value(WorkspaceType, _string(details.get("old_type"))),
            new_type=_enum_value(WorkspaceType, _string(details.get("new_type"))),
            old_default_currency=_string(details.get("old_default_currency")),
            new_default_currency=_string(details.get("new_default_currency")),
            moved_session_count=_integer(details.get("moved_sessions")),
            revoked_invitation_count=_integer(details.get("revoked_invitations")),
        ),
        created_at=event.created_at,
    )


def activity_entity_ids(
    events: list[WorkspaceAuditEvent],
) -> dict[WorkspaceActivityEntityType, set[UUID]]:
    ids: dict[WorkspaceActivityEntityType, set[UUID]] = {}
    for event in events:
        entity_type = _entity_type(event.entity_type)
        if (
            entity_type is not None
            and entity_type != WorkspaceActivityEntityType.WORKSPACE
            and event.entity_id is not None
        ):
            ids.setdefault(entity_type, set()).add(event.entity_id)
    return ids


def activity_entity(
    event: WorkspaceAuditEvent,
    details: dict[str, object],
    available_entities: frozenset[tuple[WorkspaceActivityEntityType, UUID]],
) -> WorkspaceActivityEntityDto | None:
    entity_type = _entity_type(event.entity_type)
    if entity_type is None or event.entity_id is None:
        return None
    display_label = _string(details.get("display_label")) or _string(
        details.get("display_filename")
    )
    is_available = (
        event.entity_id == event.workspace_id
        if entity_type == WorkspaceActivityEntityType.WORKSPACE
        else (entity_type, event.entity_id) in available_entities
    )
    return WorkspaceActivityEntityDto(
        type=entity_type,
        id=event.entity_id,
        display_label=display_label,
        is_available=is_available,
    )


def _entity_type(value: str) -> WorkspaceActivityEntityType | None:
    try:
        entity_type = WorkspaceActivityEntityType(value)
    except ValueError:
        return None
    return entity_type if entity_type in SUPPORTED_ENTITY_TYPES else None


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


def _string(value: object) -> str | None:
    return value if isinstance(value, str) else None


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


def _integer(value: object) -> int | None:
    try:
        return int(value) if isinstance(value, (int, str)) else None
    except (TypeError, ValueError):
        return None


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None
