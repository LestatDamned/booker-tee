from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.import_review.application.transfers import (
    ImportReviewTransferActor,
)
from app.features.import_review.schemas.commands import (
    CreateImportReviewTransferCommand,
    LinkImportReviewExistingTransferCommand,
    MatchImportReviewRawRowCommand,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.application.posting import LedgerPostingService
from app.features.ledger.domain.money import LedgerPostingPlan
from app.features.ledger.domain.types import OperationType


class SessionStub:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class ImportRepositoryStub:
    def __init__(self, raw_transaction: object) -> None:
        self.raw_transaction = raw_transaction
        self.linked_operation_id: UUID | None = None

    async def get_raw_transaction_for_workspace(self, *args: object) -> object:
        return self.raw_transaction

    async def has_confirmed_raw_transaction_with_dedupe_hash(self, **kwargs: object) -> bool:
        return False

    async def link_raw_transaction_to_operation(
        self,
        raw_transaction: object,
        *,
        operation_id: UUID,
    ) -> None:
        self.linked_operation_id = operation_id

    async def get_document_for_workspace(self, *args: object) -> None:
        return None


class LedgerRepositoryStub:
    def __init__(self) -> None:
        self.entries: list[Any] = []
        self.operations: list[object] = []
        self.operation: object | None = None

    async def create_operation(self, operation: Any) -> Any:
        operation.id = uuid4()
        self.operation = operation
        return operation

    async def create_money_entry(self, money_entry: object) -> object:
        self.entries.append(money_entry)
        return money_entry

    async def get_operation_by_idempotency_key(self, **_kwargs: object) -> None:
        return None

    async def get_operation_for_workspace_for_update(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> object | None:
        return next(
            (
                candidate
                for candidate in self.operations
                if getattr(candidate, "id", None) == operation_id
            ),
            None,
        )


class ImportReviewRepositoryStub:
    def __init__(
        self,
        candidates: list[object] | None = None,
        raw_repository: object | None = None,
    ) -> None:
        self.candidates = candidates or []
        self.raw_repository = raw_repository

    async def get_raw_transaction_for_workspace(self, *args: object) -> object:
        return await cast(Any, self.raw_repository).get_raw_transaction_for_workspace(*args)

    async def link_raw_transaction_to_operation(
        self,
        raw_transaction: object,
        *,
        operation_id: UUID,
    ) -> None:
        await cast(Any, self.raw_repository).link_raw_transaction_to_operation(
            raw_transaction,
            operation_id=operation_id,
        )

    async def list_manual_transfer_candidates_for_raw_transaction(
        self,
        **_kwargs: object,
    ) -> list[object]:
        return self.candidates


class DocumentStatusStub:
    def __init__(self) -> None:
        self.document_ids: list[UUID] = []

    async def mark_imported_if_complete(self, **kwargs: object) -> bool:
        document_id = kwargs["document_id"]
        assert isinstance(document_id, UUID)
        self.document_ids.append(document_id)
        return False


@pytest.mark.asyncio
async def test_post_imported_income_expense_creates_ledger_records_without_commit() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    account = Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name="Основной",
        type=AccountType.CHECKING,
        currency="RUB",
        initial_balance=Decimal("0.00"),
    )
    raw_transaction = SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        uploaded_document_id=document_id,
        uploaded_document=SimpleNamespace(account_id=account.id),
        linked_operation_id=None,
        account_id=None,
        status=RawTransactionStatus.NORMALIZED,
        amount=Decimal("100.00"),
        currency="RUB",
        operation_date=date(2026, 7, 21),
        posting_date=None,
        description_normalized="Пополнение",
        description_raw="Пополнение",
        balance_after=Decimal("100.00"),
        dedupe_hash=None,
        raw_payload={},
        suggested_category_id=None,
        suggested_property_id=None,
        suggested_by_rule_id=None,
    )
    session = SessionStub()
    ledger = LedgerRepositoryStub()
    use_case = LedgerPostingService(cast(Any, session))
    use_case.ledger = cast(Any, ledger)
    idempotency_key = uuid4()

    operation = await use_case.post_imported_income_expense(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=uuid4()),
            ),
        ),
        document_id=document_id,
        raw_transaction_id=raw_transaction.id,
        account=account,
        plan=LedgerPostingPlan(
            operation_type=OperationType.INCOME,
            amount=raw_transaction.amount,
            currency=raw_transaction.currency,
            operation_date=raw_transaction.operation_date,
            posting_date=raw_transaction.posting_date,
            description=raw_transaction.description_normalized,
            balance_after=raw_transaction.balance_after,
        ),
        category=cast(Any, SimpleNamespace(id=uuid4())),
        property_=None,
        idempotency_key=idempotency_key,
        idempotency_fingerprint="confirm-fingerprint",
    )

    assert operation.type == OperationType.INCOME
    assert operation.affects_profit is True
    assert operation.idempotency_key == str(idempotency_key)
    assert operation.idempotency_fingerprint == "confirm-fingerprint"
    assert operation.extra_metadata == {
        "source": "raw_transaction",
        "raw_transaction_id": str(raw_transaction.id),
        "uploaded_document_id": str(document_id),
    }
    assert len(ledger.entries) == 1
    assert session.committed is False
    assert session.rolled_back is False


