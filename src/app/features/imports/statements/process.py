from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.imports.documents.attempts import mark_attempt_requires_review
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.mapping.analysis.analyzer import StatementAnalyzer
from app.features.imports.mapping.analysis.text_tables import (
    raw_tables_with_text_candidate_tables,
)
from app.features.imports.mapping.commands.import_rows import MappedStatementRowImporter
from app.features.imports.mapping.errors import UnknownStatementMappingError
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.mapping.templates import (
    mapping_spec_from_template,
    select_compatible_mapping_template,
)
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)
from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.protocol import BankStatementParser
from app.features.imports.parsers.registry import StatementParserRegistry
from app.features.imports.statements.deduplication import RawTransactionDeduplicator
from app.features.imports.statements.raw_transactions import RawTransactionMapper
from app.features.imports.statements.repository import StatementRepository
from app.features.imports.statements.validation import validate_statement_totals
from app.features.imports.statements.validation_service import StatementValidationService
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)


class StatementParseCompletionService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        documents: DocumentRepository,
        statements: StatementRepository,
        mappings: MappingRepository,
        parser_registry: StatementParserRegistry,
    ) -> None:
        self.session = session
        self.documents = documents
        self.statements = statements
        self.mappings = mappings
        self.parser_registry = parser_registry

    async def complete_successful_attempt(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedStatement,
        *,
        currency: str,
        exclude_duplicate_document_id: UUID | None = None,
    ) -> None:
        parser = self.parser_registry.find_matching_parser(extracted)
        if parser is not None:
            attempt.parser_name = parser.parser_name
            attempt.parser_version = parser.parser_version
            document.bank_name = parser.bank_code
            document.statement_type = parser.statement_type
        attempt.finished_at = utc_now()

        await self.documents.mark_attempt_success(
            attempt,
            raw_text_by_page_json=extracted.text_by_page,
            raw_tables_json=_raw_tables_from_extracted(extracted),
            metadata=extracted.metadata,
        )
        if parser is None:
            await StatementMappingFallbackPipeline(
                self.session,
                self.documents,
                self.statements,
                self.mappings,
            ).apply_template_or_prepare_review(
                document=document,
                attempt=attempt,
                extracted=extracted,
                exclude_duplicate_document_id=exclude_duplicate_document_id,
            )
            return

        await KnownStatementImportPipeline(
            self.session,
            self.documents,
            self.statements,
        ).import_parsed_transactions(
            document=document,
            attempt=attempt,
            extracted=extracted,
            parser=parser,
            currency=currency,
            exclude_duplicate_document_id=exclude_duplicate_document_id,
        )


class StatementMappingFallbackPipeline:
    def __init__(
        self,
        session: AsyncSession,
        documents: DocumentRepository,
        statements: StatementRepository,
        mappings: MappingRepository,
    ) -> None:
        self.session = session
        self.documents = documents
        self.statements = statements
        self.mappings = mappings

    async def apply_template_or_prepare_review(
        self,
        *,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedStatement,
        exclude_duplicate_document_id: UUID | None,
    ) -> None:
        analysis = StatementAnalyzer.analyze(extracted)
        if not any(preview.source_type == "pdf_table" for preview in analysis.table_previews):
            attempt.raw_tables_json = raw_tables_with_text_candidate_tables(
                analysis.generated_text_tables,
                attempt.raw_tables_json,
            )
        document.bank_name = analysis.detected_bank_name
        document.statement_type = analysis.detected_statement_type
        validation_report = analysis.as_validation_report()
        try:
            if await self._auto_apply_template(
                document,
                attempt,
                exclude_duplicate_document_id=exclude_duplicate_document_id or document.id,
            ):
                return
        except UnknownStatementMappingError as exc:
            validation_report["template_auto_apply_error"] = str(exc)
        await mark_attempt_requires_review(
            self.documents,
            document,
            attempt,
            "No supported bank statement parser matched this document.",
            validation_report=validation_report,
            control_totals=analysis.control_totals,
        )

    async def _auto_apply_template(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        *,
        exclude_duplicate_document_id: UUID | None,
    ) -> bool:
        if document.account_id is None:
            return False
        if not document.bank_name and not document.statement_type:
            return False
        templates = await self.mappings.list_matching_templates(
            workspace_id=document.workspace_id,
            bank_name=document.bank_name,
            statement_type=document.statement_type,
        )
        if not templates:
            return False
        template = select_compatible_mapping_template(templates, attempt.raw_tables_json)
        if template is None:
            return False

        await MappedStatementRowImporter(
            self.session,
            self.documents,
            self.statements,
        ).import_rows(
            document=document,
            attempt=attempt,
            spec=mapping_spec_from_template(template),
            exclude_duplicate_document_id=exclude_duplicate_document_id,
        )
        return True


class KnownStatementImportPipeline:
    def __init__(
        self,
        session: AsyncSession,
        documents: DocumentRepository,
        statements: StatementRepository,
    ) -> None:
        self.session = session
        self.documents = documents
        self.statements = statements

    async def import_parsed_transactions(
        self,
        *,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedStatement,
        parser: BankStatementParser,
        currency: str,
        exclude_duplicate_document_id: UUID | None,
    ) -> None:
        drafts = parser.parse_transaction_drafts(
            extracted,
            account_id=document.account_id,
            currency=currency,
        )
        if not drafts:
            await mark_attempt_requires_review(
                self.documents,
                document,
                attempt,
                "Parser matched the document but did not find transaction rows.",
            )
            return

        raw_transactions = await self.statements.create_raw_transactions(
            RawTransactionMapper.from_drafts(
                drafts,
                workspace_id=document.workspace_id,
                uploaded_document_id=document.id,
                parse_attempt_id=attempt.id,
            )
        )
        await RawTransactionDeduplicator(self.statements).mark_duplicate_candidates(
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
        await StatementValidationService(self.documents).store_result(
            document,
            attempt,
            control_totals=control_totals,
            report=report,
        )


def _raw_tables_from_extracted(extracted: ExtractedStatement) -> list[dict[str, object]]:
    return [
        {"page_number": page_tables.page_number, "tables": page_tables.tables}
        for page_tables in extracted.tables_by_page
    ]
