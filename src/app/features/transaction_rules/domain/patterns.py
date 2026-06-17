import re

from app.features.transaction_rules.domain.matching import RuleMatchCandidate
from app.features.transaction_rules.domain.text import clean_rule_pattern

MERCHANT_PATTERN = re.compile(r"\sв\s(.+?)\sпо\s(?:карте|платежу)", re.IGNORECASE)


def infer_rule_pattern(raw_transaction: RuleMatchCandidate) -> str:
    description = raw_transaction.description_normalized or raw_transaction.description_raw or ""
    match = MERCHANT_PATTERN.search(description)
    if match:
        return clean_rule_pattern(match.group(1))
    if "|" in description:
        return clean_rule_pattern(description.rsplit("|", maxsplit=1)[-1])
    return clean_rule_pattern(description)
