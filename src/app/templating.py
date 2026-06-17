from enum import Enum
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

RU_LABELS = {
    "active": "активен",
    "adjustment": "корректировка",
    "any": "любое",
    "archived": "архив",
    "auto_apply": "автоприменять",
    "bank_statement": "банковская выписка",
    "business": "бизнес",
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
    "family": "семья",
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
    "personal": "личный",
    "possible_duplicate": "возможный дубль",
    "project": "проект",
    "property_management": "недвижимость",
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
    templates = Jinja2Templates(
        directory="src/app/templates",
        context_processors=[current_context_processor],
    )
    templates.env.filters["ru"] = ru_label
    templates.env.filters["short_id"] = short_id
    return templates


def current_context_processor(request: Request) -> dict[str, Any]:
    workspace_context = getattr(request.state, "workspace_context", None)
    if workspace_context is None:
        return {
            "current_user": None,
            "current_workspace": None,
        }
    return {
        "current_user": workspace_context.user,
        "current_workspace": workspace_context.workspace,
    }


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
