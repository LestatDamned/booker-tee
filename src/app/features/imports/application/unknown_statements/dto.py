"""Compatibility facade for unknown statement DTOs."""

# ruff: noqa: F401

from app.features.imports.application.unknown_statements.analysis_dto import (
    UnknownStatementAnalysis,
    UnknownStatementStatus,
)
from app.features.imports.application.unknown_statements.column_dto import (
    UnknownStatementColumnCandidate,
    UnknownStatementColumnProfile,
)
from app.features.imports.application.unknown_statements.suggestion_dto import (
    UnknownStatementMappingSuggestion,
    UnknownStatementMappingSuggestionReason,
    UnknownStatementMappingSuggestionWarning,
)
from app.features.imports.application.unknown_statements.table_preview_dto import (
    UnknownStatementContinuationMappingField,
    UnknownStatementTablePreview,
)
