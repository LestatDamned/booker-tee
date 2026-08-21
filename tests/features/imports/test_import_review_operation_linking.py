from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from import_test_support import ImportTestSession

from app.features.import_review.application.operation_candidates import (
    ExistingOperationCandidateReader,
)
from app.features.import_review.application.operation_linking import (
    ExistingOperationLinkService,
)
from app.features.import_review.schemas.commands import (
    LinkImportReviewExistingOperationCommand,
)
from app.features.imports.statements.types import RawTransactionStatus


async def test_manual_operation_candidate_matches_account_amount_currency_and_date() -> None:
    account_id = uuid4()
    row = raw_row(account_id=account_id)
    operation = manual_operation(account_id=account_id)
    source = CandidateSource([operation])

    result = await ExistingOperationCandidateReader(cast(Any, source)).read_for_document(
        workspace_id=uuid4(),
        document=cast(Any, SimpleNamespace(raw_transactions=[row])),
    )

    assert result[row.id][0].operation_id == operation.id
    assert result[row.id][0].description == "Ремонт автомобиля"
    assert result[row.id][0].category_name == "Автомобиль"
    assert result[row.id][0].day_distance == 0


async def test_manual_operation_candidate_rejects_a_different_amount() -> None:
    account_id = uuid4()
    row = raw_row(account_id=account_id)
    operation = manual_operation(account_id=account_id)
    operation.money_entries[0].amount = Decimal("-9999.00")

    result = await ExistingOperationCandidateReader(
        cast(Any, CandidateSource([operation]))
    ).read_for_document(
        workspace_id=uuid4(),
        document=cast(Any, SimpleNamespace(raw_transactions=[row])),
    )

    assert result == {}


async def test_link_existing_operation_reuses_ledger_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account_id = uuid4()
    row = raw_row(account_id=account_id)
    operation = manual_operation(account_id=account_id)
    session = ImportTestSession()
    service = ExistingOperationLinkService(cast(Any, session))
    review = LinkReviewStub(row, operation)
    service._review = cast(Any, review)
    service._ledger = cast(Any, LedgerStub(operation))
    service._documents = cast(Any, DocumentStub())

    async def no_refresh(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(
        "app.features.import_review.application.operation_linking."
        "StatementValidationService.refresh_for_document",
        no_refresh,
    )
    monkeypatch.setattr(
        "app.features.import_review.application.operation_linking."
        "ImportedDocumentStatusUpdater.sync_review_status",
        no_refresh,
    )
    command = LinkImportReviewExistingOperationCommand(
        document_id=uuid4(),
        item_id=row.id,
        operation_id=operation.id,
        expected_status=RawTransactionStatus.NORMALIZED,
    )
    workspace_id = uuid4()
    service._activity = cast(Any, SimpleNamespace(import_review_operation_linked=AsyncMock()))

    result = await service.execute(
        context=cast(
            Any,
            SimpleNamespace(
                workspace=SimpleNamespace(id=workspace_id),
                user=SimpleNamespace(id=uuid4()),
            ),
        ),
        command=command,
    )

    assert result.operation_id == operation.id
    assert row.linked_operation_id == operation.id
    assert row.status is RawTransactionStatus.CONFIRMED
    assert review.created_operation_count == 0
    service._activity.import_review_operation_linked.assert_awaited_once()
    assert session.commits == 1


class CandidateSource:
    def __init__(self, operations: list[object]) -> None:
        self.operations = operations

    async def list_manual_income_expense_candidates_for_raw_transactions(
        self,
        **_: object,
    ) -> list[object]:
        return self.operations


class LinkReviewStub:
    def __init__(self, row: SimpleNamespace, operation: SimpleNamespace) -> None:
        self.row = row
        self.operation = operation
        self.created_operation_count = 0

    async def get_raw_transaction_for_workspace(self, *_: object) -> SimpleNamespace:
        return self.row

    async def list_manual_income_expense_candidates_for_raw_transactions(
        self,
        **_: object,
    ) -> list[SimpleNamespace]:
        return [self.operation]

    async def link_raw_transaction_to_operation(
        self,
        row: SimpleNamespace,
        *,
        operation_id: UUID,
    ) -> None:
        row.linked_operation_id = operation_id
        row.status = RawTransactionStatus.CONFIRMED


class LedgerStub:
    def __init__(self, operation: SimpleNamespace) -> None:
        self.operation = operation

    async def get_operation_for_workspace_for_update(self, **_: object) -> SimpleNamespace:
        return self.operation


class DocumentStub:
    async def get_document_for_workspace_for_update(self, *_: object) -> object:
        return SimpleNamespace()


def raw_row(*, account_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        account_id=account_id,
        uploaded_document=SimpleNamespace(account_id=account_id),
        operation_date=date(2026, 5, 10),
        amount=Decimal("-10000.00"),
        currency="RUB",
        linked_operation_id=None,
        status=RawTransactionStatus.NORMALIZED,
    )


def manual_operation(*, account_id: UUID) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        operation_date=date(2026, 5, 10),
        description="Ремонт автомобиля",
        category=SimpleNamespace(name="Автомобиль"),
        raw_transactions=[],
        money_entries=[
            SimpleNamespace(
                account_id=account_id,
                amount=Decimal("-10000.00"),
                currency="RUB",
            )
        ],
    )
