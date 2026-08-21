from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI
from manual_ledger_support import (
    ManualLedgerReferenceReaderStub,
    api_context,
    filter_references,
)

from app.api.dependencies import get_api_request_context
from app.api.v1.manual_ledger.dependencies import get_manual_ledger_reference_reader
from app.api.v1.operations.dependencies import get_operations_reader
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.listing import LedgerPage, LedgerPagination, OperationFilters
from app.features.ledger.schemas.manual import (
    AccountReferenceReadDto,
    ManualOperationMoneyReadDto,
)
from app.features.ledger.schemas.operations import (
    DebtOperationProvenanceDto,
    ImportOperationProvenanceDto,
    OperationCapabilitiesDto,
    OperationReadDto,
    SystemOperationProvenanceDto,
)
from app.features.workspaces.domain.types import WorkspaceRole


class OperationsReaderStub:
    def __init__(self, operations: list[OperationReadDto]) -> None:
        self.operations = operations
        self.list_calls: list[tuple[UUID, bool, OperationFilters, LedgerPagination]] = []
        self.get_calls: list[tuple[UUID, UUID, bool]] = []

    async def list(
        self,
        *,
        workspace_id: UUID,
        can_write: bool,
        filters: OperationFilters,
        pagination: LedgerPagination,
    ) -> tuple[list[OperationReadDto], LedgerPage]:
        self.list_calls.append((workspace_id, can_write, filters, pagination))
        return self.operations, LedgerPage(
            page=pagination.page,
            per_page=pagination.per_page,
            total=len(self.operations),
        )

    async def get(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
        can_write: bool,
    ) -> OperationReadDto | None:
        self.get_calls.append((workspace_id, operation_id, can_write))
        return next((item for item in self.operations if item.id == operation_id), None)


def operations_app(
    app: FastAPI,
    operations: list[OperationReadDto],
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[
    FastAPI,
    OperationsReaderStub,
    ManualLedgerReferenceReaderStub,
    UUID,
]:
    context = api_context(role=role)
    reader = OperationsReaderStub(operations)
    references = ManualLedgerReferenceReaderStub()
    references.references = filter_references()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_operations_reader] = lambda: reader
    app.dependency_overrides[get_manual_ledger_reference_reader] = lambda: references
    return app, reader, references, context.workspace.workspace.id


def operation(source: OperationSource) -> OperationReadDto:
    account = AccountReferenceReadDto(
        id=uuid4(),
        name="Основной счёт",
        currency="RUB",
    )
    provenance = None
    capabilities = OperationCapabilitiesDto(readonly_reason="source_workflow_required")
    if source is OperationSource.MANUAL:
        capabilities = OperationCapabilitiesDto(
            can_edit=True,
            edit_kind="manual",
            can_cancel=True,
        )
    elif source is OperationSource.BANK_PDF:
        provenance = ImportOperationProvenanceDto(
            uploaded_document_id=uuid4(),
            raw_transaction_id=uuid4(),
        )
        capabilities = OperationCapabilitiesDto(
            can_edit=True,
            edit_kind="imported",
        )
    elif source is OperationSource.DEBT:
        provenance = DebtOperationProvenanceDto(debt_account_id=uuid4())
    else:
        provenance = SystemOperationProvenanceDto()
        capabilities = OperationCapabilitiesDto(readonly_reason="system_operation")
    return OperationReadDto(
        id=uuid4(),
        version=3,
        operation_type=OperationType.EXPENSE,
        source=source,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 8, 11),
        description="Аренда за август",
        money=ManualOperationMoneyReadDto(amount=Decimal("65000.00"), currency="RUB"),
        account=account,
        source_account=None,
        destination_account=None,
        category=None,
        property=None,
        provenance=provenance,
        capabilities=capabilities,
    )
