from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

OperationTone = Literal["income", "expense", "transfer", "adjustment"]
EntryDirection = Literal["inflow", "outflow"]
DisplayTone = Literal["profit", "positive", "negative", "neutral"]
MoneyTone = OperationTone | EntryDirection | DisplayTone


@dataclass(frozen=True)
class MoneyValueVM:
    amount_label: str
    currency_label: str
    operation_type: OperationTone | None = None
    entry_direction: EntryDirection | None = None
    display_tone: DisplayTone | None = None
    modifier_classes: tuple[str, ...] = ()


class MoneyFormatter:
    @staticmethod
    def format(
        amount: Decimal,
        currency: str,
        *,
        operation_type: OperationTone | None = None,
        entry_direction: EntryDirection | None = None,
        display_tone: DisplayTone | None = None,
    ) -> MoneyValueVM:
        normalized_amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if normalized_amount == 0:
            normalized_amount = abs(normalized_amount)
        amount_label = f"{normalized_amount:,.2f}".replace(",", " ").replace(".", ",")
        tones = tuple(
            tone for tone in (operation_type, entry_direction, display_tone) if tone is not None
        )
        return MoneyValueVM(
            amount_label=amount_label,
            currency_label=currency.upper(),
            operation_type=operation_type,
            entry_direction=entry_direction,
            display_tone=display_tone,
            modifier_classes=tuple(f"money-value--{tone}" for tone in tones),
        )
