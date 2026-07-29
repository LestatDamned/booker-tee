from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.features.imports.application.unknown_statement_mappings.template_commands import (
    mapping_spec_from_template,
)
from app.features.imports.documents.validation_report import (
    StoredMappingSuggestion,
    StoredTablePreview,
    StoredValidationReport,
)
from app.features.imports.mapping.dto import (
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.models import ImportMappingTemplate

FALLBACK_OPERATION_DATE_COLUMN = 0
FALLBACK_DESCRIPTION_COLUMN = 2
FALLBACK_AMOUNT_COLUMN = 3
FALLBACK_FIRST_DATA_ROW = 1


class MappingDefaultSource(StrEnum):
    TEMPLATE = "template"
    ANALYZER = "analyzer"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ResolvedMappingDefault:
    spec: StatementMappingSpec
    source: MappingDefaultSource
    template_id: UUID | None


class StatementMappingDefaultResolver:
    @staticmethod
    def resolve(
        validation: StoredValidationReport | None,
        *,
        default_currency: str,
        compatible_templates: Sequence[ImportMappingTemplate] = (),
    ) -> ResolvedMappingDefault:
        if compatible_templates:
            template = compatible_templates[0]
            return ResolvedMappingDefault(
                spec=mapping_spec_from_template(template),
                source=MappingDefaultSource.TEMPLATE,
                template_id=template.id,
            )

        table = validation.table_previews[0] if validation and validation.table_previews else None
        suggestion = table.mapping_suggestions[0] if table and table.mapping_suggestions else None
        if table is not None and suggestion is not None:
            return ResolvedMappingDefault(
                spec=StatementMappingDefaultResolver.suggested_spec(
                    table,
                    suggestion,
                    default_currency=default_currency,
                ),
                source=MappingDefaultSource.ANALYZER,
                template_id=None,
            )

        return ResolvedMappingDefault(
            spec=_spec_from_candidates(table, default_currency=default_currency),
            source=MappingDefaultSource.FALLBACK,
            template_id=None,
        )

    @staticmethod
    def suggested_spec(
        table: StoredTablePreview,
        suggestion: StoredMappingSuggestion,
        *,
        default_currency: str,
    ) -> StatementMappingSpec:
        return StatementMappingSpec(
            page_number=table.page_number,
            table_index=table.table_index,
            operation_date_column=suggestion.operation_date_column,
            posting_date_column=suggestion.posting_date_column,
            description_column=suggestion.description_column,
            amount_column=suggestion.amount_column,
            currency_column=suggestion.currency_column,
            first_data_row=suggestion.first_data_row,
            default_currency=default_currency,
            debit_amount_column=suggestion.debit_amount_column,
            credit_amount_column=suggestion.credit_amount_column,
            balance_after_column=suggestion.balance_after_column,
            unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
        )


def _spec_from_candidates(
    table: StoredTablePreview | None,
    *,
    default_currency: str,
) -> StatementMappingSpec:
    columns = (
        {candidate.field: candidate.column_index for candidate in table.column_candidates}
        if table is not None
        else {}
    )
    return StatementMappingSpec(
        page_number=table.page_number if table is not None else 1,
        table_index=table.table_index if table is not None else 0,
        operation_date_column=columns.get(
            "operation_date",
            FALLBACK_OPERATION_DATE_COLUMN,
        ),
        posting_date_column=columns.get("posting_date"),
        description_column=columns.get(
            "description",
            FALLBACK_DESCRIPTION_COLUMN,
        ),
        amount_column=_amount_column(columns),
        currency_column=columns.get("currency"),
        first_data_row=FALLBACK_FIRST_DATA_ROW,
        default_currency=default_currency,
        debit_amount_column=columns.get("debit_amount"),
        credit_amount_column=columns.get("credit_amount"),
        balance_after_column=columns.get("balance_after"),
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
    )


def _amount_column(columns: dict[str, int]) -> int | None:
    amount_column = columns.get("amount")
    has_split_amount = "debit_amount" in columns or "credit_amount" in columns
    if amount_column is None and not has_split_amount:
        return FALLBACK_AMOUNT_COLUMN
    return amount_column
