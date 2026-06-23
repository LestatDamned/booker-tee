from dataclasses import dataclass

from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.parsing.parser_types import BankStatementRawTransactionParser
from app.features.imports.parsing.parsers.alfabank.xlsx import AlfabankXlsxStatementParser
from app.features.imports.parsing.parsers.expobank.card import ExpobankCardStatementParser
from app.features.imports.parsing.parsers.ozon_bank.card import OzonBankCardStatementParser
from app.features.imports.parsing.parsers.sberbank.card import SberbankCardStatementParser
from app.features.imports.parsing.parsers.tbank.card import TbankCardStatementParser
from app.features.imports.parsing.parsers.vtb.card import VtbCardStatementParser
from app.features.imports.parsing.parsers.vtb.deposit import VtbDepositStatementParser


@dataclass(frozen=True)
class StatementParserRegistry:
    parsers: tuple[BankStatementRawTransactionParser, ...]

    def find_parser(
        self,
        extracted: ExtractedStatement,
    ) -> BankStatementRawTransactionParser | None:
        for parser in self.parsers:
            if parser.can_parse(extracted):
                return parser
        return None


def default_statement_parser_registry() -> StatementParserRegistry:
    return StatementParserRegistry(
        parsers=(
            AlfabankXlsxStatementParser(),
            OzonBankCardStatementParser(),
            TbankCardStatementParser(),
            SberbankCardStatementParser(),
            VtbCardStatementParser(),
            VtbDepositStatementParser(),
            ExpobankCardStatementParser(),
        )
    )
