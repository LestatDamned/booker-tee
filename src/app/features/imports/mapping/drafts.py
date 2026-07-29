from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.mapping.dto import (
    MappedStatementRow,
    StatementMappingSpec,
)
from app.features.imports.parsers.support.normalization import build_dedupe_hash
from app.features.imports.statements.dto import RawTransactionDraft
from app.features.imports.statements.types import RawTransactionStatus


@dataclass(frozen=True)
class StatementMappingDraftBuilder:
    spec: StatementMappingSpec
    account_id: UUID

    def build_rows(self, rows: list[MappedStatementRow]) -> list[RawTransactionDraft]:
        return [self.map_row(row, row_index=row_index) for row_index, row in enumerate(rows)]

    def map_row(
        self,
        row: MappedStatementRow,
        *,
        row_index: int,
    ) -> RawTransactionDraft:
        return RawTransactionDraft(
            row_index=row_index,
            status=StatementMappingDraftBuilder.raw_transaction_status_for(row),
            raw_payload={
                "source": "unknown_statement_mapping",
                "document_row_index": row_index,
                "page_number": row.page_number,
                "table_index": row.table_index,
                "source_row_number": row.source_row_number,
                "columns": {
                    "operation_date": self.spec.operation_date_column,
                    "posting_date": self.spec.posting_date_column,
                    "description": self.spec.description_column,
                    "amount": self.spec.amount_column,
                    "debit_amount": self.spec.debit_amount_column,
                    "credit_amount": self.spec.credit_amount_column,
                    "currency": self.spec.currency_column,
                    "balance_after": self.spec.balance_after_column,
                },
                "unsigned_amount_direction": self.spec.unsigned_amount_direction.value,
            },
            operation_date_raw=row.operation_date_raw,
            posting_date_raw=row.posting_date_raw or None,
            description_raw=row.description_raw,
            amount_raw=row.amount_raw,
            currency_raw=row.currency_raw,
            balance_after_raw=row.balance_after_raw,
            account_hint_raw=None,
            account_id=self.account_id,
            operation_date=row.operation_date,
            posting_date=row.posting_date or row.operation_date,
            description_normalized=row.description,
            amount=row.amount,
            currency=row.currency,
            balance_after=row.balance_after,
            dedupe_hash=build_dedupe_hash(
                account_id=self.account_id,
                operation_date=row.operation_date,
                amount=row.amount,
                currency=row.currency,
                description_normalized=row.description,
                source_row_id=StatementMappingDraftBuilder.source_row_id(row),
            ),
            confidence_score=Decimal("0.7000") if row.status == "valid" else Decimal("0.2500"),
            normalization_error=row.error or None,
        )

    @staticmethod
    def raw_transaction_status_for(
        row: MappedStatementRow,
    ) -> RawTransactionStatus:
        if row.status == "valid":
            return RawTransactionStatus.NORMALIZED
        return RawTransactionStatus.NEEDS_REVIEW

    @staticmethod
    def source_row_id(row: MappedStatementRow) -> str:
        return f"mapped:{row.page_number}:{row.table_index}:{row.source_row_number}"
