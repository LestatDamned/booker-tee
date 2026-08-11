from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import AccountType
from app.features.ledger.domain.types import (
    OperationSource,
    imported_operation_actions,
    manual_operation_actions,
)
from app.features.ledger.mapping.manual_read import ManualOperationReadMapper
from app.features.ledger.models import Operation
from app.features.ledger.repository import LedgerRepository
from app.features.ledger.schemas.listing import (
    DEFAULT_PER_PAGE,
    LedgerPage,
    LedgerPagination,
    OperationFilters,
    normalize_pagination,
)
from app.features.ledger.schemas.operations import (
    DebtOperationProvenanceDto,
    ImportOperationProvenanceDto,
    OperationCapabilitiesDto,
    OperationProvenanceDto,
    OperationReadDto,
    SystemOperationProvenanceDto,
)


class OperationReadMapper:
    @staticmethod
    def from_operation(operation: Operation, *, can_write: bool) -> OperationReadDto:
        manual_projection = ManualOperationReadMapper.from_operation(operation)
        return OperationReadDto.model_validate(
            {
                **manual_projection.model_dump(),
                "source": operation.source,
                "provenance": OperationReadMapper._provenance(operation),
                "capabilities": OperationReadMapper._capabilities(
                    operation,
                    can_write=can_write,
                ),
            }
        )

    @staticmethod
    def _provenance(operation: Operation) -> OperationProvenanceDto | None:
        if operation.source is OperationSource.BANK_PDF:
            raw = operation.raw_transactions[0] if operation.raw_transactions else None
            return ImportOperationProvenanceDto(
                uploaded_document_id=raw.uploaded_document_id if raw else None,
                raw_transaction_id=raw.id if raw else None,
            )
        if operation.source is OperationSource.DEBT:
            debt_entry = next(
                (
                    entry
                    for entry in operation.money_entries
                    if entry.account is not None and entry.account.type is AccountType.DEBT
                ),
                None,
            )
            return DebtOperationProvenanceDto(
                debt_account_id=debt_entry.account_id if debt_entry else None,
            )
        if operation.source is OperationSource.SYSTEM:
            return SystemOperationProvenanceDto()
        return None

    @staticmethod
    def _capabilities(
        operation: Operation,
        *,
        can_write: bool,
    ) -> OperationCapabilitiesDto:
        if not can_write:
            return OperationCapabilitiesDto(readonly_reason="financial_write_forbidden")
        if operation.source is OperationSource.MANUAL:
            actions = manual_operation_actions(operation.status)
            return OperationCapabilitiesDto(
                can_edit=actions.can_edit,
                edit_kind="manual" if actions.can_edit else "none",
                can_cancel=actions.can_cancel,
                can_restore=actions.can_restore,
                can_delete=actions.can_delete,
                readonly_reason=(
                    None
                    if any(
                        (
                            actions.can_edit,
                            actions.can_cancel,
                            actions.can_restore,
                            actions.can_delete,
                        )
                    )
                    else "operation_state_readonly"
                ),
            )
        if operation.source is OperationSource.BANK_PDF:
            can_edit = imported_operation_actions(operation.status).can_edit_review_fields
            return OperationCapabilitiesDto(
                can_edit=can_edit,
                edit_kind="imported" if can_edit else "none",
                readonly_reason=None if can_edit else "operation_state_readonly",
            )
        if operation.source is OperationSource.DEBT:
            return OperationCapabilitiesDto(readonly_reason="source_workflow_required")
        return OperationCapabilitiesDto(readonly_reason="system_operation")


class OperationsReader:
    def __init__(self, session: AsyncSession) -> None:
        self._ledger = LedgerRepository(session)

    async def list(
        self,
        *,
        workspace_id: UUID,
        can_write: bool,
        filters: OperationFilters | None = None,
        pagination: LedgerPagination | None = None,
    ) -> tuple[list[OperationReadDto], LedgerPage]:
        normalized_filters = filters or OperationFilters()
        normalized_pagination = pagination or normalize_pagination(1, DEFAULT_PER_PAGE)
        total = await self._ledger.count_operations_for_workspace(
            workspace_id=workspace_id,
            filters=normalized_filters,
        )
        operations = await self._ledger.list_operations_page_for_workspace(
            workspace_id=workspace_id,
            filters=normalized_filters,
            pagination=normalized_pagination,
        )
        return (
            [
                OperationReadMapper.from_operation(operation, can_write=can_write)
                for operation in operations
            ],
            LedgerPage(
                page=normalized_pagination.page,
                per_page=normalized_pagination.per_page,
                total=total,
            ),
        )

    async def get(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
        can_write: bool,
    ) -> OperationReadDto | None:
        operation = await self._ledger.get_operation_for_workspace(workspace_id, operation_id)
        if operation is None:
            return None
        return OperationReadMapper.from_operation(operation, can_write=can_write)
