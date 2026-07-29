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
from app.features.ledger.application.imported_operations import (
    ImportedOperationReviewUseCase,
    UpdateImportedOperationReviewFieldsCommand,
)
from app.features.ledger.application.manual_contracts import (
    CreateManualIncomeExpenseCommand,
    UpdateManualIncomeExpenseCommand,
)
from app.features.ledger.application.manual_mutations import ManualOperationWriter
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
    OperationIdempotencyConflictError,
    OperationVersionConflictError,
)
from app.features.ledger.mapping.operations import manual_income_expense_fingerprint
from app.features.ledger.models import Operation, OperationSource, OperationStatus, OperationType


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


def test_operation_type_for_amount_maps_income_and_expense() -> None:
    assert operation_type_for_amount(Decimal("100.00")) == OperationType.INCOME
    assert operation_type_for_amount(Decimal("-100.00")) == OperationType.EXPENSE
    assert affects_profit_for_operation_type(OperationType.INCOME) is True
    assert affects_profit_for_operation_type(OperationType.EXPENSE) is True
    assert affects_profit_for_operation_type(OperationType.TRANSFER) is False


def test_operation_mapper_uses_integer_version_for_optimistic_concurrency() -> None:
    assert Operation.__mapper__.version_id_col is Operation.__table__.c.version


def test_operation_type_for_amount_rejects_zero() -> None:
    with pytest.raises(LedgerPostingError):
        operation_type_for_amount(Decimal("0.00"))


def test_manual_income_expense_amount_normalizes_signs() -> None:
    assert manual_income_expense_amount(OperationType.INCOME, Decimal("100")) == Decimal("100.00")
    assert manual_income_expense_amount(OperationType.EXPENSE, Decimal("100")) == Decimal("-100.00")


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


def test_manual_transfer_amounts_reject_same_account_and_non_positive_amount() -> None:
    account_id = uuid4()

    with pytest.raises(LedgerPostingError, match="different"):
        TransferAmounts.for_manual_transfer(
            source_account_id=account_id,
            destination_account_id=account_id,
            amount=Decimal("100.00"),
        )

    with pytest.raises(LedgerPostingError, match="positive"):
        TransferAmounts.for_manual_transfer(
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            amount=Decimal("0.00"),
        )


@pytest.mark.asyncio
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
        idempotency_fingerprint=manual_income_expense_fingerprint(command),
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

    assert result is existing


@pytest.mark.asyncio
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


def test_prepare_income_expense_posting_for_income_raw_row() -> None:
    account_id = uuid4()
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=account_id,
            amount=Decimal("100.00"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type == OperationType.INCOME
    assert plan.amount == Decimal("100.00")
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


def test_prepare_income_expense_posting_for_expense_raw_row() -> None:
    account_id = uuid4()
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=RawTransactionStatus.MATCHED,
            account_id=account_id,
            amount=Decimal("-25.50"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type == OperationType.EXPENSE
    assert plan.amount == Decimal("-25.50")


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


def test_prepare_income_expense_posting_allows_user_reviewed_statuses() -> None:
    account_id = uuid4()
    for status in [RawTransactionStatus.NEEDS_REVIEW, RawTransactionStatus.IGNORED]:
        plan = prepare_income_expense_posting(
            RawTransactionStub(
                status=status,
                account_id=account_id,
                amount=Decimal("100.00"),
            ),
            AccountStub(id=account_id),
        )
        assert plan.amount == Decimal("100.00")


def test_ledger_posting_plan_blocks_currency_mismatch() -> None:
    account_id = uuid4()
    account = AccountStub(id=account_id, currency="RUB")
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=account_id,
            amount=Decimal("100.00"),
            currency="USD",
        ),
        account,
    )

    with pytest.raises(LedgerPostingError, match="currency"):
        ensure_income_expense_posting(plan, account)


def test_ledger_posting_plan_blocks_operation_type_amount_mismatch() -> None:
    account_id = uuid4()
    account = AccountStub(id=account_id)
    plan = prepare_income_expense_posting(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=account_id,
            amount=Decimal("100.00"),
        ),
        account,
    )

    with pytest.raises(LedgerPostingError, match="amount sign"):
        ensure_income_expense_posting(
            replace(plan, operation_type=OperationType.EXPENSE),
            account,
        )


