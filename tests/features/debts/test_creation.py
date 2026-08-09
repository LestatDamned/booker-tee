from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.accounts.models import Account, AccountType
from app.features.accounts.repository import AccountRepository
from app.features.categories.models import Category
from app.features.debts.creation import DebtCreator
from app.features.debts.domain import DebtKind
from app.features.debts.errors import (
    DebtAccountUnavailableError,
    DebtCurrencyMismatchError,
    DebtIdempotencyConflictError,
)
from app.features.debts.models import Debt
from app.features.debts.repository import DebtRepository
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    GiveLoanCommand,
    OpenCreditCardCommand,
    TakeLoanCommand,
)
from app.features.debts.service import DebtService
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.posting import LedgerPostingService
from app.features.ledger.domain.types import OperationSource, OperationType
from app.features.ledger.models import MoneyEntry, Operation
from app.features.ledger.repository import LedgerRepository
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
        self.commits = 0
        self.rollbacks = 0

    def begin_nested(self) -> NestedTransactionStub:
        return NestedTransactionStub()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class AccountRepositoryStub:
    def __init__(self, external_accounts: list[Account] | None = None) -> None:
        self.external_accounts = {account.id: account for account in external_accounts or []}
        self.created: list[Account] = []

    async def get_for_workspace(self, workspace_id: UUID, account_id: UUID) -> Account | None:
        account = self.external_accounts.get(account_id)
        return account if account is not None and account.workspace_id == workspace_id else None

    async def create(self, account: Account) -> Account:
        if account.id is None:
            account.id = uuid4()
        self.created.append(account)
        return account


class DebtRepositoryStub:
    def __init__(self, *, fail_create: bool = False) -> None:
        self.by_key: dict[tuple[UUID, UUID], Debt] = {}
        self.created: list[Debt] = []
        self.fail_create = fail_create

    async def get_by_creation_idempotency_key(
        self,
        workspace_id: UUID,
        idempotency_key: UUID,
    ) -> Debt | None:
        return self.by_key.get((workspace_id, idempotency_key))

    async def create(self, debt: Debt) -> Debt:
        if self.fail_create:
            raise RuntimeError("debt insert failed")
        self.created.append(debt)
        self.by_key[(debt.workspace_id, debt.creation_idempotency_key)] = debt
        return debt


class ReferenceResolverStub:
    async def get_transfer_category(self, workspace_id: UUID) -> Category:
        return Category(id=uuid4(), workspace_id=workspace_id, name="Перевод")


class PostingServiceStub:
    def __init__(self) -> None:
        self.transfers: list[dict[str, Any]] = []

    async def post_debt_transfer(self, **values: Any) -> Operation:
        self.transfers.append(values)
        return Operation(id=uuid4())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "expected_balance"),
    [
        (DebtKind.LOAN_RECEIVABLE, Decimal("100.00")),
        (DebtKind.LOAN_PAYABLE, Decimal("-100.00")),
        (DebtKind.MORTGAGE, Decimal("-100.00")),
    ],
)
async def test_add_existing_debt_uses_signed_opening_balance_without_operation(
    kind: DebtKind,
    expected_balance: Decimal,
) -> None:
    context = workspace_context()
    creator, accounts, _, posting = debt_creator()

    debt = await creator.add_existing_debt(
        context=context,
        command=AddExistingDebtCommand(
            name="Ипотека",
            kind=kind,
            currency="rub",
            opening_balance=Decimal("100"),
            original_principal=Decimal("120"),
            opened_on=date(2026, 1, 1),
            maturity_date=date(2030, 1, 1),
            notes=None,
            idempotency_key=uuid4(),
        ),
    )

    assert debt.account_id == accounts.created[0].id
    assert accounts.created[0].initial_balance == expected_balance
    assert posting.transfers == []


