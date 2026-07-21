from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.imports.application.review.read_model import (
    ImportReviewReader,
    ImportReviewReadonlyReasonCode,
)
from app.features.imports.domain.types import RawTransactionStatus
from app.features.imports.models import UploadedDocumentStatus


class DocumentSourceStub:
    def __init__(self, document: object | None) -> None:
        self.document = document
        self.workspace_ids: list[object] = []

    async def get_document_for_workspace(self, workspace_id: object, document_id: object) -> Any:
        self.workspace_ids.append(workspace_id)
        if self.document is None or getattr(self.document, "id", None) != document_id:
            return None
        return self.document


@pytest.mark.asyncio
async def test_import_review_reader_builds_ordered_raw_and_normalized_rows() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    account = SimpleNamespace(id=uuid4(), name="Основной", currency="RUB")
    first_id = uuid4()
    second_id = uuid4()
    document = SimpleNamespace(
        id=document_id,
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        account=account,
        raw_transactions=[
            row(second_id, 2, RawTransactionStatus.MATCHED),
            row(first_id, 1, RawTransactionStatus.CONFIRMED),
        ],
    )
    source = DocumentSourceStub(document)

    result = await ImportReviewReader(cast(Any, source)).read(
        workspace_id=workspace_id,
        document_id=document_id,
        can_write=False,
    )

    assert result is not None
    assert source.workspace_ids == [workspace_id]
    assert [item.id for item in result.items] == [first_id, second_id]
    assert result.queue.completed == 1
    assert result.queue.first_remaining_item_id == second_id
    assert result.items[1].source_account is not None
    assert result.items[1].source_account.name == "Основной"
    assert result.items[1].raw.amount == "-1250,50"
    assert result.items[1].normalized.amount == Decimal("-1250.50")
    assert result.capabilities.can_write is False
    assert (
        result.capabilities.readonly_reason_code
        is ImportReviewReadonlyReasonCode.FINANCIAL_WRITE_FORBIDDEN
    )


@pytest.mark.asyncio
async def test_import_review_reader_returns_none_for_unknown_document() -> None:
    source = DocumentSourceStub(None)

    result = await ImportReviewReader(cast(Any, source)).read(
        workspace_id=uuid4(),
        document_id=uuid4(),
        can_write=True,
    )

    assert result is None


def row(row_id: UUID, row_index: int, status: RawTransactionStatus) -> SimpleNamespace:
    return SimpleNamespace(
        id=row_id,
        row_index=row_index,
        status=status,
        account=None,
        operation_date_raw="20.07.2026",
        posting_date_raw=None,
        description_raw="Покупка",
        amount_raw="-1250,50",
        currency_raw="RUB",
        balance_after_raw="10000,00",
        account_hint_raw="*1234",
        operation_date=date(2026, 7, 20),
        posting_date=None,
        description_normalized="Покупка",
        amount=Decimal("-1250.50"),
        currency="RUB",
        balance_after=Decimal("10000.00"),
    )
