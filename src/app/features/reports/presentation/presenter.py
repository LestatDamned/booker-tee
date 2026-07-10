from datetime import date
from decimal import Decimal
from urllib.parse import urlencode
from uuid import UUID

from app.features.reports.presentation.models import (
    ReportCategoryRowVM,
    ReportCategoryTableVM,
    ReportPeriodNav,
    ReportSortOptionVM,
)
from app.features.reports.service import CategorySummaryRow, ReportFilters

MONTH_NAMES_RU = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

CATEGORY_SORT_OPTIONS = (
    ("name", "алфавит"),
    ("income", "доход"),
    ("expense", "расход"),
    ("profit", "прибыль"),
)
CATEGORY_SORT_VALUES = {value for value, _label in CATEGORY_SORT_OPTIONS}


def build_report_period_nav(
    filters: ReportFilters,
    *,
    category_sort: str | None = None,
    today: date | None = None,
) -> ReportPeriodNav:
    normalized_category_sort = normalize_category_sort(category_sort)
    base_day = filters.date_from or filters.date_to or today or date.today()
    month_start = base_day.replace(day=1)
    month_end = month_end_for(month_start)
    current_month_start = (today or date.today()).replace(day=1)
    has_period_filter = filters.date_from is not None or filters.date_to is not None
    is_month_period = filters.date_from == month_start and filters.date_to == month_end
    is_current_month_period = is_month_period and month_start == current_month_start
    has_entity_filters = any(
        (
            filters.account_id,
            filters.category_id,
            filters.property_id,
        )
    )
    has_exact_filters = has_entity_filters or (has_period_filter and not is_month_period)
    is_all_time_period = not has_period_filter
    mode_label = report_mode_label(
        is_all_time_period=is_all_time_period,
        is_month_period=is_month_period,
    )
    return ReportPeriodNav(
        month_start=month_start,
        month_end=month_end,
        month_label=f"{MONTH_NAMES_RU[month_start.month]} {month_start.year}",
        period_label=report_period_label(filters),
        previous_month_url=report_month_url(
            filters,
            add_months(month_start, -1),
            category_sort=normalized_category_sort,
        ),
        next_month_url=report_month_url(
            filters,
            add_months(month_start, 1),
            category_sort=normalized_category_sort,
        ),
        current_month_url=report_month_url(
            filters,
            current_month_start,
            category_sort=normalized_category_sort,
        ),
        all_time_url=report_url(
            filters,
            date_from=None,
            date_to=None,
            category_sort=normalized_category_sort,
        ),
        has_period_filter=has_period_filter,
        is_month_period=is_month_period,
        has_exact_filters=has_exact_filters,
        is_all_time_period=is_all_time_period,
        is_current_month_period=is_current_month_period,
        mode_label=mode_label,
        exact_filters_label=exact_filters_label(
            has_exact_filters=has_exact_filters,
            has_entity_filters=has_entity_filters,
            period_label=report_period_label(filters),
            is_month_period=is_month_period,
        ),
    )


def build_report_category_table(
    rows: list[CategorySummaryRow],
    filters: ReportFilters,
    *,
    sort: str,
) -> ReportCategoryTableVM:
    normalized_sort = normalize_category_sort(sort)
    return ReportCategoryTableVM(
        rows=[
            ReportCategoryRowVM(
                category_id=row.category_id,
                category_name=row.category_name,
                income=row.income,
                expense=row.expense,
                profit=row.profit,
                detail_url=category_detail_url(
                    row.category_id,
                    date_from=filters.date_from,
                    date_to=filters.date_to,
                )
                if row.category_id
                else None,
            )
            for row in sorted(rows, key=category_sort_key(normalized_sort))
        ],
        sort=normalized_sort,
        sort_options=[
            ReportSortOptionVM(
                value=value,
                label=label,
                url=report_url(
                    filters,
                    date_from=filters.date_from,
                    date_to=filters.date_to,
                    category_sort=value,
                ),
                is_active=value == normalized_sort,
            )
            for value, label in CATEGORY_SORT_OPTIONS
        ],
    )


def normalize_category_sort(raw_sort: str | None) -> str:
    if raw_sort in CATEGORY_SORT_VALUES:
        return raw_sort
    return "name"


def category_sort_key(sort: str):
    if sort == "income":
        return lambda row: (-row.income, row.category_name)
    if sort == "expense":
        return lambda row: (-row.expense, row.category_name)
    if sort == "profit":
        return lambda row: (profit_rank(row.profit), row.category_name)
    return lambda row: row.category_name


def profit_rank(value: Decimal) -> tuple[int, Decimal]:
    return (0, -value) if value >= 0 else (1, value)


def report_period_label(filters: ReportFilters) -> str:
    if filters.date_from and filters.date_to:
        return f"{format_report_date(filters.date_from)} — {format_report_date(filters.date_to)}"
    if filters.date_from:
        return f"с {format_report_date(filters.date_from)}"
    if filters.date_to:
        return f"по {format_report_date(filters.date_to)}"
    return "все время"


def report_mode_label(*, is_all_time_period: bool, is_month_period: bool) -> str:
    if is_all_time_period:
        return "все время"
    if is_month_period:
        return "месяц"
    return "точный период"


def exact_filters_label(
    *,
    has_exact_filters: bool,
    has_entity_filters: bool,
    period_label: str,
    is_month_period: bool,
) -> str:
    if not has_exact_filters:
        return "не применены"
    if has_entity_filters and is_month_period:
        return "применены"
    return period_label


def format_report_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def report_month_url(
    filters: ReportFilters,
    month_start: date,
    *,
    category_sort: str | None = None,
) -> str:
    return report_url(
        filters,
        date_from=month_start,
        date_to=month_end_for(month_start),
        category_sort=category_sort,
    )


def report_url(
    filters: ReportFilters,
    *,
    date_from: date | None,
    date_to: date | None,
    category_sort: str | None = None,
) -> str:
    params = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "account_id": str(filters.account_id) if filters.account_id else None,
        "category_id": str(filters.category_id) if filters.category_id else None,
        "property_id": str(filters.property_id) if filters.property_id else None,
        "category_sort": category_sort if category_sort and category_sort != "name" else None,
    }
    query = urlencode(
        {key: value for key, value in params.items() if value not in {None, ""}}
    )
    return f"/reports?{query}" if query else "/reports"


def category_detail_url(
    category_id: UUID,
    *,
    date_from: date | None,
    date_to: date | None,
) -> str:
    params = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
    }
    query = urlencode(
        {key: value for key, value in params.items() if value not in {None, ""}}
    )
    return f"/categories/{category_id}?{query}" if query else f"/categories/{category_id}"


def add_months(month_start: date, offset: int) -> date:
    month_index = month_start.year * 12 + (month_start.month - 1) + offset
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def month_end_for(month_start: date) -> date:
    next_month_start = add_months(month_start, 1)
    return date.fromordinal(next_month_start.toordinal() - 1)