@pytest.mark.asyncio
async def test_post_raw_transaction_as_transfer_builds_balanced_entries_without_commit() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    source_account = account(workspace_id, "Карта")
    destination_account = account(workspace_id, "Депозит")
    raw_transaction = raw_row(
        workspace_id=workspace_id,
        document_id=document_id,
        account_id=source_account.id,
        amount=Decimal("-250.00"),
    )
    session = SessionStub()
    imports = TransferImportRepositoryStub(raw_transaction)
    ledger = LedgerRepositoryStub()
    references = TransferReferenceResolverStub(
        source_account=source_account,
        destination_account=destination_account,
    )
    document_status = DocumentStatusStub()
    actor = transfer_actor(
        session=session,
        imports=imports,
        ledger=ledger,
        references=references,
        document_status=document_status,
    )
    result = await actor.apply(
        context=workspace_context(workspace_id),
        command=CreateImportReviewTransferCommand(
            document_id=document_id,
            item_id=raw_transaction.id,
            counterparty_account_id=destination_account.id,
            idempotency_key=uuid4(),
        ),
    )
    operation = cast(Any, ledger.operation)

    assert operation.type == OperationType.TRANSFER
    assert operation.affects_profit is False
    assert [entry.amount for entry in ledger.entries] == [
        Decimal("-250.00"),
        Decimal("250.00"),
    ]
    assert [entry.account.id for entry in ledger.entries] == [
        source_account.id,
        destination_account.id,
    ]
    assert imports.links == [(raw_transaction.id, operation.id)]
    assert result.updated_item_ids == frozenset({raw_transaction.id})
    assert result.affected_document_ids == frozenset({document_id})
    assert document_status.document_ids == [document_id]
    assert session.committed is False


@pytest.mark.asyncio
async def test_post_paired_raw_transactions_links_both_rows_to_one_transfer() -> None:
    workspace_id = uuid4()
    source_document_id = uuid4()
    destination_document_id = uuid4()
    source_account = account(workspace_id, "Карта")
    destination_account = account(workspace_id, "Депозит")
    source = raw_row(
        workspace_id=workspace_id,
        document_id=source_document_id,
        account_id=source_account.id,
        amount=Decimal("-500.00"),
    )
    destination = raw_row(
        workspace_id=workspace_id,
        document_id=destination_document_id,
        account_id=destination_account.id,
        amount=Decimal("500.00"),
    )
    session = SessionStub()
    imports = TransferImportRepositoryStub(source, matched=destination)
    ledger = LedgerRepositoryStub()
    references = TransferReferenceResolverStub(
        source_account=source_account,
        destination_account=destination_account,
    )
    document_status = DocumentStatusStub()
    actor = transfer_actor(
        session=session,
        imports=imports,
        ledger=ledger,
        references=references,
        document_status=document_status,
    )
    result = await actor.apply(
        context=workspace_context(workspace_id),
        command=MatchImportReviewRawRowCommand(
            document_id=source_document_id,
            item_id=source.id,
            matched_item_id=destination.id,
            idempotency_key=uuid4(),
        ),
    )
    operation = cast(Any, ledger.operation)

    assert imports.links == [
        (source.id, operation.id),
        (destination.id, operation.id),
    ]
    assert sum((entry.amount for entry in ledger.entries), Decimal("0.00")) == Decimal("0.00")
    assert set(document_status.document_ids) == {
        source_document_id,
        destination_document_id,
    }
    assert result.updated_item_ids == frozenset({source.id, destination.id})
    assert result.affected_document_ids == frozenset({source_document_id, destination_document_id})
    assert session.committed is False


