from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.features.debts.creation import DebtCreateOutcome
from app.features.debts.domain import DebtKind
from app.features.debts.maintenance import DeletedDebt
from app.features.debts.payments import DebtPaymentMutationOutcome
from app.features.debts.schemas import (
    AddExistingDebtCommand,
    DebtLifecycleCommand,
    DeleteDebtCommand,
    RecordDebtPaymentCommand,
    UndoDebtPaymentCommand,
    UpdateDebtCommand,
)
from app.features.debts.service import DebtService


@pytest.mark.asyncio
async def test_debt_service_records_one_event_per_committed_command() -> None:
    account_id = uuid4()
    payment_id = uuid4()
    debt = SimpleNamespace(account_id=account_id, kind=DebtKind.LOAN_PAYABLE)
    payment = SimpleNamespace(id=payment_id, debt_account_id=account_id)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = DebtService(cast(Any, session))
    service.creator = cast(
        Any,
        SimpleNamespace(
            add_existing_debt=AsyncMock(
                return_value=DebtCreateOutcome(debt=cast(Any, debt), replayed=False)
            )
        ),
    )
    service.payment_recorder = cast(
        Any,
        SimpleNamespace(
            record=AsyncMock(
                return_value=DebtPaymentMutationOutcome(
                    payment=cast(Any, payment),
                    replayed=False,
                )
            )
        ),
    )
    service.payment_reverser = cast(
        Any,
        SimpleNamespace(
            reverse=AsyncMock(
                return_value=DebtPaymentMutationOutcome(
                    payment=cast(Any, payment),
                    replayed=False,
                )
            )
        ),
    )
    service.lifecycle = cast(
        Any,
        SimpleNamespace(archive=AsyncMock(return_value=debt), restore=AsyncMock(return_value=debt)),
    )
    service.details_editor = cast(Any, SimpleNamespace(update=AsyncMock(return_value=debt)))
    service.deleter = cast(
        Any,
        SimpleNamespace(
            delete=AsyncMock(return_value=DeletedDebt(account_id=account_id, name="Кредит"))
        ),
    )
    activity = SimpleNamespace(
        debt_created=AsyncMock(),
        debt_payment_recorded=AsyncMock(),
        debt_payment_undone=AsyncMock(),
        debt_archived=AsyncMock(),
        debt_restored=AsyncMock(),
        debt_updated=AsyncMock(),
        debt_deleted=AsyncMock(),
    )
    service.activity = cast(Any, activity)
    context = cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=uuid4()),
            user=SimpleNamespace(id=uuid4()),
        ),
    )
    now = datetime(2026, 8, 10, tzinfo=UTC)

    await service.add_existing_debt(context=context, command=create_command())
    await service.record_payment(
        context=context,
        command=RecordDebtPaymentCommand(
            debt_account_id=account_id,
            settlement_account_id=uuid4(),
            principal_amount=Decimal("10"),
            interest_amount=Decimal("0"),
            operation_date=date(2026, 8, 10),
            interest_category_id=None,
            description=None,
            notes=None,
            idempotency_key=uuid4(),
        ),
    )
    await service.undo_payment(
        context=context,
        command=UndoDebtPaymentCommand(
            payment_id=payment_id,
            expected_principal_operation_version=1,
            expected_interest_operation_version=None,
        ),
    )
    await service.archive(
        context=context,
        command=DebtLifecycleCommand(
            debt_account_id=account_id,
            expected_active=True,
            expected_updated_at=now,
        ),
    )
    await service.restore(
        context=context,
        command=DebtLifecycleCommand(
            debt_account_id=account_id,
            expected_active=False,
            expected_updated_at=now,
        ),
    )
    await service.update(
        context=context,
        command=UpdateDebtCommand(
            debt_account_id=account_id,
            name="Кредит",
            opened_on=None,
            maturity_date=None,
            credit_limit=None,
            notes=None,
            expected_updated_at=now,
        ),
    )
    await service.delete(
        context=context,
        command=DeleteDebtCommand(debt_account_id=account_id, expected_updated_at=now),
    )

    for recorder in vars(activity).values():
        recorder.assert_awaited_once()
    assert session.commit.await_count == 7
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("replayed", [True, False])
async def test_debt_creation_activity_is_idempotent_and_transactional(replayed: bool) -> None:
    debt = SimpleNamespace(account_id=uuid4(), kind=DebtKind.LOAN_PAYABLE)
    session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    service = DebtService(cast(Any, session))
    service.creator = cast(
        Any,
        SimpleNamespace(
            add_existing_debt=AsyncMock(
                return_value=DebtCreateOutcome(debt=cast(Any, debt), replayed=replayed)
            )
        ),
    )
    activity = AsyncMock(side_effect=RuntimeError("activity failed"))
    service.activity = cast(Any, SimpleNamespace(debt_created=activity))
    context = cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=uuid4()),
            user=SimpleNamespace(id=uuid4()),
        ),
    )

    if replayed:
        await service.add_existing_debt(context=context, command=create_command())
        activity.assert_not_awaited()
        session.commit.assert_awaited_once()
        session.rollback.assert_not_awaited()
    else:
        with pytest.raises(RuntimeError, match="activity failed"):
            await service.add_existing_debt(context=context, command=create_command())
        activity.assert_awaited_once()
        session.commit.assert_not_awaited()
        session.rollback.assert_awaited_once()


def create_command() -> AddExistingDebtCommand:
    return AddExistingDebtCommand(
        name="Кредит",
        kind=DebtKind.LOAN_PAYABLE,
        currency="RUB",
        opening_balance=Decimal("100"),
        original_principal=Decimal("100"),
        opened_on=None,
        maturity_date=None,
        notes=None,
        idempotency_key=uuid4(),
    )
