from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account
from app.features.import_review.domain.posting import (
    ensure_matched_transfer_account,
    ensure_raw_transaction_can_post_as_transfer,
    prepare_income_expense_posting,
    raw_transaction_effective_account_id,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.application.manual_mutations import ManualOperationWriter
from app.features.ledger.domain.manual_idempotency import ManualOperationFingerprint
from app.features.ledger.domain.money import (
    TransferAmounts,
    affects_profit_for_operation_type,
    ensure_balanced_transfer,
    ensure_income_expense_posting,
    manual_income_expense_amount,
    operation_type_for_amount,
)
from app.features.ledger.errors import (
    LedgerPostingError,
    ManualOperationLifecycleConflictError,
    OperationIdempotencyConflictError,
    OperationVersionConflictError,
)
from app.features.ledger.models import Operation, OperationSource, OperationStatus, OperationType
from app.features.ledger.schemas.manual import (
    CreateManualIncomeExpenseCommand,
    UpdateManualIncomeExpenseCommand,
)


@dataclass(frozen=True)
class RawTransactionStub:
    status: RawTransactionStatus
    account_id: UUID | None
    amount: Decimal | None
    id: UUID = uuid4()
    currency: str | None = "RUB"
    operation_date: date | None = date(2026, 5, 29)
    linked_operation_id: UUID | None = None
    posting_date: date | None = None
    description_normalized: str | None = "Rent"
    description_raw: str | None = None
    balance_after: Decimal | None = None
    dedupe_hash: str | None = "hash"
    suggested_by_rule_id: UUID | None = None
    uploaded_document: object | None = None


@dataclass(frozen=True)
class AccountStub:
    id: UUID
    currency: str = "RUB"


@dataclass(frozen=True)
class UploadedDocumentStub:
    account_id: UUID | None


def manual_expense_update_command(
    operation_id: UUID,
    *,
    account_id: UUID | None = None,
    amount: Decimal = Decimal("10.00"),
    description: str = "Обновлённая операция",
    expected_version: int = 1,
) -> UpdateManualIncomeExpenseCommand:
    return UpdateManualIncomeExpenseCommand(
        operation_id=operation_id,
        operation_type=OperationType.EXPENSE,
        account_id=account_id or uuid4(),
        amount=amount,
        operation_date=date(2026, 7, 20),
        description=description,
        category_id=None,
        property_id=None,
        expected_version=expected_version,
    )


def workspace_context_stub(
    workspace_id: UUID,
    *,
    user_id: UUID | None = None,
) -> Any:
    return SimpleNamespace(
        workspace=SimpleNamespace(id=workspace_id),
        user=SimpleNamespace(id=user_id or uuid4()),
    )


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        pytest.param(Decimal("100.00"), OperationType.INCOME, id="positive-income"),
        pytest.param(Decimal("-100.00"), OperationType.EXPENSE, id="negative-expense"),
    ],
)
def test_operation_type_for_amount(amount: Decimal, expected: OperationType) -> None:
    assert operation_type_for_amount(amount) is expected


@pytest.mark.parametrize(
    ("operation_type", "expected"),
    [
        pytest.param(OperationType.INCOME, True, id="income"),
        pytest.param(OperationType.EXPENSE, True, id="expense"),
        pytest.param(OperationType.TRANSFER, False, id="transfer"),
    ],
)
def test_affects_profit_for_operation_type(
    operation_type: OperationType,
    expected: bool,
) -> None:
    assert affects_profit_for_operation_type(operation_type) is expected


def test_operation_mapper_uses_integer_version_for_optimistic_concurrency() -> None:
    assert Operation.__mapper__.version_id_col is Operation.__table__.c.version


def test_operation_type_for_amount_rejects_zero() -> None:
    with pytest.raises(LedgerPostingError):
        operation_type_for_amount(Decimal("0.00"))


@pytest.mark.parametrize(
    ("operation_type", "expected"),
    [
        pytest.param(OperationType.INCOME, Decimal("100.00"), id="income"),
        pytest.param(OperationType.EXPENSE, Decimal("-100.00"), id="expense"),
    ],
)
def test_manual_income_expense_amount_normalizes_sign(
    operation_type: OperationType,
    expected: Decimal,
) -> None:
    assert manual_income_expense_amount(operation_type, Decimal("100")) == expected


