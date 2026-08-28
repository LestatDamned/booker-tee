import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4, uuid5

import pytest
from fastapi import UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.settings import Settings
from app.features.accounts.models import Account, AccountType
from app.features.import_review.application.undo import ImportReviewUndoService
from app.features.import_review.schemas.commands import UndoImportReviewPostingCommand
from app.features.imports.documents.commands.upload import StatementUploadUseCase
from app.features.imports.documents.errors import UploadProcessingError
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.documents.source_cleanup import UploadSourceCleanup
from app.features.imports.documents.types import (
    ParseAttemptStatus,
    UploadedDocumentSource,
    UploadedDocumentStatus,
    UploadedDocumentType,
)
from app.features.imports.models import ParseAttempt, RawTransaction, UploadedDocument
from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import MoneyEntry, Operation
from app.features.users.models import User
from app.features.workspaces.domain.types import (
    WorkspaceMemberStatus,
    WorkspaceRole,
    WorkspaceType,
)
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.workspaces.service import WorkspaceContext

pytestmark = pytest.mark.skipif(
    not os.getenv("BOOKER_TEE_TEST_DATABASE_URL"),
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for committed failure tests.",
)


async def test_partial_raw_rows_roll_back_before_committed_failure_state(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    user_id, workspace_id, document_id, attempt_id = (uuid4() for _ in range(4))
    async with postgres_sessions() as session:
        session.add(User(id=user_id, email=f"failure-{user_id}@example.test", password_hash="hash"))
        session.add(
            Workspace(
                id=workspace_id,
                owner_id=user_id,
                name="Failure transaction",
                type=WorkspaceType.PERSONAL,
            )
        )
        session.add(
            UploadedDocument(
                id=document_id,
                workspace_id=workspace_id,
                source=UploadedDocumentSource.WEB_UPLOAD,
                document_type=UploadedDocumentType.BANK_STATEMENT,
                status=UploadedDocumentStatus.PARSING,
                original_filename="sanitized.pdf",
                sha256_hash="a" * 64,
            )
        )
        session.add(
            ParseAttempt(
                id=attempt_id,
                workspace_id=workspace_id,
                uploaded_document_id=document_id,
                parser_name="test",
            )
        )
        await session.commit()

        session.add(
            RawTransaction(
                workspace_id=workspace_id,
                uploaded_document_id=document_id,
                parse_attempt_id=attempt_id,
                row_index=0,
                status=RawTransactionStatus.EXTRACTED,
                raw_payload={"source_row_id": "partial:1"},
            )
        )
        await session.flush()
        use_case = object.__new__(StatementUploadUseCase)
        use_case.session = session
        use_case.documents = DocumentRepository(session)
        await use_case._commit_terminal_failure(
            workspace_id=workspace_id,
            document_id=document_id,
            attempt_id=attempt_id,
            error=RuntimeError("private payload"),
            extracted=ExtractedStatement(text_by_page=["bounded"], tables_by_page=[]),
        )

    try:
        async with postgres_sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RawTransaction)
                    .where(RawTransaction.uploaded_document_id == document_id)
                )
                == 0
            )
            attempt = await session.get(ParseAttempt, attempt_id)
            document = await session.get(UploadedDocument, document_id)
            assert attempt is not None and attempt.status is ParseAttemptStatus.FAILED
            assert attempt.raw_text_by_page_json == ["bounded"]
            assert attempt.error_message_sanitized == "RuntimeError"
            assert (
                document is not None and document.status is UploadedDocumentStatus.FAILED_TO_PARSE
            )
    finally:
        async with postgres_sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


