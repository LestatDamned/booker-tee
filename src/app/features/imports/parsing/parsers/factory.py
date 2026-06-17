from dataclasses import dataclass

from app.features.imports.infrastructure.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.parsing.parser_types import BankStatementRawTransactionParser
from app.features.imports.parsing.parsers.expobank import ExpobankCardStatementParser
from app.features.imports.parsing.parsers.sberbank import SberbankCardStatementParser
from app.features.imports.parsing.parsers.vtb import (
    VtbCardStatementParser,
    VtbDepositStatementParser,
)


@dataclass(frozen=True)
class StatementParserRegistry:
    parsers: tuple[BankStatementRawTransactionParser, ...]

    def find_parser(
        self,
        extracted: ExtractedPdf,
    ) -> BankStatementRawTransactionParser | None:
        for parser in self.parsers:
            if parser.can_parse(extracted):
                return parser
        return None


def default_statement_parser_registry() -> StatementParserRegistry:
    return StatementParserRegistry(
        parsers=(
            SberbankCardStatementParser(),
            VtbCardStatementParser(),
            VtbDepositStatementParser(),
            ExpobankCardStatementParser(),
        )
    )
