import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.documents.parse_attempts import (
    latest_parse_attempt,
    statement_control_totals_from_json,
)
from app.features.imports.application.documents.status import transition_document_status
from app.features.imports.application.pipelines.deduplication import (
    RawTransactionDeduplicator,
)
from app.features.imports.application.unknown_statement_mappings.control_total_cells import (
    MappingControlTotalKind,
    resolve_mapping_control_totals,
)
from app.features.imports.application.unknown_statement_mappings.drafts import (
    UnknownStatementDraftMapper,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    MappingControlTotalCellRef,
    SaveImportMappingTemplateCommand,
    StatementMappingSpec,
)
from app.features.imports.application.unknown_statement_mappings.engine import (
    StatementMappingEngine,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import (
    find_raw_table,
)
from app.features.imports.application.unknown_statement_mappings.reader import (
    validate_control_total_cells,
    validate_mapping_spec,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    clean_template_name,
    mapping_spec_as_json,
)
from app.features.imports.application.unknown_statements.control_totals import (
    extract_unknown_statement_control_totals,
)
from app.features.imports.domain.control_totals import StatementControlTotals
from app.features.imports.domain.validation import validate_statement_totals
from app.features.imports.errors import (
    MappingImportIdempotencyConflictError,
    MappingImportNotFoundError,
    MappingImportUnavailableError,
    UnknownStatementMappingError,
)
from app.features.imports.mapping.raw_transaction_mapper import RawTransactionMapper
from app.features.imports.models import (
    ImportMappingExecution,
    ImportMappingTemplate,
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)


@dataclass(frozen=True)
class MappingImportResult:
    document: UploadedDocument
    imported_row_count: int
    template_id: UUID | None
    replayed: bool


class UnknownStatementMappingImportUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)

    async def import_mapped_rows_idempotently(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        spec: StatementMappingSpec,
        idempotency_key: UUID,
        template_name: str | None = None,
    ) -> MappingImportResult:
        normalized_template_name = (
            clean_template_name(template_name) if template_name is not None else None
        )
        fingerprint = mapping_import_fingerprint(
            spec,
            template_name=normalized_template_name,
        )
        document = await self.imports.get_document_for_workspace_for_update(
            workspace_id,
            document_id,
        )
        if document is None:
            raise MappingImportNotFoundError("Документ не найден.")

        existing = await self.imports.get_mapping_execution(
            workspace_id=workspace_id,
            document_id=document_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if existing.payload_fingerprint != fingerprint:
                raise MappingImportIdempotencyConflictError(
                    "Этот ключ повторной отправки уже использован для другой настройки."
                )
            return MappingImportResult(
                document=document,
                imported_row_count=existing.imported_row_count,
                template_id=existing.template_id,
                replayed=True,
            )

        attempt = self._validate_import(document, spec)
        raw_transactions = await create_raw_transactions_from_mapping(
            session=self.session,
            imports=self.imports,
            document=document,
            attempt=attempt,
            spec=spec,
            exclude_duplicate_document_id=document.id,
            supersede_existing_rows=True,
        )
        template = (
            await self.save_template(
                workspace_id=workspace_id,
                command=SaveImportMappingTemplateCommand(
                    name=normalized_template_name,
                    bank_name=document.bank_name,
                    statement_type=document.statement_type,
                    mapping=spec,
                ),
                raw_tables=attempt.raw_tables_json,
            )
            if normalized_template_name is not None
            else None
        )
        await self.imports.create_mapping_execution(
            ImportMappingExecution(
                workspace_id=workspace_id,
                uploaded_document_id=document.id,
                idempotency_key=str(idempotency_key),
                payload_fingerprint=fingerprint,
                imported_row_count=len(raw_transactions),
                template_id=template.id if template is not None else None,
            )
        )
        await self.session.commit()

        imported_document = await self.imports.get_document_for_workspace(
            workspace_id,
            document_id,
        )
        if imported_document is None:
            raise MappingImportNotFoundError("Документ не найден после импорта.")
        return MappingImportResult(
            document=imported_document,
            imported_row_count=len(raw_transactions),
            template_id=template.id if template is not None else None,
            replayed=False,
        )

    @staticmethod
    def _validate_import(
        document: UploadedDocument,
        spec: StatementMappingSpec,
    ) -> ParseAttempt:
        if document.account_id is None:
            raise MappingImportUnavailableError("Выберите счёт перед импортом строк.")
        if any(row.status == RawTransactionStatus.CONFIRMED for row in document.raw_transactions):
            raise MappingImportUnavailableError(
                "Документ с проведёнными строками нельзя настроить повторно."
            )
        attempt = latest_parse_attempt(document)
        if attempt is None or attempt.raw_tables_json is None:
            raise MappingImportUnavailableError("Исходные таблицы документа недоступны.")
        selected_table = find_raw_table(
            attempt.raw_tables_json,
            page_number=spec.page_number,
            table_index=spec.table_index,
        )
        validate_mapping_spec(spec, selected_table)
        validate_control_total_cells(spec, attempt.raw_tables_json)
        result = StatementMappingEngine.apply(
            attempt.raw_tables_json,
            spec,
            max_rows=None,
        )
        if result.valid_count == 0 or any(
            warning.severity == "error" for warning in result.warnings
        ):
            raise MappingImportUnavailableError(
                "Исправьте блокирующие ошибки и обновите предпросмотр."
            )
        return attempt

    async def save_template(
        self,
        *,
        workspace_id: UUID,
        command: SaveImportMappingTemplateCommand,
        raw_tables: list[dict[str, object]] | None,
    ) -> ImportMappingTemplate:
        template = ImportMappingTemplate(
            workspace_id=workspace_id,
            name=clean_template_name(command.name),
            bank_name=command.bank_name,
            statement_type=command.statement_type,
            default_currency=command.mapping.default_currency,
            column_mapping_json=mapping_spec_as_json(
                command.mapping,
                raw_tables=raw_tables,
            ),
        )
        return await self.imports.create_mapping_template(template)


async def create_raw_transactions_from_mapping(
    *,
    session: AsyncSession,
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    spec: StatementMappingSpec,
    exclude_duplicate_document_id: UUID | None,
    supersede_existing_rows: bool,
) -> list[RawTransaction]:
    if document.account_id is None:
        raise UnknownStatementMappingError("Select an account before importing rows.")
    if attempt.raw_tables_json is None:
        raise UnknownStatementMappingError("Raw tables are not available for this document.")

    result = StatementMappingEngine.apply(
        attempt.raw_tables_json,
        spec,
        max_rows=None,
    )
    if not result.rows:
        raise UnknownStatementMappingError("No rows matched the selected mapping.")

    if supersede_existing_rows:
        await imports.mark_reviewable_raw_transactions_superseded(
            document,
            superseded_by_attempt_id=attempt.id,
        )
    raw_transactions = await imports.create_raw_transactions(
        RawTransactionMapper.from_drafts(
            UnknownStatementDraftMapper(
                spec=spec,
                account_id=document.account_id,
            ).map_rows(result.rows),
            workspace_id=document.workspace_id,
            uploaded_document_id=document.id,
            parse_attempt_id=attempt.id,
        )
    )
    await RawTransactionDeduplicator(imports).mark_duplicate_candidates(
        workspace_id=document.workspace_id,
        raw_transactions=raw_transactions,
        exclude_document_id=exclude_duplicate_document_id,
    )
    await TransactionRuleApplicationUseCase(session).apply_rules_to_raw_transactions(
        workspace_id=document.workspace_id,
        raw_transactions=raw_transactions,
    )
    await store_mapping_validation_result(
        imports,
        document,
        attempt,
        raw_transactions,
        spec,
    )
    return raw_transactions


async def store_mapping_validation_result(
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    raw_transactions: list[RawTransaction],
    spec: StatementMappingSpec,
) -> None:
    extracted_control_totals = statement_control_totals_from_json(
        attempt.control_totals_json
    ) or extract_unknown_statement_control_totals(attempt.raw_text_by_page_json)
    resolved = resolve_mapping_control_totals(attempt.raw_tables_json, spec)
    opening = next(
        (
            total.amount
            for total in resolved
            if total.kind is MappingControlTotalKind.OPENING_BALANCE
        ),
        None,
    )
    closing = next(
        (
            total.amount
            for total in resolved
            if total.kind is MappingControlTotalKind.CLOSING_BALANCE
        ),
        None,
    )
    control_totals = StatementControlTotals(
        currency=(
            extracted_control_totals.currency
            if extracted_control_totals is not None
            else spec.default_currency
        ),
        opening_balance=(
            opening
            if opening is not None
            else (
                extracted_control_totals.opening_balance
                if extracted_control_totals is not None
                else None
            )
        ),
        closing_balance=(
            closing
            if closing is not None
            else (
                extracted_control_totals.closing_balance
                if extracted_control_totals is not None
                else None
            )
        ),
        total_inflow=(
            extracted_control_totals.total_inflow if extracted_control_totals is not None else None
        ),
        total_outflow=(
            extracted_control_totals.total_outflow if extracted_control_totals is not None else None
        ),
    )
    report = validate_statement_totals(rows=raw_transactions, control_totals=control_totals)
    control_totals_payload = control_totals.as_json()
    control_totals_payload["mapping_sources"] = {
        total.kind.value: _control_total_cell_as_json(total.cell) for total in resolved
    }
    await imports.store_attempt_validation(
        attempt,
        control_totals=control_totals_payload,
        validation_report={
            **report.as_json(),
            "source": "unknown_statement_mapping",
        },
    )
    await imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    await transition_document_status(
        imports,
        document,
        UploadedDocumentStatus.REQUIRES_REVIEW,
    )


def mapping_import_fingerprint(
    spec: StatementMappingSpec,
    *,
    template_name: str | None,
) -> str:
    payload = {
        "mapping": mapping_spec_as_json(spec),
        "control_total_cells": {
            "opening_balance": _control_total_cell_as_json(spec.opening_balance_cell),
            "closing_balance": _control_total_cell_as_json(spec.closing_balance_cell),
        },
        "template_name": template_name,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode()).hexdigest()


def _control_total_cell_as_json(
    cell: MappingControlTotalCellRef | None,
) -> dict[str, int] | None:
    if cell is None:
        return None
    return {
        "page_number": cell.page_number,
        "table_index": cell.table_index,
        "row_number": cell.row_number,
        "column_index": cell.column_index,
    }
