import asyncio
import os
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.settings import Settings
from app.db.base import utc_now
from app.features.accounts.models import Account, AccountType
from app.features.import_review.application.lifecycle import ImportReviewLifecycleService
from app.features.import_review.domain.lifecycle import ImportReviewLifecycleAction
from app.features.import_review.schemas.commands import ImportReviewLifecycleCommand
from app.features.imports.documents.source_cleanup import UploadSourceCleanup
from app.features.imports.documents.types import (
    ParseAttemptStatus,
    UploadedDocumentStatus,
)
from app.features.imports.mapping.commands.import_rows import (
    MappedStatementRowImporter,
    StatementMappingImportService,
)
from app.features.imports.mapping.coordinate_dto import (
    CoordinateControlRegion,
    CoordinateFieldRole,
    CoordinateMappingSpec,
    CoordinatePageLayout,
    NormalizedRect,
)
from app.features.imports.mapping.coordinate_engine import CoordinateWord
from app.features.imports.mapping.coordinate_service import (
    CoordinateMappingImportService,
    CoordinateMappingService,
)
from app.features.imports.mapping.dto import (
    StatementMappingImportResult,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.errors import (
    MappingImportIdempotencyConflictError,
    MappingImportUnavailableError,
)
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.models import (
    ImportMappingExecution,
    ImportMappingTemplate,
    ParseAttempt,
    RawTransaction,
    UploadedDocument,
)
from app.features.imports.statements.types import RawTransactionStatus
from app.features.users.models import User
from app.features.workspaces.domain.types import WorkspaceType
from app.features.workspaces.models import Workspace

TEST_DATABASE_URL = os.getenv("BOOKER_TEE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="BOOKER_TEE_TEST_DATABASE_URL is required for PostgreSQL concurrency tests.",
)


async def test_concurrent_mapping_import_replays_one_execution(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
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


async def test_concurrent_coordinate_import_replays_one_execution(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    ids = await _seed_mapping_document(sessions)

    monkeypatch.setattr(CoordinateMappingService, "_validated_words", _coordinate_words)
    idempotency_key = uuid4()

    async def import_once() -> StatementMappingImportResult:
        async with sessions() as session:
            settings = cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read")))
            return await CoordinateMappingImportService(session, settings).import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=_coordinate_spec(),
                idempotency_key=idempotency_key,
                template_name=None,
            )

    try:
        results = await asyncio.gather(import_once(), import_once())
        assert sorted(result.replayed for result in results) == [False, True]
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
            row_count = await session.scalar(
                select(func.count())
                .select_from(RawTransaction)
                .where(RawTransaction.uploaded_document_id == ids.document_id)
            )
        assert execution_count == 1
        assert row_count == 1
    finally:
        await _delete_seed_data(sessions, ids)


async def test_coordinate_remap_replaces_unconfirmed_rows_and_confirmed_blocks(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    ids = await _seed_mapping_document(sessions)
    monkeypatch.setattr(CoordinateMappingService, "_validated_words", _coordinate_words)
    first_spec = _coordinate_spec()
    changed_spec = first_spec.model_copy(
        update={"unsigned_amount_direction": UnsignedAmountDirection.EXPENSE}
    )
    first_key = uuid4()

    try:
        async with sessions() as session:
            assert (
                await CoordinateMappingService(
                    session,
                    cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read"))),
                ).overview(
                    workspace_id=uuid4(),
                    document_id=ids.document_id,
                    workspace_default_currency="RUB",
                )
                is None
            )
        async with sessions() as session:
            service = CoordinateMappingImportService(
                session, cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read")))
            )
            first = await service.import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=first_spec,
                idempotency_key=first_key,
                template_name="Visual PDF",
            )
        assert first.imported_row_count == 1
        assert first.template_id is not None

        async with sessions() as session:
            replay = await CoordinateMappingImportService(
                session, cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read")))
            ).import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=first_spec,
                idempotency_key=first_key,
                template_name="Visual PDF",
            )
        assert replay.replayed is True

        async with sessions() as session:
            with pytest.raises(MappingImportIdempotencyConflictError):
                await CoordinateMappingImportService(
                    session,
                    cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read"))),
                ).import_rows_idempotently(
                    workspace_id=ids.workspace_id,
                    document_id=ids.document_id,
                    spec=changed_spec,
                    idempotency_key=first_key,
                    template_name="Visual PDF",
                )

        async with sessions() as session:
            second = await CoordinateMappingImportService(
                session, cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read")))
            ).import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=changed_spec,
                idempotency_key=uuid4(),
                template_name=None,
            )
        assert second.imported_row_count == 1

        async with sessions() as session:
            rows = list(
                (
                    await session.scalars(
                        select(RawTransaction).where(
                            RawTransaction.uploaded_document_id == ids.document_id
                        )
                    )
                ).all()
            )
            assert len(rows) == 2
            active = [row for row in rows if row.status is not RawTransactionStatus.DUPLICATE]
            assert len(active) == 1
            active[0].status = RawTransactionStatus.CONFIRMED
            await session.commit()

        async with sessions() as session:
            with pytest.raises(MappingImportUnavailableError):
                await CoordinateMappingImportService(
                    session,
                    cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read"))),
                ).import_rows_idempotently(
                    workspace_id=ids.workspace_id,
                    document_id=ids.document_id,
                    spec=first_spec,
                    idempotency_key=uuid4(),
                    template_name=None,
                )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ImportMappingExecution)
                    .where(ImportMappingExecution.uploaded_document_id == ids.document_id)
                )
                == 2
            )
    finally:
        await _delete_seed_data(sessions, ids)


