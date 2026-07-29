from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, PlainSerializer

from app.features.imports.statements.types import RawTransactionStatus
from app.shared.schemas import ApplicationModel


def _money_as_json(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


type JsonMoney = Annotated[
    Decimal,
    PlainSerializer(_money_as_json, return_type=str, when_used="json"),
]


class RawTransactionDraft(ApplicationModel):
    row_index: int
    status: RawTransactionStatus
    raw_payload: dict[str, object]
    operation_date_raw: str | None
    posting_date_raw: str | None
    description_raw: str | None
    amount_raw: str | None
    currency_raw: str | None
    balance_after_raw: str | None
    account_hint_raw: str | None
    account_id: UUID | None
    operation_date: date | None
    posting_date: date | None
    description_normalized: str | None
    amount: JsonMoney | None
    currency: str | None
    balance_after: JsonMoney | None
    dedupe_hash: str | None
    confidence_score: Decimal | None
    normalization_error: str | None


class StatementControlTotals(ApplicationModel):
    model_config = ConfigDict(extra="ignore")

    currency: str | None = None
    opening_balance: JsonMoney | None = None
    closing_balance: JsonMoney | None = None
    total_inflow: JsonMoney | None = None
    total_outflow: JsonMoney | None = None
