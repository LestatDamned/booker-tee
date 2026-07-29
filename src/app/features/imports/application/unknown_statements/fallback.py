from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.unknown_statements.analyzer import (
    analyze_unknown_statement,
)
from app.features.imports.application.unknown_statements.text_tables import (
    raw_tables_with_text_candidate_tables,
)
from app.features.imports.documents.attempts import (
    mark_attempt_requires_review,
)
from app.features.imports.documents.repository import DocumentRepository
from app.features.imports.mapping.commands.import_rows import MappedStatementRowImporter
from app.features.imports.mapping.errors import UnknownStatementMappingError
from app.features.imports.mapping.repository import MappingRepository
from app.features.imports.mapping.templates import (
    mapping_spec_from_template,
    select_compatible_mapping_template,
)
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.statements.repository import StatementRepository


class UnknownStatementFallbackPipeline:
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
        analysis = analyze_unknown_statement(extracted)
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
