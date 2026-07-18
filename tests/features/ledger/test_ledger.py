from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.imports.models import RawTransactionStatus
from app.features.ledger.application.commands import (
    UpdateImportedOperationReviewFieldsCommand,
    UpdateManualOperationCommand,
)
from app.features.ledger.application.imported_operation_review import (
    ImportedOperationReviewUseCase,
)
from app.features.ledger.application.manual_operations import ManualOperationUseCase
from app.features.ledger.domain.money import (
    TransferAmounts,
    affects_profit_for_operation_type,
    ensure_balanced_transfer,
    manual_income_expense_amount,
    operation_type_for_amount,
)
from app.features.ledger.domain.raw_transactions import (
    LedgerPostingPlan,
    ensure_matched_transfer_account,
    ensure_raw_transaction_can_post_as_transfer,
    raw_transaction_effective_account_id,
    restored_raw_status_after_unlink,
)
from app.features.ledger.errors import LedgerPostingError, OperationVersionConflictError
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


def test_ensure_balanced_transfer_rejects_unbalanced_entries() -> None:
    with pytest.raises(LedgerPostingError, match="balance"):
        ensure_balanced_transfer(Decimal("-10.00"), Decimal("9.99"))


def test_build_ledger_posting_plan_for_income_raw_row() -> None:
    account_id = uuid4()
    plan = LedgerPostingPlan.from_raw_transaction(
        RawTransactionStub(
            status=RawTransactionStatus.NORMALIZED,
            account_id=account_id,
            amount=Decimal("100.00"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type == OperationType.INCOME
    assert plan.amount == Decimal("100.00")
    assert plan.affects_profit is True
    assert plan.description == "Rent"


def test_build_ledger_posting_plan_accepts_document_account() -> None:
    account_id = uuid4()
    raw_transaction = RawTransactionStub(
        status=RawTransactionStatus.NORMALIZED,
        account_id=None,
        amount=Decimal("100.00"),
        uploaded_document=UploadedDocumentStub(account_id=account_id),
    )

    plan = LedgerPostingPlan.from_raw_transaction(raw_transaction, AccountStub(id=account_id))

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


def test_build_ledger_posting_plan_for_expense_raw_row() -> None:
    account_id = uuid4()
    plan = LedgerPostingPlan.from_raw_transaction(
        RawTransactionStub(
            status=RawTransactionStatus.MATCHED,
            account_id=account_id,
            amount=Decimal("-25.50"),
        ),
        AccountStub(id=account_id),
    )

    assert plan.operation_type == OperationType.EXPENSE
    assert plan.amount == Decimal("-25.50")


def test_build_ledger_posting_plan_blocks_already_linked_row() -> None:
    account_id = uuid4()
    with pytest.raises(LedgerPostingError, match="already linked"):
        LedgerPostingPlan.from_raw_transaction(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=account_id,
                amount=Decimal("100.00"),
                linked_operation_id=uuid4(),
            ),
            AccountStub(id=account_id),
        )


def test_build_ledger_posting_plan_allows_user_reviewed_statuses() -> None:
    account_id = uuid4()
    for status in [RawTransactionStatus.NEEDS_REVIEW, RawTransactionStatus.IGNORED]:
        plan = LedgerPostingPlan.from_raw_transaction(
            RawTransactionStub(
                status=status,
                account_id=account_id,
                amount=Decimal("100.00"),
            ),
            AccountStub(id=account_id),
        )
        assert plan.amount == Decimal("100.00")


def test_build_ledger_posting_plan_blocks_currency_mismatch() -> None:
    account_id = uuid4()
    with pytest.raises(LedgerPostingError, match="currency"):
        LedgerPostingPlan.from_raw_transaction(
            RawTransactionStub(
                status=RawTransactionStatus.NORMALIZED,
                account_id=account_id,
                amount=Decimal("100.00"),
                currency="USD",
            ),
            AccountStub(id=account_id, currency="RUB"),
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


def test_restored_raw_status_after_unlink_preserves_rule_suggestion() -> None:
    assert (
        restored_raw_status_after_unlink(
            RawTransactionStub(
                status=RawTransactionStatus.CONFIRMED,
                account_id=uuid4(),
                amount=Decimal("-100.00"),
                suggested_by_rule_id=uuid4(),
            )
        )
        == RawTransactionStatus.SUGGESTED
    )
    assert (
        restored_raw_status_after_unlink(
            RawTransactionStub(
                status=RawTransactionStatus.CONFIRMED,
                account_id=uuid4(),
                amount=Decimal("-100.00"),
            )
        )
        == RawTransactionStatus.NORMALIZED
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
        category_id=None,
        property_id=None,
        description="Old",
        operation_date=date(2026, 6, 15),
        money_entries=[money_entry],
        raw_transactions=[raw_transaction],
        updated_by_user_id=None,
    )
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
        "app.features.ledger.application.imported_operation_review.LedgerRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        "app.features.ledger.application.imported_operation_review.LedgerReferenceResolver",
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
            category_id=category_id,
            property_id=property_id,
            description="  New   label  ",
            status=OperationStatus.NEEDS_REVIEW,
        ),
    )

    assert updated is operation
    assert operation.category_id == category_id
    assert operation.property_id == property_id
    assert operation.description == "New label"
    assert operation.status == OperationStatus.NEEDS_REVIEW
    assert operation.updated_by_user_id == user_id
    assert operation.type == OperationType.EXPENSE
    assert operation.operation_date == date(2026, 6, 15)
    assert operation.money_entries == [money_entry]
    assert operation.raw_transactions == [raw_transaction]
    assert money_entry.amount == Decimal("-120.00")
    assert session.commits == 1
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
        "app.features.ledger.application.imported_operation_review.LedgerRepository",
        FakeRepository,
    )
    monkeypatch.setattr(
        "app.features.ledger.application.imported_operation_review.LedgerReferenceResolver",
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
                category_id=None,
                property_id=None,
                description="New",
                status=OperationStatus.CONFIRMED,
            ),
        )
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_manual_operation_use_case_rejects_imported_operation(monkeypatch) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    operation = SimpleNamespace(id=operation_id, source=OperationSource.BANK_PDF)

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(self, workspace_id_arg, operation_id_arg):
            assert workspace_id_arg == workspace_id
            assert operation_id_arg == operation_id
            return operation

    monkeypatch.setattr(
        "app.features.ledger.application.manual_operations.LedgerRepository",
        FakeRepository,
    )

    use_case = ManualOperationUseCase(cast(Any, object()))
    with pytest.raises(LedgerPostingError, match="Only manual operations"):
        await use_case._get_manual_operation(workspace_id, operation_id)


