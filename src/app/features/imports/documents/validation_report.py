"""Typed decoding boundary for persisted statement validation reports."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.features.imports.domain.validation import StatementValidationStatus


@dataclass(frozen=True)
class PersistedStatementValidationReport:
    status: str
    statement_status: StatementValidationStatus | None
    balance_chain_status: StatementValidationStatus | None
    message: str
    extracted_count: int | None
    calculated_total_inflow: str | None
    calculated_total_outflow: str | None
    ignored_total_inflow: str | None
    ignored_total_outflow: str | None
    unexplained_inflow_difference: Decimal | None
    unexplained_outflow_difference: Decimal | None
    currency: str | None
    table_count: int | None

    @property
    def needs_mapping(self) -> bool:
        return self.status == "needs_mapping"


def decode_persisted_statement_validation_report(
    payload: dict[str, object],
) -> PersistedStatementValidationReport:
    status = _string(payload.get("status"))
    balance_chain = payload.get("balance_chain")
    balance_chain_status = (
        _validation_status(balance_chain.get("status")) if isinstance(balance_chain, dict) else None
    )
    return PersistedStatementValidationReport(
        status=status,
        statement_status=_validation_status(status),
        balance_chain_status=balance_chain_status,
        message=_string(payload.get("message")),
        extracted_count=_integer(payload.get("extracted_count")),
        calculated_total_inflow=_optional_string(payload.get("calculated_total_inflow")),
        calculated_total_outflow=_optional_string(payload.get("calculated_total_outflow")),
        ignored_total_inflow=_optional_string(payload.get("ignored_total_inflow")),
        ignored_total_outflow=_optional_string(payload.get("ignored_total_outflow")),
        unexplained_inflow_difference=_optional_decimal(
            payload.get("unexplained_inflow_difference")
        ),
        unexplained_outflow_difference=_optional_decimal(
            payload.get("unexplained_outflow_difference")
        ),
        currency=_optional_string(payload.get("currency")),
        table_count=_integer(payload.get("table_count")),
    )


def _validation_status(value: object) -> StatementValidationStatus | None:
    if not isinstance(value, str):
        return None
    try:
        return StatementValidationStatus(value)
    except ValueError:
        return None


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string(value: object) -> str | None:
    return None if value is None or value == "" else str(value)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _optional_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