async def test_coordinate_import_failure_rolls_back_rows_template_and_execution(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    ids = await _seed_mapping_document(sessions)
    monkeypatch.setattr(CoordinateMappingService, "_validated_words", _coordinate_words)

    async def fail_execution(_self: MappingRepository, _execution: object) -> None:
        raise RuntimeError("simulated execution write failure")

    monkeypatch.setattr(MappingRepository, "create_mapping_execution", fail_execution)
    try:
        with pytest.raises(RuntimeError, match="simulated execution write failure"):
            async with sessions() as session:
                await CoordinateMappingImportService(
                    session,
                    cast(Any, SimpleNamespace(upload_storage_dir=Path("/tmp/not-read"))),
                ).import_rows_idempotently(
                    workspace_id=ids.workspace_id,
                    document_id=ids.document_id,
                    spec=_coordinate_spec(),
                    idempotency_key=uuid4(),
                    template_name="Atomic template",
                )

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RawTransaction)
                    .where(RawTransaction.uploaded_document_id == ids.document_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ImportMappingTemplate)
                    .where(ImportMappingTemplate.workspace_id == ids.workspace_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ImportMappingExecution)
                    .where(ImportMappingExecution.uploaded_document_id == ids.document_id)
                )
                == 0
            )
            document = await session.get(UploadedDocument, ids.document_id)
            attempt = await session.scalar(
                select(ParseAttempt).where(ParseAttempt.uploaded_document_id == ids.document_id)
            )
            assert document is not None
            assert document.storage_key == f"tests/mapping/{ids.document_id}"
            assert attempt is not None
            assert attempt.validation_report_json == {"status": "needs_mapping"}
    finally:
        await _delete_seed_data(sessions, ids)


async def test_visual_provenance_survives_lifecycle_then_remap_until_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    postgres_sessions: async_sessionmaker[Any],
    tmp_path: Path,
) -> None:
    sessions = postgres_sessions
    ids = await _seed_mapping_document(sessions)
    monkeypatch.setattr(CoordinateMappingService, "_validated_words", _coordinate_words_two)
    settings = Settings(upload_storage_dir=tmp_path, upload_retention_hours=48)
    source_path = tmp_path / "tests" / "mapping" / str(ids.document_id)
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"%PDF-1.4")
    try:
        async with sessions() as session:
            await CoordinateMappingImportService(session, settings).import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=_coordinate_spec(),
                idempotency_key=uuid4(),
                template_name=None,
            )

        async with sessions() as session:
            row = await session.scalar(
                select(RawTransaction)
                .where(RawTransaction.uploaded_document_id == ids.document_id)
                .order_by(RawTransaction.row_index)
            )
            assert row is not None
            await ImportReviewLifecycleService(session).execute(
                workspace_id=ids.workspace_id,
                command=ImportReviewLifecycleCommand(
                    document_id=ids.document_id,
                    item_id=row.id,
                    action=ImportReviewLifecycleAction.IGNORE,
                    expected_status=row.status,
                ),
            )

        async with sessions() as session:
            attempt = await session.scalar(
                select(ParseAttempt).where(ParseAttempt.uploaded_document_id == ids.document_id)
            )
            assert attempt is not None
            assert attempt.validation_report_json is not None
            assert attempt.validation_report_json["source"] == "visual_coordinate_mapping"

            cleanup = UploadSourceCleanup(session, settings)
            document = await cleanup.documents.get_document_for_workspace_for_update(
                ids.workspace_id, ids.document_id
            )
            assert document is not None
            now = utc_now()
            assert (
                await cleanup._cleanup_document(
                    document,
                    cutoff=now - timedelta(hours=48),
                    deleted_at=now,
                )
                == "unchanged"
            )
            assert document.storage_key == f"tests/mapping/{ids.document_id}"
            assert source_path.exists()  # noqa: ASYNC240

            remap = await CoordinateMappingImportService(
                session, settings
            ).import_rows_idempotently(
                workspace_id=ids.workspace_id,
                document_id=ids.document_id,
                spec=_coordinate_spec().model_copy(
                    update={"unsigned_amount_direction": UnsignedAmountDirection.EXPENSE}
                ),
                idempotency_key=uuid4(),
                template_name=None,
            )
            assert remap.imported_row_count == 2

        async with sessions() as session:
            active = await session.scalar(
                select(RawTransaction)
                .where(
                    RawTransaction.uploaded_document_id == ids.document_id,
                    RawTransaction.status.not_in(
                        [RawTransactionStatus.DUPLICATE, RawTransactionStatus.IGNORED]
                    ),
                )
                .order_by(RawTransaction.created_at.desc())
            )
            assert active is not None
            active.status = RawTransactionStatus.CONFIRMED
            await session.commit()

        async with sessions() as session:
            with pytest.raises(MappingImportUnavailableError):
                await CoordinateMappingImportService(session, settings).import_rows_idempotently(
                    workspace_id=ids.workspace_id,
                    document_id=ids.document_id,
                    spec=_coordinate_spec(),
                    idempotency_key=uuid4(),
                    template_name=None,
                )
    finally:
        await _delete_seed_data(sessions, ids)


