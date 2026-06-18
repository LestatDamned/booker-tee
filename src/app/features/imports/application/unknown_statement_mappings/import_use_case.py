from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.unknown_statement_mappings.drafts import (
    UnknownStatementDraftMapper,
)
from app.features.imports.application.unknown_statement_mappings.dto import (
    SaveImportMappingTemplateCommand,
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.preview import (
    preview_compatible_unknown_statement_mapping,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    clean_template_name,
    mapping_command_as_json,
)
from app.features.imports.application.unknown_statements.control_totals import (
    extract_unknown_statement_control_totals,
)
from app.features.imports.domain.deduplication import RawTransactionDeduplicator
from app.features.imports.domain.validation import validate_statement_totals
from app.features.imports.errors import UnknownStatementMappingError
from app.features.imports.mapping.raw_transaction_mapper import RawTransactionMapper
from app.features.imports.models import (
    ImportMappingTemplate,
    ParseAttempt,
    ParseAttemptStatus,
    RawTransaction,
    RawTransactionStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)


class UnknownStatementMappingImportUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)

    async def import_mapped_rows(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
        command: UnknownStatementMappingCommand,
        template_name: str | None = None,
    ) -> UploadedDocument:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise UnknownStatementMappingError("Document was not found.")
        if document.account_id is None:
            raise UnknownStatementMappingError("Select an account before importing rows.")
        if any(row.status == RawTransactionStatus.CONFIRMED for row in document.raw_transactions):
            raise UnknownStatementMappingError(
                "Documents with confirmed ledger rows cannot be remapped."
            )

        attempt = latest_parse_attempt(document)
        if attempt is None or attempt.raw_tables_json is None:
            raise UnknownStatementMappingError("Raw tables are not available for this document.")

        await create_raw_transactions_from_mapping(
            session=self.session,
            imports=self.imports,
            document=document,
            attempt=attempt,
            command=command,
            exclude_duplicate_document_id=document.id,
            supersede_existing_rows=True,
        )
        if template_name:
            await self.save_template(
                workspace_id=workspace_id,
                command=SaveImportMappingTemplateCommand(
                    name=template_name,
                    bank_name=document.bank_name,
                    statement_type=document.statement_type,
                    mapping=command,
                ),
                raw_tables=attempt.raw_tables_json,
            )
        await self.session.commit()

        imported_document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if imported_document is None:
            raise UnknownStatementMappingError("Document was not found after import.")
        return imported_document

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
            column_mapping_json=mapping_command_as_json(
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
    command: UnknownStatementMappingCommand,
    exclude_duplicate_document_id: UUID | None,
    supersede_existing_rows: bool,
) -> list[RawTransaction]:
    if document.account_id is None:
        raise UnknownStatementMappingError("Select an account before importing rows.")
    if attempt.raw_tables_json is None:
        raise UnknownStatementMappingError("Raw tables are not available for this document.")

    preview = preview_compatible_unknown_statement_mapping(
        attempt.raw_tables_json,
        command,
        max_rows=None,
    )
    if not preview.rows:
        raise UnknownStatementMappingError("No rows matched the selected mapping.")

    if supersede_existing_rows:
        await imports.mark_reviewable_raw_transactions_superseded(
            document,
            superseded_by_attempt_id=attempt.id,
        )
    raw_transactions = await imports.create_raw_transactions(
        RawTransactionMapper.from_drafts(
            UnknownStatementDraftMapper(
                command=command,
                account_id=document.account_id,
            ).map_rows(preview.rows),
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
    await store_mapping_validation_result(imports, document, attempt, raw_transactions)
    return raw_transactions


async def store_mapping_validation_result(
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    raw_transactions: list[RawTransaction],
) -> None:
    control_totals = statement_control_totals_from_json(
        attempt.control_totals_json
    ) or extract_unknown_statement_control_totals(attempt.raw_text_by_page_json)
    report = validate_statement_totals(rows=raw_transactions, control_totals=control_totals)
    await imports.store_attempt_validation(
        attempt,
        control_totals=control_totals.as_json() if control_totals else None,
        validation_report={
            **report.as_json(),
            "source": "unknown_statement_mapping",
        },
    )
    await imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    await imports.mark_document_status(document, UploadedDocumentStatus.REQUIRES_REVIEW)


def latest_parse_attempt(document: UploadedDocument) -> ParseAttempt | None:
    if not document.parse_attempts:
        return None
    return max(document.parse_attempts, key=lambda attempt: attempt.started_at)


def statement_control_totals_from_json(
    payload: dict[str, object] | None,
) -> StatementControlTotals | None:
    if payload is None:
        return None
    currency = payload.get("currency")
    if not isinstance(currency, str):
        return None
    return StatementControlTotals(
        currency=currency,
        opening_balance=decimal_from_json(payload.get("opening_balance")),
        closing_balance=decimal_from_json(payload.get("closing_balance")),
        total_inflow=decimal_from_json(payload.get("total_inflow")),
        total_outflow=decimal_from_json(payload.get("total_outflow")),
    )


def decimal_from_json(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, int):
        return Decimal(value)
    return None
