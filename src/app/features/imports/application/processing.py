from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.imports.domain.deduplication import RawTransactionDeduplicator
from app.features.imports.domain.validation import (
    StatementValidationReport,
    StatementValidationStatus,
    validate_statement_totals,
)
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.mapping.raw_transaction_mapper import RawTransactionMapper
from app.features.imports.models import (
    ParseAttempt,
    ParseAttemptStatus,
    UploadedDocument,
    UploadedDocumentStatus,
)
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.parsing.parsers.factory import StatementParserRegistry
from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)


class StatementParseProcessor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        imports: ImportRepository,
        parser_registry: StatementParserRegistry,
    ) -> None:
        self.session = session
        self.imports = imports
        self.parser_registry = parser_registry

    async def record_successful_attempt(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedPdf,
        *,
        currency: str,
        exclude_duplicate_document_id: UUID | None = None,
        supersede_existing_rows: bool = False,
    ) -> None:
        parser = self.parser_registry.find_parser(extracted)
        attempt.finished_at = utc_now()
        if parser is not None:
            attempt.parser_name = parser.parser_name
            attempt.parser_version = parser.parser_version
            document.bank_name = parser.bank_code
            document.statement_type = parser.statement_type

        await self.imports.mark_attempt_success(
            attempt,
            raw_text_by_page_json=extracted.text_by_page,
            raw_tables_json=[
                {"page_number": page_tables.page_number, "tables": page_tables.tables}
                for page_tables in extracted.tables_by_page
            ],
            metadata=extracted.metadata,
        )
        if parser is None:
            await self._mark_attempt_requires_review(
                document,
                attempt,
                "No supported bank statement parser matched this document.",
            )
            return

        drafts = parser.extract_raw_transactions(
            extracted,
            account_id=document.account_id,
            currency=currency,
        )
        if not drafts:
            await self._mark_attempt_requires_review(
                document,
                attempt,
                "Parser matched the document but did not find transaction rows.",
            )
            return

        if supersede_existing_rows:
            await self.imports.mark_reviewable_raw_transactions_superseded(
                document,
                superseded_by_attempt_id=attempt.id,
            )

        raw_transactions = await self.imports.create_raw_transactions(
            RawTransactionMapper.from_drafts(
                drafts,
                workspace_id=document.workspace_id,
                uploaded_document_id=document.id,
                parse_attempt_id=attempt.id,
            )
        )
        await RawTransactionDeduplicator(self.imports).mark_duplicate_candidates(
            workspace_id=document.workspace_id,
            raw_transactions=raw_transactions,
            exclude_document_id=exclude_duplicate_document_id or document.id,
        )
        await TransactionRuleApplicationUseCase(self.session).apply_rules_to_raw_transactions(
            workspace_id=document.workspace_id,
            raw_transactions=raw_transactions,
        )

        control_totals = parser.extract_control_totals(
            extracted,
            currency=currency,
        )
        report = validate_statement_totals(
            rows=raw_transactions,
            control_totals=control_totals,
        )
        await store_import_validation_result(
            self.imports,
            document,
            attempt,
            control_totals=control_totals,
            report=report,
        )

    async def _mark_attempt_requires_review(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        message: str,
    ) -> None:
        await self.imports.mark_attempt_requires_review(attempt, message=message)
        await self.imports.mark_document_status(document, UploadedDocumentStatus.REQUIRES_REVIEW)


async def store_import_validation_result(
    imports: ImportRepository,
    document: UploadedDocument,
    attempt: ParseAttempt,
    *,
    control_totals: StatementControlTotals | None,
    report: StatementValidationReport,
) -> None:
    await imports.store_attempt_validation(
        attempt,
        control_totals=control_totals.as_json() if control_totals else None,
        validation_report=report.as_json(),
    )
    if report.status == StatementValidationStatus.VALID:
        await imports.mark_attempt_status(attempt, ParseAttemptStatus.SUCCESS)
        await imports.mark_document_status(document, UploadedDocumentStatus.PARSED)
        return

    await imports.mark_attempt_status(attempt, ParseAttemptStatus.REQUIRES_REVIEW)
    await imports.mark_document_status(document, UploadedDocumentStatus.REQUIRES_REVIEW)
