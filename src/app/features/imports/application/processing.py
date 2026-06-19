from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import utc_now
from app.features.imports.application.strategies.context import (
    StatementImportContext,
    raw_tables_from_extracted,
)
from app.features.imports.application.strategies.resolver import (
    StatementImportStrategyResolver,
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
        self.imports = imports
        self.strategy_resolver = StatementImportStrategyResolver(
            session=session,
            imports=imports,
            parser_registry=parser_registry,
        )

    async def record_successful_attempt(
        self,
        document: UploadedDocument,
        attempt: ParseAttempt,
        extracted: ExtractedStatement,
        *,
        currency: str,
        exclude_duplicate_document_id: UUID | None = None,
        supersede_existing_rows: bool = False,
    ) -> None:
        context = StatementImportContext(
            document=document,
            attempt=attempt,
            extracted=extracted,
            currency=currency,
            exclude_duplicate_document_id=exclude_duplicate_document_id,
            supersede_existing_rows=supersede_existing_rows,
        )
        strategy = self.strategy_resolver.resolve(extracted)
        strategy.prepare_metadata(context)
        attempt.finished_at = utc_now()

        await self.imports.mark_attempt_success(
            attempt,
            raw_text_by_page_json=extracted.text_by_page,
            raw_tables_json=raw_tables_from_extracted(extracted),
            metadata=extracted.metadata,
        )
        await strategy.run(context)
