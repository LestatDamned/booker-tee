from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.import_review.application.classification import ImportReviewReferencesDto
from app.features.import_review.application.duplicate_evidence import (
    ImportReviewDuplicateEvidenceDto,
)
from app.features.import_review.application.read_model import (
    ImportReviewReader,
    ImportReviewReadonlyReasonCode,
)
from app.features.import_review.application.transfer_options import (
    ImportReviewTransferOptionsDto,
)
from app.features.import_review.domain.classification import ReviewClassificationSource
from app.features.import_review.domain.confirmability import ReviewBlockingReasonCode
from app.features.import_review.domain.lifecycle import ImportReviewLifecycleAction
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationStatus, OperationType


class DocumentSourceStub:
    def __init__(self, document: object | None) -> None:
        self.document = document
        self.workspace_ids: list[object] = []

    async def get_document_for_workspace(self, workspace_id: object, document_id: object) -> Any:
        self.workspace_ids.append(workspace_id)
        if self.document is None or getattr(self.document, "id", None) != document_id:
            return None
        return self.document


class ReferenceReaderStub:
    async def read(self, workspace_id: object) -> ImportReviewReferencesDto:
        return ImportReviewReferencesDto(categories=(), properties=())


class EmptyTransferReaderStub:
    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewTransferOptionsDto]:
        return {}


class EmptyDuplicateReaderStub:
    async def read_for_document(
        self,
        *,
        workspace_id: UUID,
        document: UploadedDocument,
    ) -> dict[UUID, ImportReviewDuplicateEvidenceDto]:
        return {}


