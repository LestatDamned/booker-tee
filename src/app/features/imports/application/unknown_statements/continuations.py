from app.features.imports.application.unknown_statements.profile_helpers import (
    profile_for_column,
)
from app.features.imports.application.unknown_statements.suggestion_dto import (
    UnknownStatementMappingSuggestion,
)
from app.features.imports.application.unknown_statements.table_preview_dto import (
    UnknownStatementContinuationMappingField,
    UnknownStatementTablePreview,
)


def mark_continuation_previews(
    previews: list[UnknownStatementTablePreview],
) -> list[UnknownStatementTablePreview]:
    marked_previews: list[UnknownStatementTablePreview] = []
    anchor: UnknownStatementTablePreview | None = None
    for preview in previews:
        if (
            anchor is not None
            and preview_is_headerless(preview)
            and preview.page_number > anchor.page_number
            and preview_matches_anchor_mapping(preview, anchor)
        ):
            marked_previews.append(continuation_preview(preview, anchor))
            continue
        marked_previews.append(preview)
        if preview.mapping_suggestions and not preview_is_headerless(preview):
            anchor = preview
    return marked_previews


def preview_is_headerless(preview: UnknownStatementTablePreview) -> bool:
    return not any(profile.header_matches for profile in preview.column_profiles)


def preview_matches_anchor_mapping(
    preview: UnknownStatementTablePreview,
    anchor: UnknownStatementTablePreview,
) -> bool:
    if not anchor.mapping_suggestions:
        return False
    suggestion = anchor.mapping_suggestions[0]
    if preview.column_count < minimum_column_count_for_suggestion(suggestion):
        return False
    return (
        profile_has_date_values(preview, suggestion.operation_date_column)
        and profile_has_description_values(preview, suggestion.description_column)
        and suggestion_has_amount_values(preview, suggestion)
    )


def minimum_column_count_for_suggestion(suggestion: UnknownStatementMappingSuggestion) -> int:
    indexes = [
        suggestion.operation_date_column,
        suggestion.description_column,
        suggestion.amount_column,
        suggestion.debit_amount_column,
        suggestion.credit_amount_column,
        suggestion.currency_column,
        suggestion.balance_after_column,
        suggestion.posting_date_column,
    ]
    return max((index for index in indexes if index is not None), default=-1) + 1


def profile_has_date_values(preview: UnknownStatementTablePreview, column_index: int) -> bool:
    return profile_for_column(preview.column_profiles, column_index).date_like_count > 0


def profile_has_description_values(
    preview: UnknownStatementTablePreview,
    column_index: int,
) -> bool:
    return profile_for_column(preview.column_profiles, column_index).description_like_count > 0


def suggestion_has_amount_values(
    preview: UnknownStatementTablePreview,
    suggestion: UnknownStatementMappingSuggestion,
) -> bool:
    if suggestion.amount_column is not None:
        return (
            profile_for_column(preview.column_profiles, suggestion.amount_column).money_like_count
            > 0
        )
    return any(
        profile_for_column(preview.column_profiles, column_index).money_like_count > 0
        for column_index in (suggestion.debit_amount_column, suggestion.credit_amount_column)
        if column_index is not None
    )


def continuation_preview(
    preview: UnknownStatementTablePreview,
    anchor: UnknownStatementTablePreview,
) -> UnknownStatementTablePreview:
    return UnknownStatementTablePreview(
        page_number=preview.page_number,
        table_index=preview.table_index,
        row_count=preview.row_count,
        column_count=preview.column_count,
        preview_row_count=preview.preview_row_count,
        rows=preview.rows,
        column_candidates=preview.column_candidates,
        column_profiles=preview.column_profiles,
        mapping_suggestions=preview.mapping_suggestions,
        is_continuation=True,
        continued_from_page_number=anchor.page_number,
        continued_from_table_index=anchor.table_index,
        continuation_mapping_fields=continuation_mapping_fields_for_anchor(anchor),
    )


def continuation_mapping_fields_for_anchor(
    anchor: UnknownStatementTablePreview,
) -> list[UnknownStatementContinuationMappingField]:
    if not anchor.mapping_suggestions:
        return []
    suggestion = anchor.mapping_suggestions[0]
    fields = [
        ("operation_date", suggestion.operation_date_column),
        ("posting_date", suggestion.posting_date_column),
        ("description", suggestion.description_column),
        ("amount", suggestion.amount_column),
        ("debit_amount", suggestion.debit_amount_column),
        ("credit_amount", suggestion.credit_amount_column),
        ("currency", suggestion.currency_column),
        ("balance_after", suggestion.balance_after_column),
    ]
    return [
        UnknownStatementContinuationMappingField(field=field, column_index=column_index)
        for field, column_index in fields
        if column_index is not None
    ]
