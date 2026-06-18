from dataclasses import dataclass
from enum import StrEnum

from app.features.imports.application.unknown_statements.table_preview_dto import (
    UnknownStatementTablePreview,
)
from app.features.imports.parsing.parser_types import StatementControlTotals


class UnknownStatementStatus(StrEnum):
    NEEDS_MAPPING = "needs_mapping"


@dataclass(frozen=True)
class UnknownStatementAnalysis:
    status: UnknownStatementStatus
    message: str
    detected_bank_name: str | None
    detected_statement_type: str | None
    text_based: bool
    page_count: int
    table_count: int
    table_previews: list[UnknownStatementTablePreview]
    control_totals: StatementControlTotals | None

    def as_validation_report(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "message": self.message,
            "detected_bank_name": self.detected_bank_name,
            "detected_statement_type": self.detected_statement_type,
            "text_based": self.text_based,
            "page_count": self.page_count,
            "table_count": self.table_count,
            "table_previews": [preview.as_json() for preview in self.table_previews],
            "statement_total_inflow": str(self.control_totals.total_inflow)
            if self.control_totals and self.control_totals.total_inflow is not None
            else None,
            "statement_total_outflow": str(self.control_totals.total_outflow)
            if self.control_totals and self.control_totals.total_outflow is not None
            else None,
            "opening_balance": str(self.control_totals.opening_balance)
            if self.control_totals and self.control_totals.opening_balance is not None
            else None,
            "closing_balance": str(self.control_totals.closing_balance)
            if self.control_totals and self.control_totals.closing_balance is not None
            else None,
        }
