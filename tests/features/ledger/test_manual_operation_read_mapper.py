from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from app.features.accounts.models import Account, AccountType
from app.features.ledger.mapping.manual_operations import ManualOperationReadDtoMapper
from app.features.ledger.models import (
    MoneyEntry,
    Operation,
    OperationSource,
    OperationStatus,
    OperationType,
)


def test_transfer_read_model_uses_one_operation_amount_and_explicit_accounts() -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    source = account(workspace_id=workspace_id, name="Основной")
    destination = account(workspace_id=workspace_id, name="Накопительный")
    operation = Operation(
        id=operation_id,
        version=4,
        workspace_id=workspace_id,
        type=OperationType.TRANSFER,
        status=OperationStatus.CONFIRMED,
        affects_profit=False,
        operation_date=date(2026, 7, 21),
        source=OperationSource.MANUAL,
        description="Между счетами",
    )
    operation.money_entries = [
        money_entry(
            workspace_id=workspace_id,
            operation_id=operation_id,
            account_=source,
            amount=Decimal("-1500.00"),
            entry_order=1,
        ),
        money_entry(
            workspace_id=workspace_id,
            operation_id=operation_id,
            account_=destination,
            amount=Decimal("1500.00"),
            entry_order=2,
        ),
    ]

    result = ManualOperationReadDtoMapper.from_model(operation)

    assert result.operation_type is OperationType.TRANSFER
    assert result.money is not None
    assert result.money.amount == Decimal("1500.00")
    assert result.money.currency == "RUB"
    assert result.account is None
    assert result.source_account is not None
    assert result.source_account.id == source.id
    assert result.destination_account is not None
    assert result.destination_account.id == destination.id


def account(*, workspace_id: UUID, name: str) -> Account:
    return Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name=name,
        type=AccountType.CHECKING,
        currency="RUB",
        initial_balance=Decimal("0.00"),
    )


def money_entry(
    *,
    workspace_id: UUID,
    operation_id: UUID,
    account_: Account,
    amount: Decimal,
    entry_order: int,
) -> MoneyEntry:
    return MoneyEntry(
        id=uuid4(),
        workspace_id=workspace_id,
        operation_id=operation_id,
        account_id=account_.id,
        account=account_,
        amount=amount,
        currency=account_.currency,
        entry_order=entry_order,
    )
