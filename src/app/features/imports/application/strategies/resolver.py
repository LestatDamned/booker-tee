from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.application.strategies.context import StatementImportContext
from app.features.imports.application.strategies.known_parser import KnownParserImportStrategy
from app.features.imports.application.strategies.unknown_fallback import (
    UnknownFallbackImportStrategy,
)
from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.parsing.parsers.factory import StatementParserRegistry
from app.features.imports.repository import ImportRepository


class StatementImportStrategy(Protocol):
    def prepare_metadata(self, context: StatementImportContext) -> None: ...

    async def run(self, context: StatementImportContext) -> None: ...


class StatementImportStrategyResolver:
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

    def resolve(self, extracted: ExtractedPdf) -> StatementImportStrategy:
        parser = self.parser_registry.find_parser(extracted)
        if parser is None:
            return UnknownFallbackImportStrategy(
                session=self.session,
                imports=self.imports,
            )
        return KnownParserImportStrategy(
            session=self.session,
            imports=self.imports,
            parser=parser,
        )
