from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.imports.models import RawTransaction
from app.features.imports.repository import ImportRepository
from app.features.transaction_rules.domain.matching import (
    can_suggest_raw_transaction,
    rule_matches_raw_transaction,
)
from app.features.transaction_rules.domain.suggestions import (
    apply_rule_suggestion,
    clear_rule_suggestion,
)
from app.features.transaction_rules.errors import TransactionRuleError
from app.features.transaction_rules.models import TransactionRule
from app.features.transaction_rules.repository import TransactionRuleRepository


@dataclass(frozen=True)
class RuleApplicationSummary:
    checked_count: int
    suggested_count: int
    updated_raw_transaction_ids: frozenset[UUID] = frozenset()


class TransactionRuleApplicationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.imports = ImportRepository(session)
        self.rules = TransactionRuleRepository(session)

    async def apply_rules_to_document(
        self,
        *,
        workspace_id: UUID,
        document_id: UUID,
    ) -> RuleApplicationSummary:
        document = await self.imports.get_document_for_workspace(workspace_id, document_id)
        if document is None:
            raise TransactionRuleError("Document was not found.")
        summary = await self.apply_rules_to_raw_transactions(
            workspace_id=workspace_id,
            raw_transactions=document.raw_transactions,
        )
        await self.session.commit()
        return summary

    async def apply_rules_to_raw_transactions(
        self,
        *,
        workspace_id: UUID,
        raw_transactions: list[RawTransaction],
    ) -> RuleApplicationSummary:
        rules = await self.rules.list_active_for_workspace(workspace_id)
        suggested_count = 0
        checked_count = 0
        updated_raw_transaction_ids: set[UUID] = set()
        for raw_transaction in raw_transactions:
            if not can_suggest_raw_transaction(raw_transaction):
                continue
            checked_count += 1
            before = raw_rule_state(raw_transaction)
            clear_rule_suggestion(raw_transaction)
            rule = select_best_matching_rule(rules, raw_transaction)
            if rule is not None:
                apply_rule_suggestion(raw_transaction, rule)
                suggested_count += 1
            if raw_rule_state(raw_transaction) != before:
                updated_raw_transaction_ids.add(raw_transaction.id)
        await self.session.flush()
        return RuleApplicationSummary(
            checked_count=checked_count,
            suggested_count=suggested_count,
            updated_raw_transaction_ids=frozenset(updated_raw_transaction_ids),
        )


def raw_rule_state(raw_transaction: RawTransaction) -> tuple[object, ...]:
    return (
        raw_transaction.status,
        raw_transaction.suggested_category_id,
        raw_transaction.suggested_property_id,
        raw_transaction.suggested_operation_type,
        raw_transaction.suggested_by_rule_id,
        (raw_transaction.raw_payload or {}).get("rule_suggestion"),
    )


def select_best_matching_rule(
    rules: list[TransactionRule],
    raw_transaction: RawTransaction,
) -> TransactionRule | None:
    best_rule: TransactionRule | None = None
    best_score: tuple[int, ...] | None = None
    for rule in rules:
        if not rule_matches_raw_transaction(rule, raw_transaction):
            continue
        score = rule_preference_score(rule)
        if best_score is None or score > best_score:
            best_rule = rule
            best_score = score
    return best_rule


def rule_preference_score(rule: TransactionRule) -> tuple[int, ...]:
    return (
        int(rule.category_id is not None),
        int(rule.property_id is not None),
        int(rule.target_operation_type is not None),
        int(rule.account_id is not None),
        int(rule.amount_min is not None or rule.amount_max is not None),
    )
