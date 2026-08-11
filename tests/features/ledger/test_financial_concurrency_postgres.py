import asyncio
import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm.exc import StaleDataError

from app.db.base import utc_now
from app.features.imports.documents.types import UploadedDocumentStatus
from app.features.imports.models import ParseAttempt, RawTransaction, UploadedDocument
from app.features.imports.statements.types import RawTransactionStatus
from app.features.ledger.domain.types import OperationSource, OperationStatus, OperationType
from app.features.ledger.models import Operation
from app.features.users.models import User
from app.features.workspaces.models import Workspace, WorkspaceType

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for financial concurrency tests.",
)


@pytest.mark.asyncio
async def test_concurrent_operation_updates_allow_one_committed_version() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, workspace_id, operation_id = uuid4(), uuid4(), uuid4()
    barrier = asyncio.Barrier(2)

    try:
        async with sessions() as session:
            session.add(
                User(
                    id=user_id, email=f"operation-race-{user_id}@example.test", password_hash="hash"
                )
            )
            session.add(
                Workspace(
                    id=workspace_id,
                    owner_id=user_id,
                    name="Operation race",
                    type=WorkspaceType.PERSONAL,
                    default_currency="RUB",
                )
            )
            session.add(
                Operation(
                    id=operation_id,
                    workspace_id=workspace_id,
                    type=OperationType.EXPENSE,
                    status=OperationStatus.CONFIRMED,
                    affects_profit=True,
                    description="Before race",
                    operation_date=date(2026, 8, 11),
                    source=OperationSource.MANUAL,
                    created_by_user_id=user_id,
                    confirmed_at=utc_now(),
                )
            )
            await session.commit()

        async def update(description: str) -> None:
            async with sessions() as session:
                operation = await session.get(Operation, operation_id)
                assert operation is not None and operation.version == 1
                await barrier.wait()
                operation.description = description
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        outcomes = await asyncio.wait_for(
            asyncio.gather(update("First"), update("Second"), return_exceptions=True),
            timeout=10,
        )
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, StaleDataError) for outcome in outcomes) == 1

        async with sessions() as session:
            operation = await session.get(Operation, operation_id)
            assert operation is not None
            assert operation.version == 2
            assert operation.description in {"First", "Second"}
    finally:
        async with sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_confirmed_dedupe_hash_allows_one_row() -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id, workspace_id = uuid4(), uuid4()
    document_ids = (uuid4(), uuid4())
    attempt_ids = (uuid4(), uuid4())
    dedupe_hash = "d" * 64
    barrier = asyncio.Barrier(2)

    try:
        async with sessions() as session:
            session.add(
                User(id=user_id, email=f"dedupe-race-{user_id}@example.test", password_hash="hash")
            )
            session.add(
                Workspace(
                    id=workspace_id,
                    owner_id=user_id,
                    name="Dedupe race",
                    type=WorkspaceType.PERSONAL,
                    default_currency="RUB",
                )
            )
            for index, (document_id, attempt_id) in enumerate(
                zip(document_ids, attempt_ids, strict=True)
            ):
                session.add(
                    UploadedDocument(
                        id=document_id,
                        workspace_id=workspace_id,
                        status=UploadedDocumentStatus.REQUIRES_REVIEW,
                        original_filename=f"statement-{index}.pdf",
                        storage_key=f"dedupe-race/{document_id}.pdf",
                        sha256_hash=str(document_id).replace("-", "") * 2,
                    )
                )
                session.add(
                    ParseAttempt(
                        id=attempt_id,
                        workspace_id=workspace_id,
                        uploaded_document_id=document_id,
                        parser_name="race-test",
                    )
                )
            await session.commit()

        async def confirm(index: int) -> None:
            async with sessions() as session:
                session.add(
                    RawTransaction(
                        workspace_id=workspace_id,
                        uploaded_document_id=document_ids[index],
                        parse_attempt_id=attempt_ids[index],
                        row_index=1,
                        status=RawTransactionStatus.CONFIRMED,
                        raw_payload={"fixture": index},
                        dedupe_hash=dedupe_hash,
                    )
                )
                await barrier.wait()
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        outcomes = await asyncio.wait_for(
            asyncio.gather(confirm(0), confirm(1), return_exceptions=True),
            timeout=10,
        )
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1

        async with sessions() as session:
            confirmed = await session.scalar(
                select(func.count())
                .select_from(RawTransaction)
                .where(
                    RawTransaction.workspace_id == workspace_id,
                    RawTransaction.status == RawTransactionStatus.CONFIRMED,
                    RawTransaction.dedupe_hash == dedupe_hash,
                )
            )
        assert confirmed == 1
    finally:
        async with sessions() as session:
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
        await engine.dispose()
