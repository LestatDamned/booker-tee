from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol, cast
from uuid import UUID

from app.features.imports.documents.validation_report import (
    StoredMappingSuggestion,
    StoredTablePreview,
    StoredValidationReport,
)
from app.features.imports.mapping.dto import (
    MappingDefaultSource,
    MappingTemplateSnapshot,
    ResolvedMappingDefault,
    StatementMappingSpec,
    UnsignedAmountDirection,
)
from app.features.imports.mapping.errors import UnknownStatementMappingError
from app.features.imports.mapping.raw_tables import find_raw_table
from app.features.imports.mapping.rows import (
    cell_at,
    parse_optional_mapped_amount,
    parse_optional_mapped_date,
)
from app.features.imports.parsers.support.normalization import normalize_description

FALLBACK_OPERATION_DATE_COLUMN = 0
FALLBACK_DESCRIPTION_COLUMN = 2
FALLBACK_AMOUNT_COLUMN = 3
FALLBACK_FIRST_DATA_ROW = 1


class MappingTemplateStore(Protocol):
    async def create_mapping_template(
        self,
        *,
        workspace_id: UUID,
        name: str,
        bank_name: str | None,
        statement_type: str | None,
        mapping: StatementMappingSpec,
        table_signature: dict[str, object] | None,
    ) -> MappingTemplateSnapshot: ...


class StatementMappingTemplateService:
    def __init__(self, templates: MappingTemplateStore) -> None:
        self._templates = templates

    async def save(
        self,
        *,
        workspace_id: UUID,
        name: str,
        bank_name: str | None,
        statement_type: str | None,
        mapping: StatementMappingSpec,
        raw_tables: list[dict[str, object]] | None,
    ) -> MappingTemplateSnapshot:
        return await self._templates.create_mapping_template(
            workspace_id=workspace_id,
            name=clean_template_name(name),
            bank_name=bank_name,
            statement_type=statement_type,
            mapping=mapping,
            table_signature=table_signature_for_mapping(raw_tables, mapping),
        )


