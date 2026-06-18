from decimal import Decimal
from typing import cast

from app.features.imports.application.unknown_statement_mappings.dto import (
    UnknownStatementMappingCommand,
)
from app.features.imports.application.unknown_statement_mappings.raw_tables import find_raw_table
from app.features.imports.application.unknown_statement_mappings.row_mapping import (
    cell_at,
    parse_optional_mapped_amount,
    parse_optional_mapped_date,
)
from app.features.imports.application.unknown_statement_mappings.values import int_value
from app.features.imports.parsing.parsers.normalization import normalize_description


def table_signature_for_mapping(
    raw_tables: list[dict[str, object]] | None,
    command: UnknownStatementMappingCommand,
) -> dict[str, object] | None:
    table = find_raw_table(
        raw_tables,
        page_number=command.page_number,
        table_index=command.table_index,
    )
    if not table:
        return None
    return table_signature_for_table(table, command)


def table_signature_for_table(
    table: list[list[str]],
    command: UnknownStatementMappingCommand,
) -> dict[str, object] | None:
    header_row_index = max(command.first_data_row - 1, 0)
    if header_row_index >= len(table):
        return None
    header = table[header_row_index]
    return {
        "column_count": len(header),
        "header": [normalize_header_cell(cell) for cell in header],
        "mapped_columns": mapped_column_profiles_for_table(table, command),
    }


def normalize_header_cell(value: str) -> str:
    return " ".join(value.casefold().split())


def table_signatures_match(
    expected: dict[str, object],
    actual: dict[str, object],
    *,
    command: UnknownStatementMappingCommand,
) -> bool:
    if expected.get("column_count") != actual.get("column_count"):
        return False
    if expected.get("header") == actual.get("header"):
        return True
    return mapped_column_profiles_match(expected, actual, command=command)


def mapped_column_profiles_for_table(
    table: list[list[str]],
    command: UnknownStatementMappingCommand,
) -> list[dict[str, object]]:
    return [
        {
            "field": field_name,
            "column_index": column_index,
            "profile": column_profile_for_table(table, command, column_index),
        }
        for field_name, column_index in mapped_field_indexes(command)
    ]


def mapped_field_indexes(command: UnknownStatementMappingCommand) -> list[tuple[str, int]]:
    fields: list[tuple[str, int | None]] = [
        ("operation_date", command.operation_date_column),
        ("posting_date", command.posting_date_column),
        ("description", command.description_column),
        ("amount", command.amount_column),
        ("debit_amount", command.debit_amount_column),
        ("credit_amount", command.credit_amount_column),
        ("currency", command.currency_column),
        ("balance_after", command.balance_after_column),
    ]
    return [
        (field_name, column_index)
        for field_name, column_index in fields
        if column_index is not None and column_index >= 0
    ]


def column_profile_for_table(
    table: list[list[str]],
    command: UnknownStatementMappingCommand,
    column_index: int,
) -> dict[str, object]:
    header_row_index = max(command.first_data_row - 1, 0)
    header = cell_at(table[header_row_index], column_index) if header_row_index < len(table) else ""
    samples = [cell_at(row, column_index) for row in table[command.first_data_row :]][:10]
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
    command: UnknownStatementMappingCommand,
) -> bool:
    expected_columns = mapped_column_profile_map(expected)
    actual_columns = mapped_column_profile_map(actual)
    if not expected_columns or not actual_columns:
        return False
    for field_name, column_index in mapped_field_indexes(command):
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
    non_empty_count = int_value(profile.get("non_empty_count"), default=0)
    if allow_empty_optional and field in optional_sparse_profile_fields() and non_empty_count == 0:
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


def optional_sparse_profile_fields() -> set[str]:
    return {"posting_date", "debit_amount", "credit_amount", "currency", "balance_after"}


def profile_ratio(profile: dict[str, object], count_key: str) -> Decimal:
    non_empty_count = int_value(profile.get("non_empty_count"), default=0)
    if non_empty_count <= 0:
        return Decimal("0")
    matched_count = int_value(profile.get(count_key), default=0)
    return Decimal(matched_count) / Decimal(non_empty_count)


def value_looks_like_date(value: str) -> bool:
    parsed, error = parse_optional_mapped_date(value)
    return parsed is not None and not error


def value_looks_like_money(value: str) -> bool:
    parsed, error = parse_optional_mapped_amount(value)
    return parsed is not None and not error


def value_looks_like_currency(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized in {
        "rub",
        "rur",
        "usd",
        "eur",
        "gbp",
        "cny",
        "try",
        "aed",
    } or value.strip() in {
        "₽",
        "$",
        "€",
        "£",
    }


def value_looks_like_description(value: str) -> bool:
    normalized = normalize_description(value)
    if normalized is None:
        return False
    return not (
        value_looks_like_date(normalized)
        or value_looks_like_money(normalized)
        or value_looks_like_currency(normalized)
    )
