from dataclasses import replace
from typing import Protocol
from uuid import UUID

from app.features.imports.documents.dto import ImportDocumentSnapshot
from app.features.imports.documents.validation_report import (
    StoredSuggestionReason,
    StoredTablePreview,
)
from app.features.imports.mapping.control_totals import (
    automatic_control_total_cell,
    detect_control_total_candidates,
)
from app.features.imports.mapping.dto import (
    MappingAccountDto,
    MappingBlockingReasonCode,
    MappingCapabilityDto,
    MappingColumnCandidateDto,
    MappingControlTotalCandidateDto,
    MappingControlTotalKind,
    MappingSourceRowDto,
    MappingSourceTableDto,
    MappingSuggestionDto,
    MappingSuggestionReasonDto,
    MappingTableRefDto,
    MappingTemplateDto,
    MappingTemplateSnapshot,
    StatementMappingOverview,
)
from app.features.imports.mapping.raw_tables import find_raw_table
from app.features.imports.mapping.templates import (
    StatementMappingDefaultResolver,
    compatible_mapping_templates,
)
from app.features.imports.statements.types import RawTransactionStatus

MAX_MAPPING_SOURCE_TABLES = 100
MAX_MAPPING_SOURCE_SAMPLE_ROWS = 12
MAX_MAPPING_SOURCE_SAMPLE_COLUMNS = 32
MAX_MAPPING_SOURCE_CELL_CHARS = 500


class MappingOverviewDocumentReader(Protocol):
    async def get_document_snapshot(
        self,
        workspace_id: UUID,
        document_id: UUID,
    ) -> ImportDocumentSnapshot | None: ...


class MappingOverviewTemplateReader(Protocol):
    async def list_matching_templates(
        self,
        *,
        workspace_id: UUID,
        bank_name: str | None,
        statement_type: str | None,
    ) -> list[MappingTemplateSnapshot]: ...


class StatementMappingOverviewReader:
    def __init__(
        self,
        documents: MappingOverviewDocumentReader,
        templates: MappingOverviewTemplateReader,
    ) -> None:
        self._documents = documents
        self._templates = templates

    async def read(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        workspace_default_currency: str,
    ) -> StatementMappingOverview | None:
        snapshot = await self._documents.get_document_snapshot(workspace_id, document_id)
        if snapshot is None:
            return None
        raw_tables = latest_mapping_raw_tables(snapshot)
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
        table_options = (
            snapshot.validation.table_previews if snapshot.validation is not None else ()
        )
        projected_tables = tuple(
            _source_table(option, raw_tables, default_currency=default_currency)
            for option in table_options[:MAX_MAPPING_SOURCE_TABLES]
        )
        return StatementMappingOverview(
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
            capability=mapping_capability(snapshot, raw_tables),
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


def mapping_capability(
    snapshot: ImportDocumentSnapshot,
    raw_tables: list[dict[str, object]] | None,
) -> MappingCapabilityDto:
    reasons: list[MappingBlockingReasonCode] = []
    if snapshot.account is None:
        reasons.append(MappingBlockingReasonCode.ACCOUNT_REQUIRED)
    if not raw_tables:
        reasons.append(MappingBlockingReasonCode.RAW_TABLES_UNAVAILABLE)
    if snapshot.validation is None or not snapshot.validation.needs_mapping:
        reasons.append(MappingBlockingReasonCode.MAPPING_NOT_REQUIRED)
    if any(row.status is RawTransactionStatus.CONFIRMED for row in snapshot.raw_transactions):
        reasons.append(MappingBlockingReasonCode.CONFIRMED_ROWS_EXIST)
    return MappingCapabilityDto(allowed=not reasons, blocking_reason_codes=tuple(reasons))


def latest_mapping_raw_tables(
    snapshot: ImportDocumentSnapshot,
) -> list[dict[str, object]] | None:
    latest_attempt = snapshot.parse_attempts[0] if snapshot.parse_attempts else None
    return latest_attempt.raw_tables if latest_attempt is not None else None


def _source_table(
    table: StoredTablePreview,
    raw_tables: list[dict[str, object]] | None,
    *,
    default_currency: str,
) -> MappingSourceTableDto:
    raw_table = find_raw_table(
        raw_tables,
        page_number=table.page_number,
        table_index=table.table_index,
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
        ref=MappingTableRefDto(table.page_number, table.table_index),
        source_type=table.source_type,
        row_count=table.row_count or len(raw_table),
        column_count=table.column_count or max((len(row) for row in raw_table), default=0),
        is_continuation=table.is_continuation,
        sample_rows=rows,
        candidates=tuple(
            MappingColumnCandidateDto(
                field=candidate.field,
                column_index=candidate.column_index,
                header=candidate.header,
            )
            for candidate in table.column_candidates
        ),
        suggestion=_mapping_suggestion(table, default_currency=default_currency),
    )


def _mapping_suggestion(
    table: StoredTablePreview,
    *,
    default_currency: str,
) -> MappingSuggestionDto | None:
    if not table.mapping_suggestions:
        return None
    suggestion = table.mapping_suggestions[0]
    spec = StatementMappingDefaultResolver.suggested_spec(
        table,
        suggestion,
        default_currency=default_currency,
    )
    return MappingSuggestionDto(
        spec=spec,
        reasons=tuple(_suggestion_reason(reason) for reason in suggestion.reasons),
        warning_codes=tuple(warning.code for warning in suggestion.warnings),
    )


def _suggestion_reason(
    reason: StoredSuggestionReason,
) -> MappingSuggestionReasonDto:
    return MappingSuggestionReasonDto(
        field=reason.field,
        column_index=reason.column_index,
        header=reason.header,
        evidence=reason.evidence,
        matched_count=reason.matched_count,
        sample_count=reason.sample_count,
    )
