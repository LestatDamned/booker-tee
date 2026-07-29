from typing import Protocol
from uuid import UUID

from app.features.imports.infrastructure.extraction.extracted_statement import ExtractedStatement
from app.features.imports.statements.dto import RawTransactionDraft, StatementControlTotals


class BankStatementRawTransactionParser(Protocol):
    @property
    def bank_code(self) -> str: ...

    @property
    def statement_type(self) -> str: ...

    @property
    def parser_name(self) -> str: ...

    @property
    def parser_version(self) -> str: ...

    def can_parse(self, extracted: ExtractedStatement) -> bool: ...

    def extract_raw_transactions(
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
