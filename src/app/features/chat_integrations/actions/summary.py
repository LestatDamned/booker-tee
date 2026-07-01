from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ChatSummaryPeriodSelection:
    month_start: date


class ChatSummaryCallbackData:
    PERIOD_PREFIX = "sum"
    CATEGORIES_PREFIX = "sumc"

    @classmethod
    def build_period_selection(cls, *, month_start: date) -> str:
        return f"{cls.PERIOD_PREFIX}:{cls._format_month(month_start)}"

    @classmethod
    def build_category_selection(cls, *, month_start: date) -> str:
        return f"{cls.CATEGORIES_PREFIX}:{cls._format_month(month_start)}"

    @classmethod
    def parse_period_selection(
        cls,
        callback_data: str | None,
    ) -> ChatSummaryPeriodSelection | None:
        return cls._parse_selection(callback_data, prefix=cls.PERIOD_PREFIX)

    @classmethod
    def parse_category_selection(
        cls,
        callback_data: str | None,
    ) -> ChatSummaryPeriodSelection | None:
        return cls._parse_selection(callback_data, prefix=cls.CATEGORIES_PREFIX)

    @classmethod
    def _parse_selection(
        cls,
        callback_data: str | None,
        *,
        prefix: str,
    ) -> ChatSummaryPeriodSelection | None:
        if callback_data is None:
            return None

        parts = callback_data.split(":")
        if len(parts) != 2 or parts[0] != prefix:
            return None

        month_parts = parts[1].split("-")
        if len(month_parts) != 2:
            return None
        try:
            return ChatSummaryPeriodSelection(
                month_start=date(int(month_parts[0]), int(month_parts[1]), 1)
            )
        except ValueError:
            return None

    @staticmethod
    def _format_month(month_start: date) -> str:
        return month_start.strftime("%Y-%m")
