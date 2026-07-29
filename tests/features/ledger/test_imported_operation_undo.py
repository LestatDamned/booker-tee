from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.import_review.application.commands.undo import (
    ImportReviewUndoService,
    UndoImportReviewPostingCommand,
)
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationSource, OperationStatus


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def flush(self) -> None:
        self.flushes += 1


class ImportRepositoryStub:
    def __init__(self, raw_transaction: object, documents: Mapping[UUID, object]) -> None:
        self.raw_transaction = raw_transaction
        self.documents = dict(documents)
        self.document_statuses: dict[UUID, UploadedDocumentStatus] = {}

    async def get_raw_transaction_for_workspace(self, *args: object) -> object:
        return self.raw_transaction

    async def get_document_for_workspace(
        self,
        _workspace_id: UUID,
        document_id: UUID,
    ) -> object | None:
        return self.documents.get(document_id)

    async def mark_document_status(
        self,
        document: object,
        status: UploadedDocumentStatus,
    ) -> None:
        document_id = cast(Any, document).id
        assert isinstance(document_id, UUID)
        self.document_statuses[document_id] = status


class LedgerRepositoryStub:
    def __init__(self, operation: object) -> None:
        self.operation = operation

    async def get_operation_for_workspace(self, *args: object) -> object:
        return self.operation


@pytest.mark.asyncio
async def test_undo_imported_transfer_restores_all_raw_rows_and_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    first_document_id = uuid4()
    second_document_id = uuid4()
    first_raw = raw_row(first_document_id, operation_id, suggested=True)
    second_raw = raw_row(second_document_id, operation_id, suggested=False)
    operation = SimpleNamespace(
        id=operation_id,
        workspace_id=workspace_id,
        source=OperationSource.BANK_PDF,
        status=OperationStatus.CONFIRMED,
        raw_transactions=[first_raw, second_raw],
        updated_by_user_id=None,
        extra_metadata={
            "raw_transaction_id": str(first_raw.id),
            "matched_raw_transaction_id": str(second_raw.id),
            "matched_uploaded_document_id": str(second_document_id),
        },
    )
    documents = {
        first_document_id: SimpleNamespace(id=first_document_id),
        second_document_id: SimpleNamespace(id=second_document_id),
    }
    session = SessionStub()
    imports = ImportRepositoryStub(first_raw, documents)
    service = ImportReviewUndoService(cast(Any, session))
    service._documents = cast(Any, imports)
    service._review_repository = cast(Any, imports)
    service._ledger = cast(Any, LedgerRepositoryStub(operation))
    refreshed: list[UUID] = []

    async def refresh(_service: object, document: object) -> None:
        document_id = cast(Any, document).id
        assert isinstance(document_id, UUID)
        refreshed.append(document_id)

    monkeypatch.setattr(
        "app.features.imports.statements.validation_service."
        "StatementValidationService.refresh_for_document",
        refresh,
    )

    result = await service.execute(
        context=workspace_context(workspace_id),
        command=UndoImportReviewPostingCommand(
            document_id=first_document_id,
            item_id=first_raw.id,
            expected_operation_id=operation_id,
        ),
    )

    assert result.operation_id == operation_id
    assert result.updated_item_ids == frozenset({first_raw.id, second_raw.id})
    assert result.affected_document_ids == frozenset({first_document_id, second_document_id})
    assert result.replayed is False
    assert operation.status == OperationStatus.IGNORED
    assert first_raw.linked_operation_id is None
    assert second_raw.linked_operation_id is None
    assert first_raw.status == RawTransactionStatus.SUGGESTED
    assert second_raw.status == RawTransactionStatus.NORMALIZED
    assert set(refreshed) == {first_document_id, second_document_id}
    assert imports.document_statuses == {
        first_document_id: UploadedDocumentStatus.REQUIRES_REVIEW,
        second_document_id: UploadedDocumentStatus.REQUIRES_REVIEW,
    }
    assert session.commits == 1


@pytest.mark.asyncio
async def test_unlink_from_manual_transfer_preserves_manual_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    document_id = uuid4()
    raw_transaction = raw_row(document_id, operation_id, suggested=False)
    operation = SimpleNamespace(
        id=operation_id,
        workspace_id=workspace_id,
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        raw_transactions=[raw_transaction],
        updated_by_user_id=None,
        extra_metadata={},
    )
    document = SimpleNamespace(id=document_id)
    session = SessionStub()
    imports = ImportRepositoryStub(raw_transaction, {document_id: document})
    service = ImportReviewUndoService(cast(Any, session))
    service._documents = cast(Any, imports)
    service._review_repository = cast(Any, imports)
    service._ledger = cast(Any, LedgerRepositoryStub(operation))

    async def refresh(_service: object, _document: object) -> None:
        return None

    monkeypatch.setattr(
        "app.features.imports.statements.validation_service."
        "StatementValidationService.refresh_for_document",
        refresh,
    )

    result = await service.execute(
        context=workspace_context(workspace_id),
        command=UndoImportReviewPostingCommand(
            document_id=document_id,
            item_id=raw_transaction.id,
            expected_operation_id=operation_id,
        ),
    )

    assert result.operation_id == operation_id
    assert result.updated_item_ids == frozenset({raw_transaction.id})
    assert result.affected_document_ids == frozenset({document_id})
    assert result.replayed is False
    assert operation.status == OperationStatus.CONFIRMED
    assert raw_transaction.linked_operation_id is None
    assert raw_transaction.status == RawTransactionStatus.NORMALIZED
    assert imports.document_statuses == {
        document_id: UploadedDocumentStatus.REQUIRES_REVIEW,
    }
    assert session.commits == 1


@pytest.mark.asyncio
async def test_undo_replay_restores_cross_document_result() -> None:
    workspace_id = uuid4()
    operation_id = uuid4()
    document_id = uuid4()
    matched_document_id = uuid4()
    raw_transaction = raw_row(document_id, operation_id, suggested=False)
    raw_transaction.linked_operation_id = None
    matched_item_id = uuid4()
    operation = SimpleNamespace(
        id=operation_id,
        workspace_id=workspace_id,
        source=OperationSource.BANK_PDF,
        status=OperationStatus.IGNORED,
        raw_transactions=[],
        extra_metadata={
            "raw_transaction_id": str(raw_transaction.id),
            "matched_raw_transaction_id": str(matched_item_id),
            "matched_uploaded_document_id": str(matched_document_id),
        },
    )
    session = SessionStub()
    service = ImportReviewUndoService(cast(Any, session))
    imports = ImportRepositoryStub(raw_transaction, {})
    service._documents = cast(Any, imports)
    service._review_repository = cast(Any, imports)
    service._ledger = cast(Any, LedgerRepositoryStub(operation))

    result = await service.execute(
        context=workspace_context(workspace_id),
        command=UndoImportReviewPostingCommand(
            document_id=document_id,
            item_id=raw_transaction.id,
            expected_operation_id=operation_id,
        ),
    )

    assert result.replayed is True
    assert result.updated_item_ids == frozenset({raw_transaction.id, matched_item_id})
    assert result.affected_document_ids == frozenset({document_id, matched_document_id})
    assert session.commits == 1
    assert session.rollbacks == 0


def raw_row(
    document_id: UUID,
    operation_id: UUID,
    *,
    suggested: bool,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        uploaded_document_id=document_id,
        linked_operation_id=operation_id,
        status=RawTransactionStatus.CONFIRMED,
        suggested_by_rule_id=uuid4() if suggested else None,
    )


def workspace_context(workspace_id: UUID) -> Any:
    return cast(
        Any,
        SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=uuid4()),
        ),
    )