async def test_expired_raw_selection_covers_terminal_status_boundaries(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    user_id, workspace_id = uuid4(), uuid4()
    cutoff = datetime(2026, 8, 24, 12, tzinfo=UTC)
    expected: set[UUID] = set()
    async with postgres_sessions() as session:
        session.add(
            User(id=user_id, email=f"raw-boundary-{user_id}@example.test", password_hash="hash")
        )
        session.add(
            Workspace(
                id=workspace_id,
                owner_id=user_id,
                name="Raw cleanup boundaries",
                type=WorkspaceType.PERSONAL,
            )
        )
        for status in (
            UploadedDocumentStatus.IMPORTED,
            UploadedDocumentStatus.IGNORED,
            UploadedDocumentStatus.FAILED_TO_PARSE,
            UploadedDocumentStatus.REQUIRES_REVIEW,
        ):
            for offset in (-timedelta(seconds=1), timedelta(0), timedelta(seconds=1)):
                document_id, attempt_id = uuid4(), uuid4()
                session.add(
                    UploadedDocument(
                        id=document_id,
                        workspace_id=workspace_id,
                        source=UploadedDocumentSource.WEB_UPLOAD,
                        document_type=UploadedDocumentType.BANK_STATEMENT,
                        status=status,
                        original_filename="sanitized.pdf",
                        sha256_hash=uuid4().hex * 2,
                        created_at=cutoff + offset,
                    )
                )
                session.add(
                    ParseAttempt(
                        id=attempt_id,
                        workspace_id=workspace_id,
                        uploaded_document_id=document_id,
                        parser_name="test",
                        raw_text_by_page_json=["private"],
                        raw_tables_json=[{"tables": [["private"]]}],
                    )
                )
                if status is not UploadedDocumentStatus.REQUIRES_REVIEW and offset <= timedelta(0):
                    expected.add(document_id)
        await session.commit()

        selected = await DocumentRepository(session).list_documents_with_expired_raw(
            cutoff=cutoff,
            limit=100,
        )
        assert {
            document.id for document in selected if document.workspace_id == workspace_id
        } == expected

    async with postgres_sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_raw_cleanup_preserves_ledger_then_import_undo_still_works(
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    user_id, workspace_id, account_id = uuid4(), uuid4(), uuid4()
    document_id, attempt_id, row_id, operation_id = (uuid4() for _ in range(4))
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    async with postgres_sessions() as session:
        session.add(
            User(id=user_id, email=f"raw-ledger-{user_id}@example.test", password_hash="hash")
        )
        session.add(
            Workspace(
                id=workspace_id,
                owner_id=user_id,
                name="Raw ledger invariant",
                type=WorkspaceType.PERSONAL,
            )
        )
        session.add(
            Account(
                id=account_id,
                workspace_id=workspace_id,
                name="Card",
                type=AccountType.CARD,
                currency="RUB",
            )
        )
        session.add(
            UploadedDocument(
                id=document_id,
                workspace_id=workspace_id,
                source=UploadedDocumentSource.WEB_UPLOAD,
                document_type=UploadedDocumentType.BANK_STATEMENT,
                status=UploadedDocumentStatus.IMPORTED,
                original_filename="sanitized.pdf",
                sha256_hash="b" * 64,
                account_id=account_id,
                created_at=now - timedelta(hours=49),
            )
        )
        session.add(
            ParseAttempt(
                id=attempt_id,
                workspace_id=workspace_id,
                uploaded_document_id=document_id,
                parser_name="test",
                status=ParseAttemptStatus.SUCCESS,
                raw_text_by_page_json=["private full page"],
                raw_tables_json=[{"tables": [["private cell"]]}],
            )
        )
        session.add(
            Operation(
                id=operation_id,
                workspace_id=workspace_id,
                type=OperationType.EXPENSE,
                status=OperationStatus.CONFIRMED,
                affects_profit=True,
                operation_date=date(2026, 8, 1),
                source=OperationSource.BANK_PDF,
                confirmed_at=now,
                extra_metadata={"raw_transaction_id": str(row_id)},
            )
        )
        session.add(
            MoneyEntry(
                workspace_id=workspace_id,
                operation_id=operation_id,
                account_id=account_id,
                amount=Decimal("-125.00"),
                currency="RUB",
                entry_order=1,
            )
        )
        session.add(
            RawTransaction(
                id=row_id,
                workspace_id=workspace_id,
                uploaded_document_id=document_id,
                parse_attempt_id=attempt_id,
                row_index=0,
                status=RawTransactionStatus.CONFIRMED,
                raw_payload={"source_row_id": "stable:1"},
                linked_operation_id=operation_id,
            )
        )
        await session.commit()

        cleanup = UploadSourceCleanup(session, Settings())
        document = await cleanup.documents.get_document_for_workspace_for_update(
            workspace_id,
            document_id,
        )
        assert document is not None

        class OwnDocumentBatch:
            calls = 0

            async def list_documents_with_expired_raw(self, **_kwargs: object):
                self.calls += 1
                return [document] if self.calls == 1 else []

        cleanup.documents = cast(Any, OwnDocumentBatch())
        assert await asyncio.wait_for(cleanup._scrub_expired_raw(now, 10), timeout=2) == 1
        attempt = await session.get(ParseAttempt, attempt_id)
        operation = await session.get(Operation, operation_id)
        entry_total = await session.scalar(
            select(func.sum(MoneyEntry.amount)).where(MoneyEntry.operation_id == operation_id)
        )
        assert attempt is not None and attempt.raw_text_by_page_json is None
        assert attempt.raw_tables_json is None
        assert operation is not None and operation.status is OperationStatus.CONFIRMED
        assert entry_total == Decimal("-125.00")

        context = SimpleNamespace(
            workspace=SimpleNamespace(id=workspace_id),
            user=SimpleNamespace(id=user_id),
        )
        result = await asyncio.wait_for(
            ImportReviewUndoService(session).execute(
                context=cast(WorkspaceContext, context),
                command=UndoImportReviewPostingCommand(
                    document_id=document_id,
                    item_id=row_id,
                    expected_operation_id=operation_id,
                ),
            ),
            timeout=2,
        )
        assert result.operation_id == operation_id
        assert operation.status is OperationStatus.IGNORED
        row = await session.get(RawTransaction, row_id)
        assert row is not None and row.linked_operation_id is None
        assert row.status is RawTransactionStatus.NORMALIZED

    async with postgres_sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()


async def test_attempt_commit_cancellation_persists_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
    tmp_path: Path,
) -> None:
    user_id, workspace_id, account_id = uuid4(), uuid4(), uuid4()
    async with postgres_sessions() as session:
        user = User(
            id=user_id,
            email=f"attempt-commit-{user_id}@example.test",
            password_hash="hash",
        )
        workspace = Workspace(
            id=workspace_id,
            owner_id=user_id,
            name="Attempt commit cancellation",
            type=WorkspaceType.PERSONAL,
        )
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        )
        session.add_all(
            [
                user,
                workspace,
                membership,
                Account(
                    id=account_id,
                    workspace_id=workspace_id,
                    name="Card",
                    type=AccountType.CARD,
                    currency="RUB",
                ),
            ]
        )
        await session.commit()

        original_commit = session.commit
        commit_calls = 0

        async def commit_then_cancel_attempt_boundary() -> None:
            nonlocal commit_calls
            await original_commit()
            commit_calls += 1
            if commit_calls == 2:
                raise asyncio.CancelledError

        monkeypatch.setattr(session, "commit", commit_then_cancel_attempt_boundary)
        use_case = StatementUploadUseCase(
            session,
            Settings(upload_storage_dir=tmp_path),
        )

        with pytest.raises(asyncio.CancelledError):
            await use_case.upload_statement(
                context=WorkspaceContext(
                    user=user,
                    workspace=workspace,
                    membership=membership,
                ),
                upload_file=UploadFile(
                    file=BytesIO(b"%PDF-1.4 synthetic"),
                    filename="statement.pdf",
                ),
                account_id=account_id,
            )

        assert commit_calls == 3

    try:
        async with postgres_sessions() as session:
            document = await session.scalar(
                select(UploadedDocument).where(UploadedDocument.workspace_id == workspace_id)
            )
            attempt = await session.scalar(
                select(ParseAttempt).where(ParseAttempt.workspace_id == workspace_id)
            )
            assert document is not None
            assert attempt is not None and attempt.status is ParseAttemptStatus.FAILED
            assert document.status is UploadedDocumentStatus.FAILED_TO_PARSE
            assert document.storage_key is not None
            assert (tmp_path / document.storage_key).is_file()
    finally:
        async with postgres_sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


