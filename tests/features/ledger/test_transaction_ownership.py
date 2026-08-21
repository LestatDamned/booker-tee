from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.features.accounts.models import AccountType
from app.features.categories.service import CategoryService
from app.features.debts.domain import DebtKind
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.manual_mutations import ManualOperationWriter
from app.features.ledger.domain.manual_idempotency import ManualOperationFingerprint
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import LedgerPostingError
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
)


async def test_uncategorized_lookup_does_not_take_commit_ownership() -> None:
    workspace_id = uuid4()
    uncategorized = SimpleNamespace(id=uuid4())
    categories = SimpleNamespace(
        ensure_uncategorized=AsyncMock(return_value=uncategorized),
    )
    resolver = LedgerReferenceResolver(cast(Any, object()))
    resolver.categories = cast(Any, categories)

    assert (
        await resolver.get_category_or_uncategorized(
            workspace_id,
            category_id=None,
        )
        is uncategorized
    )
    categories.ensure_uncategorized.assert_awaited_once_with(workspace_id)


async def test_transfer_category_lookup_does_not_take_commit_ownership() -> None:
    workspace_id = uuid4()
    transfer = SimpleNamespace(id=uuid4())
    categories = SimpleNamespace(ensure_system=AsyncMock(return_value=transfer))
    resolver = LedgerReferenceResolver(cast(Any, object()))
    resolver.categories = cast(Any, categories)

    assert await resolver.get_transfer_category(workspace_id) is transfer
    categories.ensure_system.assert_awaited_once_with(workspace_id, "transfer")


async def test_debt_accounts_cannot_bypass_manual_principal_transfer() -> None:
    workspace_id = uuid4()
    debt_account = SimpleNamespace(id=uuid4(), type=AccountType.DEBT, is_active=True)
    resolver = LedgerReferenceResolver(cast(Any, object()))
    resolver.accounts = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=debt_account)),
    )

    with pytest.raises(LedgerPostingError, match="principal transfers"):
        await resolver.get_transfer_account(workspace_id, debt_account.id)


async def test_credit_card_expense_can_use_debt_account_generically() -> None:
    workspace_id = uuid4()
    debt_account = SimpleNamespace(id=uuid4(), type=AccountType.DEBT, is_active=True)
    resolver = LedgerReferenceResolver(cast(Any, object()))
    resolver.accounts = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=debt_account)),
    )
    resolver.debts = cast(
        Any,
        SimpleNamespace(
            get_for_workspace=AsyncMock(return_value=SimpleNamespace(kind=DebtKind.CREDIT_CARD))
        ),
    )

    assert (
        await resolver.get_income_expense_account(
            workspace_id,
            debt_account.id,
            OperationType.EXPENSE,
        )
        is debt_account
    )


@pytest.mark.parametrize(
    ("kind", "is_active", "operation_type", "message"),
    [
        pytest.param(
            DebtKind.CREDIT_CARD,
            True,
            OperationType.INCOME,
            "only record an expense",
            id="credit-card-income",
        ),
        pytest.param(
            DebtKind.MORTGAGE,
            True,
            OperationType.EXPENSE,
            "Loan and mortgage",
            id="mortgage",
        ),
        pytest.param(
            DebtKind.CREDIT_CARD,
            False,
            OperationType.EXPENSE,
            "archived debt",
            id="archived-credit-card",
        ),
    ],
)
async def test_income_expense_rejects_invalid_debt_account_usage(
    kind: DebtKind,
    is_active: bool,
    operation_type: OperationType,
    message: str,
) -> None:
    workspace_id = uuid4()
    debt_account = SimpleNamespace(id=uuid4(), type=AccountType.DEBT, is_active=is_active)
    resolver = LedgerReferenceResolver(cast(Any, object()))
    resolver.accounts = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=debt_account)),
    )
    resolver.debts = cast(
        Any,
        SimpleNamespace(get_for_workspace=AsyncMock(return_value=SimpleNamespace(kind=kind))),
    )

    with pytest.raises(LedgerPostingError, match=message):
        await resolver.get_income_expense_account(
            workspace_id,
            debt_account.id,
            operation_type,
        )


async def test_category_ensure_system_keeps_commit_with_transaction_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    transfer = SimpleNamespace(id=uuid4())
    session = SimpleNamespace(commit=AsyncMock())
    service = CategoryService(cast(Any, session))
    ensure_defaults = AsyncMock()
    monkeypatch.setattr(service, "ensure_defaults", ensure_defaults)
    service.categories = cast(
        Any,
        SimpleNamespace(
            get_system_category=AsyncMock(return_value=transfer),
        ),
    )

    assert await service.ensure_system(workspace_id, "transfer") is transfer
    ensure_defaults.assert_awaited_once_with(workspace_id)
    session.commit.assert_not_awaited()


class NestedTransactionStub:
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0

    async def __aenter__(self) -> None:
        self.entered += 1

    async def __aexit__(
        self,
        _exception_type: object,
        _exception: object,
        _traceback: object,
    ) -> None:
        self.exited += 1


async def test_idempotency_race_rolls_back_only_savepoint() -> None:
    workspace_id = uuid4()
    idempotency_key = uuid4()
    command = CreateManualIncomeExpenseCommand(
        operation_type=OperationType.INCOME,
        account_id=uuid4(),
        amount=Decimal("10.00"),
        operation_date=date(2026, 7, 30),
        description="Доход",
        category_id=None,
        property_id=None,
        idempotency_key=idempotency_key,
    )
    replay = SimpleNamespace(
        id=uuid4(),
        idempotency_fingerprint=ManualOperationFingerprint.calculate_income_expense(command),
    )
    savepoint = NestedTransactionStub()
    session = SimpleNamespace(
        begin_nested=lambda: savepoint,
        rollback=AsyncMock(),
    )
    operation_lookups = 0

    async def get_operation_by_idempotency_key(**_kwargs: object) -> object | None:
        nonlocal operation_lookups
        operation_lookups += 1
        return None if operation_lookups == 1 else replay

    ledger = SimpleNamespace(
        get_operation_by_idempotency_key=get_operation_by_idempotency_key,
        create_operation=AsyncMock(
            side_effect=IntegrityError(
                "insert operation",
                {},
                RuntimeError("duplicate idempotency key"),
            )
        ),
    )
    references = SimpleNamespace(
        get_income_expense_account=AsyncMock(
            return_value=SimpleNamespace(id=command.account_id, currency="RUB"),
        ),
        get_category_or_uncategorized=AsyncMock(
            return_value=SimpleNamespace(id=uuid4()),
        ),
        get_property=AsyncMock(return_value=None),
    )
    writer = ManualOperationWriter(cast(Any, session))
    writer.ledger = cast(Any, ledger)
    writer.references = cast(Any, references)

    result = await writer.create_income_expense(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=uuid4()),
            ),
        ),
        command=command,
    )

    assert result.operation is replay
    assert result.replayed is True
    assert operation_lookups == 2
    assert savepoint.entered == 1
    assert savepoint.exited == 1
    session.rollback.assert_not_awaited()
