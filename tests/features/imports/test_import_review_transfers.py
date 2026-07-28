from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from app.features.import_review.application.transfer_options import (
    ImportReviewTransferDirection,
    ImportReviewTransferReader,
)
from app.features.import_review.application.transfer_suggestions import (
    ExistingTransferSuggestion,
    TransferSuggestion,
)
from app.features.imports.application.review.transfer_commands import (
    CreateImportReviewTransferCommand,
    ImportReviewTransferService,
    MatchImportReviewRawRowCommand,
)
from app.features.ledger.domain.types import OperationType
from app.features.ledger.errors import LedgerPostingError


class AccountSourceStub:
    def __init__(self, accounts: list[object]) -> None:
        self.accounts = accounts

    async def list_active_accounts(self, workspace_id):
        return self.accounts


class SuggestionSourceStub:
    def __init__(self, raw, existing) -> None:
        self.raw = raw
        self.existing = existing

    async def list_for_document(self, **kwargs):
        return self.raw

    async def list_existing_manual_for_document(self, **kwargs):
        return self.existing


@pytest.mark.asyncio
async def test_transfer_reader_keeps_eligibility_and_direction_on_server() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    source = account("Карта", "RUB", workspace_id)
    destination = account("Депозит", "RUB", workspace_id)
    foreign_currency = account("Евро", "EUR", workspace_id)
    row = raw_row(document_id, source, Decimal("-100.00"), 1)
    paired = raw_row(uuid4(), destination, Decimal("100.00"), 7)
    counterparty_entry = SimpleNamespace(account=destination)
    existing = ExistingTransferSuggestion(
        operation=cast(
            Any,
            SimpleNamespace(
                id=uuid4(),
                operation_date=date(2026, 7, 20),
                description="Между счетами",
            ),
        ),
        account_entry=cast(
            Any,
            SimpleNamespace(amount=Decimal("-100.00"), currency="RUB"),
        ),
        counterparty_entry=cast(Any, counterparty_entry),
        day_distance=1,
    )
    document = SimpleNamespace(
        id=document_id,
        account_id=source.id,
        raw_transactions=[row],
    )
    reader = ImportReviewTransferReader(
        cast(Any, AccountSourceStub([source, destination, foreign_currency])),
        cast(
            Any,
            SuggestionSourceStub(
                {
                    row.id: [
                        TransferSuggestion(
                            raw_transaction=cast(Any, paired),
                            day_distance=2,
                        )
                    ]
                },
                {row.id: [existing]},
            ),
        ),
    )

    options = (
        await reader.read_for_document(
            workspace_id=workspace_id,
            document=cast(Any, document),
        )
    )[row.id]

    assert options.direction is ImportReviewTransferDirection.SOURCE_TO_COUNTERPARTY
    assert options.ordinary_operation_type is OperationType.EXPENSE
    assert options.source_account is not None
    assert options.source_account.id == source.id
    assert options.counterparty_account is None
    assert [item.id for item in options.accounts] == [destination.id]
    assert options.raw_row_candidates[0].document_id == paired.uploaded_document_id
    assert options.raw_row_candidates[0].amount == Decimal("100.00")
    assert options.existing_operation_candidates[0].counterparty_account is not None
    assert options.existing_operation_candidates[0].counterparty_account.id == destination.id


