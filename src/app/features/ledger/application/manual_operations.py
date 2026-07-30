from collections.abc import Awaitable, Sequence
from typing import Protocol, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.ledger.application.manual_mutations import ManualOperationWriter
from app.features.ledger.domain.types import OperationSource, manual_operation_actions
from app.features.ledger.errors import (
    ManualOperationNotEditableError,
    ManualOperationNotFoundError,
)
from app.features.ledger.mapping.operations import ManualOperationReadDtoMapper
from app.features.ledger.repository import LedgerRepository
from app.features.ledger.schemas.listing import (
    DEFAULT_PER_PAGE,
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
    normalize_pagination,
)
from app.features.ledger.schemas.manual import (
    CreateManualOperationCommand,
    CreateManualTransferCommand,
    ManualLedgerAccountOptionDto,
    ManualLedgerNamedOptionDto,
    ManualLedgerReferenceOptionsDto,
    ManualOperationReadDto,
    UpdateManualOperationCommand,
)
from app.features.workspaces.service import WorkspaceContext

WriteResult = TypeVar("WriteResult")


class NamedReferenceRecord(Protocol):
    id: UUID
    name: str


class AccountReferenceRecord(NamedReferenceRecord, Protocol):
    currency: str


class AccountReferenceSource(Protocol):
    async def list_active_accounts(
        self,
        workspace_id: UUID,
    ) -> Sequence[AccountReferenceRecord]: ...


class CategoryReferenceSource(Protocol):
    async def list_active(self, workspace_id: UUID) -> Sequence[NamedReferenceRecord]: ...


class PropertyReferenceSource(Protocol):
    async def list_active(self, workspace_id: UUID) -> Sequence[NamedReferenceRecord]: ...


class ManualLedgerReferenceReader:
    def __init__(
        self,
        *,
        accounts: AccountReferenceSource,
        categories: CategoryReferenceSource,
        properties: PropertyReferenceSource,
    ) -> None:
        self._accounts = accounts
        self._categories = categories
        self._properties = properties

    async def read(self, workspace_id: UUID) -> ManualLedgerReferenceOptionsDto:
        accounts = await self._accounts.list_active_accounts(workspace_id)
        categories = await self._categories.list_active(workspace_id)
        properties = await self._properties.list_active(workspace_id)
        return ManualLedgerReferenceOptionsDto(
            accounts=[
                ManualLedgerAccountOptionDto(
                    id=account.id,
                    name=account.name,
                    currency=account.currency,
                )
                for account in accounts
            ],
            categories=[
                ManualLedgerNamedOptionDto(id=category.id, name=category.name)
                for category in categories
            ],
            properties=[
                ManualLedgerNamedOptionDto(id=property_.id, name=property_.name)
                for property_ in properties
            ],
        )


class ManualOperationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._ledger = LedgerRepository(session)
        self._writer = ManualOperationWriter(session)

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
            mutation = self._writer.create_transfer(context=context, command=command)
        else:
            mutation = self._writer.create_income_expense(
                context=context,
                command=command,
            )
        operation = await self._commit(mutation)
        return await self._read_changed(context.workspace.id, operation.id)

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> ManualOperationReadDto:
        operation = await self._commit(self._writer.update(context=context, command=command))
        return await self._read_changed(context.workspace.id, operation.id)

    async def cancel(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> ManualOperationReadDto:
        operation = await self._commit(
            self._writer.cancel(
                context=context,
                operation_id=operation_id,
                expected_version=expected_version,
            )
        )
        return await self._read_changed(context.workspace.id, operation.id)

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> ManualOperationReadDto:
        operation = await self._commit(
            self._writer.restore(
                context=context,
                operation_id=operation_id,
                expected_version=expected_version,
            )
        )
        return await self._read_changed(context.workspace.id, operation.id)

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> None:
        await self._commit(
            self._writer.delete(
                context=context,
                operation_id=operation_id,
                expected_version=expected_version,
            )
        )

    async def _commit(self, mutation: Awaitable[WriteResult]) -> WriteResult:
        try:
            result = await mutation
            await self._session.commit()
            return result
        except Exception:
            await self._session.rollback()
            raise

    async def _read_changed(
        self,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationReadDto:
        operation = await self.get(workspace_id=workspace_id, operation_id=operation_id)
        if operation is None:
            raise RuntimeError("Changed manual operation could not be reloaded.")
        return operation
