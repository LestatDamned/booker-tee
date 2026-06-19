from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.pipelines.attempt_review import (
    mark_attempt_requires_review,
)
from app.features.imports.application.pipelines.validation_result import (
    store_import_validation_result,
)
from app.features.imports.domain.deduplication import RawTransactionDeduplicator
from app.features.imports.domain.validation import validate_statement_totals
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.mapping.raw_transaction_mapper import RawTransactionMapper
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.imports.parsing.parser_types import BankStatementRawTransactionParser
from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.application.rule_application import (
    TransactionRuleApplicationUseCase,
)


class KnownStatementImportPipeline:
    def __init__(self, session: AsyncSession, imports: ImportRepository) -> None:
        self.session = session
        self.imports = imports

    async def record_parser_result(
        self,
        *,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedStatement,
        parser: BankStatementRawTransactionParser,
        currency: str,
        exclude_duplicate_document_id: UUID | None,
        supersede_existing_rows: bool,
    ) -> None:
        drafts = parser.extract_raw_transactions(
            extracted,
            account_id=document.account_id,
            currency=currency,
        )
        if not drafts:
            await mark_attempt_requires_review(
                self.imports,
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
