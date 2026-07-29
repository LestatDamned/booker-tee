from app.features.imports.mapping.analysis.columns import (
    build_column_profiles,
    build_mapping_suggestions,
    clean_row,
    infer_column_candidates_from_profiles,
    is_date_like_cell,
    is_description_like_cell,
    is_money_like_cell,
    normalize_cell,
    profile_for_column,
    row_has_text,
    row_looks_like_transaction,
)
from app.features.imports.mapping.analysis.dto import (
    UnknownStatementContinuationMappingField,
    UnknownStatementMappingSuggestion,
    UnknownStatementTablePreview,
)
from app.features.imports.parsers.extractors.dto import ExtractedStatement
from app.features.imports.parsers.support.headers import (
    AMOUNT_HEADER_KEYWORDS,
    CREDIT_HEADER_KEYWORDS,
    DATE_HEADER_KEYWORDS,
    DEBIT_HEADER_KEYWORDS,
    DESCRIPTION_HEADER_KEYWORDS,
    contains_header_keyword,
    header_matches_for_cell,
)

MAX_PREVIEW_ROWS = 5
MAX_PREVIEW_COLUMNS = 5
MAX_HEADER_SCAN_ROWS = 25


def looks_like_transaction_table(table: list[list[str | None]]) -> bool:
    rows = [clean_row(row) for row in table if row_has_text(clean_row(row))]
    if not rows:
        return False
    if best_header_row_index(rows) > 0:
        return True

    header_text = " ".join(rows[0]).casefold()
    header_has_date = contains_header_keyword(header_text, DATE_HEADER_KEYWORDS)
    header_has_amount = contains_header_keyword(
        header_text, AMOUNT_HEADER_KEYWORDS
    ) or contains_header_keyword(header_text, DEBIT_HEADER_KEYWORDS + CREDIT_HEADER_KEYWORDS)
    header_has_description = contains_header_keyword(header_text, DESCRIPTION_HEADER_KEYWORDS)

    if header_has_date and header_has_amount:
        return True

    header_score = sum([header_has_date, header_has_amount, header_has_description])
    date_like_rows = 0
    rich_transaction_rows = 0
    amount_like_rows = 0
    for row in rows[:15]:
        has_date = any(is_date_like_cell(cell) for cell in row)
        has_amount = any(is_money_like_cell(cell) for cell in row)
        has_text = any(is_description_like_cell(cell) for cell in row)
        if has_date:
            date_like_rows += 1
        if has_amount:
            amount_like_rows += 1
        if has_date and has_amount and has_text:
            rich_transaction_rows += 1

    if rich_transaction_rows >= 2:
        return True
    return header_score >= 1 and date_like_rows >= 2 and amount_like_rows >= 2


def compact_preview_rows(table: list[list[str | None]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table_from_best_header_row(table):
        cleaned = clean_row(row)
        if not row_has_text(cleaned):
            continue
        rows.append([normalize_cell(cell) for cell in cleaned[:MAX_PREVIEW_COLUMNS]])
        if len(rows) >= MAX_PREVIEW_ROWS:
            break
    return rows


def table_from_best_header_row(table: list[list[str | None]]) -> list[list[str | None]]:
    rows = [clean_row(row) for row in table]
    header_row_index = best_header_row_index(rows)
    return table[header_row_index:] if header_row_index > 0 else table


def best_header_row_index(rows: list[list[str]]) -> int:
    best_index = 0
    best_score = 0
    for row_index, row in enumerate(rows[:MAX_HEADER_SCAN_ROWS]):
        score = header_row_score(row)
        if score > best_score:
            best_index = row_index
            best_score = score
    return best_index if best_score >= 2 else 0


def header_row_score(row: list[str]) -> int:
    if not row_has_text(row) or row_looks_like_transaction(row):
        return 0

    matched_fields = {field for cell in row for field in header_matches_for_cell(cell)}
    has_date = bool(matched_fields.intersection({"operation_date", "posting_date"}))
    has_amount = bool(matched_fields.intersection({"amount", "debit_amount", "credit_amount"}))
    if not has_date or not has_amount:
        return 0

    score = len(matched_fields)
    if "description" in matched_fields:
        score += 1
    return score


def build_table_previews(extracted: ExtractedStatement) -> list[UnknownStatementTablePreview]:
    previews: list[UnknownStatementTablePreview] = []
    for page_tables in extracted.tables_by_page:
        for table_index, table in enumerate(page_tables.tables):
            if not looks_like_transaction_table(table):
                continue
            previews.append(
                build_table_preview(
                    table,
                    page_number=page_tables.page_number,
                    table_index=table_index,
                )
            )
    return mark_continuation_previews(previews)


def build_table_preview(
    table: list[list[str | None]],
    *,
    page_number: int,
    table_index: int,
    source_type: str = "pdf_table",
) -> UnknownStatementTablePreview:
    rows = compact_preview_rows(table)
    header_row_index = best_header_row_index([[cell or "" for cell in row] for row in table])
    profiled_table = table[header_row_index:] if header_row_index > 0 else table
    column_profiles = build_column_profiles(profiled_table)
    column_candidates = infer_column_candidates_from_profiles(column_profiles)
    return UnknownStatementTablePreview(
        page_number=page_number,
        table_index=table_index,
        row_count=len(table),
        column_count=max((len(row) for row in table), default=0),
        preview_row_count=len(rows),
        rows=rows,
        column_candidates=column_candidates,
        column_profiles=column_profiles,
        mapping_suggestions=build_mapping_suggestions(
            column_profiles,
            column_candidates,
            row_offset=header_row_index,
        ),
        source_type=source_type,
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
    return preview.model_copy(
        update={
            "is_continuation": True,
            "continued_from_page_number": anchor.page_number,
            "continued_from_table_index": anchor.table_index,
            "continuation_mapping_fields": continuation_mapping_fields_for_anchor(anchor),
        }
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
