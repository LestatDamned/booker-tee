from copy import deepcopy
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingRowErrorCode,
    MappingTableRefDto,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    MAX_MAPPING_PREVIEW_RESPONSE_ROWS,
    MAX_MAPPING_SOURCE_SAMPLE_ROWS,
    UnknownStatementMappingReader,
)
from app.features.imports.documents.dto import (
    ImportDocumentAccountDto,
    ImportDocumentSnapshot,
    ImportParseAttemptSnapshot,
)
from app.features.imports.documents.types import ParseAttemptStatus, UploadedDocumentStatus
from app.features.imports.documents.validation_report import StoredValidationReport
from app.features.imports.mapping.dto import (
    MappingDefaultSource,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.repository import MappingRepository


class DocumentSnapshotReaderStub:
    def __init__(
        self,
        snapshot: ImportDocumentSnapshot,
        *,
        workspace_id: UUID,
    ) -> None:
        self.snapshot = snapshot
        self.workspace_id = workspace_id
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None:
        self.calls.append((workspace_id, document_id))
        if workspace_id != self.workspace_id or document_id != self.snapshot.id:
            return None
        return self.snapshot


class TemplateServiceStub:
    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None,
        statement_type: str | None,
    ):
        return []


@pytest.mark.asyncio
async def test_mapping_repository_skips_template_query_without_bank_or_type() -> None:
    session = AsyncMock()
    repository = MappingRepository(cast(AsyncSession, session))

    templates = await repository.list_matching_templates(
        workspace_id=uuid4(),
        bank_name=None,
        statement_type=None,
    )

    assert templates == []
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_mapping_read_model_is_bounded_and_uses_analyzer_defaults() -> None:
    workspace_id = uuid4()
    snapshot = mapping_document_snapshot()
    documents = DocumentSnapshotReaderStub(snapshot, workspace_id=workspace_id)
    reader = UnknownStatementMappingReader(documents, TemplateServiceStub())

    mapping = await reader.read(
        workspace_id=workspace_id,
        document_id=snapshot.id,
        workspace_default_currency="USD",
    )

    assert mapping is not None
    assert mapping.capability.allowed is True
    assert mapping.default_source is MappingDefaultSource.ANALYZER
    assert mapping.default_currency == "RUB"
    assert mapping.default_mapping.first_data_row == 1
    assert mapping.total_table_count == 2
    assert len(mapping.tables[0].sample_rows) == MAX_MAPPING_SOURCE_SAMPLE_ROWS
    assert mapping.tables[0].sample_rows[0].row_number == 1
    assert mapping.tables[0].sample_rows[0].cells == ("Дата", "Описание", "Сумма")
    assert mapping.tables[0].suggestion is not None
    assert mapping.tables[0].suggestion.spec.default_currency == "RUB"
    assert documents.calls == [(workspace_id, snapshot.id)]


@pytest.mark.asyncio
async def test_mapping_preview_counts_all_compatible_rows_but_bounds_payload() -> None:
    workspace_id = uuid4()
    snapshot = mapping_document_snapshot()
    raw_tables_before = deepcopy(snapshot.parse_attempts[0].raw_tables)
    reader = UnknownStatementMappingReader(
        DocumentSnapshotReaderStub(snapshot, workspace_id=workspace_id),
        TemplateServiceStub(),
    )

    preview = await reader.preview(
        workspace_id=workspace_id,
        document_id=snapshot.id,
        workspace_default_currency="RUB",
        spec=mapping_command(),
    )

    assert preview is not None
    assert preview.total_row_count == 50
    assert preview.valid_row_count == 49
    assert preview.invalid_row_count == 1
    assert len(preview.rows) == MAX_MAPPING_PREVIEW_RESPONSE_ROWS
    assert preview.rows_truncated is True
    assert preview.compatible_tables == (
        MappingTableRefDto(1, 0),
        MappingTableRefDto(2, 0),
    )
    assert preview.rows[0].source_row_number == 2
    assert preview.rows[0].error_codes == (MappingRowErrorCode.OPERATION_DATE_INVALID,)
    assert preview.can_import is True
    assert snapshot.parse_attempts[0].raw_tables == raw_tables_before
    assert snapshot.raw_transactions == []


def mapping_document_snapshot() -> ImportDocumentSnapshot:
    document_id = uuid4()
    raw_tables: list[dict[str, object]] = [
        {
            "page_number": page_number,
            "tables": [
                [
                    ["Дата", "Описание", "Сумма"],
                    *[
                        [
                            (
                                "не дата"
                                if page_number == 1 and row_number == 1
                                else f"{row_number:02d}.07.2026"
                            ),
                            f"Операция {page_number}-{row_number}",
                            "-100.00",
                        ]
                        for row_number in range(1, 26)
                    ],
                ]
            ],
        }
        for page_number in (1, 2)
    ]
    previews = [
        {
            "page_number": page_number,
            "table_index": 0,
            "row_count": 26,
            "column_count": 3,
            "source_type": "pdf_table",
            "rows": [
                ["Дата", "Описание", "Сумма"],
                ["01.07.2026", "Операция", "-100.00"],
            ],
            "column_candidates": [
                {
                    "field": "operation_date",
                    "column_index": 0,
                    "header": "Дата",
                },
                {
                    "field": "description",
                    "column_index": 1,
                    "header": "Описание",
                },
                {
                    "field": "amount",
                    "column_index": 2,
                    "header": "Сумма",
                },
            ],
            "mapping_suggestions": [
                {
                    "operation_date_column": 0,
                    "posting_date_column": None,
                    "description_column": 1,
                    "amount_column": 2,
                    "debit_amount_column": None,
                    "credit_amount_column": None,
                    "currency_column": None,
                    "balance_after_column": None,
                    "first_data_row": 1,
                    "reasons": [],
                    "warnings": [],
                }
            ],
        }
        for page_number in (1, 2)
    ]
    validation = StoredValidationReport.model_validate(
        {
            "status": "needs_mapping",
            "table_previews": previews,
        }
    )
    return ImportDocumentSnapshot(
        id=document_id,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        original_filename="unknown-statement.xlsx",
        bank_name="Unknown Bank",
        statement_type="account_statement",
        account=ImportDocumentAccountDto(
            id=uuid4(),
            name="Основной счёт",
            currency="RUB",
        ),
        validation=validation,
        raw_transactions=[],
        parse_attempts=[
            ImportParseAttemptSnapshot(
                id=uuid4(),
                status=ParseAttemptStatus.REQUIRES_REVIEW,
                parser_name="unknown_statement",
                parser_version="1",
                started_at=datetime(2026, 7, 24, tzinfo=UTC),
                finished_at=datetime(2026, 7, 24, tzinfo=UTC),
                error_message=None,
                validation=validation,
                raw_tables=raw_tables,
            )
        ],
    )


def mapping_command() -> StatementMappingSpec:
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
