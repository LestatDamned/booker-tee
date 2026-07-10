from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.transaction_rules.listing import RULE_LIST_DEFAULT_LIMIT, normalize_limit
from app.features.transaction_rules.models import TransactionRule
from app.features.transaction_rules.repository import TransactionRuleRepository

RULE_LIST_STATUS_ALL = "all"
RULE_LIST_STATUS_ACTIVE = "active"
RULE_LIST_STATUS_INACTIVE = "inactive"
RULE_LIST_STATUSES = {
    RULE_LIST_STATUS_ALL,
    RULE_LIST_STATUS_ACTIVE,
    RULE_LIST_STATUS_INACTIVE,
}


@dataclass(frozen=True)
class TransactionRuleListResult:
    rules: list[TransactionRule]
    total_count: int
    filtered_count: int
    active_count: int
    inactive_count: int
    limit: int


class TransactionRuleQueryUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.rules = TransactionRuleRepository(session)

    async def list_rules(self, workspace_id: UUID) -> list[TransactionRule]:
        return await self.rules.list_for_workspace(workspace_id)

    async def list_rules_for_page(
        self,
        *,
        workspace_id: UUID,
        search: str = "",
        category_id: UUID | None = None,
        status: str = RULE_LIST_STATUS_ALL,
        limit: int = RULE_LIST_DEFAULT_LIMIT,
        pinned_rule_id: UUID | None = None,
    ) -> TransactionRuleListResult:
        rules = await self.rules.list_for_workspace(workspace_id)
        filtered_rules = filter_rules(
            rules,
            search=search,
            category_id=category_id,
            status=status,
        )
        normalized_limit = normalize_limit(limit)
        return TransactionRuleListResult(
            rules=visible_rules_for_page(
                filtered_rules,
                limit=normalized_limit,
                pinned_rule_id=pinned_rule_id,
            ),
            total_count=len(rules),
            filtered_count=len(filtered_rules),
            active_count=sum(1 for rule in rules if rule.is_active),
            inactive_count=sum(1 for rule in rules if not rule.is_active),
            limit=normalized_limit,
        )

    async def get_rule(self, *, workspace_id: UUID, rule_id: UUID) -> TransactionRule | None:
        return await self.rules.get_for_workspace(workspace_id, rule_id)


def filter_rules(
    rules: list[TransactionRule],
    *,
    search: str = "",
    category_id: UUID | None = None,
    status: str = RULE_LIST_STATUS_ALL,
) -> list[TransactionRule]:
    normalized_search = normalize_search(search)
    normalized_status = normalize_status(status)
    return [
        rule
        for rule in rules
        if matches_category(rule, category_id)
        and matches_status(rule, normalized_status)
        and matches_search(rule, normalized_search)
    ]


def visible_rules_for_page(
    filtered_rules: list[TransactionRule],
    *,
    limit: int,
    pinned_rule_id: UUID | None = None,
) -> list[TransactionRule]:
    visible_rules = list(filtered_rules[:limit])
    if pinned_rule_id is None:
        return visible_rules
    if any(getattr(rule, "id", None) == pinned_rule_id for rule in visible_rules):
        return visible_rules
    pinned_rule = next(
        (rule for rule in filtered_rules if getattr(rule, "id", None) == pinned_rule_id),
        None,
    )
    if pinned_rule is not None:
        visible_rules.append(pinned_rule)
    return visible_rules


def normalize_status(status: str) -> str:
    return status if status in RULE_LIST_STATUSES else RULE_LIST_STATUS_ALL


def normalize_search(value: str) -> str:
    return " ".join(value.casefold().split())


def matches_category(rule: TransactionRule, category_id: UUID | None) -> bool:
    if category_id is None:
        return True
    return getattr(rule, "category_id", None) == category_id


def matches_status(rule: TransactionRule, status: str) -> bool:
    if status == RULE_LIST_STATUS_ACTIVE:
        return bool(getattr(rule, "is_active", False))
    if status == RULE_LIST_STATUS_INACTIVE:
        return not bool(getattr(rule, "is_active", False))
    return True


def matches_search(rule: TransactionRule, search: str) -> bool:
    if not search:
        return True
    return search in rule_search_haystack(rule)


def rule_search_haystack(rule: TransactionRule) -> str:
    category = getattr(rule, "category", None)
    property_ = getattr(rule, "property", None)
    values = [
        getattr(rule, "name", ""),
        getattr(rule, "pattern", ""),
        getattr(category, "name", ""),
        getattr(property_, "name", ""),
    ]
    return normalize_search(" ".join(str(value or "") for value in values))