def test_manual_transfer_amounts_create_balanced_entries() -> None:
    source_account_id = uuid4()
    destination_account_id = uuid4()

    amounts = TransferAmounts.for_manual_transfer(
        source_account_id=source_account_id,
        destination_account_id=destination_account_id,
        amount=Decimal("250.5"),
    )

    assert amounts.source_amount == Decimal("-250.50")
    assert amounts.destination_amount == Decimal("250.50")
    amounts.ensure_balanced()
    ensure_balanced_transfer(amounts.source_amount, amounts.destination_amount)


@pytest.mark.parametrize(
    ("same_account", "amount", "message"),
    [
        pytest.param(True, Decimal("100.00"), "different", id="same-account"),
        pytest.param(False, Decimal("0.00"), "positive", id="zero-amount"),
    ],
)
def test_manual_transfer_amounts_reject_invalid_input(
    same_account: bool,
    amount: Decimal,
    message: str,
) -> None:
    source_account_id = uuid4()

    with pytest.raises(LedgerPostingError, match=message):
        TransferAmounts.for_manual_transfer(
            source_account_id=source_account_id,
            destination_account_id=(source_account_id if same_account else uuid4()),
            amount=amount,
        )


async def test_manual_create_replays_matching_idempotency_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    idempotency_key = uuid4()
    command = CreateManualIncomeExpenseCommand(
        operation_type=OperationType.INCOME,
        account_id=uuid4(),
        amount=Decimal("10.00"),
        operation_date=date(2026, 7, 20),
        description="Повтор",
        category_id=None,
        property_id=None,
        idempotency_key=idempotency_key,
    )
    existing = SimpleNamespace(
        id=uuid4(),
        idempotency_fingerprint=ManualOperationFingerprint.calculate_income_expense(command),
    )

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_by_idempotency_key(self, **_kwargs: object) -> object:
            return existing

    monkeypatch.setattr(
        "app.features.ledger.application.manual_mutations.LedgerRepository",
        FakeRepository,
    )
    result = await ManualOperationWriter(cast(Any, object())).create_income_expense(
        context=cast(
            Any,
            SimpleNamespace(workspace=SimpleNamespace(id=workspace_id)),
        ),
        command=command,
    )

    assert result.operation is existing
    assert result.replayed is True


async def test_manual_create_marks_new_operation_as_not_replayed() -> None:
    workspace_id = uuid4()
    operation = SimpleNamespace(id=uuid4())
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной счёт",
        currency="RUB",
    )
    writer = ManualOperationWriter(cast(Any, object()))
    writer.ledger = cast(
        Any,
        SimpleNamespace(
            create_operation=AsyncMock(return_value=operation),
            create_money_entry=AsyncMock(),
        ),
    )
    writer.references = cast(
        Any,
        SimpleNamespace(
            get_income_expense_account=AsyncMock(
                return_value=account,
            ),
            get_category_or_uncategorized=AsyncMock(
                return_value=SimpleNamespace(id=uuid4()),
            ),
            get_property=AsyncMock(return_value=None),
        ),
    )

    result = await writer.create_income_expense(
        context=workspace_context_stub(workspace_id),
        command=CreateManualIncomeExpenseCommand(
            operation_type=OperationType.INCOME,
            account_id=uuid4(),
            amount=Decimal("10.00"),
            operation_date=date(2026, 7, 20),
            description="Новая операция",
            category_id=None,
            property_id=None,
        ),
    )

    assert result.operation is operation
    assert result.replayed is False


async def test_manual_create_rejects_idempotency_key_reuse_with_other_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    command = CreateManualIncomeExpenseCommand(
        operation_type=OperationType.INCOME,
        account_id=uuid4(),
        amount=Decimal("10.00"),
        operation_date=date(2026, 7, 20),
        description="Новая операция",
        category_id=None,
        property_id=None,
        idempotency_key=uuid4(),
    )
    session = SimpleNamespace(rollbacks=0)

    async def rollback() -> None:
        session.rollbacks += 1

    session.rollback = rollback

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_by_idempotency_key(self, **_kwargs: object) -> object:
            return SimpleNamespace(idempotency_fingerprint="different")

    monkeypatch.setattr(
        "app.features.ledger.application.manual_mutations.LedgerRepository",
        FakeRepository,
    )

    with pytest.raises(OperationIdempotencyConflictError):
        await ManualOperationWriter(cast(Any, session)).create_income_expense(
            context=cast(
                Any,
                SimpleNamespace(workspace=SimpleNamespace(id=workspace_id)),
            ),
            command=command,
        )

    assert session.rollbacks == 0


