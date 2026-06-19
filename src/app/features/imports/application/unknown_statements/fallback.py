from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.pipelines.attempt_review import (
    mark_attempt_requires_review,
)
from app.features.imports.application.unknown_statement_mappings.import_use_case import (
    create_raw_transactions_from_mapping,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    mapping_command_from_template,
    select_compatible_mapping_template,
)
from app.features.imports.application.unknown_statements.analyzer import (
    analyze_unknown_statement,
)
from app.features.imports.application.unknown_statements.text_tables import (
    raw_tables_with_text_candidate_tables,
)
from app.features.imports.errors import UnknownStatementMappingError
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.imports.repository import ImportRepository


class UnknownStatementFallbackPipeline:
    def __init__(self, session: AsyncSession, imports: ImportRepository) -> None:
        self.session = session
        self.imports = imports

    async def record_requires_review_or_apply_template(
        self,
        *,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedPdf,
        exclude_duplicate_document_id: UUID | None,
        supersede_existing_rows: bool,
    ) -> None:
        analysis = analyze_unknown_statement(extracted)
        if not any(preview.source_type == "pdf_table" for preview in analysis.table_previews):
            attempt.raw_tables_json = raw_tables_with_text_candidate_tables(
                extracted,
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
                supersede_existing_rows=supersede_existing_rows,
            ):
                return
        except UnknownStatementMappingError as exc:
            validation_report["template_auto_apply_error"] = str(exc)
        await mark_attempt_requires_review(
            self.imports,
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
        supersede_existing_rows: bool,
    ) -> bool:
        if document.account_id is None:
            return False
        if not document.bank_name and not document.statement_type:
            return False
        templates = await self.imports.list_mapping_templates(
            workspace_id=document.workspace_id,
            bank_name=document.bank_name,
            statement_type=document.statement_type,
        )
        if not templates:
            return False
        template = select_compatible_mapping_template(templates, attempt.raw_tables_json)
        if template is None:
            return False

        await create_raw_transactions_from_mapping(
            session=self.session,
            imports=self.imports,
            document=document,
            attempt=attempt,
            command=mapping_command_from_template(template),
            exclude_duplicate_document_id=exclude_duplicate_document_id,
            supersede_existing_rows=supersede_existing_rows,
        )
        return True