class DuplicateSourceStub:
    def __init__(self, candidates: list[object]) -> None:
        self.candidates = candidates
        self.workspace_ids: list[UUID] = []
        self.exclude_document_ids: list[UUID] = []

    async def list_possible_duplicate_candidates(
        self,
        *,
        workspace_id: UUID,
        fingerprints: object,
        exclude_document_id: UUID,
    ) -> list[object]:
        self.workspace_ids.append(workspace_id)
        self.exclude_document_ids.append(exclude_document_id)
        return self.candidates


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
        account_id=account.id,
        raw_transactions=[
            row(second_id, 2, RawTransactionStatus.MATCHED),
            row(first_id, 1, RawTransactionStatus.CONFIRMED),
        ],
    )
    source = DocumentSourceStub(document)

    result = await ImportReviewReader(
        cast(Any, source),
        cast(Any, ReferenceReaderStub()),
        EmptyTransferReaderStub(),
        EmptyDuplicateReaderStub(),
    ).read(
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
    assert result.items[1].classification.source is ReviewClassificationSource.INFERRED
    assert result.items[1].confirmability.can_confirm is False
    assert set(result.items[1].lifecycle.allowed_actions) == {
        ImportReviewLifecycleAction.MARK_DUPLICATE,
        ImportReviewLifecycleAction.NEEDS_REVIEW,
        ImportReviewLifecycleAction.IGNORE,
    }
    assert result.items[1].posting.operation_id is None
    assert result.items[1].posting.can_undo is False
    assert result.items[0].posting.operation_id is not None
    assert result.items[0].posting.can_undo is True
    assert result.items[0].classification.operation_type is OperationType.TRANSFER
    assert result.items[0].classification.source is ReviewClassificationSource.EXPLICIT
    assert (
        ReviewBlockingReasonCode.MISSING_CATEGORY
        in result.items[1].confirmability.blocking_reason_codes
    )
    assert result.capabilities.can_write is False
    assert (
        result.capabilities.readonly_reason_code
        is ImportReviewReadonlyReasonCode.FINANCIAL_WRITE_FORBIDDEN
    )


@pytest.mark.asyncio
async def test_import_review_reader_returns_none_for_unknown_document() -> None:
    source = DocumentSourceStub(None)

    result = await ImportReviewReader(
        cast(Any, source),
        cast(Any, ReferenceReaderStub()),
        EmptyTransferReaderStub(),
        EmptyDuplicateReaderStub(),
    ).read(
        workspace_id=uuid4(),
        document_id=uuid4(),
        can_write=True,
    )

    assert result is None


@pytest.mark.asyncio
async def test_possible_duplicate_evidence_is_built_from_workspace_scoped_candidate() -> None:
    from app.features.import_review.application.duplicate_evidence import (
        ImportReviewDuplicateReader,
    )

    workspace_id = uuid4()
    document_id = uuid4()
    candidate_document_id = uuid4()
    account_id = uuid4()
    target = row(uuid4(), 1, RawTransactionStatus.POSSIBLE_DUPLICATE)
    target.account_id = account_id
    candidate = row(uuid4(), 4, RawTransactionStatus.CONFIRMED)
    candidate.account_id = account_id
    candidate.uploaded_document_id = candidate_document_id
    candidate.uploaded_document = SimpleNamespace(
        id=candidate_document_id,
        original_filename="previous-statement.pdf",
    )
    document = SimpleNamespace(
        id=document_id,
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        account=None,
        account_id=None,
        raw_transactions=[target],
    )
    duplicate_source = DuplicateSourceStub([candidate])

    result = await ImportReviewReader(
        cast(Any, DocumentSourceStub(document)),
        cast(Any, ReferenceReaderStub()),
        EmptyTransferReaderStub(),
        duplicates=ImportReviewDuplicateReader(cast(Any, duplicate_source)),
    ).read(
        workspace_id=workspace_id,
        document_id=document_id,
        can_write=True,
    )

    assert result is not None
    evidence = result.items[0].duplicate_evidence
    assert evidence is not None
    assert evidence.candidate.item_id == candidate.id
    assert evidence.candidate.document_filename == "previous-statement.pdf"
    assert evidence.candidate.operation_id == candidate.linked_operation_id
    assert duplicate_source.workspace_ids == [workspace_id]
    assert duplicate_source.exclude_document_ids == [document_id]


@pytest.mark.asyncio
async def test_confirmed_row_uses_linked_operation_instead_of_rule_suggestion() -> None:
    workspace_id = uuid4()
    document_id = uuid4()
    operation_category_id = uuid4()
    confirmed_row = row(uuid4(), 1, RawTransactionStatus.CONFIRMED)
    confirmed_row.suggested_operation_type = OperationType.INCOME
    confirmed_row.suggested_category_id = uuid4()
    confirmed_row.linked_operation.type = OperationType.EXPENSE
    confirmed_row.linked_operation.category_id = operation_category_id
    confirmed_row.linked_operation.category = SimpleNamespace(system_key=None)
    document = SimpleNamespace(
        id=document_id,
        original_filename="statement.pdf",
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        account=None,
        account_id=None,
        raw_transactions=[confirmed_row],
    )

    result = await ImportReviewReader(
        cast(Any, DocumentSourceStub(document)),
        cast(Any, ReferenceReaderStub()),
        EmptyTransferReaderStub(),
        EmptyDuplicateReaderStub(),
    ).read(
        workspace_id=workspace_id,
        document_id=document_id,
        can_write=True,
    )

    assert result is not None
    item = result.items[0]
    assert item.classification.operation_type is OperationType.EXPENSE
    assert item.classification.source is ReviewClassificationSource.EXPLICIT
    assert item.selection.category_id == operation_category_id


def row(row_id: UUID, row_index: int, status: RawTransactionStatus) -> SimpleNamespace:
    operation_id = uuid4() if status is RawTransactionStatus.CONFIRMED else None
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
        account_id=None,
        suggested_category_id=None,
        suggested_property_id=None,
        suggested_operation_type=None,
        suggested_by_rule_id=None,
        normalization_error=None,
        raw_payload={},
        linked_operation_id=operation_id,
        linked_operation=(
            SimpleNamespace(
                status=OperationStatus.CONFIRMED,
                type=OperationType.TRANSFER,
                category_id=None,
                category=None,
                property_id=None,
            )
            if operation_id is not None
            else None
        ),
    )
