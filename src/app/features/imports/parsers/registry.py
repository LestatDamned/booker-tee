from dataclasses import dataclass

from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.protocol import BankStatementParser
from app.features.imports.parsing.parsers.alfabank.xlsx import AlfabankXlsxStatementParser
from app.features.imports.parsing.parsers.expobank.card import ExpobankCardStatementParser
from app.features.imports.parsing.parsers.ozon_bank.card import OzonBankCardStatementParser
from app.features.imports.parsing.parsers.sberbank.card import SberbankCardStatementParser
from app.features.imports.parsing.parsers.tbank.card import TbankCardStatementParser
from app.features.imports.parsing.parsers.vtb.card import VtbCardStatementParser
from app.features.imports.parsing.parsers.vtb.deposit import VtbDepositStatementParser


@dataclass(frozen=True)
class StatementParserRegistry:
    parsers: tuple[BankStatementParser, ...]

    def find_matching_parser(
        self,
        extracted: ExtractedStatement,
    ) -> BankStatementParser | None:
        for parser in self.parsers:
            if parser.matches_statement(extracted):
                return parser
        return None

    @classmethod
    def with_default_parsers(cls) -> "StatementParserRegistry":
        return cls(
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
