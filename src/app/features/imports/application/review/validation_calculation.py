from dataclasses import dataclass

from app.features.imports.application.documents.parse_attempts import (
    latest_parse_attempt,
    statement_control_totals_from_json,
)
from app.features.imports.domain.validation import (
    StatementValidationReport,
    validate_statement_totals,
)
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.imports.parsing.parser_types import StatementControlTotals


@dataclass(frozen=True)
class CalculatedDocumentValidation:
    attempt: ParseAttempt
    control_totals: StatementControlTotals | None
    report: StatementValidationReport


def calculate_document_validation(
    document: UploadedDocument,
) -> CalculatedDocumentValidation | None:
    attempt = latest_parse_attempt(document)
    if attempt is None:
        return None
    control_totals = statement_control_totals_from_json(attempt.control_totals_json)
    return CalculatedDocumentValidation(
        attempt=attempt,
        control_totals=control_totals,
        report=validate_statement_totals(
            rows=document.raw_transactions,
            control_totals=control_totals,
        ),
    )
