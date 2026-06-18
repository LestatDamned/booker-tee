from dataclasses import dataclass

from app.features.imports.application.unknown_statements.column_dto import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
)
from app.features.imports.application.unknown_statements.suggestion_dto import (
    UnknownStatementMappingSuggestion,
)


@dataclass(frozen=True)
class UnknownStatementContinuationMappingField:
    field: str
    column_index: int

    def as_json(self) -> dict[str, object]:
        return {
            "field": self.field,
            "column_index": self.column_index,
        }


@dataclass(frozen=True)
class UnknownStatementTablePreview:
    page_number: int
    table_index: int
    row_count: int
    column_count: int
    preview_row_count: int
    rows: list[list[str]]
    column_candidates: list[UnknownStatementColumnCandidate]
    column_profiles: list[UnknownStatementColumnProfile]
    mapping_suggestions: list[UnknownStatementMappingSuggestion]
    is_continuation: bool = False
    continued_from_page_number: int | None = None
    continued_from_table_index: int | None = None
    continuation_mapping_fields: list[UnknownStatementContinuationMappingField] | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "page_number": self.page_number,
            "table_index": self.table_index,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "preview_row_count": self.preview_row_count,
            "rows": self.rows,
            "column_candidates": [candidate.as_json() for candidate in self.column_candidates],
            "column_profiles": [profile.as_json() for profile in self.column_profiles],
            "mapping_suggestions": [
                suggestion.as_json() for suggestion in self.mapping_suggestions
            ],
            "is_continuation": self.is_continuation,
            "continued_from_page_number": self.continued_from_page_number,
            "continued_from_table_index": self.continued_from_table_index,
            "continuation_mapping_fields": [
                mapping_field.as_json() for mapping_field in self.continuation_mapping_fields or []
            ],
        }
