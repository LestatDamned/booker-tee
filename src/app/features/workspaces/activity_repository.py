from collections.abc import Collection, Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.debts.models import Debt
from app.features.imports.models import UploadedDocument
from app.features.ledger.models import Operation
from app.features.workspaces.domain.types import WorkspaceAuditEventType
from app.features.workspaces.models import WorkspaceAuditEvent
from app.features.workspaces.schemas import WorkspaceActivityEntityType


class WorkspaceActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        workspace_id: UUID,
        event_type: WorkspaceAuditEventType,
        actor_user_id: UUID | None,
        entity_type: str,
        entity_id: UUID | None = None,
        target_user_id: UUID | None = None,
        details: Mapping[str, object] | None = None,
    ) -> WorkspaceAuditEvent:
        event = WorkspaceAuditEvent(
            workspace_id=workspace_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            details=dict(details) if details is not None else None,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_recent(
        self,
        workspace_id: UUID,
        *,
        limit: int,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
        event_types: Collection[WorkspaceAuditEventType] | None = None,
    ) -> list[WorkspaceAuditEvent]:
        statement = (
            select(WorkspaceAuditEvent)
            .options(
                selectinload(WorkspaceAuditEvent.actor),
                selectinload(WorkspaceAuditEvent.target_user),
            )
            .where(WorkspaceAuditEvent.workspace_id == workspace_id)
            .order_by(
                WorkspaceAuditEvent.created_at.desc(),
                WorkspaceAuditEvent.id.desc(),
            )
            .limit(limit)
        )
        if event_types is not None:
            statement = statement.where(WorkspaceAuditEvent.event_type.in_(event_types))
        if before_created_at is not None and before_id is not None:
            statement = statement.where(
                or_(
                    WorkspaceAuditEvent.created_at < before_created_at,
                    and_(
                        WorkspaceAuditEvent.created_at == before_created_at,
                        WorkspaceAuditEvent.id < before_id,
                    ),
                )
            )
        result = await self._session.execute(statement)
        return list(result.scalars().all())

    async def available_entity_keys(
        self,
        workspace_id: UUID,
        entity_ids: Mapping[WorkspaceActivityEntityType, set[UUID]],
    ) -> frozenset[tuple[WorkspaceActivityEntityType, UUID]]:
        available: set[tuple[WorkspaceActivityEntityType, UUID]] = set()
        queries = (
            (WorkspaceActivityEntityType.OPERATION, Operation.id, Operation.workspace_id),
            (WorkspaceActivityEntityType.DEBT, Debt.account_id, Debt.workspace_id),
            (
                WorkspaceActivityEntityType.UPLOADED_DOCUMENT,
                UploadedDocument.id,
                UploadedDocument.workspace_id,
            ),
        )
        for entity_type, id_column, workspace_column in queries:
            ids = entity_ids.get(entity_type)
            if not ids:
                continue
            result = await self._session.execute(
                select(id_column).where(
                    workspace_column == workspace_id,
                    id_column.in_(ids),
                )
            )
            available.update((entity_type, entity_id) for entity_id in result.scalars())
        return frozenset(available)
