from datetime import UTC, date, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from app.features.imports.application.documents.listing import (
    ImportDocumentListAccountRow,
    ImportDocumentListFilters,
    ImportDocumentListPagination,
    ImportDocumentListReader,
    ImportDocumentListReadonlyReasonCode,
    ImportDocumentListRow,
    ImportDocumentListSort,
    ImportDocumentListState,
    ImportDocumentListSummaryRow,
    ImportDocumentNextStepKind,
)
from app.features.imports.models import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.query_repository import ImportQueryRepository


class DocumentListSourceStub:
    def __init__(
        self,
        rows: list[ImportDocumentListRow],
        *,
        total: int | None = None,
    ) -> None:
        self.rows = rows
        self.total = len(rows) if total is None else total
        self.workspace_ids: list[UUID] = []
        self.filters: list[ImportDocumentListFilters] = []
        self.paginations: list[ImportDocumentListPagination] = []

    async def list_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
        pagination: ImportDocumentListPagination,
    ) -> list[ImportDocumentListRow]:
        self.workspace_ids.append(workspace_id)
        self.filters.append(filters)
        self.paginations.append(pagination)
        return self.rows

    async def count_document_rows_for_workspace(
        self,
        *,
        workspace_id: UUID,
        filters: ImportDocumentListFilters,
    ) -> int:
        self.workspace_ids.append(workspace_id)
        self.filters.append(filters)
        return self.total

    async def list_document_filter_accounts_for_workspace(
        self,
        workspace_id: UUID,
    ) -> list[ImportDocumentListAccountRow]:
        self.workspace_ids.append(workspace_id)
        return [
            ImportDocumentListAccountRow(
                id=uuid4(),
                name="Основной",
                currency="RUB",
                bank_name="Альфа-Банк",
            )
        ]

    async def summarize_documents_for_workspace(
        self,
        workspace_id: UUID,
    ) -> ImportDocumentListSummaryRow:
        self.workspace_ids.append(workspace_id)
        return ImportDocumentListSummaryRow(
            total_document_count=self.total,
            attention_document_count=min(self.total, 1),
        )


@pytest.mark.asyncio
async def test_document_list_preserves_source_order_and_workspace_scope() -> None:
    workspace_id = uuid4()
    newest = document_row(status=UploadedDocumentStatus.IMPORTED)
    oldest = document_row(status=UploadedDocumentStatus.FAILED_TO_PARSE)
    source = DocumentListSourceStub([newest, oldest])

    result = await ImportDocumentListReader(source).read(
        workspace_id=workspace_id,
        workspace_name="Дом",
        can_upload=True,
    )

    assert source.workspace_ids == [workspace_id] * 4
    assert [item.id for item in result.items] == [newest.id, oldest.id]
    assert result.pagination.total == 2
    assert result.filter_options.accounts[0].bank_name == "Альфа-Банк"
    assert result.summary.attention_document_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "attempt_status", "row_count", "next_step", "can_map", "can_review"),
    [
        (
            UploadedDocumentStatus.REQUIRES_REVIEW,
            ParseAttemptStatus.REQUIRES_REVIEW,
            0,
            ImportDocumentNextStepKind.MAPPING,
            True,
            False,
        ),
        (
            UploadedDocumentStatus.REQUIRES_REVIEW,
            ParseAttemptStatus.SUCCESS,
            4,
            ImportDocumentNextStepKind.REVIEW,
            False,
            True,
        ),
        (
            UploadedDocumentStatus.IMPORTED,
            ParseAttemptStatus.SUCCESS,
            0,
            ImportDocumentNextStepKind.REVIEW,
            False,
            True,
        ),
        (
            UploadedDocumentStatus.FAILED_TO_PARSE,
            ParseAttemptStatus.FAILED,
            0,
            ImportDocumentNextStepKind.DETAIL,
            False,
            False,
        ),
        (
            UploadedDocumentStatus.PENDING_PARSE,
            None,
            0,
            ImportDocumentNextStepKind.DETAIL,
            False,
            False,
        ),
    ],
)
async def test_document_status_to_next_step_matrix(
    status: UploadedDocumentStatus,
    attempt_status: ParseAttemptStatus | None,
    row_count: int,
    next_step: ImportDocumentNextStepKind,
    can_map: bool,
    can_review: bool,
) -> None:
    source = DocumentListSourceStub(
        [
            document_row(
                status=status,
                attempt_status=attempt_status,
                row_count=row_count,
            )
        ]
    )

    result = await ImportDocumentListReader(source).read(
        workspace_id=uuid4(),
        workspace_name="Дом",
        can_upload=True,
    )

    item = result.items[0]
    assert item.next_step_kind is next_step
    assert item.capabilities.can_open_detail is True
    assert item.capabilities.can_map is can_map
    assert item.capabilities.can_review is can_review