async def test_coordinate_missing_and_corrupt_pdf_preserve_import_state(
    tmp_path: Path,
    postgres_sessions: async_sessionmaker[Any],
) -> None:
    sessions = postgres_sessions
    ids = await _seed_mapping_document(sessions)
    settings = cast(Any, SimpleNamespace(upload_storage_dir=tmp_path))
    try:
        async with sessions() as session:
            with pytest.raises(MappingImportUnavailableError):
                await CoordinateMappingService(session, settings).preview(
                    workspace_id=ids.workspace_id,
                    document_id=ids.document_id,
                    spec=_coordinate_spec(),
                )

        corrupt_path = tmp_path / "tests" / "mapping" / str(ids.document_id)
        corrupt_path.parent.mkdir(parents=True)
        corrupt_path.write_bytes(b"not a pdf")
        async with sessions() as session:
            with pytest.raises(MappingImportUnavailableError):
                await CoordinateMappingImportService(session, settings).import_rows_idempotently(
                    workspace_id=ids.workspace_id,
                    document_id=ids.document_id,
                    spec=_coordinate_spec(),
                    idempotency_key=uuid4(),
                    template_name="Must roll back",
                )

        async with sessions() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(RawTransaction)
                    .where(RawTransaction.uploaded_document_id == ids.document_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ImportMappingExecution)
                    .where(ImportMappingExecution.uploaded_document_id == ids.document_id)
                )
                == 0
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(ImportMappingTemplate)
                    .where(ImportMappingTemplate.workspace_id == ids.workspace_id)
                )
                == 0
            )
            document = await session.get(UploadedDocument, ids.document_id)
            attempt = await session.scalar(
                select(ParseAttempt).where(ParseAttempt.uploaded_document_id == ids.document_id)
            )
            assert document is not None
            assert document.storage_key == f"tests/mapping/{ids.document_id}"
            assert attempt is not None
            assert attempt.validation_report_json == {"status": "needs_mapping"}
    finally:
        await _delete_seed_data(sessions, ids)


async def _coordinate_words(
    _self: CoordinateMappingService,
    _document: object,
    _spec: CoordinateMappingSpec,
    _control_regions: tuple[CoordinateControlRegion, ...] = (),
) -> list[tuple[float, float, list[CoordinateWord]]]:
    return [
        (
            1000,
            1000,
            [
                CoordinateWord("29.07.2026", 100, 180, 200, 220),
                CoordinateWord("Покупка", 300, 400, 200, 220),
                CoordinateWord("-100", 800, 880, 200, 220),
            ],
        )
    ]


async def _coordinate_words_two(
    _self: CoordinateMappingService,
    _document: object,
    _spec: CoordinateMappingSpec,
    control_regions: tuple[CoordinateControlRegion, ...] = (),
) -> list[tuple[float, float, list[CoordinateWord]]]:
    page = (await _coordinate_words(_self, _document, _spec, control_regions))[0]
    return [
        (
            page[0],
            page[1],
            [
                *page[2],
                CoordinateWord("30.07.2026", 100, 180, 400, 420),
                CoordinateWord("Зарплата", 300, 400, 400, 420),
                CoordinateWord("+200", 800, 880, 400, 420),
            ],
        )
    ]


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
                    original_filename="mapping.pdf",
                    content_type="application/pdf",
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
                    validation_report_json={"status": "needs_mapping"},
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


def _coordinate_spec() -> CoordinateMappingSpec:
    return CoordinateMappingSpec(
        default_currency="RUB",
        layouts={
            "first": CoordinatePageLayout(
                page_aspect_ratio=1,
                transaction_top=0.1,
                transaction_bottom=0.9,
                sample_row=NormalizedRect(x0=0.05, y0=0.2, x1=0.95, y1=0.3),
                fields={
                    CoordinateFieldRole.OPERATION_DATE: NormalizedRect(
                        x0=0.05, y0=0.2, x1=0.2, y1=0.3
                    ),
                    CoordinateFieldRole.DESCRIPTION: NormalizedRect(
                        x0=0.25, y0=0.2, x1=0.65, y1=0.3
                    ),
                    CoordinateFieldRole.AMOUNT: NormalizedRect(x0=0.75, y0=0.2, x1=0.95, y1=0.3),
                },
            )
        },
    )