class StatementMappingDefaultResolver:
    @staticmethod
    def resolve(
        validation: StoredValidationReport | None,
        *,
        default_currency: str,
        compatible_templates: Sequence[MappingTemplateSnapshot] = (),
    ) -> ResolvedMappingDefault:
        if compatible_templates:
            template = compatible_templates[0]
            return ResolvedMappingDefault(
                spec=template.mapping,
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


def compatible_mapping_templates(
    templates: Sequence[MappingTemplateSnapshot],
    raw_tables: list[dict[str, object]] | None,
) -> list[MappingTemplateSnapshot]:
    return [
        template
        for template in templates
        if mapping_template_matches_raw_tables(template, raw_tables)
    ]


def select_compatible_mapping_template(
    templates: Sequence[MappingTemplateSnapshot],
    raw_tables: list[dict[str, object]] | None,
) -> MappingTemplateSnapshot | None:
    compatible_templates = compatible_mapping_templates(templates, raw_tables)
    return compatible_templates[0] if compatible_templates else None


def mapping_template_matches_raw_tables(
    template: MappingTemplateSnapshot,
    raw_tables: list[dict[str, object]] | None,
) -> bool:
    expected_signature = template.table_signature
    if expected_signature is None:
        return False
    spec = template.mapping
    actual_signature = table_signature_for_mapping(raw_tables, spec)
    if actual_signature is None:
        return False
    return table_signatures_match(
        expected_signature,
        actual_signature,
        spec=spec,
    )


def clean_template_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise UnknownStatementMappingError("Template name is required.")
    return cleaned[:255]


def table_signature_for_mapping(
    raw_tables: list[dict[str, object]] | None,
    spec: StatementMappingSpec,
) -> dict[str, object] | None:
    table = find_raw_table(
        raw_tables,
        page_number=spec.page_number,
        table_index=spec.table_index,
    )
    if not table:
        return None
    return table_signature_for_table(table, spec)


def table_signature_for_table(
    table: list[list[str]],
    spec: StatementMappingSpec,
) -> dict[str, object] | None:
    header_row_index = max(spec.first_data_row - 1, 0)
    if header_row_index >= len(table):
        return None
    header = table[header_row_index]
    return {
        "column_count": len(header),
        "header": [normalize_header_cell(cell) for cell in header],
        "mapped_columns": mapped_column_profiles_for_table(table, spec),
    }


def normalize_header_cell(value: str) -> str:
    return " ".join(value.casefold().split())


def table_signatures_match(
    expected: dict[str, object],
    actual: dict[str, object],
    *,
    spec: StatementMappingSpec,
) -> bool:
    if expected.get("column_count") != actual.get("column_count"):
        return False
    if expected.get("header") == actual.get("header"):
        return True
    return mapped_column_profiles_match(expected, actual, spec=spec)


def mapped_column_profiles_for_table(
    table: list[list[str]],
    spec: StatementMappingSpec,
) -> list[dict[str, object]]:
    return [
        {
            "field": field_name,
            "column_index": column_index,
            "profile": column_profile_for_table(table, spec, column_index),
        }
        for field_name, column_index in mapped_field_indexes(spec)
    ]


def mapped_field_indexes(spec: StatementMappingSpec) -> list[tuple[str, int]]:
    fields: list[tuple[str, int | None]] = [
        ("operation_date", spec.operation_date_column),
        ("posting_date", spec.posting_date_column),
        ("description", spec.description_column),
        ("amount", spec.amount_column),
        ("debit_amount", spec.debit_amount_column),
        ("credit_amount", spec.credit_amount_column),
        ("currency", spec.currency_column),
        ("balance_after", spec.balance_after_column),
    ]
    return [
        (field_name, column_index)
        for field_name, column_index in fields
        if column_index is not None and column_index >= 0
    ]


def column_profile_for_table(
    table: list[list[str]],
    spec: StatementMappingSpec,
    column_index: int,
) -> dict[str, object]:
    header_row_index = max(spec.first_data_row - 1, 0)
    header = cell_at(table[header_row_index], column_index) if header_row_index < len(table) else ""
    samples = [cell_at(row, column_index) for row in table[spec.first_data_row :]][:10]
    return {
        "header": normalize_header_cell(header),
        "sample_count": len(samples),
        "non_empty_count": sum(1 for sample in samples if sample.strip()),
        "date_like_count": sum(1 for sample in samples if value_looks_like_date(sample)),
        "money_like_count": sum(1 for sample in samples if value_looks_like_money(sample)),
        "currency_like_count": sum(1 for sample in samples if value_looks_like_currency(sample)),
        "description_like_count": sum(
            1 for sample in samples if value_looks_like_description(sample)
        ),
    }


def mapped_column_profiles_match(
    expected: dict[str, object],
    actual: dict[str, object],
    *,
    spec: StatementMappingSpec,
) -> bool:
    expected_columns = mapped_column_profile_map(expected)
    actual_columns = mapped_column_profile_map(actual)
    if not expected_columns or not actual_columns:
        return False
    for field_name, column_index in mapped_field_indexes(spec):
        expected_profile = expected_columns.get((field_name, column_index))
        actual_profile = actual_columns.get((field_name, column_index))
        if expected_profile is None or actual_profile is None:
            return False
        if not profile_supports_field(expected_profile, field_name, allow_empty_optional=True):
            return False
        if not profile_supports_field(actual_profile, field_name, allow_empty_optional=True):
            return False
    return True


def mapped_column_profile_map(
    signature: dict[str, object],
) -> dict[tuple[str, int], dict[str, object]]:
    mapped_columns = signature.get("mapped_columns")
    if not isinstance(mapped_columns, list):
        return {}
    profiles: dict[tuple[str, int], dict[str, object]] = {}
    for column in mapped_columns:
        if not isinstance(column, dict):
            continue
        field = column.get("field")
        column_index = column.get("column_index")
        profile = column.get("profile")
        if isinstance(field, str) and isinstance(column_index, int) and isinstance(profile, dict):
            profiles[(field, column_index)] = cast(dict[str, object], profile)
    return profiles


def profile_supports_field(
    profile: dict[str, object],
    field: str,
    *,
    allow_empty_optional: bool,
) -> bool:
    non_empty_count = _int_value(profile.get("non_empty_count"), default=0)
    if allow_empty_optional and field in _OPTIONAL_SPARSE_PROFILE_FIELDS and non_empty_count == 0:
        return True
    if field in {"operation_date", "posting_date"}:
        return profile_ratio(profile, "date_like_count") >= Decimal("0.60")
    if field in {"amount", "debit_amount", "credit_amount", "balance_after"}:
        return profile_ratio(profile, "money_like_count") >= Decimal("0.60")
    if field == "currency":
        return profile_ratio(profile, "currency_like_count") >= Decimal("0.60")
    if field == "description":
        return profile_ratio(profile, "description_like_count") >= Decimal("0.50")
    return False


def profile_ratio(profile: dict[str, object], count_key: str) -> Decimal:
    non_empty_count = _int_value(profile.get("non_empty_count"), default=0)
    if non_empty_count <= 0:
        return Decimal("0")
    matched_count = _int_value(profile.get(count_key), default=0)
    return Decimal(matched_count) / Decimal(non_empty_count)


def value_looks_like_date(value: str) -> bool:
    parsed, error = parse_optional_mapped_date(value)
    return parsed is not None and not error


def value_looks_like_money(value: str) -> bool:
    parsed, error = parse_optional_mapped_amount(value)
    return parsed is not None and not error


def value_looks_like_currency(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized in _CURRENCY_CODES or value.strip() in _CURRENCY_SYMBOLS


def value_looks_like_description(value: str) -> bool:
    normalized = normalize_description(value)
    if normalized is None:
        return False
    return not (
        value_looks_like_date(normalized)
        or value_looks_like_money(normalized)
        or value_looks_like_currency(normalized)
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


def _int_value(value: object, *, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


_OPTIONAL_SPARSE_PROFILE_FIELDS = {
    "posting_date",
    "debit_amount",
    "credit_amount",
    "currency",
    "balance_after",
}
_CURRENCY_CODES = {"rub", "rur", "usd", "eur", "gbp", "cny", "try", "aed"}
_CURRENCY_SYMBOLS = {"₽", "$", "€", "£"}
