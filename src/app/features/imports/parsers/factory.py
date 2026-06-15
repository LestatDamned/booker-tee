from dataclasses import dataclass

from app.features.imports.extraction.pdfplumber_extractor import ExtractedPdf
from app.features.imports.parser_types import BankStatementRawTransactionParser
from app.features.imports.parsers.expobank import ExpobankCardStatementParser
from app.features.imports.parsers.vtb import VtbDepositStatementParser


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
            VtbDepositStatementParser(),
            ExpobankCardStatementParser(),
        )
    )
