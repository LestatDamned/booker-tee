from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from markupsafe import Markup

RU_LABELS = {
    "active": "активен",
    "account_movement_statement": "движение по счету",
    "adjustment": "корректировка",
    "any": "любое",
    "archived": "архив",
    "auto_apply": "автоприменять",
    "bank_statement": "банковская выписка",
    "business": "бизнес",
    "card": "карта",
    "card_statement": "карточная выписка",
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
    "inflow": "поступление",
    "matched": "сопоставлено",
    "mismatch": "не совпадает",
    "needs_review": "нужна проверка",
    "needs_mapping": "нужна настройка",
    "normalized": "нормализовано",
    "other": "другое",
    "outflow": "списание",
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

ICON_PATHS: dict[str, tuple[str, ...]] = {
    "archive": (
        '<rect width="20" height="5" x="2" y="3" rx="1" />',
        '<path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />',
        '<path d="M10 12h4" />',
    ),
    "arrow-left": (
        '<path d="m12 19-7-7 7-7" />',
        '<path d="M19 12H5" />',
    ),
    "building": (
        '<rect width="16" height="20" x="4" y="2" rx="2" />',
        '<path d="M9 22v-4h6v4" />',
        '<path d="M8 6h.01" />',
        '<path d="M16 6h.01" />',
        '<path d="M12 6h.01" />',
        '<path d="M12 10h.01" />',
        '<path d="M12 14h.01" />',
        '<path d="M16 10h.01" />',
        '<path d="M16 14h.01" />',
        '<path d="M8 10h.01" />',
        '<path d="M8 14h.01" />',
    ),
    "check": ('<path d="M20 6 9 17l-5-5" />',),
    "clipboard-check": (
        '<rect width="8" height="4" x="8" y="2" rx="1" />',
        '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6',
        'a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />',
        '<path d="m9 14 2 2 4-4" />',
    ),
    "file-text": (
        '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12',
        'a2 2 0 0 0 2-2V7Z" />',
        '<path d="M14 2v4a2 2 0 0 0 2 2h4" />',
        '<path d="M10 9H8" />',
        '<path d="M16 13H8" />',
        '<path d="M16 17H8" />',
    ),
    "filter": (
        '<path d="M3 6h18" />',
        '<path d="M7 12h10" />',
        '<path d="M10 18h4" />',
    ),
    "folder": (
        '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9',
        "a2 2 0 0 1-1.7-.9l-.8-1.2A2 2 0 0 0 7.9 3H4",
        'a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />',
    ),
    "home": (
        '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2h-4v-7H9v7H5',
        'a2 2 0 0 1-2-2Z" />',
    ),
    "ignore": (
        '<circle cx="12" cy="12" r="10" />',
        '<path d="m4.9 4.9 14.2 14.2" />',
    ),
    "import": (
        '<path d="M12 3v12" />',
        '<path d="m8 11 4 4 4-4" />',
        '<path d="M4 21h16" />',
    ),
    "list-check": (
        '<path d="m3 17 2 2 4-4" />',
        '<path d="M13 6h8" />',
        '<path d="M13 12h8" />',
        '<path d="M13 18h8" />',
        '<path d="m3 6 2 2 4-4" />',
    ),
    "plus": (
        '<path d="M5 12h14" />',
        '<path d="M12 5v14" />',
    ),
    "refresh": (
        '<path d="M21 12a9 9 0 0 0-9-9 9.8 9.8 0 0 0-6.7 2.7L3 8" />',
        '<path d="M3 3v5h5" />',
        '<path d="M3 12a9 9 0 0 0 9 9 9.8 9.8 0 0 0 6.7-2.7L21 16" />',
        '<path d="M16 16h5v5" />',
    ),
    "rotate-ccw": (
        '<path d="M3 12a9 9 0 1 0 9-9 9.8 9.8 0 0 0-6.7 2.7L3 8" />',
        '<path d="M3 3v5h5" />',
    ),
    "save": (
        '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19',
        'a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />',
        '<path d="M17 21v-7H7v7" />',
        '<path d="M7 3v5h8" />',
    ),
    "settings": (
        '<path d="M12.2 2h-.4a2 2 0 0 0-2 1.7l-.1.7a2 2 0 0 1-2.8 1.4',
        "l-.6-.3a2 2 0 0 0-2.6.8l-.2.4a2 2 0 0 0 .5 2.7l.5.4",
        "a2 2 0 0 1 0 3.2l-.5.4a2 2 0 0 0-.5 2.7l.2.4",
        "a2 2 0 0 0 2.6.8l.6-.3a2 2 0 0 1 2.8 1.4l.1.7",
        "a2 2 0 0 0 2 1.7h.4a2 2 0 0 0 2-1.7l.1-.7",
        "a2 2 0 0 1 2.8-1.4l.6.3a2 2 0 0 0 2.6-.8l.2-.4",
        "a2 2 0 0 0-.5-2.7l-.5-.4a2 2 0 0 1 0-3.2l.5-.4",
        "a2 2 0 0 0 .5-2.7l-.2-.4a2 2 0 0 0-2.6-.8l-.6.3",
        'a2 2 0 0 1-2.8-1.4l-.1-.7a2 2 0 0 0-2-1.7Z" />',
        '<circle cx="12" cy="12" r="3" />',
    ),
    "tag": (
        '<path d="M12.6 2.6A2 2 0 0 1 14 2h6a2 2 0 0 1 2 2v6',
        "a2 2 0 0 1-.6 1.4l-9.6 9.6a2 2 0 0 1-2.8 0L3 15",
        'a2 2 0 0 1 0-2.8Z" />',
        '<circle cx="17" cy="7" r="1" />',
    ),
    "trash": (
        '<path d="M3 6h18" />',
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />',
        '<path d="M19 6 18 20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />',
        '<path d="M10 11v6" />',
        '<path d="M14 11v6" />',
    ),
    "upload": (
        '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />',
        '<path d="m17 8-5-5-5 5" />',
        '<path d="M12 3v12" />',
    ),
    "user": (
        '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />',
        '<circle cx="12" cy="7" r="4" />',
    ),
    "wallet": (
        '<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14',
        'a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5" />',
        '<path d="M16 12h.01" />',
    ),
}

STATIC_CSS_PATH = Path("src/app/static/css/app.css")


def create_templates() -> Jinja2Templates:
    templates = Jinja2Templates(
        directory="src/app/templates",
        context_processors=[current_context_processor],
    )
    templates.env.filters["ru"] = ru_label
    templates.env.filters["short_id"] = short_id
    templates.env.filters["date_ru"] = date_ru
    cast(dict[str, Any], templates.env.globals)["icon"] = icon
    cast(dict[str, Any], templates.env.globals)["csrf_input"] = csrf_input
    return templates


def current_context_processor(request: Request) -> dict[str, Any]:
    workspace_context = getattr(request.state, "workspace_context", None)
    if workspace_context is None:
        return {
            "current_user": None,
            "current_workspace": None,
            "csrf_token": None,
            "css_version": static_asset_version(STATIC_CSS_PATH),
        }
    return {
        "current_user": workspace_context.user,
        "current_workspace": workspace_context.workspace,
        "csrf_token": getattr(request.state, "csrf_token", None),
        "css_version": static_asset_version(STATIC_CSS_PATH),
    }


def static_asset_version(path: Path) -> str:
    try:
        return str(path.stat().st_mtime_ns)
    except OSError:
        return "dev"


@pass_context
def csrf_input(context: Any) -> Markup:
    token = context.get("csrf_token")
    if not token:
        return Markup("")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


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


def date_ru(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    raw_value = str(value)
    try:
        return date.fromisoformat(raw_value).strftime("%d.%m.%Y")
    except ValueError:
        return raw_value


def icon(name: str) -> Markup:
    paths = ICON_PATHS.get(name)
    if paths is None:
        return Markup("")
    path = "".join(paths)
    return Markup(
        '<svg class="icon" aria-hidden="true" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    )
