from decimal import Decimal

from app.features.imports.application.pipelines.validation_result import (
    store_import_validation_result,
)
from app.features.imports.domain.validation import validate_statement_totals
from app.features.imports.models import ParseAttempt, UploadedDocument
from app.features.imports.parsing.parser_types import StatementControlTotals
from app.features.imports.repository import ImportRepository


async def refresh_document_validation(
    imports: ImportRepository,
    document: UploadedDocument,
) -> None:
    attempt = latest_parse_attempt(document)
    if attempt is None:
        return
    control_totals = statement_control_totals_from_json(attempt.control_totals_json)
    report = validate_statement_totals(
        rows=document.raw_transactions,
        control_totals=control_totals,
    )
    await store_import_validation_result(
        imports,
        document,
        attempt,
        control_totals=control_totals,
        report=report,
    )


def latest_parse_attempt(document: UploadedDocument) -> ParseAttempt | None:
    if not document.parse_attempts:
        return None
    return document.parse_attempts[0]


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
