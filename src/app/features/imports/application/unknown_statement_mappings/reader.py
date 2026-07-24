from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from app.features.imports.application.documents.detail_view import (
    ImportDocumentDetailView,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.preview import (
    preview_compatible_unknown_statement_mapping,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    compatible_mapping_tables,
    find_raw_table,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingAccountDto,
    MappingBlockingReasonCode,
    MappingCapabilityDto,
    MappingColumnCandidateDto,
    MappingDefaultSource,
    MappingSourceRowDto,
    MappingSourceTableDto,
    MappingSuggestionDto,
    MappingSuggestionReasonDto,
    MappingTableRefDto,
    MappingTemplateDto,
    UnknownStatementMappingPreviewResult,
    UnknownStatementMappingReadModel,
    mapping_preview_row,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    compatible_mapping_templates,
)
from app.features.imports.application.unknown_statement_mappings.ui_defaults import (
    default_mapping_command,
    preview_table_options,
)
from app.features.imports.models import (
    ImportMappingTemplate,
    RawTransactionStatus,
)

MAX_MAPPING_SOURCE_TABLES = 100
MAX_MAPPING_SOURCE_SAMPLE_ROWS = 12
MAX_MAPPING_SOURCE_SAMPLE_COLUMNS = 32
MAX_MAPPING_SOURCE_CELL_CHARS = 500
MAX_MAPPING_PREVIEW_RESPONSE_ROWS = 20


class MappingDocumentReader(Protocol):
    async def get_document_detail_view(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentDetailView | None: ...


class MappingTemplateReader(Protocol):
    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None,
        statement_type: str | None,
    ) -> list[ImportMappingTemplate]: ...


@dataclass(frozen=True)
class MappingCommandValidationError(Exception):
    code: str
    message: str
    fields: tuple[str, ...]

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class MappingUnavailableError(Exception):
    reason_codes: tuple[MappingBlockingReasonCode, ...]

    def __str__(self) -> str:
        return "Настройка колонок недоступна для текущего состояния документа."


class UnknownStatementMappingReader:
    def __init__(
        self,
        documents: MappingDocumentReader,
        templates: MappingTemplateReader,
    ) -> None:
        self._documents = documents
        self._templates = templates

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        workspace_default_currency: str,
    ) -> UnknownStatementMappingReadModel | None:
        view = await self._documents.get_document_detail_view(workspace_id, document_id)
        if view is None:
            return None
        return await self._read_view(
            workspace_id=workspace_id,
            workspace_default_currency=workspace_default_currency,
            view=view,
        )

    async def _read_view(
        self,
        *,
        workspace_id: UUID,
        workspace_default_currency: str,
        view: ImportDocumentDetailView,
    ) -> UnknownStatementMappingReadModel:
        raw_tables = _latest_raw_tables(view)
        templates = await self._templates.list_matching_templates(
            workspace_id=workspace_id,
            bank_name=view.bank_name,
            statement_type=view.statement_type,
        )
        compatible_templates = compatible_mapping_templates(templates, raw_tables)
        default_currency = (
            view.account.currency if view.account is not None else workspace_default_currency
        )
        command = default_mapping_command(
            view.validation,
            default_currency=default_currency,
            templates=compatible_templates,
        )
        table_options = preview_table_options(view.validation)
        projected_tables = tuple(
            _source_table(option, raw_tables, default_currency=default_currency)
            for option in table_options[:MAX_MAPPING_SOURCE_TABLES]
        )
        return UnknownStatementMappingReadModel(
            document_id=view.id,
            filename=view.original_filename,
            status=view.status,
            bank_name=view.bank_name,
            statement_type=view.statement_type,
            account=(
                MappingAccountDto(
                    id=view.account.id,
                    name=view.account.name,
                    currency=view.account.currency,
                )
                if view.account is not None
                else None
            ),
            default_currency=default_currency,
            capability=_mapping_capability(view, raw_tables),
            default_mapping=command,
            default_source=_default_source(
                compatible_templates=compatible_templates,
                table_options=table_options,
            ),
            selected_template_id=(compatible_templates[0].id if compatible_templates else None),
            templates=tuple(
                MappingTemplateDto(id=template.id, name=template.name)
                for template in compatible_templates
            ),
            tables=projected_tables,
            total_table_count=len(table_options),
            tables_truncated=len(table_options) > len(projected_tables),
        )

    async def preview(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        workspace_default_currency: str,
        command: UnknownStatementMappingCommand,
    ) -> UnknownStatementMappingPreviewResult | None:
        view = await self._documents.get_document_detail_view(workspace_id, document_id)
        if view is None:
            return None
        mapping = await self._read_view(
            workspace_id=workspace_id,
            workspace_default_currency=workspace_default_currency,
            view=view,
        )
        if not mapping.capability.allowed:
            raise MappingUnavailableError(mapping.capability.blocking_reason_codes)
        raw_tables = _latest_raw_tables(view)
        selected_table = find_raw_table(
            raw_tables,
            page_number=command.page_number,
            table_index=command.table_index,
        )
        validate_mapping_command(command, selected_table)

        compatible_tables = compatible_mapping_tables(raw_tables, command)
        preview = preview_compatible_unknown_statement_mapping(
            raw_tables,
            command,
            max_rows=None,
        )
        rows = tuple(
            mapping_preview_row(row, command)
            for row in preview.rows[:MAX_MAPPING_PREVIEW_RESPONSE_ROWS]
        )
        has_blocking_warning = any(warning.severity == "error" for warning in preview.warnings)
        return UnknownStatementMappingPreviewResult(
            rows=rows,
            total_row_count=len(preview.rows),
            valid_row_count=preview.valid_count,
            invalid_row_count=preview.error_count,
            row_limit=MAX_MAPPING_PREVIEW_RESPONSE_ROWS,
            rows_truncated=len(preview.rows) > len(rows),
            compatible_tables=tuple(
                MappingTableRefDto(table.page_number, table.table_index)
                for table in compatible_tables
            ),
            warnings=tuple(preview.warnings),
            can_import=preview.valid_count > 0 and not has_blocking_warning,
        )


