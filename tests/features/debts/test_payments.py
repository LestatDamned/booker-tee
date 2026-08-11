from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.categories.models import Category, CategoryKind
from app.features.debts.domain import DebtKind, DebtValidationError
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtIdempotencyConflictError,
    DebtPaymentConflictError,
    DebtPaymentNotFoundError,
)
from app.features.debts.models import Debt, DebtPayment
from app.features.debts.payments import DebtPaymentRecorder, DebtPaymentReverser
from app.features.debts.schemas import RecordDebtPaymentCommand, UndoDebtPaymentCommand
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import Operation
from app.features.users.models import User
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext


class NestedTransactionStub:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: object) -> None:
        return None


class SessionStub:
    def __init__(self) -> None:
        self.flushes = 0

    def begin_nested(self) -> NestedTransactionStub:
        return NestedTransactionStub()

    async def flush(self) -> None:
        self.flushes += 1


class AccountRepositoryStub:
    def __init__(self, accounts: list[Account]) -> None:
        self.accounts = {account.id: account for account in accounts}

    async def get_for_workspace(self, workspace_id: UUID, account_id: UUID) -> Account | None:
        account = self.accounts.get(account_id)
        return account if account is not None and account.workspace_id == workspace_id else None


class DebtRepositoryStub:
    def __init__(self, debt: Debt | None, payment: DebtPayment | None = None) -> None:
        self.debt = debt
        self.payment = payment
        self.created: list[DebtPayment] = []

    async def get_for_workspace_for_update(
        self,
        workspace_id: UUID,
        account_id: UUID,
    ) -> Debt | None:
        if (
            self.debt is not None
            and self.debt.workspace_id == workspace_id
            and self.debt.account_id == account_id
        ):
            return self.debt
        return None

    async def get_payment_by_idempotency_key(
        self,
        workspace_id: UUID,
        idempotency_key: UUID,
    ) -> DebtPayment | None:
        if (
            self.payment is not None
            and self.payment.workspace_id == workspace_id
            and self.payment.idempotency_key == idempotency_key
        ):
            return self.payment
        return None

    async def create_payment(self, payment: DebtPayment) -> DebtPayment:
        payment.id = payment.id or uuid4()
        self.payment = payment
        self.created.append(payment)
        return payment

    async def get_payment_for_workspace_for_update(
        self,
        workspace_id: UUID,
        payment_id: UUID,
    ) -> DebtPayment | None:
        if (
            self.payment is not None
            and self.payment.workspace_id == workspace_id
            and self.payment.id == payment_id
        ):
            return self.payment
        return None


