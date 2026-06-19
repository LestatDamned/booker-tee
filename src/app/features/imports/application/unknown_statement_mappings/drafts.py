from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappedRow,
    UnknownStatementMappingCommand,
)
from app.features.imports.models import RawTransactionStatus
from app.features.imports.parsing.parser_types import RawTransactionDraft
from app.features.imports.parsing.support.normalization import build_dedupe_hash


@dataclass(frozen=True)
class UnknownStatementDraftMapper:
    command: UnknownStatementMappingCommand
    account_id: UUID

    def map_rows(self, rows: list[UnknownStatementMappedRow]) -> list[RawTransactionDraft]:
        return [self.map_row(row, row_index=row_index) for row_index, row in enumerate(rows)]

    def map_row(
        self,
        row: UnknownStatementMappedRow,
        *,
        row_index: int,
    ) -> RawTransactionDraft:
        return RawTransactionDraft(
            row_index=row_index,
            status=UnknownStatementDraftMapper.raw_transaction_status_for(row),
            raw_payload={
                "source": "unknown_statement_mapping",
                "document_row_index": row_index,
                "page_number": row.page_number,
                "table_index": row.table_index,
                "source_row_number": row.source_row_number,
                "columns": {
                    "operation_date": self.command.operation_date_column,
                    "posting_date": self.command.posting_date_column,
                    "description": self.command.description_column,
                    "amount": self.command.amount_column,
                    "debit_amount": self.command.debit_amount_column,
                    "credit_amount": self.command.credit_amount_column,
                    "currency": self.command.currency_column,
                    "balance_after": self.command.balance_after_column,
                },
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
                source_row_id=UnknownStatementDraftMapper.source_row_id(row),
            ),
            confidence_score=Decimal("0.7000") if row.status == "valid" else Decimal("0.2500"),
            normalization_error=row.error or None,
        )

    @staticmethod
    def raw_transaction_status_for(
        row: UnknownStatementMappedRow,
    ) -> RawTransactionStatus:
        if row.status == "valid":
            return RawTransactionStatus.NORMALIZED
        return RawTransactionStatus.NEEDS_REVIEW

    @staticmethod
    def source_row_id(row: UnknownStatementMappedRow) -> str:
        return f"mapped:{row.page_number}:{row.table_index}:{row.source_row_number}"


def mapped_rows_to_drafts(
    rows: list[UnknownStatementMappedRow],
    *,
    command: UnknownStatementMappingCommand,
    account_id: UUID,
) -> list[RawTransactionDraft]:
    return UnknownStatementDraftMapper(command=command, account_id=account_id).map_rows(rows)


def mapped_row_to_draft(
    row: UnknownStatementMappedRow,
    *,
    row_index: int,
    command: UnknownStatementMappingCommand,
    account_id: UUID,
) -> RawTransactionDraft:
    return UnknownStatementDraftMapper(command=command, account_id=account_id).map_row(
        row,
        row_index=row_index,
    )


def raw_transaction_status_for_mapped_row(
    row: UnknownStatementMappedRow,
) -> RawTransactionStatus:
    return UnknownStatementDraftMapper.raw_transaction_status_for(row)


def mapped_row_source_id(row: UnknownStatementMappedRow) -> str:
    return UnknownStatementDraftMapper.source_row_id(row)
