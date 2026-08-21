from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import FastAPI

from app.api.dependencies import ApiRequestContext, get_api_request_context
from app.api.v1.debts.dependencies import get_debt_reader, get_debt_service
from app.features.debts.domain import DebtDeleteBlockedReason, DebtKind, DebtStatus
from app.features.debts.maintenance import DeletedDebt
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.schemas import (
    DebtCapabilitiesDto,
    DebtCreateCommand,
    DebtCurrencyTotalsDto,
    DebtDetailDto,
    DebtLifecycleCommand,
    DebtPaymentHistoryItemDto,
    DebtPaymentHistoryPageDto,
    DebtPaymentOperationDto,
    DebtPaymentTotalsDto,
    DebtPortfolioDto,
    DebtSummaryDto,
    DeleteDebtCommand,
    RecordDebtPaymentCommand,
    UndoDebtPaymentCommand,
    UpdateDebtCommand,
)
from app.features.ledger.domain.types import OperationStatus, OperationType
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext

NOW = datetime(2026, 8, 9, 8, 30, tzinfo=UTC)


class DebtReaderStub:
    def __init__(self, detail: DebtDetailDto) -> None:
        self.detail = detail
        self.list_calls: list[tuple[UUID, bool]] = []
        self.detail_calls: list[tuple[UUID, UUID, bool, int, int]] = []

    async def list(self, *, workspace_id: UUID, can_write: bool) -> DebtPortfolioDto:
        self.list_calls.append((workspace_id, can_write))
        return DebtPortfolioDto(
            items=[self.detail.debt],
            totals=[
                DebtCurrencyTotalsDto(
                    currency="RUB",
                    receivable=Decimal("0.00"),
                    payable=self.detail.debt.outstanding,
                    net_position=-self.detail.debt.outstanding,
                )
            ],
        )

    async def get_detail(
        self,
        *,
        workspace_id: UUID,
        account_id: UUID,
        can_write: bool,
        payments_page: int = 1,
        payments_page_size: int = 20,
    ) -> DebtDetailDto | None:
        self.detail_calls.append(
            (workspace_id, account_id, can_write, payments_page, payments_page_size)
        )
        if account_id != self.detail.debt.account_id:
            return None
        return self.detail


