from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from app.features.import_review.application.transfer_options import (
    TransferSuggestionUseCase,
)


class ImportRepositoryStub:
    def __init__(self, candidates: list[object]) -> None:
        self.candidates = candidates
        self.requests: list[tuple[UUID, object]] = []

    async def list_transfer_candidate_raw_transactions_for_sources(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[object],
    ) -> list[object]:
        self.requests.append((workspace_id, raw_transactions))
        return self.candidates


class ImportReviewRepositoryStub:
    def __init__(self, candidates: list[object]) -> None:
        self.candidates = candidates
        self.requests: list[tuple[UUID, object]] = []

    async def list_manual_transfer_candidates_for_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[object],
    ) -> list[object]:
        self.requests.append((workspace_id, raw_transactions))
        return self.candidates


async def test_transfer_suggestions_skip_linked_rows_and_preserve_day_distance() -> None:
    workspace_id = uuid4()
    source = raw_row(operation_date=date(2026, 7, 21), account_id=uuid4())
    linked = raw_row(
        operation_date=date(2026, 7, 21),
        account_id=source.account_id,
        linked_operation_id=uuid4(),
    )
    candidate = raw_row(
        operation_date=date(2026, 7, 19),
        account_id=uuid4(),
        amount=Decimal("100.00"),
    )
    imports = ImportRepositoryStub([candidate])
    use_case = TransferSuggestionUseCase(cast(Any, object()))
    use_case.review_repository = cast(Any, imports)

    suggestions = await use_case.list_for_document(
        workspace_id=workspace_id,
        raw_transactions=cast(Any, [source, linked]),
    )

    assert set(suggestions) == {source.id}
    assert suggestions[source.id][0].raw_transaction is candidate
    assert suggestions[source.id][0].day_distance == 2
    assert imports.requests == [(workspace_id, [source, linked])]


async def test_existing_manual_transfer_suggestion_selects_account_and_counterparty_entries() -> (
    None
):
    workspace_id = uuid4()
    account_id = uuid4()
    counterparty_account_id = uuid4()
    source = raw_row(
        operation_date=date(2026, 7, 21),
        account_id=account_id,
        amount=Decimal("-100.00"),
    )
    account_entry = SimpleNamespace(
        account_id=account_id,
        amount=Decimal("-100.00"),
        currency="RUB",
    )
    counterparty_entry = SimpleNamespace(
        account_id=counterparty_account_id,
        amount=Decimal("100.00"),
        currency="RUB",
    )
    operation = SimpleNamespace(
        id=uuid4(),
        operation_date=date(2026, 7, 22),
        money_entries=[account_entry, counterparty_entry],
        raw_transactions=[],
    )
    review_repository = ImportReviewRepositoryStub([operation])
    use_case = TransferSuggestionUseCase(cast(Any, object()))
    use_case.review_repository = cast(Any, review_repository)

    suggestions = await use_case.list_existing_manual_for_document(
        workspace_id=workspace_id,
        raw_transactions=cast(Any, [source]),
    )

    suggestion = suggestions[source.id][0]
    assert suggestion.operation is operation
    assert suggestion.account_entry is account_entry
    assert suggestion.counterparty_entry is counterparty_entry
    assert suggestion.day_distance == 1
    assert review_repository.requests == [(workspace_id, [source])]


def raw_row(
    *,
    operation_date: date,
    linked_operation_id: UUID | None = None,
    account_id: UUID | None = None,
    amount: Decimal = Decimal("-100.00"),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        operation_date=operation_date,
        linked_operation_id=linked_operation_id,
        account_id=account_id,
        uploaded_document=SimpleNamespace(account_id=account_id),
        amount=amount,
        currency="RUB",
    )
