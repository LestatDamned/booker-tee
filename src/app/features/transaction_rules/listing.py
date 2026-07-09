RULE_LIST_DEFAULT_LIMIT = 50
RULE_LIST_LIMIT_STEP = 50
RULE_LIST_MAX_LIMIT = 1000


def normalize_limit(limit: int) -> int:
    return max(1, min(limit, RULE_LIST_MAX_LIMIT))
