from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import cast
from uuid import UUID

from app.features.imports.application.unknown_statement_mappings.dto import (
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    mapping_spec_from_template,
)
from app.features.imports.application.unknown_statement_mappings.values import (
    int_value,
    optional_int_value,
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
        validation: dict[str, object] | None,
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

        table = first_table_preview(validation)
        suggestion = first_mapping_suggestion(table)
        if suggestion:
            return ResolvedMappingDefault(
                spec=_spec_from_suggestion(
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


def _spec_from_suggestion(
    table: dict[str, object],
    suggestion: dict[str, object],
    *,
    default_currency: str,
) -> StatementMappingSpec:
    return StatementMappingSpec(
        page_number=int_value(table.get("page_number"), default=1),
        table_index=int_value(table.get("table_index"), default=0),
        operation_date_column=int_value(
            suggestion.get("operation_date_column"),
            default=FALLBACK_OPERATION_DATE_COLUMN,
        ),
        posting_date_column=optional_int_value(suggestion.get("posting_date_column")),
        description_column=int_value(
            suggestion.get("description_column"),
            default=FALLBACK_DESCRIPTION_COLUMN,
        ),
        amount_column=optional_int_value(suggestion.get("amount_column")),
        currency_column=optional_int_value(suggestion.get("currency_column")),
        first_data_row=int_value(
            suggestion.get("first_data_row"),
            default=FALLBACK_FIRST_DATA_ROW,
        ),
        default_currency=default_currency,
        debit_amount_column=optional_int_value(suggestion.get("debit_amount_column")),
        credit_amount_column=optional_int_value(suggestion.get("credit_amount_column")),
        balance_after_column=optional_int_value(suggestion.get("balance_after_column")),
        unsigned_amount_direction=UnsignedAmountDirection.REQUIRE_SIGN,
    )


def _spec_from_candidates(
    table: dict[str, object],
    *,
    default_currency: str,
) -> StatementMappingSpec:
    columns = candidate_column_indexes(table)
    return StatementMappingSpec(
        page_number=int_value(table.get("page_number"), default=1),
        table_index=int_value(table.get("table_index"), default=0),
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


def first_table_preview(validation: dict[str, object] | None) -> dict[str, object]:
    previews = table_previews_from_validation(validation)
    return previews[0] if previews else {}


def first_mapping_suggestion(table: dict[str, object]) -> dict[str, object]:
    suggestions = table.get("mapping_suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return {}
    first = suggestions[0]
    return cast(dict[str, object], first) if isinstance(first, dict) else {}


def candidate_column_indexes(table: dict[str, object]) -> dict[str, int]:
    candidates = table.get("column_candidates")
    if not isinstance(candidates, list):
        return {}
    indexes: dict[str, int] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        field = candidate.get("field")
        column_index = candidate.get("column_index")
        if isinstance(field, str) and isinstance(column_index, int):
            indexes[field] = column_index
    return indexes


def table_previews_from_validation(
    validation: dict[str, object] | None,
) -> list[dict[str, object]]:
    if validation is None:
        return []
    previews = validation.get("table_previews")
    if not isinstance(previews, list):
        return []
    return [cast(dict[str, object], preview) for preview in previews if isinstance(preview, dict)]