def test_transfer_source_allows_manual_reviewable_raw_rows() -> None:
    for status in [
        RawTransactionStatus.POSSIBLE_DUPLICATE,
        RawTransactionStatus.NEEDS_REVIEW,
        RawTransactionStatus.IGNORED,
    ]:
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


def test_matched_transfer_row_must_belong_to_selected_account() -> None:
    matched_account_id = uuid4()

    ensure_matched_transfer_account(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=matched_account_id,
            amount=Decimal("100.00"),
        ),
        matched_account_id,
    )

    with pytest.raises(LedgerPostingError, match="selected transfer account"):
        ensure_matched_transfer_account(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=matched_account_id,
                amount=Decimal("100.00"),
            ),
            uuid4(),
        )


@pytest.mark.asyncio
async def test_imported_operation_review_update_changes_only_review_fields(monkeypatch) -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    operation_id = uuid4()
    category_id = uuid4()
    property_id = uuid4()
    money_entry = SimpleNamespace(
        account_id=uuid4(),
        amount=Decimal("-120.00"),
        currency="RUB",
    )
    raw_transaction = SimpleNamespace(id=uuid4(), linked_operation_id=operation_id)
    operation = SimpleNamespace(
        id=operation_id,
        workspace_id=workspace_id,
        source=OperationSource.BANK_PDF,
        type=OperationType.EXPENSE,
        status=OperationStatus.CONFIRMED,
        version=3,
        category_id=None,
        property_id=None,
        description="Old",
        operation_date=date(2026, 6, 15),
        money_entries=[money_entry],
        raw_transactions=[raw_transaction],
        updated_by_user_id=None,
    )
    session = SimpleNamespace(commits=0, flushes=0, rollbacks=0)

    async def commit() -> None:
        session.commits += 1

    async def rollback() -> None:
        session.rollbacks += 1

    async def flush() -> None:
        session.flushes += 1

    session.commit = commit
    session.flush = flush
    session.rollback = rollback

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(self, workspace_id_arg, operation_id_arg):
            assert workspace_id_arg == workspace_id
            assert operation_id_arg == operation_id
            return operation

    class FakeReferences:
        def __init__(self, _session: object) -> None:
            pass

        async def get_category_or_uncategorized(self, workspace_id_arg, category_id_arg):
            assert workspace_id_arg == workspace_id
            assert category_id_arg == category_id
            return SimpleNamespace(id=category_id)

        async def get_property(self, workspace_id_arg, property_id_arg):
            assert workspace_id_arg == workspace_id
            assert property_id_arg == property_id
            return SimpleNamespace(id=property_id)

    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.LedgerRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.LedgerReferenceResolver",
        FakeReferences,
    )

    updated = await ImportedOperationReviewUseCase(cast(Any, session)).update_review_fields(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=user_id),
            ),
        ),
        command=UpdateImportedOperationReviewFieldsCommand(
            operation_id=operation_id,
            expected_version=3,
            category_id=category_id,
            property_id=property_id,
            description="  New   label  ",
        ),
    )

    assert updated is operation
    assert operation.category_id == category_id
    assert operation.property_id == property_id
    assert operation.description == "New label"
    assert operation.status == OperationStatus.CONFIRMED
    assert operation.updated_by_user_id == user_id
    assert operation.type == OperationType.EXPENSE
    assert operation.operation_date == date(2026, 6, 15)
    assert operation.money_entries == [money_entry]
    assert operation.raw_transactions == [raw_transaction]
    assert money_entry.amount == Decimal("-120.00")
    assert session.commits == 1
    assert session.flushes == 1
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_imported_operation_review_update_rejects_manual_source(monkeypatch) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    operation = SimpleNamespace(id=operation_id, source=OperationSource.MANUAL)
    session = SimpleNamespace(commits=0, rollbacks=0)

    async def commit() -> None:
        session.commits += 1

    async def rollback() -> None:
        session.rollbacks += 1

    session.commit = commit
    session.rollback = rollback

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(self, _workspace_id, _operation_id):
            return operation

    class FakeReferences:
        def __init__(self, _session: object) -> None:
            pass

    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.LedgerRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.LedgerReferenceResolver",
        FakeReferences,
    )

    with pytest.raises(LedgerPostingError, match="Only imported bank PDF"):
        await ImportedOperationReviewUseCase(cast(Any, session)).update_review_fields(
            context=cast(
                Any,
                SimpleNamespace(
                    workspace=SimpleNamespace(id=workspace_id),
                    user=SimpleNamespace(id=uuid4()),
                ),
            ),
            command=UpdateImportedOperationReviewFieldsCommand(
                operation_id=operation_id,
                expected_version=1,
                category_id=None,
                property_id=None,
                description="New",
            ),
        )
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_manual_cancel_and_restore_change_only_lifecycle_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    user_id = uuid4()
    money_entries = [SimpleNamespace(id=uuid4(), amount=Decimal("-10.00"))]
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        version=3,
        money_entries=money_entries,
        updated_by_user_id=None,
    )
    session = SimpleNamespace(flushes=0)

    async def flush() -> None:
        session.flushes += 1

    session.flush = flush

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            workspace_id_arg: UUID,
            operation_id_arg: UUID,
        ) -> object:
            assert workspace_id_arg == workspace_id
            assert operation_id_arg == operation.id
            return operation

    monkeypatch.setattr(
        "app.features.ledger.application.manual_mutations.LedgerRepository",
        FakeRepository,
    )
    use_case = ManualOperationWriter(cast(Any, session))
    context = cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=user_id),
        ),
    )

    await use_case.cancel(
        context=context,
        operation_id=operation.id,
        expected_version=3,
    )
    assert operation.status is OperationStatus.IGNORED
    assert operation.updated_by_user_id == user_id
    assert operation.money_entries is money_entries

    await use_case.restore(context=context, operation_id=operation.id)
    assert operation.status is OperationStatus.CONFIRMED
    assert operation.money_entries is money_entries
    assert session.flushes == 2