def _mapping_capability(
    view: ImportDocumentDetailView,
    raw_tables: list[dict[str, object]] | None,
) -> MappingCapabilityDto:
    reasons: list[MappingBlockingReasonCode] = []
    if view.account is None:
        reasons.append(MappingBlockingReasonCode.ACCOUNT_REQUIRED)
    if not raw_tables:
        reasons.append(MappingBlockingReasonCode.RAW_TABLES_UNAVAILABLE)
    if not _needs_mapping(view.validation):
        reasons.append(MappingBlockingReasonCode.MAPPING_NOT_REQUIRED)
    if any(row.status is RawTransactionStatus.CONFIRMED for row in view.raw_transactions):
        reasons.append(MappingBlockingReasonCode.CONFIRMED_ROWS_EXIST)
    return MappingCapabilityDto(allowed=not reasons, blocking_reason_codes=tuple(reasons))


def _needs_mapping(validation: dict[str, object] | None) -> bool:
    return validation is not None and validation.get("status") == "needs_mapping"


def _latest_raw_tables(
    view: ImportDocumentDetailView,
) -> list[dict[str, object]] | None:
    latest_attempt = view.parse_attempts[0] if view.parse_attempts else None
    return latest_attempt.raw_tables if latest_attempt is not None else None


def _default_source(
    *,
    compatible_templates: list[ImportMappingTemplate],
    table_options: list[dict[str, object]],
) -> MappingDefaultSource:
    if compatible_templates:
        return MappingDefaultSource.TEMPLATE
    if table_options and _list(table_options[0].get("mapping_suggestions")):
        return MappingDefaultSource.ANALYZER
    return MappingDefaultSource.FALLBACK


def _source_table(
    value: dict[str, object],
    raw_tables: list[dict[str, object]] | None,
    *,
    default_currency: str,
) -> MappingSourceTableDto:
    page_number = _int(value.get("page_number"), 1)
    table_index = _int(value.get("table_index"), 0)
    raw_table = find_raw_table(
        raw_tables,
        page_number=page_number,
        table_index=table_index,
    )
    rows = tuple(
        MappingSourceRowDto(
            row_number=index + 1,
            cells=tuple(
                cell[:MAX_MAPPING_SOURCE_CELL_CHARS]
                for cell in row[:MAX_MAPPING_SOURCE_SAMPLE_COLUMNS]
            ),
        )
        for index, row in enumerate(raw_table[:MAX_MAPPING_SOURCE_SAMPLE_ROWS])
    )
    return MappingSourceTableDto(
        ref=MappingTableRefDto(page_number, table_index),
        source_type=_string(value.get("source_type")) or "pdf_table",
        row_count=_int(value.get("row_count"), len(raw_table)),
        column_count=_int(
            value.get("column_count"),
            max((len(row) for row in raw_table), default=0),
        ),
        is_continuation=bool(value.get("is_continuation")),
        sample_rows=rows,
        candidates=tuple(
            candidate
            for item in _list(value.get("column_candidates"))
            if (candidate := _column_candidate(item)) is not None
        ),
        suggestion=_mapping_suggestion(value, default_currency=default_currency),
    )


def _column_candidate(value: object) -> MappingColumnCandidateDto | None:
    if not isinstance(value, dict):
        return None
    field = _string(value.get("field"))
    column_index = value.get("column_index")
    if not field or not isinstance(column_index, int):
        return None
    confidence = value.get("confidence")
    return MappingColumnCandidateDto(
        field=field,
        column_index=column_index,
        header=_string(value.get("header")),
        confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
    )


