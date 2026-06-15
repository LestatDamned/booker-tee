from enum import Enum
from typing import Any

from fastapi.templating import Jinja2Templates

RU_LABELS = {
    "active": "активен",
    "adjustment": "корректировка",
    "any": "любое",
    "archived": "архив",
    "auto_apply": "автоприменять",
    "bank_statement": "банковская выписка",
    "card": "карта",
    "cash": "наличные",
    "checking": "расчетный",
    "confirmed": "подтверждено",
    "contains": "содержит",
    "deposit": "депозит",
    "disabled": "отключен",
    "draft": "черновик",
    "duplicate": "дубль",
    "exact": "точное совпадение",
    "expense": "расход",
    "extracted": "извлечено",
    "failed": "ошибка",
    "failed_to_parse": "ошибка парсинга",
    "ignored": "игнор",
    "imported": "импортировано",
    "inactive": "неактивен",
    "income": "доход",
    "inflow": "приход",
    "matched": "сопоставлено",
    "mismatch": "не совпадает",
    "needs_review": "нужна проверка",
    "normalized": "нормализовано",
    "other": "другое",
    "outflow": "расход",
    "parsed": "распознано",
    "parsing": "парсинг",
    "pending_parse": "ожидает парсинга",
    "possible_duplicate": "возможный дубль",
    "requires_review": "требует проверки",
    "running": "выполняется",
    "suggest": "предлагать",
    "suggested": "предложено",
    "success": "успешно",
    "transfer": "перевод",
    "unavailable": "недоступно",
    "uploaded": "загружено",
    "valid": "корректно",
}


def create_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory="src/app/templates")
    templates.env.filters["ru"] = ru_label
    templates.env.filters["short_id"] = short_id
    return templates


def ru_label(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    if value is None:
        return ""
    raw_value = str(value)
    return RU_LABELS.get(raw_value, raw_value)


def short_id(value: Any, length: int = 8) -> str:
    if value is None:
        return ""
    return str(value)[:length]
