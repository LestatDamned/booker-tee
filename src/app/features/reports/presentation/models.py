from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ReportPeriodNav:
    month_start: date
    month_end: date
    month_label: str
    period_label: str
    previous_month_url: str
    next_month_url: str
    current_month_url: str
    all_time_url: str
    has_period_filter: bool
    is_month_period: bool
    has_exact_filters: bool
    is_all_time_period: bool
    is_current_month_period: bool
    mode_label: str
    exact_filters_label: str