@pytest.mark.asyncio
async def test_transfer_reader_exposes_confirmed_counterparty_from_same_workspace_only() -> None:
    workspace_id = uuid4()
    foreign_workspace_id = uuid4()
    document_id = uuid4()
    source = account("Карта", "RUB", workspace_id)
    destination = account("Накопительный", "RUB", workspace_id)
    foreign = account("Чужой счёт", "RUB", foreign_workspace_id)
    row = raw_row(document_id, source, Decimal("-100.00"), 1)
    row.linked_operation = SimpleNamespace(
        type=OperationType.TRANSFER,
        workspace_id=workspace_id,
        money_entries=[
            SimpleNamespace(
                workspace_id=workspace_id,
                account_id=source.id,
                account=source,
            ),
            SimpleNamespace(
                workspace_id=workspace_id,
                account_id=destination.id,
                account=destination,
            ),
        ],
    )
    document = SimpleNamespace(
        id=document_id,
        account=source,
        account_id=source.id,
        raw_transactions=[row],
    )
    reader = ImportReviewTransferReader(
        cast(Any, AccountSourceStub([source, destination, foreign])),
        cast(Any, SuggestionSourceStub({}, {})),
    )

    options = (
        await reader.read_for_document(
            workspace_id=workspace_id,
            document=cast(Any, document),
        )
    )[row.id]

    assert options.source_account is not None
    assert options.source_account.name == "Карта"
    assert options.counterparty_account is not None
    assert options.counterparty_account.name == "Накопительный"
    assert foreign.id not in {item.id for item in options.accounts}

    row.linked_operation.workspace_id = foreign_workspace_id
    isolated_options = (
        await reader.read_for_document(
            workspace_id=workspace_id,
            document=cast(Any, document),
        )
    )[row.id]
    assert isolated_options.counterparty_account is None


@pytest.mark.asyncio
async def test_transfer_service_replays_cross_document_result_by_idempotency_key() -> None:
    document_id = uuid4()
    paired_document_id = uuid4()
    item_id = uuid4()
    paired_item_id = uuid4()
    command = MatchImportReviewRawRowCommand(
        document_id=document_id,
        item_id=item_id,
        matched_item_id=paired_item_id,
        idempotency_key=uuid4(),
    )
    service = ImportReviewTransferService(cast(Any, SimpleNamespace()))
    operation = SimpleNamespace(
        idempotency_fingerprint=service._fingerprint(command),
        extra_metadata={
            "matched_uploaded_document_id": str(paired_document_id),
            "matched_raw_transaction_id": str(paired_item_id),
        },
    )
    service._ledger = cast(
        Any,
        SimpleNamespace(get_operation_by_idempotency_key=lambda **kwargs: async_value(operation)),
    )

    result = await service.execute(
        context=cast(Any, SimpleNamespace(workspace=SimpleNamespace(id=uuid4()))),
        command=command,
    )

    assert result.updated_item_ids == frozenset({item_id, paired_item_id})
    assert result.affected_document_ids == frozenset({document_id, paired_document_id})


@pytest.mark.asyncio
async def test_transfer_service_rejects_reused_key_with_another_payload() -> None:
    command = CreateImportReviewTransferCommand(
        document_id=uuid4(),
        item_id=uuid4(),
        counterparty_account_id=uuid4(),
        idempotency_key=uuid4(),
    )
    service = ImportReviewTransferService(cast(Any, SimpleNamespace()))
    operation = SimpleNamespace(idempotency_fingerprint="another", extra_metadata={})
    service._ledger = cast(
        Any,
        SimpleNamespace(get_operation_by_idempotency_key=lambda **kwargs: async_value(operation)),
    )

    with pytest.raises(LedgerPostingError, match="another payload"):
        await service.execute(
            context=cast(Any, SimpleNamespace(workspace=SimpleNamespace(id=uuid4()))),
            command=command,
        )


def account(name: str, currency: str, workspace_id) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        currency=currency,
        workspace_id=workspace_id,
    )


def raw_row(
    document_id,
    row_account,
    amount: Decimal,
    row_index: int,
) -> SimpleNamespace:
    document = SimpleNamespace(account=row_account, account_id=row_account.id)
    return SimpleNamespace(
        id=uuid4(),
        uploaded_document_id=document_id,
        uploaded_document=document,
        account=row_account,
        account_id=row_account.id,
        row_index=row_index,
        operation_date=date(2026, 7, 21),
        description_normalized="Перевод",
        description_raw=None,
        amount=amount,
        currency="RUB",
        linked_operation=None,
    )


async def async_value(value):
    return value
