from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.manual_ledger.dependencies import (
    get_manual_ledger_reference_reader,
    get_manual_operation_service,
)
from app.features.ledger.domain.types import (
    OperationStatus,
    OperationType,
    manual_operation_actions,
)
from app.features.ledger.errors import (
    LedgerPostingError,
    ManualOperationNotEditableError,
    ManualOperationNotFoundError,
)
from app.features.ledger.schemas.listing import (
    LedgerPage,
    LedgerPagination,
    ManualOperationFilters,
)
from app.features.ledger.schemas.manual import (
    AccountReferenceReadDto,
    CreateManualIncomeExpenseCommand,
    CreateManualOperationCommand,
    CreateManualTransferCommand,
    ManualLedgerAccountOptionDto,
    ManualLedgerNamedOptionDto,
    ManualLedgerReferenceOptionsDto,
    ManualOperationMoneyReadDto,
    ManualOperationReadDto,
    UpdateManualOperationCommand,
)
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext
from app.main import create_app


class ManualOperationServiceStub:
    def __init__(self, operations: list[ManualOperationReadDto]) -> None:
        self.operations = operations
        self.workspace_ids: list[UUID] = []
        self.filters: list[ManualOperationFilters] = []
        self.paginations: list[LedgerPagination] = []
        self.income_commands: list[CreateManualIncomeExpenseCommand] = []
        self.transfer_commands: list[CreateManualTransferCommand] = []
        self.update_commands: list[UpdateManualOperationCommand] = []
        self.lifecycle_calls: list[tuple[str, UUID, int]] = []
        self.create_error: LedgerPostingError | None = None
        self.update_error: LedgerPostingError | None = None
        self.lifecycle_error: LedgerPostingError | None = None

    async def list(
        self,
        *,
        workspace_id: UUID,
        filters: ManualOperationFilters,
        pagination: LedgerPagination,
    ) -> tuple[list[ManualOperationReadDto], LedgerPage]:
        self.workspace_ids.append(workspace_id)
        self.filters.append(filters)
        self.paginations.append(pagination)
        return self.operations, LedgerPage(
            page=pagination.page,
            per_page=pagination.per_page,
            total=len(self.operations),
        )

    async def create(
        self,
        *,
        context: WorkspaceContext,
        command: CreateManualOperationCommand,
    ) -> ManualOperationReadDto:
        if self.create_error is not None:
            raise self.create_error
        self.workspace_ids.append(context.workspace.id)
        if isinstance(command, CreateManualTransferCommand):
            self.transfer_commands.append(command)
        else:
            self.income_commands.append(command)
        return self.operations[-1]

    async def get(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationReadDto | None:
        self.workspace_ids.append(workspace_id)
        return next(
            (operation for operation in self.operations if operation.id == operation_id),
            None,
        )

    async def get_for_edit(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> ManualOperationReadDto:
        self.workspace_ids.append(workspace_id)
        operation = next(
            (operation for operation in self.operations if operation.id == operation_id),
            None,
        )
        if operation is None:
            raise ManualOperationNotFoundError()
        if not manual_operation_actions(operation.status).can_edit:
            raise ManualOperationNotEditableError()
        return operation

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateManualOperationCommand,
    ) -> ManualOperationReadDto:
        if self.update_error is not None:
            raise self.update_error
        self.workspace_ids.append(context.workspace.id)
        self.update_commands.append(command)
        return next(
            operation for operation in self.operations if operation.id == command.operation_id
        )

    async def cancel(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> ManualOperationReadDto:
        return self._change_status(
            action="cancel",
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
            status=OperationStatus.IGNORED,
        )

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> ManualOperationReadDto:
        return self._change_status(
            action="restore",
            context=context,
            operation_id=operation_id,
            expected_version=expected_version,
            status=OperationStatus.CONFIRMED,
        )

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
    ) -> None:
        if self.lifecycle_error is not None:
            raise self.lifecycle_error
        self.workspace_ids.append(context.workspace.id)
        self.lifecycle_calls.append(("delete", operation_id, expected_version))
        self.operations = [
            operation for operation in self.operations if operation.id != operation_id
        ]

    def _change_status(
        self,
        *,
        action: str,
        context: WorkspaceContext,
        operation_id: UUID,
        expected_version: int,
        status: OperationStatus,
    ) -> ManualOperationReadDto:
        if self.lifecycle_error is not None:
            raise self.lifecycle_error
        self.workspace_ids.append(context.workspace.id)
        self.lifecycle_calls.append((action, operation_id, expected_version))
        self.operations = [
            operation.model_copy(update={"status": status, "version": operation.version + 1})
            if operation.id == operation_id
            else operation
            for operation in self.operations
        ]
        return next(operation for operation in self.operations if operation.id == operation_id)


class ManualLedgerReferenceReaderStub:
    def __init__(self) -> None:
        self.workspace_ids: list[UUID] = []
        self.references = ManualLedgerReferenceOptionsDto(
            accounts=[],
            categories=[],
            properties=[],
        )

    async def read(self, workspace_id: UUID) -> ManualLedgerReferenceOptionsDto:
        self.workspace_ids.append(workspace_id)
        return self.references


def manual_ledger_app(
    operations: list[ManualOperationReadDto],
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, ManualOperationServiceStub, ManualLedgerReferenceReaderStub, UUID]:
    app = create_app()
    context = api_context(role=role)
    service = ManualOperationServiceStub(operations)
    reference_reader = ManualLedgerReferenceReaderStub()
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_manual_operation_service] = lambda: service
    app.dependency_overrides[get_manual_ledger_reference_reader] = lambda: reference_reader
    return app, service, reference_reader, context.workspace.workspace.id