def test_ensure_balanced_transfer_rejects_unbalanced_entries() -> None:
    with pytest.raises(LedgerPostingError, match="balance"):
        ensure_balanced_transfer(Decimal("-10.00"), Decimal("9.99"))


@pytest.mark.parametrize(
    ("status", "amount", "expected_type"),
    [
        pytest.param(
            RawTransactionStatus.NORMALIZED,
            Decimal("100.00"),
            OperationType.INCOME,
            id="income",
        ),
        pytest.param(
            RawTransactionStatus.MATCHED,
            Decimal("-25.50"),
            OperationType.EXPENSE,
            id="expense",
        ),
    ],
)
def test_prepare_income_expense_posting_builds_plan(
    status: RawTransactionStatus,
    amount: Decimal,
    expected_type: OperationType,
) -> None:
    account_id = uuid4()
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=status,
            account_id=account_id,
            amount=amount,
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type is expected_type
    assert plan.amount == amount
    assert plan.description == "Rent"


def test_prepare_income_expense_posting_accepts_document_account() -> None:
    account_id = uuid4()
    raw_transaction = RawTransactionStub(
        status=RawTransactionStatus.NORMALIZED,
        account_id=None,
        amount=Decimal("100.00"),
        uploaded_document=UploadedDocumentStub(account_id=account_id),
    )

    plan = prepare_income_expense_posting(raw_transaction, AccountStub(id=account_id))

    assert raw_transaction_effective_account_id(raw_transaction) == account_id
    assert plan.operation_type == OperationType.INCOME


def test_ensure_matched_transfer_account_accepts_document_account() -> None:
    account_id = uuid4()
    raw_transaction = RawTransactionStub(
        status=RawTransactionStatus.NORMALIZED,
        account_id=None,
        amount=Decimal("-100.00"),
        uploaded_document=UploadedDocumentStub(account_id=account_id),
    )

    ensure_matched_transfer_account(raw_transaction, account_id)


def test_prepare_income_expense_posting_blocks_already_linked_row() -> None:
    account_id = uuid4()
    with pytest.raises(LedgerPostingError, match="already linked"):
        prepare_income_expense_posting(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=account_id,
                amount=Decimal("100.00"),
                linked_operation_id=uuid4(),
            ),
            AccountStub(id=account_id),
        )


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(RawTransactionStatus.NEEDS_REVIEW, id="needs-review"),
        pytest.param(RawTransactionStatus.IGNORED, id="ignored"),
    ],
)
def test_prepare_income_expense_posting_allows_user_reviewed_status(
    status: RawTransactionStatus,
) -> None:
    account_id = uuid4()
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=status,
            account_id=account_id,
            amount=Decimal("100.00"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.amount == Decimal("100.00")


@pytest.mark.parametrize(
    ("plan_currency", "operation_type", "message"),
    [
        pytest.param("USD", OperationType.INCOME, "currency", id="currency"),
        pytest.param("RUB", OperationType.EXPENSE, "amount sign", id="amount-sign"),
    ],
)
def test_ledger_posting_plan_rejects_inconsistent_accounting_facts(
    plan_currency: str,
    operation_type: OperationType,
    message: str,
) -> None:
    account_id = uuid4()
    account = AccountStub(id=account_id, currency="RUB")
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=account_id,
            amount=Decimal("100.00"),
            currency=plan_currency,
        ),
        account,
    )

    with pytest.raises(LedgerPostingError, match=message):
        ensure_income_expense_posting(
            replace(plan, operation_type=operation_type),
            account,
        )


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(RawTransactionStatus.POSSIBLE_DUPLICATE, id="possible-duplicate"),
        pytest.param(RawTransactionStatus.NEEDS_REVIEW, id="needs-review"),
        pytest.param(RawTransactionStatus.IGNORED, id="ignored"),
    ],
)
def test_transfer_source_allows_manual_reviewable_raw_row(
    status: RawTransactionStatus,
) -> None:
    ensure_raw_transaction_can_post_as_transfer(
        RawTransactionStub(
            status=status,
            account_id=uuid4(),
            amount=Decimal("-100.00"),
        )
    )