@pytest.mark.asyncio
async def test_give_loan_creates_receivable_transfer() -> None:
    context = workspace_context()
    funding = regular_account(context.workspace.id, currency="RUB")
    creator, accounts, _, posting = debt_creator([funding])

    debt = await creator.give_loan(
        context=context,
        command=give_loan_command(funding.id),
    )

    debt_account = accounts.created[0]
    assert debt.kind is DebtKind.LOAN_RECEIVABLE
    assert debt_account.initial_balance == Decimal("0.00")
    assert posting.transfers[0]["source_account"] is funding
    assert posting.transfers[0]["destination_account"] is debt_account
    assert posting.transfers[0]["amount"] == Decimal("100.00")


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [DebtKind.LOAN_PAYABLE, DebtKind.MORTGAGE])
async def test_take_loan_creates_payable_transfer(kind: DebtKind) -> None:
    context = workspace_context()
    receiving = regular_account(context.workspace.id, currency="RUB")
    creator, accounts, _, posting = debt_creator([receiving])

    debt = await creator.take_loan(
        context=context,
        command=TakeLoanCommand(
            name="Кредит",
            kind=kind,
            currency="RUB",
            amount=Decimal("100"),
            receiving_account_id=receiving.id,
            operation_date=date(2026, 1, 1),
            opened_on=date(2026, 1, 1),
            maturity_date=date(2030, 1, 1),
            description="Получение кредита",
            notes=None,
            idempotency_key=uuid4(),
        ),
    )

    debt_account = accounts.created[0]
    assert debt.kind is kind
    assert debt_account.initial_balance == Decimal("0.00")
    assert posting.transfers[0]["source_account"] is debt_account
    assert posting.transfers[0]["destination_account"] is receiving


@pytest.mark.asyncio
async def test_open_credit_card_uses_opening_balance_without_fake_operation() -> None:
    context = workspace_context()
    creator, accounts, _, posting = debt_creator()

    debt = await creator.open_credit_card(
        context=context,
        command=OpenCreditCardCommand(
            name="Кредитка",
            currency="RUB",
            credit_limit=Decimal("1000"),
            opening_debt=Decimal("250"),
            opened_on=date(2026, 1, 1),
            notes=None,
            idempotency_key=uuid4(),
        ),
    )

    assert debt.kind is DebtKind.CREDIT_CARD
    assert debt.credit_limit == Decimal("1000.00")
    assert accounts.created[0].initial_balance == Decimal("-250.00")
    assert posting.transfers == []


@pytest.mark.asyncio
async def test_same_creation_retry_replays_and_other_payload_conflicts() -> None:
    context = workspace_context()
    funding = regular_account(context.workspace.id, currency="RUB")
    creator, accounts, debts, posting = debt_creator([funding])
    command = give_loan_command(funding.id)

    created = await creator.give_loan(context=context, command=command)
    replay = await creator.give_loan(context=context, command=command)

    assert replay is created
    assert len(accounts.created) == 1
    assert len(debts.created) == 1
    assert len(posting.transfers) == 1

    with pytest.raises(DebtIdempotencyConflictError):
        await creator.give_loan(
            context=context,
            command=command.model_copy(update={"amount": Decimal("101")}),
        )


@pytest.mark.asyncio
async def test_transfer_account_must_be_active_workspace_owned_and_same_currency() -> None:
    context = workspace_context()
    foreign = regular_account(uuid4(), currency="RUB")
    creator, _, _, _ = debt_creator([foreign])

    with pytest.raises(DebtAccountUnavailableError):
        await creator.give_loan(
            context=context,
            command=give_loan_command(foreign.id),
        )

    wrong_currency = regular_account(context.workspace.id, currency="USD")
    creator, _, _, _ = debt_creator([wrong_currency])
    with pytest.raises(DebtCurrencyMismatchError):
        await creator.give_loan(
            context=context,
            command=give_loan_command(wrong_currency.id),
        )

    inactive = regular_account(context.workspace.id, currency="RUB")
    inactive.is_active = False
    creator, _, _, _ = debt_creator([inactive])
    with pytest.raises(DebtAccountUnavailableError):
        await creator.give_loan(
            context=context,
            command=give_loan_command(inactive.id),
        )