class DebtServiceStub:
    def __init__(self, debt_account_id: UUID, payment_id: UUID) -> None:
        self.debt_account_id = debt_account_id
        self.payment_id = payment_id
        self.create_calls: list[tuple[WorkspaceContext, DebtCreateCommand]] = []
        self.payment_calls: list[tuple[WorkspaceContext, RecordDebtPaymentCommand]] = []
        self.undo_calls: list[tuple[WorkspaceContext, UndoDebtPaymentCommand]] = []
        self.lifecycle_calls: list[tuple[str, WorkspaceContext, DebtLifecycleCommand]] = []
        self.update_calls: list[tuple[WorkspaceContext, UpdateDebtCommand]] = []
        self.delete_calls: list[tuple[WorkspaceContext, DeleteDebtCommand]] = []
        self.error: Exception | None = None

    async def create(
        self,
        *,
        context: WorkspaceContext,
        command: DebtCreateCommand,
    ) -> Debt:
        self._raise_error()
        self.create_calls.append((context, command))
        return Debt(account_id=self.debt_account_id)

    async def record_payment(
        self,
        *,
        context: WorkspaceContext,
        command: RecordDebtPaymentCommand,
    ) -> DebtPayment:
        self._raise_error()
        self.payment_calls.append((context, command))
        return DebtPayment(id=self.payment_id, debt_account_id=self.debt_account_id)

    async def undo_payment(
        self,
        *,
        context: WorkspaceContext,
        command: UndoDebtPaymentCommand,
    ) -> DebtPayment:
        self._raise_error()
        self.undo_calls.append((context, command))
        return DebtPayment(id=self.payment_id, debt_account_id=self.debt_account_id)

    async def archive(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        self._raise_error()
        self.lifecycle_calls.append(("archive", context, command))
        return Debt(account_id=self.debt_account_id)

    async def restore(
        self,
        *,
        context: WorkspaceContext,
        command: DebtLifecycleCommand,
    ) -> Debt:
        self._raise_error()
        self.lifecycle_calls.append(("restore", context, command))
        return Debt(account_id=self.debt_account_id)

    async def update(
        self,
        *,
        context: WorkspaceContext,
        command: UpdateDebtCommand,
    ) -> Debt:
        self._raise_error()
        self.update_calls.append((context, command))
        return Debt(account_id=self.debt_account_id)

    async def delete(
        self,
        *,
        context: WorkspaceContext,
        command: DeleteDebtCommand,
    ) -> DeletedDebt:
        self._raise_error()
        self.delete_calls.append((context, command))
        return DeletedDebt(account_id=self.debt_account_id, name="Кредит")

    def _raise_error(self) -> None:
        if self.error is not None:
            raise self.error


def debts_app(
    app: FastAPI,
    *,
    role: WorkspaceRole = WorkspaceRole.OWNER,
) -> tuple[FastAPI, DebtReaderStub, DebtServiceStub, ApiRequestContext]:
    context = api_context(role=role)
    detail = debt_detail(context.workspace.workspace.id)
    reader = DebtReaderStub(detail)
    service = DebtServiceStub(
        debt_account_id=detail.debt.account_id,
        payment_id=detail.payments.items[0].payment_id,
    )
    app.dependency_overrides[get_api_request_context] = lambda: context
    app.dependency_overrides[get_debt_reader] = lambda: reader
    app.dependency_overrides[get_debt_service] = lambda: service
    return app, reader, service, context


def debt_detail(workspace_id: UUID) -> DebtDetailDto:
    account_id = uuid4()
    principal = DebtPaymentOperationDto(
        operation_id=uuid4(),
        version=1,
        operation_date=date(2026, 8, 9),
        operation_type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        description="Платёж",
        amount=Decimal("25.00"),
    )
    interest = DebtPaymentOperationDto(
        operation_id=uuid4(),
        version=1,
        operation_date=date(2026, 8, 9),
        operation_type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        description="Проценты",
        amount=Decimal("10.00"),
    )
    return DebtDetailDto(
        debt=DebtSummaryDto(
            account_id=account_id,
            name="Кредит",
            kind=DebtKind.LOAN_PAYABLE,
            currency="RUB",
            balance=Decimal("-75.00"),
            outstanding=Decimal("75.00"),
            status=DebtStatus.ACTIVE,
            opened_on=date(2026, 1, 1),
            original_principal=Decimal("100.00"),
            maturity_date=date(2027, 1, 1),
            credit_limit=None,
            available_credit=None,
            is_active=True,
            updated_at=NOW,
            capabilities=DebtCapabilitiesDto(
                can_record_payment=True,
                can_archive=False,
                can_restore=False,
                can_update=True,
                can_delete=False,
                payment_blocked_reason=None,
                delete_blocked_reason=DebtDeleteBlockedReason.FINANCIAL_HISTORY,
            ),
        ),
        notes="Тестовый долг",
        payment_totals=DebtPaymentTotalsDto(
            principal=Decimal("25.00"),
            interest=Decimal("10.00"),
        ),
        payments=DebtPaymentHistoryPageDto(
            items=[
                DebtPaymentHistoryItemDto(
                    payment_id=uuid4(),
                    principal=principal,
                    interest=interest,
                    notes=None,
                    created_at=NOW,
                    reversed_at=None,
                    can_undo=True,
                )
            ],
            page=1,
            page_size=20,
            total=1,
            total_pages=1,
            has_previous=False,
            has_next=False,
        ),
    )


def api_context(*, role: WorkspaceRole) -> ApiRequestContext:
    user_id = uuid4()
    workspace_id = uuid4()
    user = User(id=user_id, email="debts-api@example.test", password_hash="hash")
    workspace = Workspace(
        id=workspace_id,
        owner_id=user_id,
        name="Debts API",
        type=WorkspaceType.PERSONAL,
        default_currency="RUB",
    )
    membership = WorkspaceMember(
        id=uuid4(),
        workspace_id=workspace_id,
        user_id=user_id,
        role=role,
        status=WorkspaceMemberStatus.ACTIVE,
    )
    return ApiRequestContext(
        workspace=WorkspaceContext(user=user, workspace=workspace, membership=membership),
        csrf_token="csrf",
    )