@pytest.mark.parametrize("failure_kind", ["cancellation", "unexpected"])
async def test_ambiguous_initial_document_commit_reconciles_terminal_state_and_retry(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
    tmp_path: Path,
    failure_kind: str,
) -> None:
    marker = "INITIAL_COMMIT_PRIVATE_MARKER /private/source.pdf sql-params"
    user_id, workspace_id, account_id = uuid4(), uuid4(), uuid4()
    foreign_user_id, foreign_workspace_id = uuid4(), uuid4()
    idempotency_key = uuid4()
    document_id = uuid5(workspace_id, f"statement-upload:{idempotency_key}")
    foreign_document_id = uuid4()
    async with postgres_sessions() as session:
        user = User(
            id=user_id,
            email=f"initial-commit-{user_id}@example.test",
            password_hash="hash",
        )
        workspace = Workspace(
            id=workspace_id,
            owner_id=user_id,
            name="Initial commit reconciliation",
            type=WorkspaceType.PERSONAL,
        )
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        )
        session.add_all(
            [
                user,
                workspace,
                membership,
                Account(
                    id=account_id,
                    workspace_id=workspace_id,
                    name="Card",
                    type=AccountType.CARD,
                    currency="RUB",
                ),
                User(
                    id=foreign_user_id,
                    email=f"foreign-initial-{foreign_user_id}@example.test",
                    password_hash="hash",
                ),
                Workspace(
                    id=foreign_workspace_id,
                    owner_id=foreign_user_id,
                    name="Foreign initial commit",
                    type=WorkspaceType.PERSONAL,
                ),
                UploadedDocument(
                    id=foreign_document_id,
                    workspace_id=foreign_workspace_id,
                    source=UploadedDocumentSource.WEB_UPLOAD,
                    document_type=UploadedDocumentType.BANK_STATEMENT,
                    status=UploadedDocumentStatus.UPLOADED,
                    original_filename="foreign.pdf",
                    sha256_hash="f" * 64,
                ),
            ]
        )
        await session.commit()

        original_commit = session.commit
        commit_calls = 0

        async def commit_then_fail_initial_boundary() -> None:
            nonlocal commit_calls
            await original_commit()
            commit_calls += 1
            if commit_calls == 1:
                if failure_kind == "cancellation":
                    raise asyncio.CancelledError
                raise RuntimeError(marker)

        monkeypatch.setattr(session, "commit", commit_then_fail_initial_boundary)
        use_case = StatementUploadUseCase(session, Settings(upload_storage_dir=tmp_path))
        context = WorkspaceContext(user=user, workspace=workspace, membership=membership)
        upload = UploadFile(file=BytesIO(b"%PDF-1.4 synthetic"), filename="statement.pdf")

        expected_error = (
            asyncio.CancelledError if failure_kind == "cancellation" else UploadProcessingError
        )
        with pytest.raises(expected_error):
            await use_case.upload_statement(
                context=context,
                upload_file=upload,
                account_id=account_id,
                idempotency_key=idempotency_key,
            )

        assert commit_calls == 2
        monkeypatch.setattr(session, "commit", original_commit)
        document = await session.get(UploadedDocument, document_id)
        attempts = list(
            await session.scalars(
                select(ParseAttempt).where(
                    ParseAttempt.workspace_id == workspace_id,
                    ParseAttempt.uploaded_document_id == document_id,
                )
            )
        )
        foreign_document = await session.get(UploadedDocument, foreign_document_id)
        assert document is not None
        assert document.workspace_id == workspace_id
        assert document.status is UploadedDocumentStatus.FAILED_TO_PARSE
        assert document.storage_key is not None
        assert (tmp_path / document.storage_key).is_file()
        assert len(attempts) == 1 and attempts[0].status is ParseAttemptStatus.FAILED
        assert foreign_document is not None
        assert foreign_document.status is UploadedDocumentStatus.UPLOADED

        retry = await use_case.upload_statement(
            context=context,
            upload_file=UploadFile(
                file=BytesIO(b"%PDF-1.4 synthetic"),
                filename="statement.pdf",
            ),
            account_id=account_id,
            idempotency_key=idempotency_key,
        )
        assert retry.document_id == document_id
        assert retry.document_status is UploadedDocumentStatus.FAILED_TO_PARSE
        assert retry.replayed
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ParseAttempt)
                .where(ParseAttempt.uploaded_document_id == document_id)
            )
            == 1
        )

    async with postgres_sessions() as session:
        await session.execute(
            delete(Workspace).where(Workspace.id.in_([workspace_id, foreign_workspace_id]))
        )
        await session.execute(delete(User).where(User.id.in_([user_id, foreign_user_id])))
        await session.commit()