@pytest.mark.asyncio
async def test_debt_service_rolls_back_when_creation_fails_after_account() -> None:
    context = workspace_context()
    session = SessionStub()
    creator, accounts, _, _ = debt_creator(session=session, fail_debt_create=True)
    service = DebtService(cast(AsyncSession, session))
    service.creator = creator

    with pytest.raises(RuntimeError, match="debt insert failed"):
        await service.add_existing_debt(
            context=context,
            command=AddExistingDebtCommand(
                name="Долг",
                kind=DebtKind.LOAN_PAYABLE,
                currency="RUB",
                opening_balance=Decimal("100"),
                original_principal=Decimal("100"),
                opened_on=None,
                maturity_date=None,
                notes=None,
                idempotency_key=uuid4(),
            ),
        )

    assert len(accounts.created) == 1
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_ledger_posting_creates_balanced_non_profit_debt_transfer() -> None:
    context = workspace_context()
    source = regular_account(context.workspace.id, currency="RUB")
    destination = regular_account(context.workspace.id, currency="RUB")
    ledger = LedgerRepositoryStub()
    posting = LedgerPostingService(cast(AsyncSession, SessionStub()))
    posting.ledger = cast(LedgerRepository, ledger)

    operation = await posting.post_debt_transfer(
        context=context,
        source_account=source,
        destination_account=destination,
        amount=Decimal("100"),
        operation_date=date(2026, 1, 1),
        description="Выдан заём",
        transfer_category=Category(
            id=uuid4(),
            workspace_id=context.workspace.id,
            name="Перевод",
        ),
    )

    assert operation.source is OperationSource.DEBT
    assert operation.type is OperationType.TRANSFER
    assert operation.affects_profit is False
    assert [entry.amount for entry in ledger.entries] == [
        Decimal("-100.00"),
        Decimal("100.00"),
    ]
    assert sum(entry.amount for entry in ledger.entries) == Decimal("0.00")


class LedgerRepositoryStub:
    def __init__(self) -> None:
        self.operations: list[Operation] = []
        self.entries: list[MoneyEntry] = []

    async def create_operation(self, operation: Operation) -> Operation:
        self.operations.append(operation)
        return operation

    async def create_money_entry(self, entry: MoneyEntry) -> MoneyEntry:
        self.entries.append(entry)
        return entry


def debt_creator(
    external_accounts: list[Account] | None = None,
    *,
    session: SessionStub | None = None,
    fail_debt_create: bool = False,
) -> tuple[DebtCreator, AccountRepositoryStub, DebtRepositoryStub, PostingServiceStub]:
    session = session or SessionStub()
    accounts = AccountRepositoryStub(external_accounts)
    debts = DebtRepositoryStub(fail_create=fail_debt_create)
    posting = PostingServiceStub()
    creator = DebtCreator(cast(AsyncSession, session))
    creator.accounts = cast(AccountRepository, accounts)
    creator.debts = cast(DebtRepository, debts)
    creator.references = cast(LedgerReferenceResolver, ReferenceResolverStub())
    creator.posting = cast(LedgerPostingService, posting)
    return creator, accounts, debts, posting


def workspace_context() -> WorkspaceContext:
    user_id = uuid4()
    workspace_id = uuid4()
    return WorkspaceContext(
        user=User(id=user_id),
        workspace=Workspace(id=workspace_id),
        membership=WorkspaceMember(
            id=uuid4(),
            workspace_id=workspace_id,
            user_id=user_id,
        ),
    )


def regular_account(workspace_id: UUID, *, currency: str) -> Account:
    return Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной",
        type=AccountType.CARD,
        currency=currency,
        initial_balance=Decimal("0.00"),
        is_active=True,
    )


def give_loan_command(funding_account_id: UUID) -> GiveLoanCommand:
    return GiveLoanCommand(
        name="Займ Ивану",
        currency="RUB",
        amount=Decimal("100"),
        funding_account_id=funding_account_id,
        operation_date=date(2026, 1, 1),
        opened_on=date(2026, 1, 1),
        maturity_date=date(2027, 1, 1),
        description="Выдан заём",
        notes=None,
        idempotency_key=uuid4(),
    )