@pytest.mark.asyncio
async def test_manual_update_rejects_stale_expected_version_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    account_id = uuid4()
    operation = SimpleNamespace(
        id=operation_id,
        source=OperationSource.MANUAL,
        version=2,
    )
    session = SimpleNamespace(rollbacks=0)

    async def rollback() -> None:
        session.rollbacks += 1

    session.rollback = rollback

    class FakeRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def get_operation_for_workspace(
            self,
            workspace_id_arg: UUID,
            operation_id_arg: UUID,
        ) -> object:
            assert workspace_id_arg == workspace_id
            assert operation_id_arg == operation_id
            return operation

    monkeypatch.setattr(
        "app.features.ledger.application.manual_operations.LedgerRepository",
        FakeRepository,
    )

    with pytest.raises(OperationVersionConflictError):
        await ManualOperationUseCase(cast(Any, session)).update(
            context=cast(
                Any,
                SimpleNamespace(
                    workspace=SimpleNamespace(id=workspace_id),
                    user=SimpleNamespace(id=uuid4()),
                ),
            ),
            command=UpdateManualOperationCommand(
                operation_id=operation_id,
                operation_type=OperationType.EXPENSE,
                account_id=account_id,
                amount=Decimal("10.00"),
                operation_date=date(2026, 7, 18),
                description="Устаревшая форма",
                category_id=None,
                property_id=None,
                destination_account_id=None,
                expected_version=1,
            ),
        )

    assert session.rollbacks == 1
    assert not hasattr(operation, "description")


@pytest.mark.asyncio
async def test_replacing_manual_money_entries_keeps_operation_state_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_entry = SimpleNamespace(id=uuid4())
    replacement_entry = SimpleNamespace(id=uuid4())
    operation = SimpleNamespace(money_entries=[previous_entry])
    session = SimpleNamespace(deleted=[], flushes=0)

    async def delete(entry: object) -> None:
        session.deleted.append(entry)

    async def flush() -> None:
        session.flushes += 1

    session.delete = delete
    session.flush = flush
    use_case = ManualOperationUseCase(cast(Any, session))
    created_entries: list[object] = []

    async def create_money_entry(entry: object) -> object:
        created_entries.append(entry)
        return entry

    monkeypatch.setattr(use_case.ledger, "create_money_entry", create_money_entry)

    await use_case._replace_money_entries(
        cast(Any, operation),
        cast(Any, [replacement_entry]),
    )

    assert session.deleted == [previous_entry]
    assert created_entries == [replacement_entry]
    assert operation.money_entries == [replacement_entry]