@pytest.mark.asyncio
async def test_manual_cancel_rejects_stale_version_before_state_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        version=4,
    )

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            _workspace_id: UUID,
            _operation_id: UUID,
        ) -> object:
            return operation

    monkeypatch.setattr(
        "app.features.ledger.application.manual_mutations.LedgerRepository",
        FakeRepository,
    )

    with pytest.raises(OperationVersionConflictError):
        await ManualOperationWriter(cast(Any, object())).cancel(
            context=cast(
                Any,
                SimpleNamespace(
                    workspace=SimpleNamespace(id=workspace_id),
                    user=SimpleNamespace(id=uuid4()),
                ),
            ),
            operation_id=operation.id,
            expected_version=3,
        )

    assert operation.status is OperationStatus.CONFIRMED


@pytest.mark.asyncio
async def test_manual_delete_requires_deletable_state_and_expected_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation = SimpleNamespace(
        id=uuid4(),
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        version=3,
    )
    deleted: list[object] = []
    session = SimpleNamespace(flushes=0)

    async def flush() -> None:
        session.flushes += 1

    session.flush = flush

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            _workspace_id: UUID,
            _operation_id: UUID,
        ) -> object:
            return operation

        async def delete_operation(self, operation_to_delete: object) -> None:
            deleted.append(operation_to_delete)

    monkeypatch.setattr(
        "app.features.ledger.application.manual_mutations.LedgerRepository",
        FakeRepository,
    )
    use_case = ManualOperationWriter(cast(Any, session))
    context = cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )

    with pytest.raises(LedgerPostingError, match="Cancel a manual operation"):
        await use_case.delete(
            context=context,
            operation_id=operation.id,
            expected_version=3,
        )
    assert deleted == []

    operation.status = OperationStatus.IGNORED
    operation.version = 4
    with pytest.raises(OperationVersionConflictError):
        await use_case.delete(
            context=context,
            operation_id=operation.id,
            expected_version=3,
        )
    assert deleted == []

    await use_case.delete(
        context=context,
        operation_id=operation.id,
        expected_version=4,
    )
    assert deleted == [operation]
    assert session.flushes == 1


@pytest.mark.asyncio
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
            get_account=AsyncMock(return_value=account),
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
