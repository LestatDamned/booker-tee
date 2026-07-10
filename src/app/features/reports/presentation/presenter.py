from datetime import date
from urllib.parse import urlencode

from app.features.reports.presentation.models import ReportPeriodNav
from app.features.reports.service import ReportFilters

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


def build_report_period_nav(
    filters: ReportFilters,
    *,
    today: date | None = None,
) -> ReportPeriodNav:
    base_day = filters.date_from or filters.date_to or today or date.today()
    month_start = base_day.replace(day=1)
    month_end = month_end_for(month_start)
    current_month_start = (today or date.today()).replace(day=1)
    has_period_filter = filters.date_from is not None or filters.date_to is not None
    is_month_period = filters.date_from == month_start and filters.date_to == month_end
    return ReportPeriodNav(
        month_start=month_start,
        month_end=month_end,
        month_label=f"{MONTH_NAMES_RU[month_start.month]} {month_start.year}",
        period_label=report_period_label(filters),
        previous_month_url=report_month_url(filters, add_months(month_start, -1)),
        next_month_url=report_month_url(filters, add_months(month_start, 1)),
        current_month_url=report_month_url(filters, current_month_start),
        all_time_url=report_url(
            filters,
            date_from=None,
            date_to=None,
        ),
        has_period_filter=has_period_filter,
        is_month_period=is_month_period,
    )


def report_period_label(filters: ReportFilters) -> str:
    if filters.date_from and filters.date_to:
        return f"{format_report_date(filters.date_from)} — {format_report_date(filters.date_to)}"
    if filters.date_from:
        return f"с {format_report_date(filters.date_from)}"
    if filters.date_to:
        return f"по {format_report_date(filters.date_to)}"
    return "все время"


def format_report_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def report_month_url(filters: ReportFilters, month_start: date) -> str:
    return report_url(
        filters,
        date_from=month_start,
        date_to=month_end_for(month_start),
    )


def report_url(
    filters: ReportFilters,
    *,
    date_from: date | None,
    date_to: date | None,
) -> str:
    params = {
        "date_from": date_from.isoformat() if date_from else None,
        "date_to": date_to.isoformat() if date_to else None,
        "account_id": str(filters.account_id) if filters.account_id else None,
        "category_id": str(filters.category_id) if filters.category_id else None,
        "property_id": str(filters.property_id) if filters.property_id else None,
    }
    query = urlencode(
        {key: value for key, value in params.items() if value not in {None, ""}}
    )
    return f"/reports?{query}" if query else "/reports"


def add_months(month_start: date, offset: int) -> date:
    month_index = month_start.year * 12 + (month_start.month - 1) + offset
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def month_end_for(month_start: date) -> date:
    next_month_start = add_months(month_start, 1)
    return date.fromordinal(next_month_start.toordinal() - 1)