def _mapping_suggestion(
    value: dict[str, object],
    *,
    default_currency: str,
) -> MappingSuggestionDto | None:
    suggestions = _list(value.get("mapping_suggestions"))
    if not suggestions or not isinstance(suggestions[0], dict):
        return None
    suggestion = cast(dict[str, object], suggestions[0])
    command = _command_from_suggestion(
        value,
        suggestion,
        default_currency=default_currency,
    )
    confidence = suggestion.get("confidence")
    return MappingSuggestionDto(
        command=command,
        confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
        reasons=tuple(
            reason
            for item in _list(suggestion.get("reasons"))
            if (reason := _suggestion_reason(item)) is not None
        ),
        warning_codes=tuple(
            code
            for item in _list(suggestion.get("warnings"))
            if isinstance(item, dict) and (code := _string(item.get("code")))
        ),
    )


def _command_from_suggestion(
    table: dict[str, object],
    suggestion: dict[str, object],
    *,
    default_currency: str,
) -> UnknownStatementMappingCommand:
    return UnknownStatementMappingCommand(
        page_number=_int(table.get("page_number"), 1),
        table_index=_int(table.get("table_index"), 0),
        operation_date_column=_int(suggestion.get("operation_date_column"), 0),
        posting_date_column=_optional_int(suggestion.get("posting_date_column")),
        description_column=_int(suggestion.get("description_column"), 0),
        amount_column=_optional_int(suggestion.get("amount_column")),
        debit_amount_column=_optional_int(suggestion.get("debit_amount_column")),
        credit_amount_column=_optional_int(suggestion.get("credit_amount_column")),
        currency_column=_optional_int(suggestion.get("currency_column")),
        balance_after_column=_optional_int(suggestion.get("balance_after_column")),
        first_data_row=_int(suggestion.get("first_data_row"), 1),
        default_currency=default_currency,
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
    )


def _suggestion_reason(value: object) -> MappingSuggestionReasonDto | None:
    if not isinstance(value, dict):
        return None
    field = _string(value.get("field"))
    column_index = value.get("column_index")
    if not field or not isinstance(column_index, int):
        return None
    return MappingSuggestionReasonDto(
        field=field,
        column_index=column_index,
        header=_string(value.get("header")),
        evidence=_string(value.get("evidence")),
        matched_count=_optional_int(value.get("matched_count")),
        sample_count=_optional_int(value.get("sample_count")),
    )


def validate_mapping_command(
    command: UnknownStatementMappingCommand,
    selected_table: list[list[str]],
) -> None:
    if not selected_table:
        raise MappingCommandValidationError(
            "mapping_table_not_found",
            "Выбранная таблица не найдена.",
            ("tableRef",),
        )
    fields = _selected_column_fields(command)
    duplicates = _duplicate_fields(fields)
    if duplicates:
        raise MappingCommandValidationError(
            "duplicate_mapping_roles",
            "Одна колонка не может использоваться для нескольких ролей.",
            duplicates,
        )
    if command.amount_column is not None and (
        command.debit_amount_column is not None or command.credit_amount_column is not None
    ):
        raise MappingCommandValidationError(
            "conflicting_amount_mapping",
            "Выберите единую сумму или отдельные списание и зачисление.",
            ("amountColumn", "debitAmountColumn", "creditAmountColumn"),
        )
    if command.amount_column is None and (
        command.debit_amount_column is None or command.credit_amount_column is None
    ):
        raise MappingCommandValidationError(
            "incomplete_amount_mapping",
            "Укажите колонку суммы либо обе колонки списания и зачисления.",
            ("amountColumn", "debitAmountColumn", "creditAmountColumn"),
        )
    max_column_count = max((len(row) for row in selected_table), default=0)
    out_of_range = tuple(field for field, index in fields if index >= max_column_count)
    if out_of_range:
        raise MappingCommandValidationError(
            "mapping_column_out_of_range",
            "Выбранной колонки нет в исходной таблице.",
            out_of_range,
        )
    if command.first_data_row >= len(selected_table):
        raise MappingCommandValidationError(
            "mapping_first_row_out_of_range",
            "Первая строка данных находится за пределами таблицы.",
            ("firstDataRowNumber",),
        )


def _selected_column_fields(
    command: UnknownStatementMappingCommand,
) -> tuple[tuple[str, int], ...]:
    values = (
        ("operationDateColumn", command.operation_date_column),
        ("postingDateColumn", command.posting_date_column),
        ("descriptionColumn", command.description_column),
        ("amountColumn", command.amount_column),
        ("debitAmountColumn", command.debit_amount_column),
        ("creditAmountColumn", command.credit_amount_column),
        ("currencyColumn", command.currency_column),
        ("balanceAfterColumn", command.balance_after_column),
    )
    return tuple((field, index) for field, index in values if index is not None)


def _duplicate_fields(fields: tuple[tuple[str, int], ...]) -> tuple[str, ...]:
    fields_by_index: dict[int, list[str]] = {}
    for field, index in fields:
        fields_by_index.setdefault(index, []).append(field)
    return tuple(
        field
        for grouped_fields in fields_by_index.values()
        if len(grouped_fields) > 1
        for field in grouped_fields
    )


def _list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