def filter_references() -> ManualLedgerReferenceOptionsDto:
    return ManualLedgerReferenceOptionsDto(
        accounts=[
            ManualLedgerAccountOptionDto(
                id=uuid4(),
                name="Основной счёт",
                currency="RUB",
                can_record_income=True,
                can_record_expense=True,
                can_transfer=True,
            )
        ],
        categories=[
            ManualLedgerNamedOptionDto(
                id=uuid4(),
                name="Аренда",
            )
        ],
        properties=[
            ManualLedgerNamedOptionDto(
                id=uuid4(),
                name="Квартира",
            )
        ],
    )


def api_context(*, role: WorkspaceRole) -> ApiRequestContext:
    user_id = uuid4()
    workspace_id = uuid4()
    user = User(id=user_id, email="max@example.test", name="Max", password_hash="hash")
    workspace = Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Personal ledger",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    membership = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    return ApiRequestContext(
        workspace=WorkspaceContext(
            user=user,
            workspace=workspace,
            membership=membership,
        ),
        csrf_token="csrf-token",
    )


def manual_operation(operation_type: OperationType) -> ManualOperationReadDto:
    source_account = account_reference("Основной счёт")
    destination_account = account_reference("Накопительный счёт")
    is_transfer = operation_type == OperationType.TRANSFER
    return ManualOperationReadDto(
        id=uuid4(),
        version=3,
        operation_type=operation_type,
        status=OperationStatus.CONFIRMED,
        operation_date=date(2026, 7, 20),
        description="Аренда за июль",
        money=ManualOperationMoneyReadDto(
            amount=Decimal("65000.00"),
            currency="RUB",
        ),
        account=None if is_transfer else source_account,
        source_account=source_account if is_transfer else None,
        destination_account=destination_account if is_transfer else None,
        category=None,
        property=None,
    )


def primary_account_id(operation: ManualOperationReadDto) -> UUID:
    assert operation.account is not None
    return operation.account.id


def account_reference(name: str) -> AccountReferenceReadDto:
    return AccountReferenceReadDto(
        id=uuid4(),
        name=name,
        currency="RUB",
    )
