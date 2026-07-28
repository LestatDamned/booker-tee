from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID

from app.features.imports.application.documents.snapshot import (
    ImportDocumentSnapshot,
)
from app.features.imports.application.unknown_statement_mappings.control_total_cells import (
    MappingControlTotalKind,
    ResolvedMappingControlTotal,
    automatic_control_total_cell,
    detect_control_total_candidates,
    resolve_mapping_control_totals,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    MappedStatementRow,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.engine import (
    StatementMappingEngine,
)
from app.features.imports.application.unknown_statement_mappings.mapping_defaults import (
    StatementMappingDefaultResolver,
    table_previews_from_validation,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    compatible_mapping_tables,
    find_raw_table,
)
from app.features.imports.application.unknown_statement_mappings.read_models import (
    MappingAccountDto,
    MappingBalanceReconciliationDto,
    MappingBlockingReasonCode,
    MappingCapabilityDto,
    MappingColumnCandidateDto,
    MappingControlTotalCandidateDto,
    MappingResolvedControlTotalDto,
    MappingSourceRowDto,
    MappingSourceRowsDto,
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
from app.features.imports.application.unknown_statement_mappings.validation import (
    StatementMappingValidator,
    raise_for_mapping_validation_issues,
)
from app.features.imports.models import (
    ImportMappingTemplate,
    RawTransactionStatus,
)

MAX_MAPPING_SOURCE_TABLES = 100
MAX_MAPPING_SOURCE_SAMPLE_ROWS = 12
MAX_MAPPING_SOURCE_SAMPLE_COLUMNS = 32
MAX_MAPPING_SOURCE_CELL_CHARS = 500
MAX_MAPPING_SOURCE_WINDOW_ROWS = 50
MAX_MAPPING_PREVIEW_RESPONSE_ROWS = 20


class MappingDocumentReader(Protocol):
    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None: ...


class MappingTemplateReader(Protocol):
    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None,
        statement_type: str | None,
    ) -> list[ImportMappingTemplate]: ...


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
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        return await self._read_snapshot(
            workspace_id=workspace_id,
            workspace_default_currency=workspace_default_currency,
            snapshot=snapshot,
        )

    async def _read_snapshot(
        self,
        *,
        workspace_id: UUID,
        workspace_default_currency: str,
        snapshot: ImportDocumentSnapshot,
    ) -> UnknownStatementMappingReadModel:
        raw_tables = _latest_raw_tables(snapshot)
        templates = await self._templates.list_matching_templates(
            workspace_id=workspace_id,
            bank_name=snapshot.bank_name,
            statement_type=snapshot.statement_type,
        )
        compatible_templates = compatible_mapping_templates(templates, raw_tables)
        default_currency = (
            snapshot.account.currency
            if snapshot.account is not None
            else workspace_default_currency
        )
        default = StatementMappingDefaultResolver.resolve(
            snapshot.validation,
            default_currency=default_currency,
            compatible_templates=compatible_templates,
        )
        control_total_candidates = detect_control_total_candidates(raw_tables)
        spec = replace(
            default.spec,
            opening_balance_cell=automatic_control_total_cell(
                control_total_candidates,
                MappingControlTotalKind.OPENING_BALANCE,
            ),
            closing_balance_cell=automatic_control_total_cell(
                control_total_candidates,
                MappingControlTotalKind.CLOSING_BALANCE,
            ),
        )
        table_options = table_previews_from_validation(snapshot.validation)
        projected_tables = tuple(
            _source_table(option, raw_tables, default_currency=default_currency)
            for option in table_options[:MAX_MAPPING_SOURCE_TABLES]
        )
        return UnknownStatementMappingReadModel(
            document_id=snapshot.id,
            filename=snapshot.original_filename,
            status=snapshot.status,
            bank_name=snapshot.bank_name,
            statement_type=snapshot.statement_type,
            account=(
                MappingAccountDto(
                    id=snapshot.account.id,
                    name=snapshot.account.name,
                    currency=snapshot.account.currency,
                )
                if snapshot.account is not None
                else None
            ),
            default_currency=default_currency,
            capability=_mapping_capability(snapshot, raw_tables),
            default_mapping=spec,
            default_source=default.source,
            selected_template_id=default.template_id,
            templates=tuple(
                MappingTemplateDto(id=template.id, name=template.name)
                for template in compatible_templates
            ),
            tables=projected_tables,
            control_total_candidates=tuple(
                MappingControlTotalCandidateDto(
                    kind=candidate.kind,
                    cell=candidate.cell,
                    label=candidate.label,
                    raw_value=candidate.raw_value[:MAX_MAPPING_SOURCE_CELL_CHARS],
                    amount=str(candidate.amount),
                    currency=default_currency,
                    confidence=candidate.confidence,
                )
                for candidate in control_total_candidates
            ),
            total_table_count=len(table_options),
            tables_truncated=len(table_options) > len(projected_tables),
        )

    async def preview(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        workspace_default_currency: str,
        spec: StatementMappingSpec,
    ) -> UnknownStatementMappingPreviewResult | None:
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        mapping = await self._read_snapshot(
            workspace_id=workspace_id,
            workspace_default_currency=workspace_default_currency,
            snapshot=snapshot,
        )
        if not mapping.capability.allowed:
            raise MappingUnavailableError(mapping.capability.blocking_reason_codes)
        raw_tables = _latest_raw_tables(snapshot)
        selected_table = find_raw_table(
            raw_tables,
            page_number=spec.page_number,
            table_index=spec.table_index,
        )
        raise_for_mapping_validation_issues(
            StatementMappingValidator.validate(
                spec=spec,
                selected_table=selected_table,
                raw_tables=raw_tables,
            )
        )

        compatible_tables = compatible_mapping_tables(raw_tables, spec)
        result = StatementMappingEngine.apply(
            raw_tables,
            spec,
            max_rows=None,
        )
        resolved_control_totals = resolve_mapping_control_totals(raw_tables, spec)
        reconciliation = _balance_reconciliation(
            result.rows,
            resolved_control_totals,
        )
        rows = tuple(
            mapping_preview_row(row, spec)
            for row in result.rows[:MAX_MAPPING_PREVIEW_RESPONSE_ROWS]
        )
        has_blocking_warning = any(warning.severity == "error" for warning in result.warnings)
        return UnknownStatementMappingPreviewResult(
            rows=rows,
            total_row_count=len(result.rows),
            valid_row_count=result.valid_count,
            invalid_row_count=result.error_count,
            row_limit=MAX_MAPPING_PREVIEW_RESPONSE_ROWS,
            rows_truncated=len(result.rows) > len(rows),
            compatible_tables=tuple(
                MappingTableRefDto(table.page_number, table.table_index)
                for table in compatible_tables
            ),
            warnings=tuple(result.warnings),
            control_totals=tuple(
                MappingResolvedControlTotalDto(
                    kind=total.kind,
                    cell=total.cell,
                    raw_value=total.raw_value[:MAX_MAPPING_SOURCE_CELL_CHARS],
                    amount=str(total.amount),
                    currency=spec.default_currency,
                )
                for total in resolved_control_totals
            ),
            reconciliation=reconciliation,
            can_import=result.valid_count > 0 and not has_blocking_warning,
        )

    async def source_rows(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        page_number: int,
        table_index: int,
        start_row_number: int,
        row_limit: int,
    ) -> MappingSourceRowsDto | None:
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        raw_table = find_raw_table(
            _latest_raw_tables(snapshot),
            page_number=page_number,
            table_index=table_index,
        )
        if not raw_table:
            return None
        bounded_limit = min(max(row_limit, 1), MAX_MAPPING_SOURCE_WINDOW_ROWS)
        start_index = min(max(start_row_number - 1, 0), len(raw_table) - 1)
        selected_rows = raw_table[start_index : start_index + bounded_limit]
        rows = tuple(
            MappingSourceRowDto(
                row_number=start_index + index + 1,
                cells=tuple(
                    cell[:MAX_MAPPING_SOURCE_CELL_CHARS]
                    for cell in row[:MAX_MAPPING_SOURCE_SAMPLE_COLUMNS]
                ),
            )
            for index, row in enumerate(selected_rows)
        )
        return MappingSourceRowsDto(
            table_ref=MappingTableRefDto(page_number, table_index),
            rows=rows,
            total_row_count=len(raw_table),
            start_row_number=start_index + 1,
            row_limit=bounded_limit,
            has_previous=start_index > 0,
            has_next=start_index + len(rows) < len(raw_table),
        )


def _mapping_capability(
    snapshot: ImportDocumentSnapshot,
    raw_tables: list[dict[str, object]] | None,
) -> MappingCapabilityDto:
    reasons: list[MappingBlockingReasonCode] = []
    if snapshot.account is None:
        reasons.append(MappingBlockingReasonCode.ACCOUNT_REQUIRED)
    if not raw_tables:
        reasons.append(MappingBlockingReasonCode.RAW_TABLES_UNAVAILABLE)
    if not _needs_mapping(snapshot.validation):
        reasons.append(MappingBlockingReasonCode.MAPPING_NOT_REQUIRED)
    if any(row.status is RawTransactionStatus.CONFIRMED for row in snapshot.raw_transactions):
        reasons.append(MappingBlockingReasonCode.CONFIRMED_ROWS_EXIST)
    return MappingCapabilityDto(allowed=not reasons, blocking_reason_codes=tuple(reasons))


def _needs_mapping(validation: dict[str, object] | None) -> bool:
    return validation is not None and validation.get("status") == "needs_mapping"


def _latest_raw_tables(
    snapshot: ImportDocumentSnapshot,
) -> list[dict[str, object]] | None:
    latest_attempt = snapshot.parse_attempts[0] if snapshot.parse_attempts else None
    return latest_attempt.raw_tables if latest_attempt is not None else None


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


def _balance_reconciliation(
    rows: list[MappedStatementRow],
    control_totals: tuple[ResolvedMappingControlTotal, ...],
) -> MappingBalanceReconciliationDto | None:
    opening = next(
        (
            total.amount
            for total in control_totals
            if total.kind is MappingControlTotalKind.OPENING_BALANCE
        ),
        None,
    )
    closing = next(
        (
            total.amount
            for total in control_totals
            if total.kind is MappingControlTotalKind.CLOSING_BALANCE
        ),
        None,
    )
    if opening is None or closing is None:
        return None
    movement = sum(
        (row.amount for row in rows if row.amount is not None),
        start=Decimal("0"),
    )
    calculated_closing = opening + movement
    difference = calculated_closing - closing
    return MappingBalanceReconciliationDto(
        opening_balance=str(opening),
        movement=str(movement),
        calculated_closing_balance=str(calculated_closing),
        statement_closing_balance=str(closing),
        difference=str(difference),
        matches=difference == 0,
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
    spec = _command_from_suggestion(
        value,
        suggestion,
        default_currency=default_currency,
    )
    confidence = suggestion.get("confidence")
    return MappingSuggestionDto(
        spec=spec,
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
) -> StatementMappingSpec:
    return StatementMappingSpec(
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


def _list(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object, default: int) -> int:
    return value if isinstance(value, int) else default


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None