def test_transfer_source_blocks_already_linked_rows() -> None:
    with pytest.raises(LedgerPostingError, match="already linked"):
        ensure_raw_transaction_can_post_as_transfer(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=uuid4(),
                amount=Decimal("-100.00"),
                linked_operation_id=uuid4(),
            )
        )


def test_matched_transfer_row_rejects_other_selected_account() -> None:
    matched_account_id = uuid4()

    with pytest.raises(LedgerPostingError, match="selected transfer account"):
        ensure_matched_transfer_account(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=matched_account_id,
                amount=Decimal("100.00"),
            ),
            uuid4(),
        )


async def test_manual_update_rejects_imported_operation() -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    operation = SimpleNamespace(id=operation_id, source=OperationSource.BANK_PDF)
    operation_lookup = AsyncMock(return_value=operation)
    use_case = ManualOperationWriter(cast(Any, object()))
    use_case.ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=operation_lookup),
    )

    with pytest.raises(LedgerPostingError, match="Only manual operations"):
        await use_case.update(
            context=workspace_context_stub(workspace_id),
            command=manual_expense_update_command(operation_id),
        )

    operation_lookup.assert_awaited_once_with(workspace_id, operation_id)


async def test_manual_update_rejects_stale_expected_version_before_mutation() -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    account_id = uuid4()
    operation = SimpleNamespace(
        id=operation_id,
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        version=2,
    )
    use_case = ManualOperationWriter(cast(Any, object()))
    use_case.ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=AsyncMock(return_value=operation)),
    )

    with pytest.raises(OperationVersionConflictError):
        await use_case.update(
            context=workspace_context_stub(workspace_id),
            command=manual_expense_update_command(
                operation_id,
                account_id=account_id,
                description="Устаревшая форма",
                expected_version=1,
            ),
        )

    assert not hasattr(operation, "description")


async def test_manual_update_rejects_ignored_operation_before_mutation() -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    operation = SimpleNamespace(
        id=operation_id,
        source=OperationSource.MANUAL,
        status=OperationStatus.IGNORED,
        version=1,
    )
    use_case = ManualOperationWriter(cast(Any, object()))
    use_case.ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=AsyncMock(return_value=operation)),
    )

    with pytest.raises(LedgerPostingError, match="confirmed or draft"):
        await use_case.update(
            context=workspace_context_stub(workspace_id),
            command=manual_expense_update_command(
                operation_id,
                description="Нельзя изменить",
                expected_version=1,
            ),
        )

    assert not hasattr(operation, "description")


@pytest.mark.parametrize(
    ("action", "initial_status", "target_status"),
    [
        pytest.param(
            "cancel",
            OperationStatus.CONFIRMED,
            OperationStatus.IGNORED,
            id="cancel",
        ),
        pytest.param(
            "restore",
            OperationStatus.IGNORED,
            OperationStatus.CONFIRMED,
            id="restore",
        ),
    ],
)
async def test_manual_lifecycle_changes_only_state(
    action: str,
    initial_status: OperationStatus,
    target_status: OperationStatus,
) -> None:
    operation, use_case, session, context = manual_lifecycle_context(
        status=initial_status,
        version=3,
    )
    money_entries = operation.money_entries

    await getattr(use_case, action)(
        context=context,
        operation_id=operation.id,
        expected_version=3,
    )

    assert operation.status is target_status
    assert operation.updated_by_user_id == context.user.id
    assert operation.money_entries is money_entries
    session.flush.assert_awaited_once()


async def test_manual_cancel_rejects_stale_version_before_state_change() -> None:
    operation, use_case, session, context = manual_lifecycle_context(
        status=OperationStatus.CONFIRMED,
        version=4,
    )

    with pytest.raises(OperationVersionConflictError):
        await use_case.cancel(
            context=context,
            operation_id=operation.id,
            expected_version=3,
        )

    assert operation.status is OperationStatus.CONFIRMED
    session.flush.assert_not_awaited()


def manual_lifecycle_context(
    *,
    status: OperationStatus,
    version: int,
) -> tuple[SimpleNamespace, ManualOperationWriter, Any, Any]:
    workspace_id = uuid4()
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        status=status,
        version=version,
        money_entries=[SimpleNamespace(id=uuid4(), amount=Decimal("-10.00"))],
        updated_by_user_id=None,
    )
    session = SimpleNamespace(flush=AsyncMock())
    use_case = ManualOperationWriter(cast(Any, session))
    use_case.ledger = cast(
        Any,
        SimpleNamespace(get_operation_for_workspace=AsyncMock(return_value=operation)),
    )
    return operation, use_case, session, workspace_context_stub(workspace_id)


