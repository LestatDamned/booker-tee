from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.known_statements.pipeline import (
    KnownStatementImportPipeline,
)
from app.features.imports.application.strategies.context import StatementImportContext
from app.features.imports.parsing.parser_types import BankStatementRawTransactionParser
from app.features.imports.repository import ImportRepository


class KnownParserImportStrategy:
    def __init__(
        self,
        *,
        session: AsyncSession,
        imports: ImportRepository,
        parser: BankStatementRawTransactionParser,
    ) -> None:
        self.session = session
        self.imports = imports
        self.parser = parser

    def prepare_metadata(self, context: StatementImportContext) -> None:
        context.attempt.parser_name = self.parser.parser_name
        context.attempt.parser_version = self.parser.parser_version
        context.document.bank_name = self.parser.bank_code
        context.document.statement_type = self.parser.statement_type

    async def run(self, context: StatementImportContext) -> None:
        await KnownStatementImportPipeline(
            self.session,
            self.imports,
        ).record_parser_result(
            document=context.document,
            attempt=context.attempt,
            extracted=context.extracted,
            parser=self.parser,
            currency=context.currency,
            exclude_duplicate_document_id=context.exclude_duplicate_document_id,
            supersede_existing_rows=context.supersede_existing_rows,
        )
