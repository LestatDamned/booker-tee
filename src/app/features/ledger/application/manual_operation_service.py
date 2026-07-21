from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ledger.application.commands import (
    CreateManualOperationCommand,
    CreateManualTransferCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.application.listing import (
    DEFAULT_PER_PAGE,
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
    normalize_pagination,
)
from app.features.ledger.application.manual_operation_dtos import ManualOperationReadDto
from app.features.ledger.application.manual_operations import ManualOperationUseCase
from app.features.ledger.domain.manual_operation_lifecycle import manual_operation_actions
from app.features.ledger.domain.types import OperationSource
from app.features.ledger.errors import (
    ManualOperationNotEditableError,
    ManualOperationNotFoundError,
)
from app.features.ledger.mapping.manual_operations import ManualOperationReadDtoMapper
from app.features.ledger.repository import LedgerRepository
from app.features.workspaces.service import WorkspaceContext


class ManualOperationService:
    def __init__(self, session: AsyncSession) -> None:
        self._ledger = LedgerRepository(session)
        self._use_case = ManualOperationUseCase(session)

    async def list(
        self,
        *,
        workspace_id: UUID,
        filters: ManualOperationFilters | None = None,
        pagination: LedgerPagination | None = None,
    ) -> tuple[list[ManualOperationReadDto], LedgerPage]:
        normalized_filters = filters or ManualOperationFilters()
        normalized_pagination = pagination or normalize_pagination(1, DEFAULT_PER_PAGE)
        operation_count = await self._ledger.count_manual_operations_for_workspace(
            workspace_id=workspace_id,
            filters=normalized_filters,
        )
        operations = await self._ledger.list_manual_operations_page_for_workspace(
            workspace_id=workspace_id,
            filters=normalized_filters,
            pagination=normalized_pagination,
        )
        return (
            [ManualOperationReadDtoMapper.from_model(operation) for operation in operations],
            LedgerPage(
                page=normalized_pagination.page,
                per_page=normalized_pagination.per_page,
                total=operation_count,
            ),
        )

    async def get(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationReadDto | None:
        operation = await self._ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None or operation.source != OperationSource.MANUAL:
            return None
        return ManualOperationReadDtoMapper.from_model(operation)

    async def get_for_edit(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationReadDto:
        operation = await self.get(workspace_id=workspace_id, operation_id=operation_id)
        if operation is None:
            raise ManualOperationNotFoundError()
        if not manual_operation_actions(operation.status).can_edit:
            raise ManualOperationNotEditableError()
        return operation

    async def create(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualOperationCommand,
    ) -> ManualOperationReadDto:
        if isinstance(command, CreateManualTransferCommand):
            operation = await self._use_case.create_transfer(context=context, command=command)
        else:
            operation = await self._use_case.create_income_expense(
                context=context,
                command=command,
            )
        return await self._read_changed(context.workspace.id, operation.id)

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> ManualOperationReadDto:
        operation = await self._use_case.update(context=context, command=command)
        return await self._read_changed(context.workspace.id, operation.id)

    async def cancel(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> ManualOperationReadDto:
        operation = await self._use_case.cancel(
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
        )
        return await self._read_changed(context.workspace.id, operation.id)

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> ManualOperationReadDto:
        operation = await self._use_case.restore(
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
        )
        return await self._read_changed(context.workspace.id, operation.id)

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> None:
        await self._use_case.delete(
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
        )

    async def _read_changed(
        self,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationReadDto:
        operation = await self.get(workspace_id=workspace_id, operation_id=operation_id)
        if operation is None:
            raise RuntimeError("Changed manual operation could not be reloaded.")
        return operation
