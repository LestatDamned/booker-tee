from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import Account, AccountType
from app.features.imports.models import RawTransactionStatus
from app.features.ledger.application.raw_transaction_posting import (
    RawTransactionPostingUseCase,
)
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
        self.entries: list[object] = []

    async def create_operation(self, operation: Any) -> Any:
        operation.id = uuid4()
        return operation

    async def create_money_entry(self, money_entry: object) -> object:
        self.entries.append(money_entry)
        return money_entry


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

    async def get_category_or_uncategorized(self, *args: object) -> object:
        return SimpleNamespace(id=uuid4())

    async def get_property(self, *args: object) -> None:
        return None


class DocumentStatusStub:
    async def mark_imported_if_complete(self, **kwargs: object) -> bool:
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
    use_case = RawTransactionPostingUseCase(cast(Any, session))
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
    )

    assert references.raw_account_requests == [raw_transaction]
    assert operation.type == OperationType.INCOME
    assert imports.linked_operation_id == operation.id
    assert len(ledger.entries) == 1
    assert session.committed is True
    assert session.rolled_back is False
