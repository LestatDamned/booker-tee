from dataclasses import dataclass

from app.features.imports.parsers.alfabank import AlfabankXlsxStatementParser
from app.features.imports.parsers.expobank import ExpobankCardStatementParser
from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.ozon_bank import OzonBankCardStatementParser
from app.features.imports.parsers.protocol import BankStatementParser
from app.features.imports.parsers.sberbank import SberbankCardStatementParser
from app.features.imports.parsers.tbank import TbankCardStatementParser
from app.features.imports.parsers.vtb.card import VtbCardStatementParser
from app.features.imports.parsers.vtb.deposit import VtbDepositStatementParser


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
