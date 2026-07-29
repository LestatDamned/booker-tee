import asyncio
import os
from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.accounts.models import Account, AccountType
from app.features.imports.documents.types import (
    ParseAttemptStatus,
    UploadedDocumentStatus,
)
from app.features.imports.mapping.commands.import_rows import (
    MappedStatementRowImporter,
    StatementMappingImportService,
)
from app.features.imports.mapping.dto import (
    StatementMappingImportResult,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.models import (
    ImportMappingExecution,
    ParseAttempt,
    UploadedDocument,
)
from app.features.users.models import User
from app.features.workspaces.domain.types import WorkspaceType
from app.features.workspaces.models import Workspace

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL concurrency tests.",
)


@pytest.mark.asyncio
async def test_concurrent_mapping_import_replays_one_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert TEST_DATABASE_URL is not None
    engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    ids = await _seed_mapping_document(sessions)

    async def imported_rows(
        _self: MappedStatementRowImporter,
        **_kwargs: object,
    ) -> Sequence[object]:
        await asyncio.sleep(0.05)
        return (object(), object())

    monkeypatch.setattr(MappedStatementRowImporter, "replace_rows", imported_rows)
    idempotency_key = uuid4()

    async def import_once() -> StatementMappingImportResult:
        async with sessions() as session:
            return await StatementMappingImportService(session).import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=_mapping_spec(),
                idempotency_key=idempotency_key,
            )

    try:
        results = await asyncio.gather(import_once(), import_once())
        assert sorted(result.replayed for result in results) == [False, True]
        assert {result.imported_row_count for result in results} == {2}

        async with sessions() as session:
            execution_count = await session.scalar(
                select(func.count())
                .select_from(ImportMappingExecution)
                .where(
                    ImportMappingExecution.workspace_id == ids.workspace_id,
                    ImportMappingExecution.uploaded_document_id == ids.document_id,
                    ImportMappingExecution.idempotency_key == str(idempotency_key),
                )
            )
        assert execution_count == 1
    finally:
        await _delete_seed_data(sessions, ids)
        await engine.dispose()


class MappingPostgresIds:
    def __init__(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        document_id: UUID,
    ) -> None:
        self.user_id = user_id
        self.workspace_id = workspace_id
        self.document_id = document_id


async def _seed_mapping_document(
    sessions: async_sessionmaker[Any],
) -> MappingPostgresIds:
    user_id = uuid4()
    workspace_id = uuid4()
    account_id = uuid4()
    document_id = uuid4()
    attempt_id = uuid4()
    async with sessions() as session:
        session.add_all(
            [
                User(
                    id=user_id,
                    email=f"mapping-{user_id}@example.test",
                    password_hash="hash",
                    name="Mapping concurrency",
                ),
                Workspace(
                    id=workspace_id,
                    owner_id=user_id,
                    name="Mapping concurrency",
                    type=WorkspaceType.PERSONAL,
                    default_currency="RUB",
                ),
                Account(
                    id=account_id,
                    workspace_id=workspace_id,
                    name="Mapping account",
                    type=AccountType.CARD,
                    currency="RUB",
                ),
                UploadedDocument(
                    id=document_id,
                    workspace_id=workspace_id,
                    status=UploadedDocumentStatus.REQUIRES_REVIEW,
                    original_filename="mapping.xlsx",
                    storage_key=f"tests/mapping/{document_id}",
                    sha256_hash=uuid4().hex * 2,
                    bank_name="Test Bank",
                    statement_type="card_statement",
                    account_id=account_id,
                ),
                ParseAttempt(
                    id=attempt_id,
                    workspace_id=workspace_id,
                    uploaded_document_id=document_id,
                    parser_name="mapping-test",
                    status=ParseAttemptStatus.REQUIRES_REVIEW,
                    raw_tables_json=[
                        {
                            "page_number": 1,
                            "tables": [
                                [
                                    ["Дата", "Описание", "Сумма"],
                                    ["29.07.2026", "Покупка", "-100.00"],
                                ]
                            ],
                        }
                    ],
                ),
            ]
        )
        await session.commit()
    return MappingPostgresIds(
        user_id=user_id,
        workspace_id=workspace_id,
        document_id=document_id,
    )


async def _delete_seed_data(
    sessions: async_sessionmaker[Any],
    ids: MappingPostgresIds,
) -> None:
    async with sessions() as session:
        await session.execute(delete(Workspace).where(Workspace.id == ids.workspace_id))
        await session.execute(delete(User).where(User.id == ids.user_id))
        await session.commit()


def _mapping_spec() -> StatementMappingSpec:
    return StatementMappingSpec(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
    )