@pytest.mark.parametrize(
    ("status", "version", "expected_version", "expected_error"),
    [
        pytest.param(
            OperationStatus.CONFIRMED,
            3,
            3,
            ManualOperationLifecycleConflictError,
            id="not-deletable",
        ),
        pytest.param(
            OperationStatus.IGNORED,
            4,
            3,
            OperationVersionConflictError,
            id="stale-version",
        ),
    ],
)
async def test_manual_delete_rejects_invalid_state_or_version(
    status: OperationStatus,
    version: int,
    expected_version: int,
    expected_error: type[LedgerPostingError],
) -> None:
    operation, use_case, session, ledger, context = manual_delete_context(
        status=status,
        version=version,
    )

    with pytest.raises(expected_error):
        await use_case.delete(
            context=context,
            operation_id=operation.id,
            expected_version=expected_version,
        )

    ledger.delete_operation.assert_not_awaited()
    session.flush.assert_not_awaited()


async def test_manual_delete_removes_deletable_operation_and_returns_identity() -> None:
    operation, use_case, session, ledger, context = manual_delete_context(
        status=OperationStatus.IGNORED,
        version=4,
    )

    outcome = await use_case.delete(
        context=context,
        operation_id=operation.id,
        expected_version=4,
    )

    ledger.delete_operation.assert_awaited_once_with(operation)
    session.flush.assert_awaited_once()
    assert outcome.operation_id == operation.id
    assert outcome.operation_type is OperationType.EXPENSE
    assert outcome.display_label == "Покупка"


def manual_delete_context(
    *,
    status: OperationStatus,
    version: int,
) -> tuple[SimpleNamespace, ManualOperationWriter, Any, Any, Any]:
    workspace_id = uuid4()
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        status=status,
        version=version,
        type=OperationType.EXPENSE,
        description="Покупка",
    )
    session = SimpleNamespace(flush=AsyncMock())
    ledger = SimpleNamespace(
        get_operation_for_workspace=AsyncMock(return_value=operation),
        delete_operation=AsyncMock(),
    )
    use_case = ManualOperationWriter(cast(Any, session))
    use_case.ledger = cast(Any, ledger)
    return operation, use_case, session, ledger, workspace_context_stub(workspace_id)


async def test_manual_update_replaces_existing_money_entry() -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    account_id = uuid4()
    previous_entry = SimpleNamespace(id=uuid4(), amount=Decimal("100.00"))
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        version=1,
        type=OperationType.INCOME,
        affects_profit=True,
        description="Старое описание",
        operation_date=date(2026, 7, 19),
        money_entries=[previous_entry],
        updated_by_user_id=None,
    )
    session = SimpleNamespace(
        delete=AsyncMock(),
        flush=AsyncMock(),
    )
    account = Account(
        id=account_id,
        workspace_id=workspace_id,
        name="Основной счёт",
        currency="RUB",
    )
    use_case = ManualOperationWriter(cast(Any, session))
    use_case.ledger = cast(
        Any,
        SimpleNamespace(
            get_operation_for_workspace=AsyncMock(return_value=operation),
            create_money_entry=AsyncMock(side_effect=lambda entry: entry),
        ),
    )
    use_case.references = cast(
        Any,
        SimpleNamespace(
            get_income_expense_account=AsyncMock(return_value=account),
            get_category_or_uncategorized=AsyncMock(
                return_value=SimpleNamespace(id=uuid4()),
            ),
            get_property=AsyncMock(return_value=None),
        ),
    )

    updated = await use_case.update(
        context=workspace_context_stub(workspace_id, user_id=user_id),
        command=manual_expense_update_command(
            operation.id,
            account_id=account_id,
            amount=Decimal("125.00"),
            description="  Новое   описание  ",
        ),
    )

    assert updated is operation
    assert operation.type is OperationType.EXPENSE
    assert operation.description == "Новое описание"
    assert operation.operation_date == date(2026, 7, 20)
    assert operation.updated_by_user_id == user_id
    assert len(operation.money_entries) == 1
    assert operation.money_entries[0].account.id == account_id
    assert operation.money_entries[0].amount == Decimal("-125.00")
    assert operation.money_entries[0].currency == "RUB"
