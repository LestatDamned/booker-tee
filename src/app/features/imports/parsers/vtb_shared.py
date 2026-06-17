import re

PERIOD_RE = re.compile(
    r"Период выписки\s+(?P<date_from>\d{2}\.\d{2}\.\d{4})\s+-\s+"
    r"(?P<date_to>\d{2}\.\d{2}\.\d{4})"
)


def extract_statement_period(text: str) -> tuple[str, str] | None:
    match = PERIOD_RE.search(text)
    if match is None:
        return None
    return (match.group("date_from"), match.group("date_to"))