@pytest.mark.asyncio
async def test_viewer_sees_mapping_document_as_readonly_detail() -> None:
    source = DocumentListSourceStub(
        [
            document_row(
                status=UploadedDocumentStatus.REQUIRES_REVIEW,
                attempt_status=ParseAttemptStatus.REQUIRES_REVIEW,
            )
        ]
    )

    result = await ImportDocumentListReader(source).read(
        workspace_id=uuid4(),
        workspace_name="Дом",
        can_upload=False,
    )

    assert result.capabilities.can_upload is False
    assert (
        result.capabilities.readonly_reason_code
        is ImportDocumentListReadonlyReasonCode.IMPORT_MANAGEMENT_FORBIDDEN
    )
    assert result.items[0].capabilities.can_map is False
    assert result.items[0].next_step_kind is ImportDocumentNextStepKind.DETAIL


@pytest.mark.asyncio
async def test_empty_workspace_has_no_items() -> None:
    source = DocumentListSourceStub([])

    result = await ImportDocumentListReader(source).read(
        workspace_id=uuid4(),
        workspace_name="Дом",
        can_upload=True,
    )

    assert result.items == ()
    assert source.rows == []


@pytest.mark.asyncio
async def test_document_list_passes_filters_and_clamps_page_to_last_page() -> None:
    account_id = uuid4()
    filters = ImportDocumentListFilters(
        state=ImportDocumentListState.ATTENTION,
        account_id=account_id,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 12, 31),
    )
    source = DocumentListSourceStub(
        [document_row(status=UploadedDocumentStatus.REQUIRES_REVIEW)],
        total=51,
    )

    result = await ImportDocumentListReader(source).read(
        workspace_id=uuid4(),
        workspace_name="Дом",
        can_upload=True,
        filters=filters,
        pagination=ImportDocumentListPagination(page=99, per_page=25),
    )

    assert source.filters == [filters, filters]
    assert source.paginations == [ImportDocumentListPagination(page=3, per_page=25)]
    assert result.pagination.page == 3
    assert result.pagination.total_pages == 3
    assert result.pagination.has_previous is True
    assert result.pagination.has_next is False


@pytest.mark.asyncio
async def test_document_projection_query_is_workspace_scoped_and_deterministic() -> None:
    workspace_id = uuid4()

    class ResultStub:
        def all(self) -> list[object]:
            return []

    class SessionStub:
        statement: object | None = None

        async def execute(self, statement: object) -> ResultStub:
            self.statement = statement
            return ResultStub()

    session = SessionStub()

    result = await ImportQueryRepository(cast(Any, session)).list_document_rows_for_workspace(
        workspace_id=workspace_id,
        filters=ImportDocumentListFilters(),
        pagination=ImportDocumentListPagination(),
    )

    assert result == []
    assert session.statement is not None
    compiled = cast(Any, session.statement).compile()
    sql = str(compiled)
    assert workspace_id in compiled.params.values()
    assert "uploaded_documents.workspace_id" in sql
    assert "raw_transactions.workspace_id" in sql
    assert "parse_attempts.workspace_id" in sql
    assert "ORDER BY uploaded_documents.created_at DESC, uploaded_documents.id DESC" in sql


@pytest.mark.asyncio
async def test_document_projection_applies_registry_filters_sort_and_page() -> None:
    workspace_id = uuid4()
    account_id = uuid4()

    class ResultStub:
        def all(self) -> list[object]:
            return []

    class SessionStub:
        statement: object | None = None

        async def execute(self, statement: object) -> ResultStub:
            self.statement = statement
            return ResultStub()

    session = SessionStub()
    filters = ImportDocumentListFilters(
        state=ImportDocumentListState.ATTENTION,
        account_id=account_id,
        period_from=date(2026, 1, 1),
        period_to=date(2026, 3, 31),
        sort=ImportDocumentListSort.CREATED_AT_ASC,
    )

    await ImportQueryRepository(cast(Any, session)).list_document_rows_for_workspace(
        workspace_id=workspace_id,
        filters=filters,
        pagination=ImportDocumentListPagination(page=3, per_page=50),
    )

    assert session.statement is not None
    compiled = cast(Any, session.statement).compile()
    sql = str(compiled)
    assert account_id in compiled.params.values()
    assert date(2026, 1, 1) in compiled.params.values()
    assert date(2026, 3, 31) in compiled.params.values()
    assert "uploaded_documents.status IN" in sql
    assert "uploaded_documents.account_id =" in sql
    assert "coalesce(uploaded_documents.statement_period_end" in sql
    assert "coalesce(uploaded_documents.statement_period_start" in sql
    assert "ORDER BY uploaded_documents.created_at ASC, uploaded_documents.id ASC" in sql
    assert "LIMIT" in sql
    assert "OFFSET" in sql


def document_row(
    *,
    status: UploadedDocumentStatus,
    attempt_status: ParseAttemptStatus | None = None,
    row_count: int = 0,
) -> ImportDocumentListRow:
    return ImportDocumentListRow(
        id=uuid4(),
        filename="statement.pdf",
        status=status,
        created_at=datetime(2026, 7, 24, 10, 0, tzinfo=UTC),
        file_size_bytes=2048,
        detected_bank_name="Альфа-Банк",
        statement_period_start=date(2026, 7, 1),
        statement_period_end=date(2026, 7, 31),
        account_id=uuid4(),
        account_name="Основной",
        account_currency="RUB",
        account_bank_name="Альфа-Банк",
        total_row_count=row_count,
        reviewable_row_count=row_count,
        latest_parse_attempt_status=attempt_status,
    )
