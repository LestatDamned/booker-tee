from dataclasses import dataclass
from decimal import Decimal

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


def latest_parse_attempt(document: UploadedDocument) -> ParseAttempt | None:
    attempts = getattr(document, "parse_attempts", ())
    if not attempts:
        return None
    return attempts[0]


def statement_control_totals_from_json(
    payload: dict[str, object] | None,
) -> StatementControlTotals | None:
    if payload is None:
        return None
    currency = payload.get("currency")
    if not isinstance(currency, str):
        return None
    return StatementControlTotals(
        currency=currency,
        opening_balance=_decimal_from_json(payload.get("opening_balance")),
        closing_balance=_decimal_from_json(payload.get("closing_balance")),
        total_inflow=_decimal_from_json(payload.get("total_inflow")),
        total_outflow=_decimal_from_json(payload.get("total_outflow")),
    )


def _decimal_from_json(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, str):
        return Decimal(value)
    if isinstance(value, int):
        return Decimal(value)
    return None
