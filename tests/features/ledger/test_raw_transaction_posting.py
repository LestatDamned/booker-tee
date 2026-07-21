from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.imports.models import RawTransactionStatus
from app.features.ledger.application.ledger_reference_resolver import LedgerReferenceResolver
from app.features.ledger.application.raw_transaction_posting import (
    RawTransactionPoster,
)
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import LedgerPostingError


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
        self.manual_transfer_candidates: list[object] = []

    async def create_operation(self, operation: Any) -> Any:
        operation.id = uuid4()
        return operation

    async def create_money_entry(self, money_entry: object) -> object:
        self.entries.append(money_entry)
        return money_entry

    async def list_manual_transfer_candidates_for_raw_transaction(
        self,
        **_kwargs: object,
    ) -> list[object]:
        return self.manual_transfer_candidates

    async def get_operation_for_workspace_for_update(
        self,
        *,
        workspace_id: UUID,
        operation_id: UUID,
    ) -> object | None:
        return next(
            (
                candidate
                for candidate in self.manual_transfer_candidates
                if getattr(candidate, "id", None) == operation_id
            ),
            None,
        )


class ReferenceResolverStub:
    def __init__(self, account: Account) -> None:
        self.account = account
        self.raw_account_requests: list[object] = []

    async def get_account_for_raw_transaction(
        self,
        workspace_id: UUID,
        raw_transaction: object,
    ) -> Account:
        self.raw_account_requests.append(raw_transaction)
        return self.account

    async def get_required_import_category(self, *args: object) -> object:
        return SimpleNamespace(id=uuid4())

    async def get_property(self, *args: object) -> None:
        return None


class CategoryLookupStub:
    def __init__(self, category: object | None) -> None:
        self.category = category

    async def get_for_workspace(self, *args: object) -> object | None:
        return self.category


class DocumentStatusStub:
    def __init__(self) -> None:
        self.document_ids: list[UUID] = []

    async def mark_imported_if_complete(self, **kwargs: object) -> bool:
        document_id = kwargs["document_id"]
        assert isinstance(document_id, UUID)
        self.document_ids.append(document_id)
        return False


@pytest.mark.asyncio
async def test_post_raw_transaction_uses_document_level_account() -> None:
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
    imports = ImportRepositoryStub(raw_transaction)
    ledger = LedgerRepositoryStub()
    references = ReferenceResolverStub(account)
    use_case = RawTransactionPoster(cast(Any, session))
    use_case.imports = cast(Any, imports)
    use_case.ledger = cast(Any, ledger)
    use_case.references = cast(Any, references)
    use_case.document_status = cast(Any, DocumentStatusStub())

    operation = await use_case.post_raw_transaction(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=uuid4()),
            ),
        ),
        document_id=document_id,
        raw_transaction_id=raw_transaction.id,
        category_id=uuid4(),
    )

    assert references.raw_account_requests == [raw_transaction]
    assert operation.type == OperationType.INCOME
    assert imports.linked_operation_id == operation.id
    assert len(ledger.entries) == 1
    assert session.committed is False
    assert session.rolled_back is False


@pytest.mark.asyncio
async def test_import_posting_rejects_missing_and_uncategorized_category() -> None:
    resolver = LedgerReferenceResolver(cast(Any, SessionStub()))
    resolver.categories = cast(Any, CategoryLookupStub(None))

    with pytest.raises(LedgerPostingError, match="requires a category"):
        await resolver.get_required_import_category(uuid4(), None)

    resolver.categories = cast(
        Any,
        CategoryLookupStub(SimpleNamespace(id=uuid4(), system_key="uncategorized")),
    )
    with pytest.raises(LedgerPostingError, match="requires a real category"):
        await resolver.get_required_import_category(uuid4(), uuid4())


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
    use_case = RawTransactionPoster(cast(Any, session))
    use_case.imports = cast(Any, imports)
    use_case.ledger = cast(Any, ledger)
    use_case.references = cast(Any, references)
    use_case.document_status = cast(Any, document_status)

    operation = await use_case.post_raw_transaction_as_transfer(
        context=workspace_context(workspace_id),
        document_id=document_id,
        raw_transaction_id=raw_transaction.id,
        counterparty_account_id=destination_account.id,
        matched_raw_transaction_id=None,
    )

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
        matched_raw_transaction=destination,
    )
    document_status = DocumentStatusStub()
    use_case = RawTransactionPoster(cast(Any, session))
    use_case.imports = cast(Any, imports)
    use_case.ledger = cast(Any, ledger)
    use_case.references = cast(Any, references)
    use_case.document_status = cast(Any, document_status)

    operation = await use_case.post_raw_transaction_as_transfer(
        context=workspace_context(workspace_id),
        document_id=source_document_id,
        raw_transaction_id=source.id,
        counterparty_account_id=destination_account.id,
        matched_raw_transaction_id=destination.id,
    )

    assert imports.links == [
        (source.id, operation.id),
        (destination.id, operation.id),
    ]
    assert sum((entry.amount for entry in ledger.entries), Decimal("0.00")) == Decimal("0.00")
    assert set(document_status.document_ids) == {
        source_document_id,
        destination_document_id,
    }
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
    ledger.manual_transfer_candidates = [existing_operation]
    use_case = RawTransactionPoster(cast(Any, SessionStub()))
    use_case.imports = cast(Any, imports)
    use_case.ledger = cast(Any, ledger)
    use_case.document_status = cast(Any, DocumentStatusStub())

    operation = await use_case.link_raw_transaction_to_existing_transfer(
        context=workspace_context(workspace_id),
        document_id=document_id,
        raw_transaction_id=raw_transaction.id,
        operation_id=existing_operation.id,
    )

    assert operation is existing_operation
    assert imports.links == [(raw_transaction.id, existing_operation.id)]
    assert ledger.entries == []


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
        matched_raw_transaction: object | None = None,
    ) -> None:
        self.source_account = source_account
        self.destination_account = destination_account
        self.matched_raw_transaction = matched_raw_transaction

    async def get_account_for_raw_transaction(
        self,
        _workspace_id: UUID,
        raw_transaction: object,
    ) -> Account:
        if raw_transaction is self.matched_raw_transaction:
            return self.destination_account
        return self.source_account

    async def get_account(self, _workspace_id: UUID, account_id: UUID) -> Account:
        assert account_id == self.destination_account.id
        return self.destination_account

    async def get_transfer_category(self, _workspace_id: UUID) -> object:
        return SimpleNamespace(id=uuid4())