@pytest.mark.asyncio
async def test_link_raw_transaction_to_existing_manual_transfer_creates_no_entries() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    source_account = account(workspace_id, "Карта")
    raw_transaction = raw_row(
        workspace_id=workspace_id,
        document_id=document_id,
        account_id=source_account.id,
        amount=Decimal("-100.00"),
    )
    existing_operation = SimpleNamespace(id=uuid4())
    imports = TransferImportRepositoryStub(raw_transaction)
    ledger = LedgerRepositoryStub()
    ledger.operations = [existing_operation]
    actor = transfer_actor(
        session=SessionStub(),
        imports=imports,
        ledger=ledger,
        review_repository=ImportReviewRepositoryStub([existing_operation]),
        references=TransferReferenceResolverStub(
            source_account=source_account,
            destination_account=source_account,
        ),
        document_status=DocumentStatusStub(),
    )
    result = await actor.apply(
        context=workspace_context(workspace_id),
        command=LinkImportReviewExistingTransferCommand(
            document_id=document_id,
            item_id=raw_transaction.id,
            operation_id=existing_operation.id,
            idempotency_key=uuid4(),
        ),
    )

    assert imports.links == [(raw_transaction.id, existing_operation.id)]
    assert ledger.entries == []
    assert result.updated_item_ids == frozenset({raw_transaction.id})
    assert result.affected_document_ids == frozenset({document_id})


def account(workspace_id: UUID, name: str) -> Account:
    return Account(
        id=uuid4(),
        workspace_id=workspace_id,
        name=name,
        type=AccountType.CHECKING,
        currency="RUB",
        initial_balance=Decimal("0.00"),
    )


def raw_row(
    *,
    workspace_id: UUID,
    document_id: UUID,
    account_id: UUID,
    amount: Decimal,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=workspace_id,
        uploaded_document_id=document_id,
        uploaded_document=SimpleNamespace(account_id=account_id),
        linked_operation_id=None,
        account_id=account_id,
        status=RawTransactionStatus.NORMALIZED,
        amount=amount,
        currency="RUB",
        operation_date=date(2026, 7, 21),
        posting_date=None,
        description_normalized="Перевод",
        description_raw="Перевод",
        balance_after=None,
        dedupe_hash=None,
        raw_payload={},
        suggested_category_id=None,
        suggested_property_id=None,
        suggested_by_rule_id=None,
    )


def workspace_context(workspace_id: UUID) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )


def transfer_actor(
    *,
    session: SessionStub,
    imports: object,
    ledger: LedgerRepositoryStub,
    review_repository: ImportReviewRepositoryStub | None = None,
    references: object,
    document_status: DocumentStatusStub,
) -> ImportReviewTransferActor:
    actor = ImportReviewTransferActor(cast(Any, session))
    actor._documents = cast(Any, imports)
    actor._ledger = cast(Any, ledger)
    if review_repository is not None:
        review_repository.raw_repository = imports
    actor._review_repository = cast(
        Any,
        review_repository or imports,
    )
    actor._references = cast(Any, references)
    actor._posting = LedgerPostingService(cast(Any, session))
    actor._posting.ledger = cast(Any, ledger)
    actor._document_status = cast(Any, document_status)
    return actor


class TransferImportRepositoryStub(ImportRepositoryStub):
    def __init__(self, raw_transaction: object, *, matched: object | None = None) -> None:
        super().__init__(raw_transaction)
        self.matched = matched
        self.links: list[tuple[UUID, UUID]] = []

    async def get_raw_transaction_by_id_for_workspace(
        self,
        _workspace_id: UUID,
        _raw_transaction_id: UUID,
    ) -> object | None:
        return self.matched

    async def lock_raw_transactions_for_workspace(
        self,
        *,
        workspace_id: UUID,
        raw_transaction_ids: set[UUID],
    ) -> list[object]:
        rows = [self.raw_transaction]
        if self.matched is not None:
            rows.append(self.matched)
        return [
            row
            for row in rows
            if cast(Any, row).id in raw_transaction_ids
            and cast(Any, row).workspace_id == workspace_id
        ]

    async def list_transfer_candidate_raw_transactions(self, **_kwargs: object) -> list[object]:
        return [self.matched] if self.matched is not None else []

    async def link_raw_transaction_to_operation(
        self,
        raw_transaction: object,
        *,
        operation_id: UUID,
    ) -> None:
        raw_id = cast(Any, raw_transaction).id
        assert isinstance(raw_id, UUID)
        self.links.append((raw_id, operation_id))


class TransferReferenceResolverStub:
    def __init__(
        self,
        *,
        source_account: Account,
        destination_account: Account,
    ) -> None:
        self.source_account = source_account
        self.destination_account = destination_account

    async def get_transfer_account(
        self,
        _workspace_id: UUID,
        account_id: UUID,
    ) -> Account:
        if account_id == self.destination_account.id:
            return self.destination_account
        assert account_id == self.source_account.id
        return self.source_account

    async def get_transfer_category(self, _workspace_id: UUID) -> object:
        return SimpleNamespace(id=uuid4())