class LedgerRepositoryStub:
    def __init__(self, total: Decimal = Decimal("0.00")) -> None:
        self.total = total
        self.operations: dict[UUID, Operation] = {}

    async def get_confirmed_account_entries_total(self, **_: Any) -> Decimal:
        return self.total

    async def get_operation_for_workspace_for_update(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> Operation | None:
        operation = self.operations.get(operation_id)
        return (
            operation if operation is not None and operation.workspace_id == workspace_id else None
        )


class ReferenceResolverStub:
    def __init__(self, category: Category) -> None:
        self.category = category
        self.transfer_category = Category(
            id=uuid4(),
            workspace_id=category.workspace_id,
            name="Перевод",
            kind=CategoryKind.TRANSFER,
        )

    async def get_transfer_category(self, workspace_id: UUID) -> Category:
        return self.transfer_category

    async def get_category_or_uncategorized(
        self,
        workspace_id: UUID,
        category_id: UUID | None,
    ) -> Category:
        return self.category


class PostingServiceStub:
    def __init__(self) -> None:
        self.transfers: list[dict[str, Any]] = []
        self.interests: list[dict[str, Any]] = []

    async def post_debt_transfer(self, **values: Any) -> Operation:
        self.transfers.append(values)
        return operation(values["context"].workspace.id, OperationType.TRANSFER)

    async def post_debt_interest(self, **values: Any) -> Operation:
        self.interests.append(values)
        return operation(values["context"].workspace.id, values["operation_type"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "principal_source", "interest_type", "interest_amount"),
    [
        (DebtKind.LOAN_RECEIVABLE, "debt", OperationType.INCOME, Decimal("10.00")),
        (DebtKind.LOAN_PAYABLE, "settlement", OperationType.EXPENSE, Decimal("-10.00")),
        (DebtKind.MORTGAGE, "settlement", OperationType.EXPENSE, Decimal("-10.00")),
        (DebtKind.CREDIT_CARD, "settlement", OperationType.EXPENSE, Decimal("-10.00")),
    ],
)
async def test_payment_records_principal_and_interest_with_debt_direction(
    kind: DebtKind,
    principal_source: str,
    interest_type: OperationType,
    interest_amount: Decimal,
) -> None:
    context = workspace_context()
    balance = Decimal("100.00") if kind is DebtKind.LOAN_RECEIVABLE else Decimal("-100.00")
    recorder, debts, posting, debt_account, settlement, category = payment_recorder(
        context,
        kind=kind,
        balance=balance,
    )

    outcome = await recorder.record(
        context=context,
        command=payment_command(debt_account.id, settlement.id, category.id),
    )
    payment = outcome.payment

    assert outcome.replayed is False
    assert len(debts.created) == 1
    expected_source = debt_account if principal_source == "debt" else settlement
    assert posting.transfers[0]["source_account"] is expected_source
    assert posting.transfers[0]["amount"] == Decimal("25.00")
    assert posting.interests[0]["operation_type"] is interest_type
    assert posting.interests[0]["amount"] == interest_amount
    assert payment.principal_operation_id is not None
    assert payment.interest_operation_id is not None


@pytest.mark.asyncio
async def test_payment_supports_principal_only_without_interest_category() -> None:
    context = workspace_context()
    recorder, _, posting, debt_account, settlement, _ = payment_recorder(
        context,
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-100.00"),
    )

    outcome = await recorder.record(
        context=context,
        command=payment_command(
            debt_account.id,
            settlement.id,
            None,
            interest_amount=Decimal("0.00"),
        ),
    )
    payment = outcome.payment

    assert outcome.replayed is False
    assert payment.principal_operation_id is not None
    assert payment.interest_operation_id is None
    assert posting.interests == []


@pytest.mark.asyncio
async def test_payment_supports_interest_only() -> None:
    context = workspace_context()
    recorder, _, posting, debt_account, settlement, category = payment_recorder(
        context,
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-100.00"),
    )

    outcome = await recorder.record(
        context=context,
        command=payment_command(
            debt_account.id,
            settlement.id,
            category.id,
            principal_amount=Decimal("0.00"),
        ),
    )
    payment = outcome.payment

    assert outcome.replayed is False
    assert payment.principal_operation_id is None
    assert payment.interest_operation_id is not None
    assert posting.transfers == []


@pytest.mark.asyncio
async def test_payment_rejects_excessive_principal_and_archived_debt() -> None:
    context = workspace_context()
    recorder, _, _, debt_account, settlement, category = payment_recorder(
        context,
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-20.00"),
    )
    with pytest.raises(DebtValidationError, match="exceeds"):
        await recorder.record(
            context=context,
            command=payment_command(
                debt_account.id,
                settlement.id,
                category.id,
                principal_amount=Decimal("25.00"),
            ),
        )

    debt_account.initial_balance = Decimal("0.00")
    with pytest.raises(DebtValidationError, match="settled"):
        await recorder.record(
            context=context,
            command=payment_command(
                debt_account.id,
                settlement.id,
                category.id,
                idempotency_key=uuid4(),
            ),
        )

    debt_account.is_active = False
    with pytest.raises(DebtAccountUnavailableError, match="not active"):
        await recorder.record(
            context=context,
            command=payment_command(
                debt_account.id,
                settlement.id,
                category.id,
                idempotency_key=uuid4(),
            ),
        )


@pytest.mark.asyncio
async def test_payment_retry_reuses_payment_and_changed_payload_conflicts() -> None:
    context = workspace_context()
    recorder, debts, posting, debt_account, settlement, category = payment_recorder(
        context,
        kind=DebtKind.LOAN_PAYABLE,
        balance=Decimal("-100.00"),
    )
    command = payment_command(debt_account.id, settlement.id, category.id)
    created = await recorder.record(context=context, command=command)

    replay = await recorder.record(context=context, command=command)

    assert replay.payment is created.payment
    assert created.replayed is False
    assert replay.replayed is True
    assert len(debts.created) == 1
    assert len(posting.transfers) == 1
    with pytest.raises(DebtIdempotencyConflictError):
        await recorder.record(
            context=context,
            command=command.model_copy(update={"principal_amount": Decimal("24.00")}),
        )


@pytest.mark.asyncio
async def test_undo_ignores_both_operations_and_replay_is_safe() -> None:
    context = workspace_context()
    principal = operation(context.workspace.id, OperationType.TRANSFER)
    interest = operation(context.workspace.id, OperationType.EXPENSE)
    payment = debt_payment(context.workspace.id, principal.id, interest.id)
    reverser, session = payment_reverser(payment, [principal, interest])
    command = UndoDebtPaymentCommand(
        payment_id=payment.id,
        expected_principal_operation_version=1,
        expected_interest_operation_version=1,
    )

    reversed_outcome = await reverser.reverse(context=context, command=command)
    replay = await reverser.reverse(context=context, command=command)

    assert reversed_outcome.payment.reversed_at is not None
    assert reversed_outcome.replayed is False
    assert replay.payment is payment
    assert replay.replayed is True
    assert principal.status is OperationStatus.IGNORED
    assert interest.status is OperationStatus.IGNORED
    assert principal.updated_by_user_id == context.user.id
    assert interest.updated_by_user_id == context.user.id
    assert session.flushes == 1


@pytest.mark.asyncio
async def test_undo_rejects_stale_version_and_foreign_workspace() -> None:
    context = workspace_context()
    principal = operation(context.workspace.id, OperationType.TRANSFER)
    payment = debt_payment(context.workspace.id, principal.id, None)
    reverser, _ = payment_reverser(payment, [principal])

    with pytest.raises(DebtPaymentConflictError, match="changed"):
        await reverser.reverse(
            context=context,
            command=UndoDebtPaymentCommand(
                payment_id=payment.id,
                expected_principal_operation_version=2,
                expected_interest_operation_version=None,
            ),
        )

    foreign_context = workspace_context()
    with pytest.raises(DebtPaymentNotFoundError):
        await reverser.reverse(
            context=foreign_context,
            command=UndoDebtPaymentCommand(
                payment_id=payment.id,
                expected_principal_operation_version=1,
                expected_interest_operation_version=None,
            ),
        )


def payment_recorder(
    context: WorkspaceContext,
    *,
    kind: DebtKind,
    balance: Decimal,
) -> tuple[
    DebtPaymentRecorder,
    DebtRepositoryStub,
    PostingServiceStub,
    Account,
    Account,
    Category,
]:
    debt_account = account(
        context.workspace.id,
        account_type=AccountType.DEBT,
        initial_balance=balance,
    )
    settlement = account(context.workspace.id, account_type=AccountType.CARD)
    debt = Debt(
        account_id=debt_account.id,
        workspace_id=context.workspace.id,
        kind=kind,
        original_principal=Decimal("100.00") if kind is not DebtKind.CREDIT_CARD else None,
        credit_limit=Decimal("1000.00") if kind is DebtKind.CREDIT_CARD else None,
        creation_idempotency_key=uuid4(),
        creation_fingerprint="a" * 64,
    )
    category = Category(
        id=uuid4(),
        workspace_id=context.workspace.id,
        name="Проценты",
        kind=(CategoryKind.INCOME if kind is DebtKind.LOAN_RECEIVABLE else CategoryKind.EXPENSE),
    )
    session = SessionStub()
    recorder = DebtPaymentRecorder(cast(Any, session))
    debts = DebtRepositoryStub(debt)
    posting = PostingServiceStub()
    recorder.accounts = cast(Any, AccountRepositoryStub([debt_account, settlement]))
    recorder.debts = cast(Any, debts)
    recorder.ledger = cast(Any, LedgerRepositoryStub())
    recorder.references = cast(Any, ReferenceResolverStub(category))
    recorder.posting = cast(Any, posting)
    return recorder, debts, posting, debt_account, settlement, category


def payment_reverser(
    payment: DebtPayment,
    operations: list[Operation],
) -> tuple[DebtPaymentReverser, SessionStub]:
    session = SessionStub()
    reverser = DebtPaymentReverser(cast(Any, session))
    reverser.debts = cast(Any, DebtRepositoryStub(None, payment))
    ledger = LedgerRepositoryStub()
    ledger.operations = {operation.id: operation for operation in operations}
    reverser.ledger = cast(Any, ledger)
    return reverser, session


def payment_command(
    debt_account_id: UUID,
    settlement_account_id: UUID,
    interest_category_id: UUID | None,
    *,
    principal_amount: Decimal = Decimal("25.00"),
    interest_amount: Decimal = Decimal("10.00"),
    idempotency_key: UUID | None = None,
) -> RecordDebtPaymentCommand:
    return RecordDebtPaymentCommand(
        debt_account_id=debt_account_id,
        settlement_account_id=settlement_account_id,
        principal_amount=principal_amount,
        interest_amount=interest_amount,
        operation_date=date(2026, 8, 9),
        interest_category_id=interest_category_id,
        description="Платёж",
        notes=" заметка ",
        idempotency_key=idempotency_key or uuid4(),
    )


def debt_payment(
    workspace_id: UUID,
    principal_operation_id: UUID | None,
    interest_operation_id: UUID | None,
) -> DebtPayment:
    return DebtPayment(
        id=uuid4(),
        workspace_id=workspace_id,
        debt_account_id=uuid4(),
        principal_operation_id=principal_operation_id,
        interest_operation_id=interest_operation_id,
        idempotency_key=uuid4(),
        idempotency_fingerprint="b" * 64,
    )


def operation(workspace_id: UUID, operation_type: OperationType) -> Operation:
    return Operation(
        id=uuid4(),
        version=1,
        workspace_id=workspace_id,
        type=operation_type,
        status=OperationStatus.CONFIRMED,
        affects_profit=operation_type is not OperationType.TRANSFER,
        operation_date=date(2026, 8, 9),
        source=OperationSource.DEBT,
    )


def account(
    workspace_id: UUID,
    *,
    account_type: AccountType,
    initial_balance: Decimal = Decimal("0.00"),
) -> Account:
    return Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Счёт",
        type=account_type,
        currency="RUB",
        initial_balance=initial_balance,
        is_active=True,
    )


def workspace_context() -> WorkspaceContext:
    user = User(id=uuid4(), email="debts@example.test", password_hash="hash")
    workspace = Workspace(id=uuid4(), owner_id=user.id, name="Личный", default_currency="RUB")
    membership = WorkspaceMember(id=uuid4(), workspace_id=workspace.id, user_id=user.id)
    return WorkspaceContext(user=user, workspace=workspace, membership=membership)
