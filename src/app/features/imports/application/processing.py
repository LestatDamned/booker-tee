from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.imports.application.known_statements.pipeline import (
    KnownStatementImportPipeline,
)
from app.features.imports.application.unknown_statements.fallback import (
    UnknownStatementFallbackPipeline,
)
from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.models import (
    ParseAttempt,
    UploadedDocument,
)
from app.features.imports.parsing.registry import StatementParserRegistry
from app.features.imports.repository import ImportRepository


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

        await self.imports.mark_attempt_success(
            attempt,
            raw_text_by_page_json=extracted.text_by_page,
            raw_tables_json=_raw_tables_from_extracted(extracted),
            metadata=extracted.metadata,
        )
        if parser is None:
            await UnknownStatementFallbackPipeline(
                self.session,
                self.imports,
            ).record_requires_review_or_apply_template(
                document=document,
                attempt=attempt,
                extracted=extracted,
                exclude_duplicate_document_id=exclude_duplicate_document_id,
            )
            return

        await KnownStatementImportPipeline(
            self.session,
            self.imports,
        ).record_parser_result(
            document=document,
            attempt=attempt,
            extracted=extracted,
            parser=parser,
            currency=currency,
            exclude_duplicate_document_id=exclude_duplicate_document_id,
        )


def _raw_tables_from_extracted(extracted: ExtractedStatement) -> list[dict[str, object]]:
    return [
        {"page_number": page_tables.page_number, "tables": page_tables.tables}
        for page_tables in extracted.tables_by_page
    ]