async def test_initial_document_commit_error_before_persistence_removes_orphan_only(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
    tmp_path: Path,
) -> None:
    marker = "PRE_PERSIST_PRIVATE_MARKER /private/orphan.pdf"
    user_id, workspace_id, account_id = uuid4(), uuid4(), uuid4()
    idempotency_key = uuid4()
    document_id = uuid5(workspace_id, f"statement-upload:{idempotency_key}")
    async with postgres_sessions() as session:
        user = User(
            id=user_id,
            email=f"pre-persist-{user_id}@example.test",
            password_hash="hash",
        )
        workspace = Workspace(
            id=workspace_id,
            owner_id=user_id,
            name="Pre-persist cleanup",
            type=WorkspaceType.PERSONAL,
        )
        membership = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
            status=WorkspaceMemberStatus.ACTIVE,
        )
        session.add_all(
            [
                user,
                workspace,
                membership,
                Account(
                    id=account_id,
                    workspace_id=workspace_id,
                    name="Card",
                    type=AccountType.CARD,
                    currency="RUB",
                ),
            ]
        )
        await session.commit()

        async def fail_before_commit() -> None:
            raise RuntimeError(marker)

        monkeypatch.setattr(session, "commit", fail_before_commit)
        use_case = StatementUploadUseCase(session, Settings(upload_storage_dir=tmp_path))
        with pytest.raises(UploadProcessingError):
            await use_case.upload_statement(
                context=WorkspaceContext(
                    user=user,
                    workspace=workspace,
                    membership=membership,
                ),
                upload_file=UploadFile(
                    file=BytesIO(b"%PDF-1.4 synthetic"),
                    filename="statement.pdf",
                ),
                account_id=account_id,
                idempotency_key=idempotency_key,
            )

        assert await session.get(UploadedDocument, document_id) is None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ParseAttempt)
                .where(ParseAttempt.workspace_id == workspace_id)
            )
            == 0
        )
        assert list(tmp_path.rglob("source.pdf")) == []  # noqa: ASYNC240

    async with postgres_sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
