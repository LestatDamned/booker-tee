from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.strategies.context import StatementImportContext
from app.features.imports.application.unknown_statements.fallback import (
    UnknownStatementFallbackPipeline,
)
from app.features.imports.repository import ImportRepository


class UnknownFallbackImportStrategy:
    def __init__(self, *, session: AsyncSession, imports: ImportRepository) -> None:
        self.session = session
        self.imports = imports

    def prepare_metadata(self, context: StatementImportContext) -> None:
        return None

    async def run(self, context: StatementImportContext) -> None:
        await UnknownStatementFallbackPipeline(
            self.session,
            self.imports,
        ).record_requires_review_or_apply_template(
            document=context.document,
            attempt=context.attempt,
            extracted=context.extracted,
            exclude_duplicate_document_id=context.exclude_duplicate_document_id,
            supersede_existing_rows=context.supersede_existing_rows,
        )
