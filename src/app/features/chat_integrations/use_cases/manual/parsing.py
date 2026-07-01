import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.features.chat_integrations.actions.manual import ChatManualDateCallbackData
from app.features.chat_integrations.errors import ChatManualOperationError


class ChatManualAmountParser:
    @staticmethod
    def parse_positive_amount(raw_value: str | None) -> Decimal:
        if raw_value is None:
            raise ChatManualOperationError("Напиши сумму числом.")

        cleaned = raw_value.casefold().strip()
        cleaned = re.sub(r"\b(rub|rur|руб\.?|р)\b", "", cleaned)
        cleaned = cleaned.replace("₽", "")
        cleaned = cleaned.replace("\u00a0", "")
        cleaned = cleaned.replace(" ", "")
        cleaned = cleaned.replace(",", ".")
        try:
            amount = Decimal(cleaned).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ChatManualOperationError("Не понял сумму. Напиши, например: 1250") from exc

        if amount <= Decimal("0"):
            raise ChatManualOperationError("Сумма должна быть больше нуля.")
        return amount


class ChatManualDateResolver:
    @staticmethod
    def resolve(date_action: str) -> date:
        match date_action:
            case ChatManualDateCallbackData.TODAY_ACTION:
                return date.today()
            case ChatManualDateCallbackData.YESTERDAY_ACTION:
                return date.today() - timedelta(days=1)
            case _:
                raise ChatManualOperationError("Выбери дату кнопкой.")


class ChatManualDateParser:
    @staticmethod
    def parse(raw_value: str | None) -> date:
        if raw_value is None:
            raise ChatManualOperationError("Напиши дату.")

        cleaned = raw_value.strip()
        if cleaned.casefold() == "сегодня":
            return date.today()
        if cleaned.casefold() == "вчера":
            return date.today() - timedelta(days=1)

        for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(cleaned, date_format).date()
            except ValueError:
                continue

        try:
            parsed_without_year = datetime.strptime(cleaned, "%d.%m").date()
        except ValueError as exc:
            raise ChatManualOperationError("Не понял дату. Напиши, например: 30.06.2026") from exc

        today = date.today()
        return parsed_without_year.replace(year=today.year)


class ChatManualDescriptionCleaner:
    @staticmethod
    def clean(raw_value: str | None) -> str | None:
        if raw_value is None:
            return None

        cleaned = " ".join(raw_value.split())
        if not cleaned:
            return None
        return cleaned[:255]
