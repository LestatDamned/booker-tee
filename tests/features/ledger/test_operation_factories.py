from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from app.features.ledger.application.manual_contracts import (
    CreateManualIncomeExpenseCommand,
    CreateManualTransferCommand,
)
from app.features.ledger.domain.money import affects_profit_for_operation_type
from app.features.ledger.domain.raw_transactions import LedgerPostingPlan
from app.features.ledger.domain.types import (
    OperationSource,
    OperationStatus,
    OperationType,
)
from app.features.ledger.mapping.operations import (
    build_bank_pdf_operation,
    build_bank_pdf_transfer_operation,
    build_manual_income_expense_operation,
    build_manual_transfer_operation,
)
from app.features.workspaces.service import WorkspaceContext


def test_operation_factories_share_confirmed_core_invariants() -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    context = cast(
        WorkspaceContext,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=user_id),
        ),
    )
    category = SimpleNamespace(id=uuid4())
    property_ = SimpleNamespace(id=uuid4())
    raw_transaction = raw_transaction_stub()

    operations = [
        build_manual_income_expense_operation(
            context=context,
            command=CreateManualIncomeExpenseCommand(
                operation_type=OperationType.EXPENSE,
                account_id=uuid4(),
                amount=Decimal("100.00"),
                operation_date=date(2026, 7, 21),
                description="Расход",
                category_id=category.id,
                property_id=property_.id,
            ),
            category=cast(Any, category),
            property_=cast(Any, property_),
        ),
        build_manual_transfer_operation(
            context=context,
            command=CreateManualTransferCommand(
                source_account_id=uuid4(),
                destination_account_id=uuid4(),
                amount=Decimal("100.00"),
                operation_date=date(2026, 7, 21),
                description="Перевод",
            ),
            transfer_category=cast(Any, category),
        ),
        build_bank_pdf_operation(
            context=context,
            document_id=uuid4(),
            raw_transaction=cast(Any, raw_transaction),
            plan=LedgerPostingPlan(
                operation_type=OperationType.INCOME,
                amount=Decimal("100.00"),
                currency="RUB",
                operation_date=date(2026, 7, 21),
                posting_date=None,
                description="Доход",
                balance_after=None,
            ),
            category=cast(Any, category),
            property_=cast(Any, property_),
        ),
        build_bank_pdf_transfer_operation(
            context=context,
            raw_transaction=cast(Any, raw_transaction),
            matched_raw_transaction=None,
            transfer_category=cast(Any, category),
        ),
    ]

    assert [operation.source for operation in operations] == [
        OperationSource.MANUAL,
        OperationSource.MANUAL,
        OperationSource.BANK_PDF,
        OperationSource.BANK_PDF,
    ]
    for operation in operations:
        assert operation.workspace_id == workspace_id
        assert operation.status is OperationStatus.CONFIRMED
        assert operation.affects_profit is affects_profit_for_operation_type(operation.type)
        assert operation.created_by_user_id == user_id
        assert operation.updated_by_user_id == user_id
        assert operation.confirmed_at is not None


def raw_transaction_stub() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        description_normalized="Перевод",
        description_raw=None,
        operation_date=date(2026, 7, 21),
        posting_date=None,
    )
