from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.imports.application.unknown_statements.fallback import (
    UnknownStatementFallbackPipeline,
)
from app.features.imports.documents.attempts import mark_attempt_requires_review
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)
from app.features.imports.parsing.parser_types import BankStatementRawTransactionParser
from app.features.imports.parsing.registry import StatementParserRegistry
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
        parser = self.parser_registry.find_parser(extracted)
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
            await UnknownStatementFallbackPipeline(
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
        parser: BankStatementRawTransactionParser,
        currency: str,
        exclude_duplicate_document_id: UUID | None,
    ) -> None:
        drafts = parser.extract_raw_transactions(
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
