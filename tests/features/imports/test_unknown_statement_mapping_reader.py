from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.features.accounts.models import AccountType
from app.features.imports.application.documents.detail_view import (
    ImportAccountRef,
    ImportDocumentDetailView,
    ImportParseAttemptView,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingDefaultSource,
    MappingRowErrorCode,
    MappingTableRefDto,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    MAX_MAPPING_PREVIEW_RESPONSE_ROWS,
    MAX_MAPPING_SOURCE_SAMPLE_ROWS,
    MappingCommandValidationError,
    UnknownStatementMappingReader,
)
from app.features.imports.models import ParseAttemptStatus, UploadedDocumentStatus


class DocumentServiceStub:
    def __init__(
        self,
        view: ImportDocumentDetailView,
        *,
        workspace_id: UUID,
    ) -> None:
        self.view = view
        self.workspace_id = workspace_id
        self.calls: list[tuple[UUID, UUID]] = []

    async def get_document_detail_view(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentDetailView | None:
        self.calls.append((workspace_id, document_id))
        if workspace_id != self.workspace_id or document_id != self.view.id:
            return None
        return self.view


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
async def test_mapping_read_model_is_bounded_and_uses_analyzer_defaults() -> None:
    workspace_id = uuid4()
    view = mapping_document_view()
    documents = DocumentServiceStub(view, workspace_id=workspace_id)
    reader = UnknownStatementMappingReader(documents, TemplateServiceStub())

    mapping = await reader.read(
        workspace_id=workspace_id,
        document_id=view.id,
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
    assert mapping.tables[0].suggestion.command.default_currency == "RUB"
    assert documents.calls == [(workspace_id, view.id)]


@pytest.mark.asyncio
async def test_mapping_preview_counts_all_compatible_rows_but_bounds_payload() -> None:
    workspace_id = uuid4()
    view = mapping_document_view()
    raw_tables_before = deepcopy(view.parse_attempts[0].raw_tables)
    reader = UnknownStatementMappingReader(
        DocumentServiceStub(view, workspace_id=workspace_id),
        TemplateServiceStub(),
    )

    preview = await reader.preview(
        workspace_id=workspace_id,
        document_id=view.id,
        workspace_default_currency="RUB",
        command=mapping_command(),
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
    assert view.parse_attempts[0].raw_tables == raw_tables_before
    assert view.raw_transactions == []


@pytest.mark.asyncio
async def test_mapping_preview_rejects_duplicate_roles_with_stable_fields() -> None:
    workspace_id = uuid4()
    view = mapping_document_view()
    reader = UnknownStatementMappingReader(
        DocumentServiceStub(view, workspace_id=workspace_id),
        TemplateServiceStub(),
    )
    command = mapping_command()
    duplicate = UnknownStatementMappingCommand(
        page_number=command.page_number,
        table_index=command.table_index,
        operation_date_column=command.operation_date_column,
        posting_date_column=command.posting_date_column,
        description_column=command.operation_date_column,
        amount_column=command.amount_column,
        debit_amount_column=command.debit_amount_column,
        credit_amount_column=command.credit_amount_column,
        currency_column=command.currency_column,
        balance_after_column=command.balance_after_column,
        first_data_row=command.first_data_row,
        default_currency=command.default_currency,
    )

    with pytest.raises(MappingCommandValidationError) as error:
        await reader.preview(
            workspace_id=workspace_id,
            document_id=view.id,
            workspace_default_currency="RUB",
            command=duplicate,
        )

    assert error.value.code == "duplicate_mapping_roles"
    assert error.value.fields == ("operationDateColumn", "descriptionColumn")


@pytest.mark.asyncio
async def test_mapping_preview_requires_complete_amount_strategy() -> None:
    workspace_id = uuid4()
    view = mapping_document_view()
    reader = UnknownStatementMappingReader(
        DocumentServiceStub(view, workspace_id=workspace_id),
        TemplateServiceStub(),
    )
    command = mapping_command()
    incomplete = replace(
        command,
        amount_column=None,
        debit_amount_column=2,
        credit_amount_column=None,
    )

    with pytest.raises(MappingCommandValidationError) as error:
        await reader.preview(
            workspace_id=workspace_id,
            document_id=view.id,
            workspace_default_currency="RUB",
            command=incomplete,
        )

    assert error.value.code == "incomplete_amount_mapping"
    assert error.value.fields == (
        "amountColumn",
        "debitAmountColumn",
        "creditAmountColumn",
    )


def mapping_document_view() -> ImportDocumentDetailView:
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
                    "confidence": 0.95,
                },
                {
                    "field": "description",
                    "column_index": 1,
                    "header": "Описание",
                    "confidence": 0.9,
                },
                {
                    "field": "amount",
                    "column_index": 2,
                    "header": "Сумма",
                    "confidence": 0.85,
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
                    "confidence": 0.9,
                    "reasons": [],
                    "warnings": [],
                }
            ],
        }
        for page_number in (1, 2)
    ]
    return ImportDocumentDetailView(
        id=document_id,
        status=UploadedDocumentStatus.REQUIRES_REVIEW,
        original_filename="unknown-statement.xlsx",
        sha256_hash="a" * 64,
        storage_key="private/statement.xlsx",
        bank_name="Unknown Bank",
        statement_type="account_statement",
        account=ImportAccountRef(
            id=uuid4(),
            name="Основной счёт",
            type=AccountType.CHECKING,
            currency="RUB",
        ),
        validation={
            "status": "needs_mapping",
            "table_previews": previews,
        },
        raw_transactions=[],
        parse_attempts=[
            ImportParseAttemptView(
                id=uuid4(),
                status=ParseAttemptStatus.REQUIRES_REVIEW,
                parser_name="unknown_statement",
                parser_version="1",
                started_at=datetime(2026, 7, 24, tzinfo=UTC),
                finished_at=datetime(2026, 7, 24, tzinfo=UTC),
                error_message=None,
                validation_report={
                    "status": "needs_mapping",
                    "table_previews": previews,
                },
                raw_tables=raw_tables,
                raw_text_by_page=None,
            )
        ],
    )


def mapping_command() -> UnknownStatementMappingCommand:
    return UnknownStatementMappingCommand(
        page_number=1,
        table_index=0,
        operation_date_column=0,
        description_column=1,
        amount_column=2,
        currency_column=None,
        first_data_row=1,
        default_currency="RUB",
    )
