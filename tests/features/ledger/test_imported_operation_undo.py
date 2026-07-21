from collections.abc import Mapping
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.imports.models import RawTransactionStatus, UploadedDocumentStatus
from app.features.ledger.application.imported_operations import ImportedOperationUndoUseCase
from app.features.ledger.domain.types import OperationSource, OperationStatus


class SessionStub:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


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
        source=OperationSource.BANK_PDF,
        status=OperationStatus.CONFIRMED,
        raw_transactions=[first_raw, second_raw],
        updated_by_user_id=None,
    )
    documents = {
        first_document_id: SimpleNamespace(id=first_document_id),
        second_document_id: SimpleNamespace(id=second_document_id),
    }
    session = SessionStub()
    imports = ImportRepositoryStub(first_raw, documents)
    use_case = ImportedOperationUndoUseCase(cast(Any, session))
    use_case.imports = cast(Any, imports)
    use_case.ledger = cast(Any, LedgerRepositoryStub(operation))
    refreshed: list[UUID] = []

    async def refresh(_repository: object, document: object) -> None:
        document_id = cast(Any, document).id
        assert isinstance(document_id, UUID)
        refreshed.append(document_id)

    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.refresh_document_validation",
        refresh,
    )

    result = await use_case.undo_raw_transaction_posting(
        context=workspace_context(workspace_id),
        document_id=first_document_id,
        raw_transaction_id=first_raw.id,
    )

    assert result is operation
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
        source=OperationSource.MANUAL,
        status=OperationStatus.CONFIRMED,
        raw_transactions=[raw_transaction],
        updated_by_user_id=None,
    )
    document = SimpleNamespace(id=document_id)
    session = SessionStub()
    imports = ImportRepositoryStub(raw_transaction, {document_id: document})
    use_case = ImportedOperationUndoUseCase(cast(Any, session))
    use_case.imports = cast(Any, imports)
    use_case.ledger = cast(Any, LedgerRepositoryStub(operation))

    async def refresh(_repository: object, _document: object) -> None:
        return None

    monkeypatch.setattr(
        "app.features.ledger.application.imported_operations.refresh_document_validation",
        refresh,
    )

    result = await use_case.undo_raw_transaction_posting(
        context=workspace_context(workspace_id),
        document_id=document_id,
        raw_transaction_id=raw_transaction.id,
    )

    assert result is operation
    assert operation.status == OperationStatus.CONFIRMED
    assert raw_transaction.linked_operation_id is None
    assert raw_transaction.status == RawTransactionStatus.NORMALIZED
    assert imports.document_statuses == {
        document_id: UploadedDocumentStatus.REQUIRES_REVIEW,
    }
    assert session.commits == 1


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
