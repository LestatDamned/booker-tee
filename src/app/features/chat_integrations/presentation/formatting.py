from datetime import date
from decimal import Decimal


class TelegramDatePresenter:
    MONTH_NAMES = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }

    @staticmethod
    def format_date(value: date) -> str:
        return value.strftime("%d.%m.%Y")

    @classmethod
    def format_month(cls, value: date) -> str:
        return f"{cls.MONTH_NAMES[value.month]} {value.year}"


class TelegramMoneyPresenter:
    @staticmethod
    def format_money(amount: Decimal, currency: str) -> str:
        return f"{amount:.2f} {currency}".strip()
