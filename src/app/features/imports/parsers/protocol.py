from typing import Protocol
from uuid import UUID

from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.statements.dto import RawTransactionDraft, StatementControlTotals


class BankStatementParser(Protocol):
    @property
    def bank_code(self) -> str: ...

    @property
    def statement_type(self) -> str: ...

    @property
    def parser_name(self) -> str: ...

    @property
    def parser_version(self) -> str: ...

    def matches_statement(self, extracted: ExtractedStatement) -> bool: ...

    def parse_transaction_drafts(
        self,
        extracted: ExtractedStatement,
        *,
        account_id: UUID | None,
        currency: str,
    ) -> list[RawTransactionDraft]: ...

    def extract_control_totals(
        self,
        extracted: ExtractedStatement,
        *,
        currency: str,
    ) -> StatementControlTotals | None: ...
