"""Compatibility facade for unknown statement mapping template helpers."""

# ruff: noqa: F401

from app.features.imports.application.unknown_statement_mappings.form_commands import (
    command_from_form_data,
)
from app.features.imports.application.unknown_statement_mappings.template_commands import (
    clean_template_name,
    compatible_mapping_templates,
    mapping_command_as_json,
    mapping_command_from_template,
    mapping_template_matches_raw_tables,
    select_compatible_mapping_template,
)
from app.features.imports.application.unknown_statement_mappings.template_signatures import (
    column_profile_for_table,
    mapped_column_profile_map,
    mapped_column_profiles_for_table,
    mapped_column_profiles_match,
    mapped_field_indexes,
    normalize_header_cell,
    optional_sparse_profile_fields,
    profile_ratio,
    profile_supports_field,
    table_signature_for_mapping,
    table_signature_for_table,
    table_signatures_match,
    value_looks_like_currency,
    value_looks_like_date,
    value_looks_like_description,
    value_looks_like_money,
)
from app.features.imports.application.unknown_statement_mappings.ui_defaults import (
    candidate_column_indexes,
    default_mapping_command,
    first_mapping_suggestion,
    first_table_preview,
    preview_table_options,
)
from app.features.imports.application.unknown_statement_mappings.values import (
    int_value,
    optional_int_value,
)
